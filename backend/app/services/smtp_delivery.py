"""Private SMTP adapter. Log only allowlisted diagnostics, never raw exceptions."""
import logging
import socket
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from app.config import get_settings
from app.services.email_delivery import DeliveryUnavailable, verification_body

logger = logging.getLogger(__name__)

def log_delivery_failure(error: Exception, stage: str) -> None:
    # SMTP response text/exception arguments may contain credentials or message data.
    # Generate the sanitized message from known exception classes, never str(error).
    categories = [
        (ssl.SSLCertVerificationError, 'TLS certificate verification failed'),
        (ssl.SSLError, 'TLS negotiation failed'),
        (smtplib.SMTPAuthenticationError, 'SMTP authentication rejected'),
        (smtplib.SMTPRecipientsRefused, 'SMTP recipient rejected'),
        (smtplib.SMTPSenderRefused, 'SMTP sender rejected'),
        (smtplib.SMTPDataError, 'SMTP message rejected'),
        (smtplib.SMTPNotSupportedError, 'Required SMTP capability unavailable'),
        (smtplib.SMTPServerDisconnected, 'SMTP connection disconnected'),
        (smtplib.SMTPResponseException, 'SMTP server rejected operation'),
        (smtplib.SMTPException, 'SMTP protocol failure'),
        (TimeoutError, 'SMTP connection or operation timed out'),
        (socket.gaierror, 'SMTP hostname resolution failed'),
        (ConnectionRefusedError, 'SMTP connection refused'),
        (OSError, 'SMTP network operation failed'),
        (ValueError, 'Invalid email delivery configuration or message format'),
    ]
    kind, message = next(((cls.__name__, message) for cls, message in categories if isinstance(error, cls)),
                         ('DeliveryUnavailable', 'SMTP delivery unavailable'))
    code = getattr(error, 'smtp_code', None)
    code = code if type(code) is int and 100 <= code <= 599 else None
    number = getattr(error, 'errno', None) if not isinstance(error, smtplib.SMTPException) else None
    number = number if type(number) is int and -100000 <= number <= 100000 else None
    logger.error('Email delivery failed: stage=%s exception=%s message=%s smtp_code=%s errno=%s',
                 stage, kind, message, code, number)

def send_verification_email(email: str, token: str) -> None:
    settings = get_settings()
    if not all([settings.smtp_host, settings.smtp_username,
                settings.smtp_password.get_secret_value(), settings.email_from_address,
                settings.frontend_base_url]):
        log_delivery_failure(DeliveryUnavailable(), 'configuration_missing')
        raise DeliveryUnavailable('Email delivery unavailable')
    # False selects implicit TLS (465), never plaintext authenticated SMTP.
    if not settings.smtp_use_tls and settings.smtp_port != 465:
        log_delivery_failure(DeliveryUnavailable(), 'configuration_tls_mode')
        raise DeliveryUnavailable('Email delivery unavailable')
    stage = 'message_setup'
    try:
        message = EmailMessage()
        message['Subject'] = 'Verify your AXIOM account'
        message['From'] = formataddr((settings.email_from_name, settings.email_from_address))
        message['To'] = email
        message.set_content(
            verification_body(settings.frontend_base_url, token),
            charset='utf-8',
        )
        context = ssl.create_default_context()
        transport = smtplib.SMTP if settings.smtp_use_tls else smtplib.SMTP_SSL
        kwargs = {'timeout': settings.smtp_timeout_seconds}
        if not settings.smtp_use_tls:
            kwargs['context'] = context
        stage = 'connect'
        with transport(settings.smtp_host, settings.smtp_port, **kwargs) as smtp:
            if settings.smtp_use_tls:
                stage = 'ehlo'
                smtp.ehlo()
                stage = 'starttls'
                smtp.starttls(context=context)
                stage = 'ehlo_after_tls'
                smtp.ehlo()
            stage = 'authenticate'
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            stage = 'send'
            if smtp.send_message(message):
                log_delivery_failure(smtplib.SMTPRecipientsRefused({}), stage)
                raise DeliveryUnavailable('Email delivery unavailable')
            stage = 'quit'
    except (OSError, smtplib.SMTPException, ValueError) as error:
        log_delivery_failure(error, stage)
        raise DeliveryUnavailable('Email delivery unavailable') from None
