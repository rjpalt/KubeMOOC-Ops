"""Tests for the deprovisioning service."""

from unittest.mock import Mock, patch, MagicMock
import pytest
from config import Settings
from deprovisioning_service import PROTECTED_NAMESPACES, DeprovisioningService


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock(spec=Settings)
    settings.azure_subscription_id = "test-subscription-id"
    settings.postgres_resource_group = "test-postgres-rg"
    settings.postgres_server_name = "test-postgres-server"
    settings.aks_resource_group = "test-aks-rg"
    settings.aks_cluster_name = "test-aks-cluster"
    settings.deprovisioning_function_client_id = "test-deprovisioning-client-id"
    settings.database_identity_name = "test-database-identity"
    settings.database_identity_client_id = "test-database-client-id"
    settings.database_identity_resource_group = "test-database-rg"
    settings.keyvault_identity_name = "test-keyvault-identity"
    settings.keyvault_identity_client_id = "test-keyvault-client-id"
    settings.keyvault_identity_resource_group = "test-keyvault-rg"
    settings.postgres_admin_user = "postgres"
    settings.postgres_admin_password = "test-password"
    settings.postgres_host = "test-postgres-server.postgres.database.azure.com"
    return settings


class TestDeprovisioningService:
    """Test cases for DeprovisioningService."""

    def test_init_success(self, mock_settings):
        """Test successful initialization of deprovisioning service."""
        with patch("deprovisioning_service.DefaultAzureCredential") as mock_credential:
            service = DeprovisioningService(mock_settings, "test-correlation-id")
            assert service.settings == mock_settings
            assert service.correlation_id == "test-correlation-id"
            mock_credential.assert_called_once()

    def test_protected_namespace_validation(self, mock_settings):
        """Test that protected namespaces cannot be deleted."""
        with patch("deprovisioning_service.DefaultAzureCredential"):
            service = DeprovisioningService(mock_settings, "test-correlation-id")
            for protected_ns in PROTECTED_NAMESPACES:
                with pytest.raises(ValueError, match=f"Cannot delete protected namespace: {protected_ns}"):
                    service.delete_namespace(protected_ns)
