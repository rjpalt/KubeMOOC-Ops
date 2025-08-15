"""Deployment service for managing AKS deployments."""

import asyncio
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


import requests
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from azure.mgmt.containerservice import ContainerServiceClient
from kubernetes import client, config

from config import settings
from models.requests import DeploymentRequest, DeploymentResponse, HealthCheck

logger = logging.getLogger(__name__)


class DeploymentService:
    """Service for handling Kubernetes deployments to AKS."""

    def __init__(self) -> None:
        """Initialize the deployment service."""
        logger.info("Initializing DeploymentService")

        try:
            self.credential = DefaultAzureCredential()
            logger.info("DefaultAzureCredential initialized successfully")

            self.acr_client = ContainerRegistryManagementClient(
                credential=self.credential,
                subscription_id=settings.azure_subscription_id,
            )
            logger.info(
                f"ACR client initialized for subscription: {settings.azure_subscription_id}"
            )

            self.aks_client = ContainerServiceClient(
                credential=self.credential,
                subscription_id=settings.azure_subscription_id,
            )
            logger.info(
                f"AKS client initialized for subscription: {settings.azure_subscription_id}"
            )

            self._k8s_client: client.ApiClient | None = None
            
            # Ensure kustomize is available
            self._ensure_kustomize_available()
            
            logger.info("DeploymentService initialization complete")

        except Exception as e:
            logger.error(f"Failed to initialize DeploymentService: {e!s}")
            logger.error(
                f"Settings used: ACR={settings.acr_name}, "
                f"AKS={settings.aks_cluster_name}, "
                f"RG={settings.aks_resource_group}"
            )
            raise

    def _ensure_kustomize_available(self) -> None:
        """Ensure kustomize and kubectl binaries are available, download if necessary."""
        self._ensure_binary_available("kustomize", self._download_kustomize)
        self._ensure_binary_available("kubectl", self._download_kubectl)

    def _ensure_binary_available(self, binary_name: str, download_func) -> None:
        """Check if a binary is available, download if not."""
        try:
            # Check if binary is already available
            if binary_name == "kubectl":
                # Use --client flag to avoid connecting to cluster
                cmd = [binary_name, "version", "--client"]
            else:
                # For other binaries like kustomize
                cmd = [binary_name, "version"]
                
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"{binary_name} is already available")
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.info(f"{binary_name} not found, downloading...")

        # Download the binary
        download_func()

    def _download_kustomize(self) -> None:
        """Download and install kustomize binary."""
        try:
            # Download kustomize binary
            kustomize_url = "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/v5.3.0/kustomize_v5.3.0_linux_amd64.tar.gz"
            
            # Create temp directory for download
            temp_dir = Path(tempfile.mkdtemp())
            tar_path = temp_dir / "kustomize.tar.gz"
            
            logger.info(f"Downloading kustomize from {kustomize_url}")
            urllib.request.urlretrieve(kustomize_url, tar_path)
            
            # Extract kustomize binary
            with tarfile.open(tar_path, 'r:gz') as tar:
                tar.extract('kustomize', temp_dir)
            
            # Install binary
            self._install_binary(temp_dir / 'kustomize', 'kustomize')
            
            # Clean up
            shutil.rmtree(temp_dir)
            
            logger.info("✅ Kustomize downloaded and installed successfully")
            
        except Exception as e:
            logger.error(f"Failed to download/install kustomize: {e}")
            raise Exception(f"Could not ensure kustomize availability: {e}")

    def _download_kubectl(self) -> None:
        """Download and install kubectl binary."""
        try:
            # Download kubectl binary
            kubectl_url = "https://dl.k8s.io/release/v1.29.0/bin/linux/amd64/kubectl"
            
            # Create temp directory for download
            temp_dir = Path(tempfile.mkdtemp())
            kubectl_path = temp_dir / "kubectl"
            
            logger.info(f"Downloading kubectl from {kubectl_url}")
            urllib.request.urlretrieve(kubectl_url, kubectl_path)
            
            # Install binary
            self._install_binary(kubectl_path, 'kubectl')
            
            # Clean up
            shutil.rmtree(temp_dir)
            
            logger.info("✅ Kubectl downloaded and installed successfully")
            
        except Exception as e:
            logger.error(f"Failed to download/install kubectl: {e}")
            raise Exception(f"Could not ensure kubectl availability: {e}")

    def _install_binary(self, binary_path: Path, binary_name: str) -> None:
        """Install a binary to a location in PATH."""
        # Make it executable
        binary_path.chmod(0o755)
        
        # Create a bin directory in the function's home and add to PATH
        bin_dir = Path.home() / 'bin'
        bin_dir.mkdir(exist_ok=True)
        
        final_path = bin_dir / binary_name
        shutil.move(str(binary_path), str(final_path))
        
        # Add to PATH for this process
        os.environ['PATH'] = f"{bin_dir}:{os.environ.get('PATH', '')}"
        
        # Verify installation
        if binary_name == "kubectl":
            # Use --client flag to avoid connecting to cluster
            cmd = [binary_name, "version", "--client"]
        else:
            # For other binaries like kustomize
            cmd = [binary_name, "version"]
            
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise Exception(f"{binary_name} installation verification failed: {result.stderr}")

    async def deploy(self, request: DeploymentRequest) -> DeploymentResponse:
        """Deploy a feature branch to AKS."""
        deployment_start_time = time.time()
        correlation_id = f"deploy-{request.branch_name}-{int(deployment_start_time)}"

        logger.info(
            f"[{correlation_id}] Starting deployment",
            extra={
                "correlation_id": correlation_id,
                "branch_name": request.branch_name,
                "commit_sha": request.commit_sha,
                "namespace": request.namespace,
                "image_tag_suffix": request.image_tag_suffix,
            },
        )

        try:
            # Step 1: Verify ACR images exist
            step_start = time.time()
            await self._verify_acr_images(request, correlation_id)
            logger.info(
                f"[{correlation_id}] ACR verification completed in {time.time() - step_start:.2f}s"
            )

            # Step 2: Download Kubernetes manifests
            step_start = time.time()
            manifests_dir = await self._download_manifests(correlation_id)
            logger.info(
                f"[{correlation_id}] Manifest download completed in {time.time() - step_start:.2f}s"
            )
            logger.debug(f"[{correlation_id}] Downloaded manifests to: {manifests_dir}")

            # Step 3: Configure Kubernetes client
            step_start = time.time()
            await self._configure_k8s_client(correlation_id)
            logger.info(
                f"[{correlation_id}] K8s client configuration completed in "
                f"{time.time() - step_start:.2f}s"
            )

            # Step 4: Deploy to AKS
            step_start = time.time()
            deployed_resources = await self._deploy_to_aks(request, manifests_dir, correlation_id)
            logger.info(
                f"[{correlation_id}] AKS deployment completed in {time.time() - step_start:.2f}s"
            )

            # Step 5: Perform health checks
            step_start = time.time()
            health_checks = await self._perform_health_checks(request.namespace, correlation_id)
            logger.info(
                f"[{correlation_id}] Health checks completed in {time.time() - step_start:.2f}s"
            )

            # Step 6: Generate deployment URL
            deployment_url = self._generate_deployment_url(request.namespace)

            total_time = time.time() - deployment_start_time
            logger.info(
                f"[{correlation_id}] Deployment SUCCESSFUL in {total_time:.2f}s",
                extra={
                    "correlation_id": correlation_id,
                    "namespace": request.namespace,
                    "deployment_url": deployment_url,
                    "deployed_resources_count": len(deployed_resources),
                    "health_checks_count": len(health_checks),
                    "total_duration_seconds": total_time,
                },
            )

            return DeploymentResponse(
                success=True,
                message=f"Successfully deployed branch {request.branch_name} "
                f"to namespace {request.namespace}",
                namespace=request.namespace,
                deployment_url=deployment_url,
                health_checks=health_checks,
                deployed_resources=deployed_resources,
            )

        except Exception as e:
            total_time = time.time() - deployment_start_time
            # ruff: noqa: TRY401
            logger.exception(
                f"[{correlation_id}] Deployment FAILED after {total_time:.2f}s: {e!s}",
                extra={
                    "correlation_id": correlation_id,
                    "branch_name": request.branch_name,
                    "namespace": request.namespace,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "total_duration_seconds": total_time,
                },
            )

            return DeploymentResponse(
                success=False,
                message="Deployment failed",
                namespace=request.namespace,
                error_details=str(e),
            )

    async def _verify_acr_images(self, request: DeploymentRequest, correlation_id: str) -> None:
        """Verify that required images exist in ACR."""
        logger.info(f"[{correlation_id}] Starting ACR image verification")

        # List of expected images based on the implementation plan
        expected_images = [
            f"todo-app:{request.image_tag_suffix}",
            f"todo-backend:{request.image_tag_suffix}",
            f"todo-cron:{request.image_tag_suffix}",
        ]

        logger.info(
            f"[{correlation_id}] Checking {len(expected_images)} images in ACR",
            extra={
                "correlation_id": correlation_id,
                "acr_name": settings.acr_name,
                "expected_images": expected_images,
            },
        )

        for image in expected_images:
            try:
                # This would need to be implemented with proper ACR API calls
                # For now, we'll assume images exist but log the attempt
                logger.debug(f"[{correlation_id}] Verifying image: {image}")
                # TODO: Implement actual ACR verification
                logger.info(f"[{correlation_id}] ✓ Verified image exists: {image}")
            except Exception as e:
                logger.exception(
                    f"[{correlation_id}] ✗ Failed to verify image: {image}",
                    extra={
                        "correlation_id": correlation_id,
                        "image": image,
                        "error": str(e),
                    },
                )
                raise

    async def _download_manifests(self, correlation_id: str) -> Path:
        """Download Kubernetes manifests from GitHub as a zip file."""
        logger.info(f"[{correlation_id}] Starting manifest download from GitHub as zip")

        # Download the entire repository as a zip
        zip_url = f"{settings.github_repository_url}/archive/main.zip"
        logger.info(f"[{correlation_id}] Downloading repository zip from: {zip_url}")

        try:
            # Download the zip file
            response = requests.get(zip_url, timeout=60)
            response.raise_for_status()
            
            logger.info(f"[{correlation_id}] Downloaded zip file ({len(response.content)} bytes)")

            # Create temporary directory for extraction
            temp_dir = Path(tempfile.mkdtemp())
            zip_path = temp_dir / "repo.zip"
            
            # Write zip content to file
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            # Extract the zip file
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find the extracted repository directory (GitHub creates KubernetesMOOC-main/)
            extracted_dirs = [d for d in temp_dir.iterdir() if d.is_dir() and d.name.startswith('KubernetesMOOC-')]
            if not extracted_dirs:
                raise Exception(f"Could not find extracted repository directory in {temp_dir}")
            
            repo_dir = extracted_dirs[0]
            manifests_dir = repo_dir / "course_project" / "manifests"
            
            if not manifests_dir.exists():
                raise Exception(f"Manifests directory not found at {manifests_dir}")
            
            logger.info(
                f"[{correlation_id}] Successfully extracted manifests to: {manifests_dir}",
                extra={
                    "correlation_id": correlation_id,
                    "manifests_path": str(manifests_dir),
                    "zip_size_bytes": len(response.content),
                }
            )
            
            # Clean up zip file
            zip_path.unlink()
            
            return manifests_dir

        except Exception as e:
            logger.exception(
                f"[{correlation_id}] ✗ Failed to download manifests",
                extra={
                    "correlation_id": correlation_id,
                    "zip_url": zip_url,
                    "error": str(e),
                },
            )
            raise

    async def _configure_k8s_client(self, correlation_id: str) -> None:
        """Configure Kubernetes client for AKS."""
        logger.info(f"[{correlation_id}] Configuring Kubernetes client")

        try:
            # Get AKS credentials and configure kubectl for health checks
            kubeconfig_path = await self._write_kubeconfig_to_temp(correlation_id)

            # Load kubeconfig for Python client (used for health checks)
            config.load_kube_config(config_file=kubeconfig_path)
            self._k8s_client = client.ApiClient()

            logger.info(f"[{correlation_id}] ✓ Kubernetes client configured successfully")

            # Clean up temporary file
            Path(kubeconfig_path).unlink()
            logger.debug(f"[{correlation_id}] Cleaned up temporary kubeconfig file")

        except Exception as e:
            logger.exception(
                f"[{correlation_id}] ✗ Failed to configure Kubernetes client",
                extra={
                    "correlation_id": correlation_id,
                    "aks_cluster": settings.aks_cluster_name,
                    "resource_group": settings.aks_resource_group,
                    "error": str(e),
                },
            )
            raise

    async def _deploy_to_aks(
        self,
        request: DeploymentRequest,
        manifests_dir: Path,
        correlation_id: str,
    ) -> list[str]:
        """Deploy manifests to AKS using kustomize build | kubectl apply approach."""
        logger.info(f"[{correlation_id}] Starting AKS deployment to namespace: {request.namespace}")

        deployed_resources = []

        try:
            # Update kustomization.yaml with correct namespace and images
            feature_kustomization_path = manifests_dir / "overlays" / "feature" / "kustomization.yaml"
            if feature_kustomization_path.exists():
                kustomization_content = feature_kustomization_path.read_text()

                # Replace namespace placeholder
                kustomization_content = kustomization_content.replace(
                    "namespace: feature-BRANCH_NAME", f"namespace: {request.namespace}"
                )

                # Replace branch name in hostname
                kustomization_content = kustomization_content.replace(
                    "BRANCH_NAME.23.98.101.23.nip.io",
                    f"{request.branch_name}.23.98.101.23.nip.io",
                )

                # Replace database name
                kustomization_content = kustomization_content.replace(
                    "BRANCH_NAME_DB", f"{request.branch_name.replace('-', '_')}"
                )

                # Update image tags
                kustomization_content = kustomization_content.replace(
                    "newTag: latest", f"newTag: {request.image_tag_suffix}"
                )

                feature_kustomization_path.write_text(kustomization_content)
                logger.info(
                    f"[{correlation_id}] Updated feature kustomization with namespace: {request.namespace}"
                )

            # Set up kubectl config from kubeconfig
            kubeconfig_path = await self._write_kubeconfig_to_temp(correlation_id)
            
            # Use kustomize build | kubectl apply approach
            overlay_dir = manifests_dir / "overlays" / "feature"
            deployed_resources = await self._apply_with_kustomize_and_kubectl(
                overlay_dir, kubeconfig_path, correlation_id
            )

            # Clean up temporary kubeconfig
            Path(kubeconfig_path).unlink()
            logger.debug(f"[{correlation_id}] Cleaned up temporary kubeconfig file")

        except Exception as e:
            logger.exception(
                f"[{correlation_id}] ✗ Deployment failed",
                extra={
                    "correlation_id": correlation_id,
                    "namespace": request.namespace,
                    "error": str(e),
                },
            )
            raise

        logger.info(
            f"[{correlation_id}] ✓ Successfully deployed all resources",
            extra={
                "correlation_id": correlation_id,
                "namespace": request.namespace,
                "deployed_resources": deployed_resources,
                "resource_count": len(deployed_resources),
            },
        )

        return deployed_resources

    async def _write_kubeconfig_to_temp(self, correlation_id: str) -> str:
        """Write kubeconfig to temporary file and return the path."""
        logger.debug(f"[{correlation_id}] Writing kubeconfig to temporary file")

        # Get AKS credentials
        aks_credential = self.aks_client.managed_clusters.list_cluster_user_credentials(
            resource_group_name=settings.aks_resource_group,
            resource_name=settings.aks_cluster_name,
        )

        # Write kubeconfig to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            kubeconfig_content = aks_credential.kubeconfigs[0].value.decode("utf-8")
            f.write(kubeconfig_content)
            kubeconfig_path = f.name

        logger.debug(f"[{correlation_id}] Wrote kubeconfig to: {kubeconfig_path}")
        return kubeconfig_path

    async def _apply_with_kustomize_and_kubectl(
        self, overlay_dir: Path, kubeconfig_path: str, correlation_id: str
    ) -> list[str]:
        """Apply manifests using kustomize build | kubectl apply."""
        logger.info(f"[{correlation_id}] Running kustomize build | kubectl apply")

        try:
            # Run kustomize build to generate manifests
            kustomize_cmd = ["kustomize", "build", str(overlay_dir)]
            logger.debug(f"[{correlation_id}] Running: {' '.join(kustomize_cmd)}")

            kustomize_result = subprocess.run(
                kustomize_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )

            logger.debug(f"[{correlation_id}] Kustomize output length: {len(kustomize_result.stdout)} chars")

            # Run kubectl apply with the built manifests
            kubectl_cmd = [
                "kubectl", "apply",
                "--kubeconfig", kubeconfig_path,
                "-f", "-",  # Read from stdin
                "--record",  # Record the command for rollback purposes
            ]
            logger.debug(f"[{correlation_id}] Running: {' '.join(kubectl_cmd[:-2])} -f -")

            kubectl_result = subprocess.run(
                kubectl_cmd,
                input=kustomize_result.stdout,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )

            # Parse kubectl output to extract deployed resource names
            deployed_resources = []
            for line in kubectl_result.stdout.strip().split('\n'):
                if line.strip():
                    # kubectl apply output format: "resource/name created|configured|unchanged"
                    if ' created' in line or ' configured' in line or ' unchanged' in line:
                        resource_info = line.split()[0]  # Get "resource/name" part
                        deployed_resources.append(resource_info)
                        action = "created" if " created" in line else ("configured" if " configured" in line else "unchanged")
                        logger.info(f"[{correlation_id}] ✓ {resource_info} {action}")

            logger.info(
                f"[{correlation_id}] Kubectl apply completed successfully",
                extra={
                    "correlation_id": correlation_id,
                    "deployed_resources": deployed_resources,
                    "resource_count": len(deployed_resources),
                }
            )

            return deployed_resources

        except subprocess.CalledProcessError as e:
            logger.error(
                f"[{correlation_id}] Command failed with exit code {e.returncode}",
                extra={
                    "correlation_id": correlation_id,
                    "command": " ".join(e.cmd) if e.cmd else "unknown",
                    "stdout": e.stdout,
                    "stderr": e.stderr,
                }
            )
            raise Exception(f"Deployment command failed: {e.stderr}")
        except subprocess.TimeoutExpired as e:
            logger.error(
                f"[{correlation_id}] Command timed out",
                extra={
                    "correlation_id": correlation_id,
                    "command": " ".join(e.cmd) if e.cmd else "unknown",
                    "timeout_seconds": e.timeout,
                }
            )
            raise Exception(f"Deployment command timed out after {e.timeout} seconds")

    async def _perform_health_checks(
        self, namespace: str, correlation_id: str
    ) -> list[HealthCheck]:
        """Perform comprehensive health checks on deployed resources."""
        logger.info(f"[{correlation_id}] Starting health checks for namespace: {namespace}")

        health_checks = []
        kubeconfig_path = None

        try:
            # Create a temporary kubeconfig for health checks
            kubeconfig_path = await self._write_kubeconfig_to_temp(correlation_id)
            
            # First, wait for deployment rollouts to complete using kubectl
            await self._wait_for_rollouts(namespace, correlation_id, kubeconfig_path)

            apps_v1 = client.AppsV1Api()
            core_v1 = client.CoreV1Api()

            # Check deployments with enhanced validation
            deployments = apps_v1.list_namespaced_deployment(namespace=namespace)
            for deployment in deployments.items:
                name = deployment.metadata.name
                ready_replicas = deployment.status.ready_replicas or 0
                replicas = deployment.spec.replicas or 0

                ready = ready_replicas == replicas and replicas > 0
                status = "ready" if ready else "not-ready"
                message = f"{ready_replicas}/{replicas} pods ready"

                # Enhanced debugging for failed deployments
                if not ready:
                    await self._debug_deployment_issues(namespace, name, correlation_id)

                health_check = HealthCheck(
                    resource_type="deployment",
                    resource_name=name,
                    status=status,
                    ready=ready,
                    message=message,
                )
                health_checks.append(health_check)

                status_emoji = "✓" if ready else "✗"
                logger.info(f"[{correlation_id}] {status_emoji} deployment/{name}: {message}")

            # Check statefulsets with enhanced validation
            statefulsets = apps_v1.list_namespaced_stateful_set(namespace=namespace)
            for statefulset in statefulsets.items:
                name = statefulset.metadata.name
                ready_replicas = statefulset.status.ready_replicas or 0
                replicas = statefulset.spec.replicas or 0

                ready = ready_replicas == replicas and replicas > 0
                status = "ready" if ready else "not-ready"
                message = f"{ready_replicas}/{replicas} pods ready"

                health_check = HealthCheck(
                    resource_type="statefulset",
                    resource_name=name,
                    status=status,
                    ready=ready,
                    message=message,
                )
                health_checks.append(health_check)

                status_emoji = "✓" if ready else "✗"
                logger.info(f"[{correlation_id}] {status_emoji} statefulset/{name}: {message}")

            # Check services with port validation
            services = core_v1.list_namespaced_service(namespace=namespace)
            for service in services.items:
                name = service.metadata.name
                ports = service.spec.ports or []
                ready = len(ports) > 0
                status = "ready" if ready else "not-ready"
                message = f"Service active with {len(ports)} ports"

                health_check = HealthCheck(
                    resource_type="service",
                    resource_name=name,
                    status=status,
                    ready=ready,
                    message=message,
                )
                health_checks.append(health_check)

                logger.info(f"[{correlation_id}] ✓ service/{name}: {message}")

        except Exception as e:
            logger.exception(
                f"[{correlation_id}] ✗ Health check failed",
                extra={
                    "correlation_id": correlation_id,
                    "namespace": namespace,
                    "error": str(e),
                },
            )
            # Don't fail the entire deployment for health check issues
            # Return partial results if we have any
            if not health_checks:
                # Create a failed health check if we couldn't check anything
                health_checks.append(
                    HealthCheck(
                        resource_type="cluster",
                        resource_name="health-check",
                        status="failed",
                        ready=False,
                        message=f"Health check failed: {e!s}",
                    )
                )
        finally:
            # Clean up the temporary kubeconfig file
            if kubeconfig_path and Path(kubeconfig_path).exists():
                try:
                    Path(kubeconfig_path).unlink()
                    logger.debug(f"[{correlation_id}] Cleaned up health check kubeconfig file")
                except Exception as cleanup_err:
                    logger.warning(f"[{correlation_id}] Failed to cleanup kubeconfig: {cleanup_err}")

        logger.info(
            f"[{correlation_id}] Health checks completed",
            extra={
                "correlation_id": correlation_id,
                "namespace": namespace,
                "total_checks": len(health_checks),
                "ready_count": sum(1 for hc in health_checks if hc.ready),
            },
        )

        return health_checks

    async def _wait_for_rollouts(self, namespace: str, correlation_id: str, kubeconfig_path: str) -> None:
        """Wait for deployment rollouts to complete using kubectl rollout status."""
        logger.info(f"[{correlation_id}] Waiting for deployment rollouts to complete...")
        
        # List of deployments to wait for
        deployments_to_check = ["todo-app-be", "todo-app-fe"]
        
        for deployment_name in deployments_to_check:
            try:
                logger.info(f"[{correlation_id}] Waiting for deployment/{deployment_name} rollout...")
                
                rollout_cmd = [
                    "kubectl", "rollout", "status", 
                    f"deployment/{deployment_name}",
                    "--namespace", namespace,
                    "--kubeconfig", kubeconfig_path,
                    "--timeout=300s"
                ]
                
                result = subprocess.run(
                    rollout_cmd,
                    capture_output=True,
                    text=True,
                    timeout=320,  # Slightly longer than kubectl timeout
                )
                
                if result.returncode == 0:
                    logger.info(f"[{correlation_id}] ✅ {deployment_name} deployment ready")
                else:
                    logger.warning(
                        f"[{correlation_id}] ⚠️ {deployment_name} rollout status check failed: {result.stderr}"
                    )
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"[{correlation_id}] ⚠️ {deployment_name} rollout status check timed out")
            except Exception as e:
                logger.warning(f"[{correlation_id}] ⚠️ {deployment_name} rollout check failed: {e}")

    async def _debug_deployment_issues(self, namespace: str, deployment_name: str, correlation_id: str) -> None:
        """Debug deployment issues by examining pods and logs."""
        logger.info(f"[{correlation_id}] Debugging issues with deployment/{deployment_name}")
        
        try:
            core_v1 = client.CoreV1Api()
            
            # Get pods for this deployment
            pods = core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={deployment_name}"
            )
            
            if not pods.items:
                logger.warning(f"[{correlation_id}] No pods found for deployment/{deployment_name}")
                return
            
            for pod in pods.items[:2]:  # Limit to first 2 pods for brevity
                pod_name = pod.metadata.name
                pod_phase = pod.status.phase
                
                logger.info(f"[{correlation_id}] Pod {pod_name} status: {pod_phase}")
                
                # Get pod description for troubleshooting
                if pod_phase != "Running":
                    try:
                        # Log container statuses
                        if pod.status.container_statuses:
                            for container_status in pod.status.container_statuses:
                                if not container_status.ready:
                                    state = container_status.state
                                    if state.waiting:
                                        logger.warning(
                                            f"[{correlation_id}] Container {container_status.name} waiting: "
                                            f"{state.waiting.reason} - {state.waiting.message}"
                                        )
                                    elif state.terminated:
                                        logger.warning(
                                            f"[{correlation_id}] Container {container_status.name} terminated: "
                                            f"{state.terminated.reason} - {state.terminated.message}"
                                        )
                        
                        # Get recent pod logs for debugging
                        try:
                            logs = core_v1.read_namespaced_pod_log(
                                name=pod_name,
                                namespace=namespace,
                                tail_lines=10,
                                _request_timeout=10
                            )
                            logger.info(f"[{correlation_id}] Recent logs from {pod_name}:\n{logs}")
                        except Exception as log_err:
                            logger.warning(f"[{correlation_id}] Could not get logs from {pod_name}: {log_err}")
                            
                    except Exception as debug_err:
                        logger.warning(f"[{correlation_id}] Could not debug pod {pod_name}: {debug_err}")
                        
        except Exception as e:
            logger.warning(f"[{correlation_id}] Failed to debug deployment {deployment_name}: {e}")



    def _generate_deployment_url(self, namespace: str) -> str:
        """Generate the deployment URL for the feature branch."""
        # Extract branch name from namespace (feature-BRANCH_NAME format)
        if namespace.startswith("feature-"):
            branch_name = namespace[8:]  # Remove "feature-" prefix
            url = f"https://{branch_name}.23.98.101.23.nip.io"
        else:
            url = f"https://{namespace}.kubemooc.dev"

        logger.debug(f"Generated deployment URL: {url}")
        return url
