"""Brevo HTTPS transport with fixed destination and allowlisted diagnostics."""
import http.client
import json
import logging
import ssl
from app.config import get_settings
from app.services.email_delivery import DeliveryUnavailable, password_reset_body, verification_body

logger = logging.getLogger(__name__)

def fail(category: str, status: int | None = None) -> None:
    # Never include exception text, response bodies, headers or recipient data.
    logger.error('Email delivery failed: provider=brevo status=%s category=%s', status, category)
    raise DeliveryUnavailable('Email delivery unavailable') from None

def _send_email(email: str, subject: str, body: str) -> None:
    settings = get_settings()
    key = settings.brevo_api_key.get_secret_value()
    if not all([key.strip(), settings.email_from_address, settings.email_from_name.strip(), settings.frontend_base_url]):
        fail('configuration_missing')
    if '\r' in key or '\n' in key:
        fail('configuration_invalid')
    payload = {
        'sender': {'email': settings.email_from_address, 'name': settings.email_from_name},
        'to': [{'email': email}],
        'subject': subject,
        'textContent': body,
    }
    connection = None
    try:
        # Standard-library client: no new runtime dependency, redirects or retries.
        connection = http.client.HTTPSConnection('api.brevo.com', timeout=settings.email_http_timeout_seconds,
                                                 context=ssl.create_default_context())
        connection.request('POST', '/v3/smtp/email', body=json.dumps(payload).encode('utf-8'),
                           headers={'api-key': key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            category = ({401: 'authentication_rejected', 403: 'permission_denied', 429: 'rate_limited'}
                        .get(response.status, 'upstream_unavailable' if response.status >= 500 else 'request_rejected'))
            fail(category, response.status)
    except ssl.SSLError:
        fail('tls_failure')
    except TimeoutError:
        fail('timeout')
    except (OSError, http.client.HTTPException):
        fail('network_or_protocol_failure')
    except ValueError:
        fail('configuration_invalid')
    finally:
        if connection is not None:
            connection.close()

def send_verification_email(email: str, token: str) -> None:
    _send_email(email, 'Verify your AXIOM account', verification_body(get_settings().frontend_base_url, token))

def send_password_reset_email(email: str, token: str) -> None:
    _send_email(email, 'Reset your AXIOM password', password_reset_body(get_settings().frontend_base_url, token))
