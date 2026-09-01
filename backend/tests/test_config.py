from app.config import Settings


def _settings(**kw):
    return Settings(
        database_url="postgresql://x/x", jwt_secret="x", anthropic_api_key="x", **kw
    )


def test_admin_email_set_splits_lowercases_and_trims():
    s = _settings(admin_emails=" Founder@Example.com , ops@example.com ;extra@x.io")
    assert s.admin_email_set == {
        "founder@example.com",
        "ops@example.com",
        "extra@x.io",
    }


def test_admin_email_set_empty_by_default():
    assert _settings().admin_email_set == set()
