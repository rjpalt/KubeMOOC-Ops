"""Provisioning service for managing Azure and Kubernetes resources."""

import logging
import time
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
        # Use the specific user-assigned managed identity for this function
        self.credential = DefaultAzureCredential(
            managed_identity_client_id=settings.managed_identity_client_id
        )

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

    # Note: Kubernetes operations use Azure SDK to get credentials then Kubernetes Python client

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
            self.logger.error(
                "PostgreSQL admin password not configured",
                extra={
                    "operation": "create_database",
                    "database_name": database_name,
                    "error_type": "missing_password"
                }
            )
            raise ValueError(msg)

        self.logger.info(
            "Starting database creation",
            extra={
                "operation": "create_database",
                "database_name": database_name
            }
        )

        try:
            # Connect to PostgreSQL server
            self.logger.debug(
                "Attempting PostgreSQL connection",
                extra={
                    "operation": "create_database",
                    "database_name": database_name
                }
            )
            
            conn = psycopg2.connect(
                host=self.settings.postgres_host,
                port=5432,
                user=self.settings.postgres_admin_user,
                password=self.settings.postgres_admin_password,
                database="postgres",
            )
            conn.autocommit = True

            self.logger.info(
                "PostgreSQL connection established successfully",
                extra={
                    "operation": "create_database",
                    "database_name": database_name
                }
            )

            with conn.cursor() as cursor:
                # Sanitize database name for PostgreSQL (replace hyphens with underscores)
                sanitized_name = database_name.replace("-", "_")
                
                self.logger.info(
                    "Executing database creation command",
                    extra={
                        "operation": "create_database",
                        "original_name": database_name,
                        "sanitized_name": sanitized_name
                    }
                )
                
                cursor.execute(f'CREATE DATABASE "{sanitized_name}"')
                self.logger.info(
                    "Database created successfully",
                    extra={
                        "operation": "create_database",
                        "database_name": sanitized_name,
                        "status": "created"
                    }
                )

            conn.close()
            self.logger.debug(
                "PostgreSQL connection closed",
                extra={
                    "operation": "create_database",
                    "database_name": database_name
                }
            )
            
        except psycopg2.Error as e:
            if "already exists" in str(e):
                self.logger.warning(
                    "Database already exists, continuing",
                    extra={
                        "operation": "create_database",
                        "database_name": database_name,
                        "status": "already_exists",
                        "error_message": str(e)
                    }
                )
                return True
            
            self.logger.error(
                "Failed to create database",
                extra={
                    "operation": "create_database",
                    "database_name": database_name,
                    "error_type": "psycopg2_error",
                    "error_message": str(e),
                    "error_code": getattr(e, 'pgcode', None)
                }
            )
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error during database creation",
                extra={
                    "operation": "create_database",
                    "database_name": database_name,
                    "error_type": "unexpected_error",
                    "error_class": type(e).__name__,
                    "error_message": str(e)
                }
            )
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
        self.logger.info(
            "Starting federated credential creation",
            extra={
                "operation": "create_federated_credential",
                "branch_name": branch_name,
                "managed_identity": self.settings.managed_identity_name,
                "aks_cluster": self.settings.aks_cluster_name
            }
        )
        
        try:
            # Get OIDC issuer URL from AKS cluster
            self.logger.debug(
                "Validating AKS OIDC configuration",
                extra={
                    "operation": "create_federated_credential",
                    "branch_name": branch_name,
                    "aks_cluster": self.settings.aks_cluster_name
                }
            )
            
            issuer_url = self._validate_oidc_configuration(self.settings.aks_cluster_name)
            
            self.logger.info(
                "AKS OIDC issuer URL retrieved",
                extra={
                    "operation": "create_federated_credential",
                    "branch_name": branch_name,
                    "issuer_url": issuer_url
                }
            )

            identity_client = self.get_identity_client()
            credential_name = f"cred-{branch_name}"
            subject = f"system:serviceaccount:{branch_name}:default"

            self.logger.info(
                "Creating federated credential",
                extra={
                    "operation": "create_federated_credential",
                    "branch_name": branch_name,
                    "credential_name": credential_name,
                    "subject": subject,
                    "managed_identity_rg": self.settings.managed_identity_resource_group
                }
            )

            # Create federated credential
            result = identity_client.federated_identity_credentials.create_or_update(
                resource_group_name=self.settings.managed_identity_resource_group,
                resource_name=self.settings.managed_identity_name,
                federated_identity_credential_resource_name=credential_name,
                parameters={
                    "properties": {
                        "issuer": issuer_url,
                        "subject": subject,
                        "audiences": ["api://AzureADTokenExchange"],
                    },
                },
            )

            self.logger.info(
                "Federated credential created successfully",
                extra={
                    "operation": "create_federated_credential",
                    "branch_name": branch_name,
                    "credential_name": credential_name,
                    "credential_id": getattr(result, 'id', None),
                    "status": "created"
                }
            )
            
        except ValueError as e:
            self.logger.error(
                "OIDC validation failed",
                extra={
                    "operation": "create_federated_credential",
                    "branch_name": branch_name,
                    "error_type": "oidc_validation_error",
                    "error_message": str(e)
                }
            )
            raise
        except Exception as e:
            self.logger.error(
                "Failed to create federated credential",
                extra={
                    "operation": "create_federated_credential",
                    "branch_name": branch_name,
                    "credential_name": f"cred-{branch_name}",
                    "error_type": "credential_creation_error",
                    "error_class": type(e).__name__,
                    "error_message": str(e)
                }
            )
            raise
        else:
            return True

    def create_namespace(self, namespace_name: str) -> bool:
        """Create Kubernetes namespace using Azure SDK and Kubernetes client.

        Args:
            namespace_name: Name of the namespace to create

        Returns:
            True if namespace was created or already exists

        Raises:
            Exception: If namespace creation fails
        """
        self.logger.info(
            "Starting Kubernetes namespace creation using Azure SDK",
            extra={
                "operation": "create_namespace",
                "namespace_name": namespace_name,
                "aks_cluster": self.settings.aks_cluster_name
            }
        )
        
        try:
            # Get AKS cluster credentials using Azure SDK
            container_client = ContainerServiceClient(
                self.credential,
                self.settings.azure_subscription_id,
            )
            
            # Get cluster admin credentials
            credential_results = container_client.managed_clusters.list_cluster_admin_credentials(
                resource_group_name=self.settings.aks_resource_group,
                resource_name=self.settings.aks_cluster_name,
            )
            
            if not credential_results.kubeconfigs:
                raise Exception("No kubeconfig found for AKS cluster")
            
            # Load kubeconfig from Azure SDK result
            import tempfile
            import os
            
            kubeconfig_content = credential_results.kubeconfigs[0].value.decode('utf-8')
            
            # Create temporary kubeconfig file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(kubeconfig_content)
                temp_kubeconfig_path = f.name
            
            try:
                # Load configuration from temporary file
                config.load_kube_config(config_file=temp_kubeconfig_path)
                self.logger.info("Successfully loaded AKS credentials")
                
                # Initialize Kubernetes client
                k8s_client = client.CoreV1Api()
                
                # Check if namespace already exists
                try:
                    existing_ns = k8s_client.read_namespace(name=namespace_name)
                    self.logger.warning(
                        "Namespace already exists",
                        extra={
                            "operation": "create_namespace",
                            "namespace_name": namespace_name,
                            "status": "already_exists",
                            "creation_timestamp": str(existing_ns.metadata.creation_timestamp),
                            "uid": existing_ns.metadata.uid
                        }
                    )
                    return True
                except client.ApiException as e:
                    if e.status != HTTP_NOT_FOUND:
                        self.logger.error(f"Error checking namespace existence: {e}")
                        raise
                    
                    self.logger.debug("Namespace does not exist, proceeding with creation")

                # Create namespace with labels
                labels = {
                    "app.kubernetes.io/managed-by": "provisioning-function",
                    "provisioning.kubernetes.io/branch": namespace_name,
                    "dev-gateway-access": "allowed",  # Required for AGC gateway access
                }
                
                self.logger.info(f"Creating namespace: {namespace_name} with labels: {labels}")
                
                namespace_manifest = client.V1Namespace(
                    metadata=client.V1ObjectMeta(
                        name=namespace_name,
                        labels=labels,
                    ),
                )

                created_ns = k8s_client.create_namespace(body=namespace_manifest)
                
                self.logger.info(
                    "Kubernetes namespace created successfully",
                    extra={
                        "operation": "create_namespace",
                        "namespace_name": namespace_name,
                        "status": "created",
                        "creation_timestamp": str(created_ns.metadata.creation_timestamp),
                        "uid": created_ns.metadata.uid,
                        "labels_applied": labels
                    }
                )
                
                return True
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_kubeconfig_path):
                    os.unlink(temp_kubeconfig_path)
            
        except client.ApiException as e:
            self.logger.error(
                "Kubernetes API error during namespace creation",
                extra={
                    "operation": "create_namespace",
                    "namespace_name": namespace_name,
                    "error_type": "k8s_api_error",
                    "error_status": e.status,
                    "error_reason": e.reason,
                    "error_message": str(e)
                }
            )
            raise
        except Exception as e:
            self.logger.error(
                "Failed to create namespace using Azure SDK",
                extra={
                    "operation": "create_namespace",
                    "namespace_name": namespace_name,
                    "error_type": "azure_sdk_error",
                    "error_class": type(e).__name__,
                    "error_message": str(e)
                }
            )
            raise

    def provision_environment(self, branch_name: str) -> dict[str, Any]:
        """Main provisioning method.

        Args:
            branch_name: Name of the branch to provision environment for

        Returns:
            Dictionary containing provisioning status and details

        Raises:
            Exception: If any provisioning step fails
        """
        operation_start_time = time.time()
        self.logger.info(
            "Starting environment provisioning workflow",
            extra={
                "operation": "provision_environment",
                "branch_name": branch_name,
                "subscription_id": self.settings.azure_subscription_id,
                "postgres_server": self.settings.postgres_server_name,
                "managed_identity": self.settings.managed_identity_name,
                "aks_cluster": self.settings.aks_cluster_name
            }
        )
        
        try:
            # Create database
            self.logger.info(
                "Step 1/3: Creating PostgreSQL database",
                extra={
                    "operation": "provision_environment",
                    "branch_name": branch_name,
                    "step": "database_creation"
                }
            )
            database_start_time = time.time()
            database_created = self.create_database(branch_name)
            database_duration = time.time() - database_start_time
            
            self.logger.info(
                "Database creation completed",
                extra={
                    "operation": "provision_environment",
                    "branch_name": branch_name,
                    "step": "database_creation",
                    "duration_seconds": round(database_duration, 2),
                    "success": database_created
                }
            )

            # Create federated credential
            self.logger.info(
                "Step 2/3: Creating federated credential",
                extra={
                    "operation": "provision_environment",
                    "branch_name": branch_name,
                    "step": "credential_creation"
                }
            )
            credential_start_time = time.time()
            credential_created = self.create_federated_credential(branch_name)
            credential_duration = time.time() - credential_start_time
            
            self.logger.info(
                "Credential creation completed",
                extra={
                    "operation": "provision_environment",
                    "branch_name": branch_name,
                    "step": "credential_creation",
                    "duration_seconds": round(credential_duration, 2),
                    "success": credential_created
                }
            )

            # Create Kubernetes namespace
            self.logger.info(
                "Step 3/3: Creating Kubernetes namespace",
                extra={
                    "operation": "provision_environment",
                    "branch_name": branch_name,
                    "step": "namespace_creation"
                }
            )
            namespace_start_time = time.time()
            namespace_created = self.create_namespace(branch_name)
            namespace_duration = time.time() - namespace_start_time
            
            self.logger.info(
                "Namespace creation completed",
                extra={
                    "operation": "provision_environment",
                    "branch_name": branch_name,
                    "step": "namespace_creation",
                    "duration_seconds": round(namespace_duration, 2),
                    "success": namespace_created
                }
            )

            # Build result
            total_duration = time.time() - operation_start_time
            result = {
                "status": "success",
                "branch_name": branch_name,
                "database_created": database_created,
                "credential_created": credential_created,
                "namespace_created": namespace_created,
                "message": f"Environment for branch '{branch_name}' provisioned successfully",
                "timing": {
                    "total_duration_seconds": round(total_duration, 2),
                    "database_duration_seconds": round(database_duration, 2),
                    "credential_duration_seconds": round(credential_duration, 2),
                    "namespace_duration_seconds": round(namespace_duration, 2)
                }
            }

            self.logger.info(
                "Environment provisioning completed successfully",
                extra={
                    "operation": "provision_environment",
                    "branch_name": branch_name,
                    "total_duration_seconds": round(total_duration, 2),
                    "all_steps_successful": True,
                    "result": result
                }
            )
            
        except Exception as e:
            total_duration = time.time() - operation_start_time
            error_msg = f"Provisioning failed for branch '{branch_name}': {e!s}"
            
            self.logger.error(
                "Environment provisioning failed",
                extra={
                    "operation": "provision_environment",
                    "branch_name": branch_name,
                    "total_duration_seconds": round(total_duration, 2),
                    "error_type": "provisioning_failure",
                    "error_class": type(e).__name__,
                    "error_message": str(e),
                    "all_steps_successful": False
                }
            )
            
            return {
                "status": "error",
                "branch_name": branch_name,
                "error": error_msg,
                "timing": {
                    "total_duration_seconds": round(total_duration, 2)
                }
            }
        else:
            return result
