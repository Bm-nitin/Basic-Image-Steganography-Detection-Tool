import os
import pytest
from app import create_app


class TestSecurityConfiguration:
    """Test suite for Phase F Security Hardening and Configuration Safety."""

    def test_production_fails_without_secret_key(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError) as excinfo:
            create_app("production")
        assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(excinfo.value)
        assert "SECRET_KEY" in str(excinfo.value)

    def test_production_succeeds_with_secret_key(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "super-secure-production-random-token-2026")
        prod_app = create_app("production")
        assert prod_app.config["SECRET_KEY"] == "super-secure-production-random-token-2026"
        assert prod_app.config["DEBUG"] is False

    def test_development_config_has_fallback(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        dev_app = create_app("development")
        assert dev_app.config["SECRET_KEY"] is not None
        assert dev_app.config["DEBUG"] is True

    def test_testing_config_isolated(self):
        test_app = create_app("testing")
        assert test_app.config["TESTING"] is True
