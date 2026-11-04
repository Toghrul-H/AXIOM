from app.config import Settings


def test_database_url_carries_explicit_libpq_tls_mode_without_exposing_password():
    settings = Settings(
        database_host="neon.example.test",
        database_name="axiom",
        database_user="axiom_app",
        database_password="test-only-password",
        database_sslmode="require",
    )
    url = settings.database_url()
    assert url.query["sslmode"] == "require"
    assert "test-only-password" not in url.render_as_string(hide_password=True)
