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
    azure_subscription_id: str  # No default - must be provided via environment

    # GitHub repository settings
    github_repository_url: str = "https://github.com/rjpalt/KubernetesMOOC"

    # Azure Functions settings
    azure_client_id: str  # No default - must be provided via environment


# Global settings instance
settings = Settings()
