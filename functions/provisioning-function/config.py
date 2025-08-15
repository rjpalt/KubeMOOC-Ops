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
    aks_resource_group: str
    aks_cluster_name: str

    # Provisioning Function Identity (used to authenticate this function)
    provisioning_function_identity_name: str
    provisioning_function_client_id: str

    # Database Access Identity (used by pods for PostgreSQL access)
    database_identity_name: str
    database_identity_client_id: str
    database_identity_resource_group: str

    # Keyvault Identity Configuration (used by pods for Key Vault access)
    keyvault_identity_name: str
    keyvault_identity_client_id: str
    keyvault_identity_resource_group: str

    # Database Configuration
    postgres_admin_user: str
    postgres_admin_password: str

    # Computed properties
    @property
    def postgres_host(self) -> str:
        """PostgreSQL server hostname."""
        return f"{self.postgres_server_name}.postgres.database.azure.com"
