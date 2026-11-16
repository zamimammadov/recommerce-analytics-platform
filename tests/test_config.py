from recommerce.config import Settings


def test_settings_build_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "warehouse")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "market")
    monkeypatch.setenv("POSTGRES_USER", "analyst")
    monkeypatch.setenv("POSTGRES_PASSWORD", "local-only")

    settings = Settings.from_env()

    assert settings.database_url == ("postgresql://analyst:local-only@warehouse:5433/market")


def test_explicit_database_url_takes_precedence(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://explicit.example/recommerce")

    assert Settings.from_env().database_url == "postgresql://explicit.example/recommerce"
