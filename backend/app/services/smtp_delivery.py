"""Private SMTP adapter. Never log SMTP exceptions or message contents."""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import urlencode
from app.config import get_settings

class DeliveryUnavailable(Exception):
    pass

def send_verification_email(email: str, token: str) -> None:
    settings = get_settings()
    if not all([settings.smtp_host, settings.smtp_username,
                settings.smtp_password.get_secret_value(), settings.email_from_address,
                settings.frontend_base_url]):
        raise DeliveryUnavailable('Email delivery unavailable')
    # False selects implicit TLS (465), never plaintext authenticated SMTP.
    if not settings.smtp_use_tls and settings.smtp_port != 465:
        raise DeliveryUnavailable('Email delivery unavailable')
    try:
        message = EmailMessage()
        message['Subject'] = 'Verify your AXIOM account'
        message['From'] = formataddr((settings.email_from_name, settings.email_from_address))
        message['To'] = email
        link = settings.frontend_base_url + '/verify-email?' + urlencode({'token': token})
        message.set_content(
            'Welcome to AXIOM — Discrete Mathematics.\n\n'
            'Please verify your email address to complete your registration:\n\n'
            f'{link}\n\n'
            'This link expires in one hour and can be used only once.\n'
            'If you did not register for AXIOM, you can ignore this email.\n',
            charset='utf-8',
        )
        context = ssl.create_default_context()
        transport = smtplib.SMTP if settings.smtp_use_tls else smtplib.SMTP_SSL
        kwargs = {'timeout': settings.smtp_timeout_seconds}
        if not settings.smtp_use_tls:
            kwargs['context'] = context
        with transport(settings.smtp_host, settings.smtp_port, **kwargs) as smtp:
            if settings.smtp_use_tls:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            if smtp.send_message(message):
                raise DeliveryUnavailable('Email delivery unavailable')
    except (OSError, smtplib.SMTPException, ValueError):
        raise DeliveryUnavailable('Email delivery unavailable') from None
