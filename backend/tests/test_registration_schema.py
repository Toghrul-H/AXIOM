"""Database-independent validation checks for the public-only domain rule."""
import pytest
from pydantic import ValidationError
from app.auth_schemas import Credentials, LoginCredentials, RegistrationCredentials

@pytest.mark.parametrize('email', ['student@inf.elte.hu', '  Name.Surname@INF.ELTE.HU  '])
def test_inf_registration_schema(email):
    result = RegistrationCredentials(email=email, password='test-only-password-42!')
    assert str(result.email) == email.strip().lower()

@pytest.mark.parametrize('email', ['user@gmail.com', 'user@elte.hu', 'user@student.elte.hu', 'user@inf.elte.hu.example.com', 'user@example.com?x=@inf.elte.hu'])
def test_public_domain_rejected(email):
    with pytest.raises(ValidationError):
        RegistrationCredentials(email=email, password='test-only-password-42!')

def test_trusted_credentials_and_existing_login_are_unrestricted():
    for schema in [Credentials, LoginCredentials]:
        assert schema(email='existing@example.com', password='test-only-password-42!').email == 'existing@example.com'

@pytest.mark.parametrize('extra', [{'role': 'ADMIN'}, {'email_verified': True}])
def test_privileged_registration_fields_rejected(extra):
    with pytest.raises(ValidationError):
        RegistrationCredentials(email='student@inf.elte.hu', password='test-only-password-42!', **extra)
