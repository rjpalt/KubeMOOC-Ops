"""Configuration settings for the deployment function."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(
        env_prefix="",
        case_sensitive=False,
    )

    # Azure Container Registry settings
    acr_login_server: str = "kubemooc.azurecr.io"
    acr_name: str = "kubemooc"

    # Azure Kubernetes Service settings
    aks_cluster_name: str = "kube-mooc"
    aks_resource_group: str = "kubernetes-learning"
    azure_subscription_id: str = "ede18d8a-a758-4a40-b15e-6eded5264b93"

    # GitHub repository settings
    github_repository_url: str = "https://github.com/rjpalt/KubernetesMOOC"

    # Azure Functions settings
    azure_client_id: str = "7d02038e-70a7-4666-833c-e00de5e103d1"  # Managed identity client ID


# Global settings instance
settings = Settings()
