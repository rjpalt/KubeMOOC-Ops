"""Test configuration settings for the deprovisioning function."""

from unittest.mock import patch

from config import Settings

# Test constants
TEST_PASSWORD = "test_password"  # nosec: B105 - Test value only
ENV_PASSWORD = "env_password"  # nosec: B105 - Test value only


def test_settings_defaults() -> None:
    """Test that settings have correct default values."""
    mock_env = {
        "POSTGRES_ADMIN_PASSWORD": TEST_PASSWORD,
        "AZURE_SUBSCRIPTION_ID": "12345678-1234-1234-1234-123456789012",
        "POSTGRES_RESOURCE_GROUP": "test-postgres-rg",
        "POSTGRES_SERVER_NAME": "test-postgres-server",
        "DATABASE_IDENTITY_RESOURCE_GROUP": "test-identity-rg",
        "DATABASE_IDENTITY_NAME": "test-database-identity",
        "DATABASE_IDENTITY_CLIENT_ID": "11111111-1111-1111-1111-111111111111",
        "KEYVAULT_IDENTITY_RESOURCE_GROUP": "test-keyvault-identity-rg",
        "KEYVAULT_IDENTITY_NAME": "test-keyvault-identity",
        "KEYVAULT_IDENTITY_CLIENT_ID": "22222222-2222-2222-2222-222222222222",
        "DEPROVISIONING_FUNCTION_IDENTITY_NAME": "test-deprovisioning-identity",
        "DEPROVISIONING_FUNCTION_CLIENT_ID": "33333333-3333-3333-3333-333333333333",
        "AKS_RESOURCE_GROUP": "test-aks-rg",
        "AKS_CLUSTER_NAME": "test-aks-cluster",
        "POSTGRES_ADMIN_USER": "postgres",
    }

    with patch.dict("os.environ", mock_env):
        settings = Settings()

        assert settings.azure_subscription_id == "12345678-1234-1234-1234-123456789012"
        assert settings.postgres_resource_group == "test-postgres-rg"
        assert settings.postgres_server_name == "test-postgres-server"
        assert settings.database_identity_resource_group == "test-identity-rg"
        assert settings.database_identity_name == "test-database-identity"
        assert settings.database_identity_client_id == "11111111-1111-1111-1111-111111111111"
        assert settings.keyvault_identity_resource_group == "test-keyvault-identity-rg"
        assert settings.keyvault_identity_name == "test-keyvault-identity"
        assert settings.keyvault_identity_client_id == "22222222-2222-2222-2222-222222222222"
        assert settings.deprovisioning_function_identity_name == "test-deprovisioning-identity"
        assert settings.deprovisioning_function_client_id == "33333333-3333-3333-3333-333333333333"
        assert settings.aks_resource_group == "test-aks-rg"
        assert settings.aks_cluster_name == "test-aks-cluster"
        assert settings.postgres_admin_user == "postgres"
        assert settings.postgres_admin_password == TEST_PASSWORD


def test_postgres_host_property() -> None:
    """Test that postgres_host property is computed correctly."""
    mock_env = {
        "POSTGRES_ADMIN_PASSWORD": TEST_PASSWORD,
        "AZURE_SUBSCRIPTION_ID": "12345678-1234-1234-1234-123456789012",
        "POSTGRES_RESOURCE_GROUP": "test-postgres-rg",
        "POSTGRES_SERVER_NAME": "test-postgres-server",
        "DATABASE_IDENTITY_RESOURCE_GROUP": "test-identity-rg",
        "DATABASE_IDENTITY_NAME": "test-database-identity",
        "DATABASE_IDENTITY_CLIENT_ID": "11111111-1111-1111-1111-111111111111",
        "KEYVAULT_IDENTITY_RESOURCE_GROUP": "test-keyvault-identity-rg",
        "KEYVAULT_IDENTITY_NAME": "test-keyvault-identity",
        "KEYVAULT_IDENTITY_CLIENT_ID": "22222222-2222-2222-2222-222222222222",
        "DEPROVISIONING_FUNCTION_IDENTITY_NAME": "test-deprovisioning-identity",
        "DEPROVISIONING_FUNCTION_CLIENT_ID": "33333333-3333-3333-3333-333333333333",
        "AKS_RESOURCE_GROUP": "test-aks-rg",
        "AKS_CLUSTER_NAME": "test-aks-cluster",
        "POSTGRES_ADMIN_USER": "postgres",
    }

    with patch.dict("os.environ", mock_env):
        settings = Settings()
        expected_host = f"{settings.postgres_server_name}.postgres.database.azure.com"
        assert settings.postgres_host == expected_host


def test_settings_environment_override() -> None:
    """Test that environment variables override default settings."""
    env_vars = {
        "POSTGRES_ADMIN_PASSWORD": ENV_PASSWORD,
        "POSTGRES_SERVER_NAME": "env-postgres-server",
        "AKS_CLUSTER_NAME": "env-aks-cluster",
        "DEPROVISIONING_FUNCTION_CLIENT_ID": "44444444-4444-4444-4444-444444444444",
        # Required fields with minimal values
        "AZURE_SUBSCRIPTION_ID": "12345678-1234-1234-1234-123456789012",
        "POSTGRES_RESOURCE_GROUP": "test-postgres-rg",
        "DATABASE_IDENTITY_RESOURCE_GROUP": "test-identity-rg",
        "DATABASE_IDENTITY_NAME": "test-database-identity",
        "DATABASE_IDENTITY_CLIENT_ID": "11111111-1111-1111-1111-111111111111",
        "KEYVAULT_IDENTITY_RESOURCE_GROUP": "test-keyvault-identity-rg",
        "KEYVAULT_IDENTITY_NAME": "test-keyvault-identity",
        "KEYVAULT_IDENTITY_CLIENT_ID": "22222222-2222-2222-2222-222222222222",
        "DEPROVISIONING_FUNCTION_IDENTITY_NAME": "test-deprovisioning-identity",
        "AKS_RESOURCE_GROUP": "test-aks-rg",
        "POSTGRES_ADMIN_USER": "postgres",
    }

    with patch.dict("os.environ", env_vars):
        settings = Settings()

        assert settings.postgres_admin_password == ENV_PASSWORD
        assert settings.postgres_server_name == "env-postgres-server"
        assert settings.aks_cluster_name == "env-aks-cluster"
        assert settings.deprovisioning_function_client_id == "44444444-4444-4444-4444-444444444444"
