"""Deprovisioning service for cleaning up Azure and Kubernetes resources."""

import logging
import time
from typing import Any

import psycopg2
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.msi import ManagedServiceIdentityClient
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from config import Settings

# Constants for error codes and limits
HTTP_NOT_FOUND = 404

# Protected namespaces that should never be deleted
PROTECTED_NAMESPACES = {
    "default", "kube-system", "azure-alb-system",
    "project", "kube-public", "kube-node-lease",
    "azure-system", "gatekeeper-system",
}


class DeprovisioningService:
    """Service for deprovisioning Azure and Kubernetes resources."""

    def __init__(self, settings: Settings, correlation_id: str) -> None:
        """Initialize the deprovisioning service."""
        self.settings = settings
        self.correlation_id = correlation_id
        self.logger = logging.getLogger(__name__)
        # Use the specific user-assigned managed identity for this function
        self.credential = DefaultAzureCredential(
            managed_identity_client_id=settings.deprovisioning_function_client_id,
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

    def delete_database(self, database_name: str) -> dict[str, Any]:
        """Delete a database from the PostgreSQL server.

        Args:
            database_name: Name of the database to delete

        Returns:
            Dictionary with deletion status and timing

        Raises:
            ValueError: If admin password is not configured
        """
        operation_start_time = time.time()

        if not self.settings.postgres_admin_password:
            msg = "POSTGRES_ADMIN_PASSWORD environment variable is required"
            self.logger.error(
                "PostgreSQL admin password not configured",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_database",
                    "database_name": database_name,
                    "error_type": "missing_password",
                },
            )
            raise ValueError(msg)

        # Sanitize database name for PostgreSQL (replace hyphens with underscores)
        sanitized_name = database_name.replace("-", "_")

        self.logger.info(
            "Starting database deletion",
            extra={
                "correlation_id": self.correlation_id,
                "operation": "delete_database",
                "original_name": database_name,
                "sanitized_name": sanitized_name,
            },
        )

        try:
            # Connect to PostgreSQL server
            self.logger.debug(
                "Attempting PostgreSQL connection",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_database",
                    "database_name": sanitized_name,
                },
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
                    "correlation_id": self.correlation_id,
                    "operation": "delete_database",
                    "database_name": sanitized_name,
                },
            )

            with conn.cursor() as cursor:
                # Check if database exists first
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (sanitized_name,),
                )
                exists = cursor.fetchone()

                if not exists:
                    self.logger.warning(
                        "Database does not exist, continuing",
                        extra={
                            "correlation_id": self.correlation_id,
                            "operation": "delete_database",
                            "database_name": sanitized_name,
                            "status": "already_deleted",
                        },
                    )
                else:
                    # Terminate connections to the database before deletion
                    self.logger.info(
                        "Terminating connections to database before deletion",
                        extra={
                            "correlation_id": self.correlation_id,
                            "operation": "delete_database",
                            "database_name": sanitized_name,
                        },
                    )

                    cursor.execute("""
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = %s AND pid <> pg_backend_pid()
                    """, (sanitized_name,))

                    # Drop the database
                    self.logger.info(
                        "Executing database deletion command",
                        extra={
                            "correlation_id": self.correlation_id,
                            "operation": "delete_database",
                            "database_name": sanitized_name,
                        },
                    )

                    cursor.execute(f'DROP DATABASE "{sanitized_name}"')
                    self.logger.info(
                        "Database deleted successfully",
                        extra={
                            "correlation_id": self.correlation_id,
                            "operation": "delete_database",
                            "database_name": sanitized_name,
                            "status": "deleted",
                        },
                    )

            conn.close()
            self.logger.debug(
                "PostgreSQL connection closed",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_database",
                    "database_name": sanitized_name,
                },
            )

            operation_duration = time.time() - operation_start_time
            return {
                "deleted": True,
                "database_name": sanitized_name,
                "duration_seconds": round(operation_duration, 2),
            }

        except psycopg2.Error as e:
            operation_duration = time.time() - operation_start_time
            self.logger.error(
                "Failed to delete database",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_database",
                    "database_name": sanitized_name,
                    "error_type": "psycopg2_error",
                    "error_message": str(e),
                    "error_code": getattr(e, "pgcode", None),
                    "duration_seconds": round(operation_duration, 2),
                },
            )
            raise
        except Exception as e:
            operation_duration = time.time() - operation_start_time
            self.logger.error(
                "Unexpected error during database deletion",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_database",
                    "database_name": sanitized_name,
                    "error_type": "unexpected_error",
                    "error_class": type(e).__name__,
                    "error_message": str(e),
                    "duration_seconds": round(operation_duration, 2),
                },
            )
            raise

    def delete_federated_credentials(self, branch_name: str) -> dict[str, Any]:
        """Delete federated credentials for both database and keyvault access.

        Args:
            branch_name: Name of the branch to delete credentials for

        Returns:
            Dictionary with deletion status for both credentials

        Raises:
            Exception: If credential deletion fails critically
        """
        operation_start_time = time.time()

        self.logger.info(
            "Starting federated credential deletion for both database and keyvault access",
            extra={
                "correlation_id": self.correlation_id,
                "operation": "delete_federated_credentials",
                "branch_name": branch_name,
                "database_identity": self.settings.database_identity_name,
                "keyvault_identity": self.settings.keyvault_identity_name,
            },
        )

        identity_client = self.get_identity_client()
        database_credential_name = f"database-workload-identity-{branch_name}"
        keyvault_credential_name = f"keyvault-workload-identity-{branch_name}"

        results = {
            "database_credential": False,
            "keyvault_credential": False,
        }
        errors = []

        # 1. Delete database federated credential
        try:
            self.logger.info(
                "Deleting federated credential for database access",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_federated_credentials",
                    "branch_name": branch_name,
                    "credential_name": database_credential_name,
                    "identity": self.settings.database_identity_name,
                    "resource_group": self.settings.database_identity_resource_group,
                },
            )

            identity_client.federated_identity_credentials.delete(
                resource_group_name=self.settings.database_identity_resource_group,
                resource_name=self.settings.database_identity_name,
                federated_identity_credential_resource_name=database_credential_name,
            )

            results["database_credential"] = True
            self.logger.info(
                "Database federated credential deleted successfully",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_federated_credentials",
                    "branch_name": branch_name,
                    "credential_name": database_credential_name,
                    "status": "deleted",
                },
            )

        except ResourceNotFoundError:
            self.logger.warning(
                "Database federated credential not found, continuing",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_federated_credentials",
                    "branch_name": branch_name,
                    "credential_name": database_credential_name,
                    "status": "not_found",
                },
            )
            results["database_credential"] = True  # Consider as successful if already gone
        except Exception as e:
            error_msg = f"Failed to delete database federated credential: {e}"
            errors.append({
                "operation": "database_credential_deletion",
                "error": error_msg,
                "severity": "warning",
            })
            self.logger.error(
                "Failed to delete database federated credential",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_federated_credentials",
                    "branch_name": branch_name,
                    "credential_name": database_credential_name,
                    "error_type": "credential_deletion_error",
                    "error_message": str(e),
                },
            )

        # 2. Delete keyvault federated credential
        try:
            self.logger.info(
                "Deleting federated credential for keyvault access",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_federated_credentials",
                    "branch_name": branch_name,
                    "credential_name": keyvault_credential_name,
                    "identity": self.settings.keyvault_identity_name,
                    "resource_group": self.settings.keyvault_identity_resource_group,
                },
            )

            identity_client.federated_identity_credentials.delete(
                resource_group_name=self.settings.keyvault_identity_resource_group,
                resource_name=self.settings.keyvault_identity_name,
                federated_identity_credential_resource_name=keyvault_credential_name,
            )

            results["keyvault_credential"] = True
            self.logger.info(
                "Keyvault federated credential deleted successfully",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_federated_credentials",
                    "branch_name": branch_name,
                    "credential_name": keyvault_credential_name,
                    "status": "deleted",
                },
            )

        except ResourceNotFoundError:
            self.logger.warning(
                "Keyvault federated credential not found, continuing",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_federated_credentials",
                    "branch_name": branch_name,
                    "credential_name": keyvault_credential_name,
                    "status": "not_found",
                },
            )
            results["keyvault_credential"] = True  # Consider as successful if already gone
        except Exception as e:
            error_msg = f"Failed to delete keyvault federated credential: {e}"
            errors.append({
                "operation": "keyvault_credential_deletion",
                "error": error_msg,
                "severity": "warning",
            })
            self.logger.error(
                "Failed to delete keyvault federated credential",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_federated_credentials",
                    "branch_name": branch_name,
                    "credential_name": keyvault_credential_name,
                    "error_type": "credential_deletion_error",
                    "error_message": str(e),
                },
            )

        operation_duration = time.time() - operation_start_time

        return {
            "deleted": results,
            "duration_seconds": round(operation_duration, 2),
            "errors": errors,
        }

    def suspend_cronjobs_in_namespace(self, namespace_name: str) -> int:
        """Suspend all CronJobs in a namespace before deletion.

        Args:
            namespace_name: Name of the namespace

        Returns:
            Number of CronJobs suspended

        Raises:
            Exception: If CronJob suspension fails critically
        """
        self.logger.info(
            "Suspending CronJobs in namespace before deletion",
            extra={
                "correlation_id": self.correlation_id,
                "operation": "suspend_cronjobs",
                "namespace_name": namespace_name,
            },
        )

        try:
            # Get CronJobs in the namespace
            batch_v1 = client.BatchV1Api()
            cronjobs = batch_v1.list_namespaced_cron_job(namespace=namespace_name)

            suspended_count = 0
            for cronjob in cronjobs.items:
                if not cronjob.spec.suspend:
                    self.logger.info(
                        "Suspending CronJob",
                        extra={
                            "correlation_id": self.correlation_id,
                            "operation": "suspend_cronjobs",
                            "namespace_name": namespace_name,
                            "cronjob_name": cronjob.metadata.name,
                        },
                    )

                    # Patch the CronJob to suspend it
                    cronjob.spec.suspend = True
                    batch_v1.patch_namespaced_cron_job(
                        name=cronjob.metadata.name,
                        namespace=namespace_name,
                        body=cronjob,
                    )
                    suspended_count += 1

            self.logger.info(
                "CronJobs suspended successfully",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "suspend_cronjobs",
                    "namespace_name": namespace_name,
                    "suspended_count": suspended_count,
                },
            )

            return suspended_count

        except ApiException as e:
            if e.status == HTTP_NOT_FOUND:
                self.logger.warning(
                    "Namespace not found during CronJob suspension, continuing",
                    extra={
                        "correlation_id": self.correlation_id,
                        "operation": "suspend_cronjobs",
                        "namespace_name": namespace_name,
                        "status": "not_found",
                    },
                )
                return 0

            self.logger.error(
                "Failed to suspend CronJobs",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "suspend_cronjobs",
                    "namespace_name": namespace_name,
                    "error_type": "k8s_api_error",
                    "error_status": e.status,
                    "error_message": str(e),
                },
            )
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error during CronJob suspension",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "suspend_cronjobs",
                    "namespace_name": namespace_name,
                    "error_type": "unexpected_error",
                    "error_class": type(e).__name__,
                    "error_message": str(e),
                },
            )
            raise

    def delete_namespace(self, namespace_name: str) -> dict[str, Any]:
        """Delete Kubernetes namespace using Azure SDK and Kubernetes client.

        Args:
            namespace_name: Name of the namespace to delete

        Returns:
            Dictionary with deletion status and timing

        Raises:
            ValueError: If attempting to delete a protected namespace
            Exception: If namespace deletion fails
        """
        operation_start_time = time.time()

        # Safety check: Prevent deletion of protected namespaces
        if namespace_name in PROTECTED_NAMESPACES:
            raise ValueError(
                f"Cannot delete protected namespace: {namespace_name}. "
                f"Protected namespaces: {sorted(PROTECTED_NAMESPACES)}",
            )

        self.logger.info(
            "Starting Kubernetes namespace deletion using Azure SDK",
            extra={
                "correlation_id": self.correlation_id,
                "operation": "delete_namespace",
                "namespace_name": namespace_name,
                "aks_cluster": self.settings.aks_cluster_name,
            },
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
            import os
            import tempfile

            kubeconfig_content = credential_results.kubeconfigs[0].value.decode("utf-8")

            # Create temporary kubeconfig file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                f.write(kubeconfig_content)
                temp_kubeconfig_path = f.name

            try:
                # Load configuration from temporary file
                config.load_kube_config(config_file=temp_kubeconfig_path)
                self.logger.info("Successfully loaded AKS credentials")

                # Initialize Kubernetes client
                k8s_client = client.CoreV1Api()

                # Check if namespace exists
                try:
                    namespace = k8s_client.read_namespace(name=namespace_name)
                    self.logger.info(
                        "Namespace found, proceeding with deletion",
                        extra={
                            "correlation_id": self.correlation_id,
                            "operation": "delete_namespace",
                            "namespace_name": namespace_name,
                            "creation_timestamp": str(namespace.metadata.creation_timestamp),
                            "uid": namespace.metadata.uid,
                        },
                    )
                except ApiException as e:
                    if e.status == HTTP_NOT_FOUND:
                        self.logger.warning(
                            "Namespace not found, considering as already deleted",
                            extra={
                                "correlation_id": self.correlation_id,
                                "operation": "delete_namespace",
                                "namespace_name": namespace_name,
                                "status": "already_deleted",
                            },
                        )
                        operation_duration = time.time() - operation_start_time
                        return {
                            "deleted": True,
                            "namespace_name": namespace_name,
                            "cronjobs_suspended": 0,
                            "duration_seconds": round(operation_duration, 2),
                            "status": "already_deleted",
                        }
                    raise

                # Suspend CronJobs before namespace deletion
                cronjobs_suspended = self.suspend_cronjobs_in_namespace(namespace_name)

                # Delete the namespace
                self.logger.info(
                    "Deleting namespace",
                    extra={
                        "correlation_id": self.correlation_id,
                        "operation": "delete_namespace",
                        "namespace_name": namespace_name,
                        "cronjobs_suspended": cronjobs_suspended,
                    },
                )

                k8s_client.delete_namespace(name=namespace_name)

                self.logger.info(
                    "Namespace deletion initiated successfully",
                    extra={
                        "correlation_id": self.correlation_id,
                        "operation": "delete_namespace",
                        "namespace_name": namespace_name,
                        "status": "deletion_initiated",
                    },
                )

                operation_duration = time.time() - operation_start_time
                return {
                    "deleted": True,
                    "namespace_name": namespace_name,
                    "cronjobs_suspended": cronjobs_suspended,
                    "duration_seconds": round(operation_duration, 2),
                }

            finally:
                # Clean up temporary file
                if os.path.exists(temp_kubeconfig_path):
                    os.unlink(temp_kubeconfig_path)

        except ApiException as e:
            operation_duration = time.time() - operation_start_time
            self.logger.error(
                "Kubernetes API error during namespace deletion",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_namespace",
                    "namespace_name": namespace_name,
                    "error_type": "k8s_api_error",
                    "error_status": e.status,
                    "error_reason": e.reason,
                    "error_message": str(e),
                    "duration_seconds": round(operation_duration, 2),
                },
            )
            raise
        except Exception as e:
            operation_duration = time.time() - operation_start_time
            self.logger.error(
                "Failed to delete namespace using Azure SDK",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "delete_namespace",
                    "namespace_name": namespace_name,
                    "error_type": "azure_sdk_error",
                    "error_class": type(e).__name__,
                    "error_message": str(e),
                    "duration_seconds": round(operation_duration, 2),
                },
            )
            raise

    def deprovision_environment(self, branch_name: str) -> dict[str, Any]:
        """Main deprovisioning method.

        Args:
            branch_name: Name of the branch to deprovision environment for

        Returns:
            Dictionary containing deprovisioning status and details

        Raises:
            Exception: If any deprovisioning step fails critically
        """
        operation_start_time = time.time()
        self.logger.info(
            "Starting environment deprovisioning workflow",
            extra={
                "correlation_id": self.correlation_id,
                "operation": "deprovision_environment",
                "branch_name": branch_name,
                "subscription_id": self.settings.azure_subscription_id,
                "postgres_server": self.settings.postgres_server_name,
                "database_identity": self.settings.database_identity_name,
                "keyvault_identity": self.settings.keyvault_identity_name,
                "aks_cluster": self.settings.aks_cluster_name,
            },
        )

        operations = {
            "database_deleted": False,
            "database_name": None,
            "credentials_deleted": {
                "database_credential": False,
                "keyvault_credential": False,
            },
            "namespace_deleted": False,
            "namespace_name": f"feature-{branch_name}",
            "cronjobs_suspended": 0,
        }

        timing = {}
        errors = []

        try:
            # Step 1: Delete Kubernetes namespace (with CronJob suspension)
            self.logger.info(
                "Step 1/3: Deleting Kubernetes namespace",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "deprovision_environment",
                    "branch_name": branch_name,
                    "step": "namespace_deletion",
                },
            )

            try:
                namespace_result = self.delete_namespace(f"feature-{branch_name}")
                operations["namespace_deleted"] = namespace_result["deleted"]
                operations["cronjobs_suspended"] = namespace_result["cronjobs_suspended"]
                timing["namespace_duration_seconds"] = namespace_result["duration_seconds"]

                self.logger.info(
                    "Namespace deletion completed",
                    extra={
                        "correlation_id": self.correlation_id,
                        "operation": "deprovision_environment",
                        "branch_name": branch_name,
                        "step": "namespace_deletion",
                        "duration_seconds": namespace_result["duration_seconds"],
                        "success": namespace_result["deleted"],
                        "cronjobs_suspended": namespace_result["cronjobs_suspended"],
                    },
                )
            except Exception as e:
                timing["namespace_duration_seconds"] = 0
                error_msg = f"Namespace deletion failed: {e}"
                errors.append({
                    "operation": "namespace_deletion",
                    "error": error_msg,
                    "severity": "critical",
                })
                self.logger.error(
                    "Namespace deletion failed",
                    extra={
                        "correlation_id": self.correlation_id,
                        "operation": "deprovision_environment",
                        "branch_name": branch_name,
                        "step": "namespace_deletion",
                        "error_message": str(e),
                    },
                )

            # Step 2: Delete federated credentials
            self.logger.info(
                "Step 2/3: Deleting federated credentials",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "deprovision_environment",
                    "branch_name": branch_name,
                    "step": "credentials_deletion",
                },
            )

            try:
                credentials_result = self.delete_federated_credentials(branch_name)
                operations["credentials_deleted"] = credentials_result["deleted"]
                timing["credentials_duration_seconds"] = credentials_result["duration_seconds"]

                # Add any credential deletion errors to the main errors list
                errors.extend(credentials_result["errors"])

                self.logger.info(
                    "Credentials deletion completed",
                    extra={
                        "correlation_id": self.correlation_id,
                        "operation": "deprovision_environment",
                        "branch_name": branch_name,
                        "step": "credentials_deletion",
                        "duration_seconds": credentials_result["duration_seconds"],
                        "database_credential_deleted": credentials_result["deleted"]["database_credential"],
                        "keyvault_credential_deleted": credentials_result["deleted"]["keyvault_credential"],
                        "errors_count": len(credentials_result["errors"]),
                    },
                )
            except Exception as e:
                timing["credentials_duration_seconds"] = 0
                error_msg = f"Credentials deletion failed: {e}"
                errors.append({
                    "operation": "credentials_deletion",
                    "error": error_msg,
                    "severity": "warning",
                })
                self.logger.error(
                    "Credentials deletion failed",
                    extra={
                        "correlation_id": self.correlation_id,
                        "operation": "deprovision_environment",
                        "branch_name": branch_name,
                        "step": "credentials_deletion",
                        "error_message": str(e),
                    },
                )

            # Step 3: Delete database
            self.logger.info(
                "Step 3/3: Deleting PostgreSQL database",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "deprovision_environment",
                    "branch_name": branch_name,
                    "step": "database_deletion",
                },
            )

            try:
                database_result = self.delete_database(branch_name)
                operations["database_deleted"] = database_result["deleted"]
                operations["database_name"] = database_result["database_name"]
                timing["database_duration_seconds"] = database_result["duration_seconds"]

                self.logger.info(
                    "Database deletion completed",
                    extra={
                        "correlation_id": self.correlation_id,
                        "operation": "deprovision_environment",
                        "branch_name": branch_name,
                        "step": "database_deletion",
                        "duration_seconds": database_result["duration_seconds"],
                        "success": database_result["deleted"],
                        "database_name": database_result["database_name"],
                    },
                )
            except Exception as e:
                timing["database_duration_seconds"] = 0
                error_msg = f"Database deletion failed: {e}"
                errors.append({
                    "operation": "database_deletion",
                    "error": error_msg,
                    "severity": "critical",
                })
                self.logger.error(
                    "Database deletion failed",
                    extra={
                        "correlation_id": self.correlation_id,
                        "operation": "deprovision_environment",
                        "branch_name": branch_name,
                        "step": "database_deletion",
                        "error_message": str(e),
                    },
                )

            # Build result
            total_duration = time.time() - operation_start_time
            timing["total_duration_seconds"] = round(total_duration, 2)

            # Determine overall status
            critical_errors = [e for e in errors if e.get("severity") == "critical"]
            if critical_errors:
                status = "error"
                message = f"Deprovisioning completed with {len(critical_errors)} critical error(s)"
            elif errors:
                status = "success"
                message = f"Deprovisioning completed with {len(errors)} warning(s)"
            else:
                status = "success"
                message = f"Environment for branch '{branch_name}' deprovisioned successfully"

            result = {
                "status": status,
                "branch_name": branch_name,
                "operations": operations,
                "timing": timing,
                "message": message,
            }

            if errors:
                result["errors"] = errors

            self.logger.info(
                "Environment deprovisioning workflow completed",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "deprovision_environment",
                    "branch_name": branch_name,
                    "total_duration_seconds": round(total_duration, 2),
                    "status": status,
                    "errors_count": len(errors),
                    "critical_errors_count": len(critical_errors),
                    "result": result,
                },
            )

        except Exception as e:
            total_duration = time.time() - operation_start_time
            error_msg = f"Deprovisioning failed for branch '{branch_name}': {e!s}"

            self.logger.error(
                "Environment deprovisioning workflow failed",
                extra={
                    "correlation_id": self.correlation_id,
                    "operation": "deprovision_environment",
                    "branch_name": branch_name,
                    "total_duration_seconds": round(total_duration, 2),
                    "error_type": "deprovisioning_failure",
                    "error_class": type(e).__name__,
                    "error_message": str(e),
                },
            )

            return {
                "status": "error",
                "branch_name": branch_name,
                "operations": operations,
                "message": error_msg,
                "timing": {
                    "total_duration_seconds": round(total_duration, 2),
                },
                "errors": [{
                    "operation": "deprovisioning_workflow",
                    "error": error_msg,
                    "severity": "critical",
                }],
            }
        else:
            return result
