"""Configuration settings for the provisioning function."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings using environment variables."""

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    # Azure Subscription and Resource Groups
    azure_subscription_id: str
    postgres_resource_group: str
    postgres_server_name: str
    managed_identity_resource_group: str
    managed_identity_name: str
    managed_identity_client_id: str
    aks_resource_group: str
    aks_cluster_name: str

    # Database Configuration
    postgres_admin_user: str
    postgres_admin_password: str

    # Keyvault Identity Configuration (used by pods for Key Vault access)
    keyvault_identity_name: str
    keyvault_identity_resource_group: str

    # Computed properties
    @property
    def postgres_host(self) -> str:
        """PostgreSQL server hostname."""
        return f"{self.postgres_server_name}.postgres.database.azure.com"
