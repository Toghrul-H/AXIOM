"""Private Google Drive storage boundary for course materials.

The application validates bytes before upload and serves authorized reads
itself. It never creates Drive sharing permissions or returns Drive URLs.
"""

from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
from secrets import token_hex
import unicodedata
from zipfile import BadZipFile, ZipFile

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from app.config import Settings, get_settings


DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"


class StorageConfigurationError(RuntimeError):
    pass


class StorageOperationError(RuntimeError):
    pass


class MaterialValidationError(ValueError):
    pass


@dataclass(frozen=True)
class GoogleDriveStorageConfig:
    folder_id: str
    token_json: str = field(repr=False)


@dataclass(frozen=True)
class VerifiedMaterialFile:
    filename: str
    media_type: str
    content: bytes
    sha256: str

    @property
    def size_bytes(self) -> int:
        return len(self.content)


_FORMATS = {
    ".pdf": ("application/pdf", {"application/pdf"}),
    ".ppt": ("application/vnd.ms-powerpoint", {"application/vnd.ms-powerpoint", "application/octet-stream"}),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/octet-stream"}),
    ".doc": ("application/msword", {"application/msword", "application/octet-stream"}),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/octet-stream"}),
    ".png": ("image/png", {"image/png", "application/octet-stream"}),
    ".jpg": ("image/jpeg", {"image/jpeg", "application/octet-stream"}),
    ".jpeg": ("image/jpeg", {"image/jpeg", "application/octet-stream"}),
    ".webp": ("image/webp", {"image/webp", "application/octet-stream"}),
    ".txt": ("text/plain", {"text/plain", "application/octet-stream"}),
    ".md": ("text/markdown", {"text/markdown", "text/plain", "application/octet-stream"}),
    ".markdown": ("text/markdown", {"text/markdown", "text/plain", "application/octet-stream"}),
}
_OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
_INLINE_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp", "text/plain", "text/markdown"}


def private_object_storage_config(settings: Settings | None = None) -> GoogleDriveStorageConfig | None:
    """Load exactly one private Drive token source without exposing it."""
    settings = settings or get_settings()
    provider = settings.materials_storage_provider
    values = (
        settings.materials_google_drive_folder_id,
        settings.materials_google_drive_token_file,
        settings.materials_google_drive_token_json.get_secret_value(),
    )
    if provider == "disabled":
        if any(values):
            raise StorageConfigurationError("Course-material storage provider is disabled")
        return None
    if provider != "google_drive" or not settings.materials_google_drive_folder_id:
        raise StorageConfigurationError("Course-material Google Drive storage is incomplete")
    has_file = bool(settings.materials_google_drive_token_file)
    has_json = bool(settings.materials_google_drive_token_json.get_secret_value())
    if has_file == has_json:
        raise StorageConfigurationError("Configure exactly one Google Drive token source")
    try:
        token_json = (
            Path(settings.materials_google_drive_token_file).read_text(encoding="utf-8")
            if has_file
            else settings.materials_google_drive_token_json.get_secret_value()
        )
        token_data = json.loads(token_json)
    except (OSError, ValueError, TypeError) as error:
        raise StorageConfigurationError("Google Drive token configuration is unavailable") from error
    if not isinstance(token_data, dict):
        raise StorageConfigurationError("Google Drive token configuration is invalid")
    return GoogleDriveStorageConfig(settings.materials_google_drive_folder_id, token_json)


def sanitize_filename(filename: str) -> str:
    value = unicodedata.normalize("NFKC", filename)
    value = "".join(character for character in value if character.isprintable() and character not in "\\/\r\n")
    value = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip(" .")
    value = re.sub(r"\s+", " ", value)
    if not value or value in {".", ".."}:
        raise MaterialValidationError("Filename must contain safe visible characters")
    stem, dot, suffix = value.rpartition(".")
    return value[:180] if not dot or not stem else f"{stem[: max(1, 180 - len(suffix) - 1)]}.{suffix[:32]}"


