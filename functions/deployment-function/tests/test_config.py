"""Tests for configuration module."""

import pytest

from config import Settings


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables with test values."""
    monkeypatch.setenv("ACR_LOGIN_SERVER", "test-acr.azurecr.io")
    monkeypatch.setenv("ACR_NAME", "test-acr")
    monkeypatch.setenv("AKS_CLUSTER_NAME", "test-cluster")
    monkeypatch.setenv("AKS_RESOURCE_GROUP", "test-rg")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "12345678-1234-1234-1234-123456789012")
    monkeypatch.setenv("GITHUB_REPOSITORY_URL", "https://github.com/test-org/test-repo")
    monkeypatch.setenv("AZURE_CLIENT_ID", "87654321-4321-4321-4321-210987654321")


def test_settings_default_values():
    """Test that settings have reasonable default values."""
    settings = Settings()

    # Test that defaults are set (using real defaults since these are safe constants)
    assert "azurecr.io" in settings.acr_login_server
    assert isinstance(settings.acr_name, str)
    assert isinstance(settings.aks_cluster_name, str)
    assert isinstance(settings.aks_resource_group, str)
    assert settings.github_repository_url.startswith("https://github.com/")


def test_settings_environment_override(mock_env_vars):
    """Test that environment variables override default values."""
    settings = Settings()

    assert settings.acr_login_server == "test-acr.azurecr.io"
    assert settings.acr_name == "test-acr"
    assert settings.aks_cluster_name == "test-cluster"
    assert settings.aks_resource_group == "test-rg"
    assert settings.azure_subscription_id == "12345678-1234-1234-1234-123456789012"
    assert settings.github_repository_url == "https://github.com/test-org/test-repo"
    assert settings.azure_client_id == "87654321-4321-4321-4321-210987654321"


def test_settings_validation():
    """Test that settings validation works correctly."""
    # This would test any pydantic validation if we had it
    settings = Settings()

    # Ensure all required fields are present
    assert settings.acr_login_server
    assert settings.acr_name
    assert settings.aks_cluster_name
    assert settings.aks_resource_group
    assert settings.azure_subscription_id
    assert settings.github_repository_url
    assert settings.azure_client_id
