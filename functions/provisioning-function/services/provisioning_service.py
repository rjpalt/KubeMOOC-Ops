"""Provisioning service for managing Azure and Kubernetes resources."""

import logging
from typing import Any

import psycopg2
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.msi import ManagedServiceIdentityClient
from azure.mgmt.rdbms.postgresql import PostgreSQLManagementClient
from kubernetes import client, config

from config import Settings

# Constants for error codes and limits
HTTP_NOT_FOUND = 404


class ProvisioningService:
    """Service for provisioning Azure and Kubernetes resources."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the provisioning service."""
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.credential = DefaultAzureCredential()

    def get_postgres_client(self) -> PostgreSQLManagementClient:
        """Initialize PostgreSQL management client.

        Returns:
            PostgreSQL management client instance

        Raises:
            Exception: If client initialization fails
        """
        return PostgreSQLManagementClient(
            self.credential,
            self.settings.azure_subscription_id,
        )

    def get_identity_client(self) -> ManagedServiceIdentityClient:
        """Initialize Managed Identity client.

        Returns:
            Managed Identity client instance

        Raises:
            Exception: If client initialization fails
        """
        return ManagedServiceIdentityClient(
            self.credential,
            self.settings.azure_subscription_id,
        )

    def get_kubernetes_client(self) -> client.CoreV1Api:
        """Initialize Kubernetes client using managed identity.

        Returns:
            Kubernetes CoreV1Api client instance

        Raises:
            Exception: If Kubernetes configuration cannot be loaded
        """
        try:
            config.load_incluster_config()
        except config.ConfigException:
            try:
                config.load_kube_config()
            except config.ConfigException:
                self.logger.exception("Failed to load Kubernetes configuration")
                raise

        return client.CoreV1Api()

    def create_database(self, database_name: str) -> bool:
        """Create a new database on the PostgreSQL server.

        Args:
            database_name: Name of the database to create

        Returns:
            True if database was created or already exists

        Raises:
            ValueError: If admin password is not configured
            psycopg2.Error: If database creation fails
        """
        if not self.settings.postgres_admin_password:
            msg = "POSTGRES_ADMIN_PASSWORD environment variable is required"
            raise ValueError(msg)

        try:
            # Connect to PostgreSQL server
            conn = psycopg2.connect(
                host=self.settings.postgres_host,
                port=5432,
                user=self.settings.postgres_admin_user,
                password=self.settings.postgres_admin_password,
                database="postgres",
            )
            conn.autocommit = True

            with conn.cursor() as cursor:
                # Sanitize database name for PostgreSQL (replace hyphens with underscores)
                sanitized_name = database_name.replace("-", "_")
                cursor.execute(f'CREATE DATABASE "{sanitized_name}"')
                self.logger.info("Database %s created successfully", sanitized_name)

            conn.close()
        except psycopg2.Error as e:
            if "already exists" in str(e):
                self.logger.warning("Database %s already exists", database_name)
                return True
            self.logger.exception("Failed to create database %s", database_name)
            raise
        else:
            return True

    def _validate_oidc_configuration(self, cluster_name: str) -> str:
        """Validate OIDC configuration and return issuer URL.

        Args:
            cluster_name: Name of the AKS cluster

        Returns:
            OIDC issuer URL

        Raises:
            ValueError: If OIDC is not configured
        """
        container_client = ContainerServiceClient(
            self.credential,
            self.settings.azure_subscription_id,
        )

        cluster = container_client.managed_clusters.get(
            self.settings.aks_resource_group,
            cluster_name,
        )

        if not cluster.oidc_issuer_profile or not cluster.oidc_issuer_profile.issuer_url:
            msg = "AKS cluster does not have OIDC issuer enabled"
            raise ValueError(msg)

        return cluster.oidc_issuer_profile.issuer_url

    def create_federated_credential(self, branch_name: str) -> bool:
        """Create federated credential for the managed identity.

        Args:
            branch_name: Name of the branch to create credential for

        Returns:
            True if credential was created successfully

        Raises:
            ValueError: If AKS cluster doesn't have OIDC issuer enabled
            Exception: If credential creation fails
        """
        try:
            # Get OIDC issuer URL from AKS cluster
            issuer_url = self._validate_oidc_configuration(self.settings.aks_cluster_name)

            identity_client = self.get_identity_client()
            credential_name = f"cred-{branch_name}"

            # Create federated credential
            identity_client.federated_identity_credentials.create_or_update(
                resource_group_name=self.settings.managed_identity_resource_group,
                resource_name=self.settings.managed_identity_name,
                federated_identity_credential_resource_name=credential_name,
                parameters={
                    "properties": {
                        "issuer": issuer_url,
                        "subject": f"system:serviceaccount:{branch_name}:default",
                        "audiences": ["api://AzureADTokenExchange"],
                    },
                },
            )

            self.logger.info("Federated credential %s created successfully", credential_name)
        except Exception:
            self.logger.exception("Failed to create federated credential")
            raise
        else:
            return True

    def create_namespace(self, namespace_name: str) -> bool:
        """Create Kubernetes namespace.

        Args:
            namespace_name: Name of the namespace to create

        Returns:
            True if namespace was created or already exists

        Raises:
            Exception: If namespace creation fails
        """
        try:
            k8s_client = self.get_kubernetes_client()

            # Check if namespace already exists
            try:
                k8s_client.read_namespace(name=namespace_name)
                self.logger.warning("Namespace %s already exists", namespace_name)
            except client.ApiException as e:
                if e.status != HTTP_NOT_FOUND:
                    raise
            else:
                return True

            # Create namespace
            namespace_manifest = client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=namespace_name,
                    labels={
                        "app.kubernetes.io/managed-by": "provisioning-function",
                        "provisioning.kubernetes.io/branch": namespace_name,
                    },
                ),
            )

            k8s_client.create_namespace(body=namespace_manifest)
            self.logger.info("Namespace %s created successfully", namespace_name)
        except Exception:
            self.logger.exception("Failed to create namespace %s", namespace_name)
            raise
        else:
            return True

    def provision_environment(self, branch_name: str) -> dict[str, Any]:
        """Main provisioning method.

        Args:
            branch_name: Name of the branch to provision environment for

        Returns:
            Dictionary containing provisioning status and details

        Raises:
            Exception: If any provisioning step fails
        """
        try:
            # Create database
            database_created = self.create_database(branch_name)

            # Create federated credential
            credential_created = self.create_federated_credential(branch_name)

            # Create Kubernetes namespace
            namespace_created = self.create_namespace(branch_name)

            # Build result
            result = {
                "status": "success",
                "branch_name": branch_name,
                "database_created": database_created,
                "credential_created": credential_created,
                "namespace_created": namespace_created,
                "message": f"Environment for branch '{branch_name}' provisioned successfully",
            }

            self.logger.info("Provisioning completed successfully: %s", result)
        except Exception as e:
            error_msg = f"Provisioning failed for branch '{branch_name}': {e!s}"
            self.logger.exception("%s", error_msg)
            return {
                "status": "error",
                "branch_name": branch_name,
                "error": error_msg,
            }
        else:
            return result
