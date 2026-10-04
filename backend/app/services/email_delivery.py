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
