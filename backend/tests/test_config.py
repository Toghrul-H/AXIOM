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


def test_database_schema_accepts_only_safe_postgresql_identifiers():
    assert Settings(database_schema="axiom_e2e_ab12").database_schema == "axiom_e2e_ab12"
    for value in ("public; DROP SCHEMA public", "MixedCase", "1starts_with_number"):
        try:
            Settings(database_schema=value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe schema was accepted: {value!r}")
