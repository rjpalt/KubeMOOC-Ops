"""Azure Function App entry point."""

import json
import logging
import time
import uuid
from typing import Any

import azure.functions as func
from azure.identity import DefaultAzureCredential

from config import Settings
from models.requests import ProvisionRequest
from services.provisioning_service import ProvisioningService

# Initialize the function app
app = func.FunctionApp()


@app.route(route="provision", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def provision_environment(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function entry point for environment provisioning.

    Args:
        req: HTTP request object containing the branch name to provision

    Returns:
        HTTP response with provisioning status

    Raises:
        ValueError: If request validation fails
        Exception: For any other provisioning errors
    """
    # Generate correlation ID for request tracking
    correlation_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Configure logging with correlation ID
    logger = logging.getLogger(__name__)
    logger.info(
        "ProvisionEnvironment function started",
        extra={
            "correlation_id": correlation_id,
            "function_name": "provision_environment",
            "request_method": req.method,
            "request_url": req.url,
            "user_agent": req.headers.get("User-Agent", "Unknown"),
            "content_type": req.headers.get("Content-Type", "Unknown")
        }
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
                    "status_code": 400
                }
            )
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Request body is required",
                    "correlation_id": correlation_id
                }),
                status_code=400,
                headers={"Content-Type": "application/json"},
            )

        logger.info(
            "Request body parsed successfully",
            extra={
                "correlation_id": correlation_id,
                "request_keys": list(req_body.keys())
            }
        )

        # Validate request
        try:
            provision_request = ProvisionRequest(**req_body)
            logger.info(
                "Request validation successful",
                extra={
                    "correlation_id": correlation_id,
                    "branch_name": provision_request.branch_name,
                    "branch_name_length": len(provision_request.branch_name)
                }
            )
        except Exception as e:
            logger.error(
                "Request validation failed",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": "validation_error",
                    "error_message": str(e),
                    "request_body": req_body,
                    "status_code": 400
                }
            )
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": f"Invalid request: {e!s}",
                    "correlation_id": correlation_id
                }),
                status_code=400,
                headers={"Content-Type": "application/json"},
            )

        # Initialize services
        logger.info(
            "Initializing Azure services",
            extra={
                "correlation_id": correlation_id,
                "branch_name": provision_request.branch_name
            }
        )
        
        settings = Settings()
        provisioning_service = ProvisioningService(settings)
        
        logger.info(
            "Azure services initialized, starting provisioning",
            extra={
                "correlation_id": correlation_id,
                "branch_name": provision_request.branch_name,
                "azure_subscription": settings.azure_subscription_id,
                "postgres_server": settings.postgres_server_name,
                "aks_cluster": settings.aks_cluster_name
            }
        )

        # Provision environment
        provisioning_start_time = time.time()
        result = provisioning_service.provision_environment(
            provision_request.branch_name,
        )
        provisioning_duration = time.time() - provisioning_start_time
        
        # Log provisioning results
        if result.get("status") == "success":
            logger.info(
                "Environment provisioning completed successfully",
                extra={
                    "correlation_id": correlation_id,
                    "branch_name": provision_request.branch_name,
                    "provisioning_duration_seconds": round(provisioning_duration, 2),
                    "database_created": result.get("database_created", False),
                    "credential_created": result.get("credential_created", False),
                    "namespace_created": result.get("namespace_created", False),
                    "total_duration_seconds": round(time.time() - start_time, 2)
                }
            )
        else:
            logger.error(
                "Environment provisioning failed",
                extra={
                    "correlation_id": correlation_id,
                    "branch_name": provision_request.branch_name,
                    "provisioning_duration_seconds": round(provisioning_duration, 2),
                    "error_message": result.get("error", "Unknown error"),
                    "total_duration_seconds": round(time.time() - start_time, 2)
                }
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
                "status_code": 400
            }
        )
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": str(e),
                "correlation_id": correlation_id
            }),
            status_code=400,
            headers={"Content-Type": "application/json"},
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.exception(
            "Unexpected error in ProvisionEnvironment function",
            extra={
                "correlation_id": correlation_id,
                "error_type": "unexpected_error",
                "error_class": type(e).__name__,
                "error_message": str(e),
                "duration_seconds": round(duration, 2),
                "status_code": 500
            }
        )
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": "Internal server error",
                "correlation_id": correlation_id
            }),
            status_code=500,
            headers={"Content-Type": "application/json"},
        )