def _validate_signature(extension: str, content: bytes) -> None:
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise MaterialValidationError("The file does not match its PDF extension")
    if extension == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise MaterialValidationError("The file does not match its PNG extension")
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise MaterialValidationError("The file does not match its JPEG extension")
    if extension == ".webp" and not (len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"):
        raise MaterialValidationError("The file does not match its WebP extension")
    if extension in {".doc", ".ppt"} and not content.startswith(_OLE_SIGNATURE):
        raise MaterialValidationError("The file does not match its Office extension")
    if extension in {".docx", ".pptx"}:
        try:
            with ZipFile(BytesIO(content)) as archive:
                names = set(archive.namelist())
                if any(item.flag_bits & 0x1 for item in archive.infolist()):
                    raise MaterialValidationError("Encrypted Office files are not supported")
                if sum(item.file_size for item in archive.infolist()) > len(content) * 20:
                    raise MaterialValidationError("Compressed Office file is unsafe")
        except BadZipFile as error:
            raise MaterialValidationError("The file does not match its Office extension") from error
        needed = "word/document.xml" if extension == ".docx" else "ppt/presentation.xml"
        if "[Content_Types].xml" not in names or needed not in names:
            raise MaterialValidationError("The file does not match its Office extension")
    if extension in {".txt", ".md", ".markdown"}:
        if b"\x00" in content:
            raise MaterialValidationError("Text files may not contain NUL bytes")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise MaterialValidationError("Text files must be UTF-8") from error


def validate_material_upload(filename: str | None, claimed_media_type: str | None, content: bytes, *, max_bytes: int) -> VerifiedMaterialFile:
    if not filename or not content:
        raise MaterialValidationError("A non-empty material file is required")
    if len(content) > max_bytes:
        raise MaterialValidationError("Material file exceeds the configured size limit")
    safe_name = sanitize_filename(filename)
    extension = PurePosixPath(safe_name).suffix.lower()
    details = _FORMATS.get(extension)
    if details is None:
        raise MaterialValidationError("Unsupported material file type")
    media_type, accepted_claims = details
    claimed = (claimed_media_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if claimed not in accepted_claims:
        raise MaterialValidationError("The uploaded MIME type does not match the file extension")
    _validate_signature(extension, content)
    return VerifiedMaterialFile(filename=safe_name, media_type=media_type, content=content, sha256=sha256(content).hexdigest())


def is_inline_preview_type(media_type: str) -> bool:
    return media_type in _INLINE_TYPES


def _load_drive_credentials(config: GoogleDriveStorageConfig) -> Credentials:
    try:
        credentials = Credentials.from_authorized_user_info(json.loads(config.token_json), scopes=[DRIVE_FILE_SCOPE])
    except (ValueError, TypeError, KeyError) as error:
        raise StorageConfigurationError("Google Drive token configuration is invalid") from error
    scopes = set(credentials.scopes or ())
    if scopes and scopes != {DRIVE_FILE_SCOPE}:
        raise StorageConfigurationError("Google Drive token has an unsupported scope")
    return credentials


class GoogleDriveStorage:
    """Private Drive API adapter; files remain accessible only through AXIOM."""

    def __init__(self, config: GoogleDriveStorageConfig):
        self.config = config
        self.credentials = _load_drive_credentials(config)

    def new_key(self) -> str:
        # This is only an opaque Drive filename. put() returns the actual ID.
        return f"axiom-material-{token_hex(32)}"

    def _files(self):
        try:
            return build("drive", "v3", credentials=self.credentials, cache_discovery=False).files()
        except Exception as error:
            raise StorageOperationError("Private material storage operation failed") from error

    def put(self, key: str, file: VerifiedMaterialFile) -> str:
        try:
            result = self._files().create(
                body={"name": key, "parents": [self.config.folder_id], "mimeType": file.media_type},
                media_body=MediaIoBaseUpload(BytesIO(file.content), mimetype=file.media_type, resumable=False),
                fields="id",
            ).execute()
            file_id = result.get("id") if isinstance(result, dict) else None
            if not isinstance(file_id, str) or not file_id:
                raise StorageOperationError("Private material storage operation failed")
            return file_id
        except StorageOperationError:
            raise
        except Exception as error:
            raise StorageOperationError("Private material storage operation failed") from error

    def get(self, key: str, *, max_bytes: int) -> bytes:
        try:
            content = self._files().get_media(fileId=key).execute()
            if not isinstance(content, bytes) or len(content) > max_bytes:
                raise StorageOperationError("Private material storage operation failed")
            return content
        except StorageOperationError:
            raise
        except Exception as error:
            raise StorageOperationError("Private material storage operation failed") from error

    def delete(self, key: str) -> None:
        try:
            metadata = self._files().get(
                fileId=key,
                fields="id,name,parents,trashed",
            ).execute()
            if (
                not isinstance(metadata, dict)
                or metadata.get("id") != key
                or self.config.folder_id not in (metadata.get("parents") or [])
                or not isinstance(metadata.get("name"), str)
                or not metadata["name"].startswith("axiom-material-")
            ):
                raise StorageOperationError("Private material storage operation failed")
            self._files().delete(fileId=key).execute()
        except HttpError as error:
            # Deletion is idempotent: a prior provider success followed by a
            # database failure is reconciled by retrying the metadata deletion.
            if getattr(error.resp, "status", None) == 404:
                return
            raise StorageOperationError("Private material storage operation failed") from error
        except StorageOperationError:
            raise
        except Exception as error:
            raise StorageOperationError("Private material storage operation failed") from error


def required_private_storage(settings: Settings | None = None) -> GoogleDriveStorage:
    config = private_object_storage_config(settings)
    if config is None:
        raise StorageConfigurationError("Course-material storage is not configured")
    return GoogleDriveStorage(config)
