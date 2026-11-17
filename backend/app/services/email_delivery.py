"""Provider-independent delivery failure and verification email content."""
from urllib.parse import urlencode

class DeliveryUnavailable(Exception):
    pass

def verification_body(frontend_base_url: str, token: str) -> str:
    link = frontend_base_url + '/verify-email?' + urlencode({'token': token})
    return (
        'Welcome to AXIOM — Discrete Mathematics.\n\n'
        'Please verify your email address to complete your registration:\n\n'
        f'{link}\n\n'
        'This link expires in one hour and can be used only once.\n'
        'If you did not register for AXIOM, you can ignore this email.\n'
    )

def password_reset_body(frontend_base_url: str, token: str) -> str:
    link = frontend_base_url + '/reset-password?' + urlencode({'token': token})
    return (
        'AXIOM password reset\n\n'
        'Use this link to choose a new password:\n\n'
        f'{link}\n\n'
        'This link expires in 30 minutes and can be used only once.\n'
        'If you did not request a password reset, you can ignore this email.\n'
    )
