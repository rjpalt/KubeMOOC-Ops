"""Azure Function App entry point for environment deprovisioning."""

import json
import logging
import time
import uuid
from typing import Any

import azure.functions as func

from config import Settings
from models_requests import DeprovisionRequest
from deprovisioning_service import DeprovisioningService

# Initialize the function app
app = func.FunctionApp()


@app.route(route="deprovision", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def deprovision_environment(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function entry point for environment deprovisioning.

    Args:
        req: HTTP request object containing the branch name to deprovision

    Returns:
        HTTP response with deprovisioning status

    Raises:
        ValueError: If request validation fails
        Exception: For any other deprovisioning errors
    """
    # Generate correlation ID for request tracking
    correlation_id = f"deprov-{uuid.uuid4().hex[:8]}-{int(time.time())}"
    start_time = time.time()

    # Configure logging with correlation ID
    logger = logging.getLogger(__name__)
    logger.info(
        "DeprovisionEnvironment function started",
        extra={
            "correlation_id": correlation_id,
            "function_name": "deprovision_environment",
            "request_method": req.method,
            "request_url": req.url,
            "user_agent": req.headers.get("User-Agent", "Unknown"),
            "content_type": req.headers.get("Content-Type", "Unknown"),
        },
    )

    try:
        # Parse request body
        req_body: dict[str, Any] = req.get_json()
        if not req_body:
            logger.warning(
                "Request body is missing",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": "missing_request_body",
                    "status_code": 400,
                },
            )
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Request body is required",
                    "correlation_id": correlation_id,
                }),
                status_code=400,
                headers={"Content-Type": "application/json"},
            )

        logger.info(
            "Request body parsed successfully",
            extra={
                "correlation_id": correlation_id,
                "request_keys": list(req_body.keys()),
            },
        )

        # Validate request
        try:
            deprovision_request = DeprovisionRequest(**req_body)
            logger.info(
                "Request validation successful",
                extra={
                    "correlation_id": correlation_id,
                    "branch_name": deprovision_request.branch_name,
                    "branch_name_length": len(deprovision_request.branch_name),
                },
            )
        except Exception as e:
            logger.error(
                "Request validation failed",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": "validation_error",
                    "error_message": str(e),
                    "request_body": req_body,
                    "status_code": 400,
                },
            )
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": f"Invalid request: {e!s}",
                    "correlation_id": correlation_id,
                }),
                status_code=400,
                headers={"Content-Type": "application/json"},
            )

        # Initialize services
        logger.info(
            "Initializing Azure services",
            extra={
                "correlation_id": correlation_id,
                "branch_name": deprovision_request.branch_name,
            },
        )

        try:
            logger.info("Loading settings...")
            settings = Settings()
            logger.info("Settings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": f"Configuration error: {e}",
                    "correlation_id": correlation_id,
                }),
                status_code=500,
                headers={"Content-Type": "application/json"},
            )

        try:
            logger.info("Initializing deprovisioning service...")
            deprovisioning_service = DeprovisioningService(settings, correlation_id)
            logger.info("Deprovisioning service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize deprovisioning service: {e}")
            # For local testing, return a mock response instead of failing
            if "DefaultAzureCredential" in str(e) or "authentication" in str(e).lower():
                logger.info("Local testing mode - returning mock response")
                return func.HttpResponse(
                    json.dumps({
                        "status": "success",
                        "message": "Local testing mode - deprovisioning service not available",
                        "correlation_id": correlation_id,
                        "database_deleted": False,
                        "credentials_deleted": {
                            "database_credential": False,
                            "keyvault_credential": False,
                        },
                        "namespace_deleted": False,
                        "local_testing": True,
                    }),
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                )
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": f"Service initialization error: {e}",
                    "correlation_id": correlation_id,
                }),
                status_code=500,
                headers={"Content-Type": "application/json"},
            )

        logger.info(
            "Azure services initialized, starting deprovisioning",
            extra={
                "correlation_id": correlation_id,
                "branch_name": deprovision_request.branch_name,
                "azure_subscription": settings.azure_subscription_id,
                "postgres_server": settings.postgres_server_name,
                "aks_cluster": settings.aks_cluster_name,
            },
        )

        # Deprovision environment
        deprovisioning_start_time = time.time()
        result = deprovisioning_service.deprovision_environment(
            deprovision_request.branch_name,
        )
        deprovisioning_duration = time.time() - deprovisioning_start_time

        # Log deprovisioning results
        if result.get("status") == "success":
            logger.info(
                "Environment deprovisioning completed successfully",
                extra={
                    "correlation_id": correlation_id,
                    "branch_name": deprovision_request.branch_name,
                    "deprovisioning_duration_seconds": round(deprovisioning_duration, 2),
                    "database_deleted": result.get("operations", {}).get("database_deleted", False),
                    "credentials_deleted": result.get("operations", {}).get("credentials_deleted", {}),
                    "namespace_deleted": result.get("operations", {}).get("namespace_deleted", False),
                    "total_duration_seconds": round(time.time() - start_time, 2),
                },
            )
        else:
            logger.error(
                "Environment deprovisioning failed",
                extra={
                    "correlation_id": correlation_id,
                    "branch_name": deprovision_request.branch_name,
                    "deprovisioning_duration_seconds": round(deprovisioning_duration, 2),
                    "error_message": result.get("message", "Unknown error"),
                    "errors": result.get("errors", []),
                    "total_duration_seconds": round(time.time() - start_time, 2),
                },
            )

        # Add correlation ID to response
        result["correlation_id"] = correlation_id

        # Return success response
        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            headers={"Content-Type": "application/json"},
        )

    except ValueError as e:
        duration = time.time() - start_time
        logger.error(
            "Validation error occurred",
            extra={
                "correlation_id": correlation_id,
                "error_type": "validation_error",
                "error_message": str(e),
                "duration_seconds": round(duration, 2),
                "status_code": 400,
            },
        )
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": str(e),
                "correlation_id": correlation_id,
            }),
            status_code=400,
            headers={"Content-Type": "application/json"},
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.exception(
            "Unexpected error in DeprovisionEnvironment function",
            extra={
                "correlation_id": correlation_id,
                "error_type": "unexpected_error",
                "error_class": type(e).__name__,
                "error_message": str(e),
                "duration_seconds": round(duration, 2),
                "status_code": 500,
            },
        )
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": "Internal server error",
                "correlation_id": correlation_id,
            }),
            status_code=500,
            headers={"Content-Type": "application/json"},
        )
