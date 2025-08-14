"""Azure Function App entry point."""

import json
import logging
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
    logging.info("ProvisionEnvironment function started")

    try:
        # Parse request body
        req_body: dict[str, Any] = req.get_json()
        if not req_body:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Request body is required",
                }),
                status_code=400,
                headers={"Content-Type": "application/json"},
            )

        # Validate request
        try:
            provision_request = ProvisionRequest(**req_body)
        except Exception as e:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": f"Invalid request: {e!s}",
                }),
                status_code=400,
                headers={"Content-Type": "application/json"},
            )

        # Initialize services
        settings = Settings()
        provisioning_service = ProvisioningService(settings)

        # Provision environment
        result = provisioning_service.provision_environment(
            provision_request.branch_name,
        )

        # Return success response
        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            headers={"Content-Type": "application/json"},
        )

    except ValueError as e:
        logging.exception("Validation error: %s", e)
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": str(e),
            }),
            status_code=400,
            headers={"Content-Type": "application/json"},
        )

    except Exception:
        logging.exception("Unexpected error in ProvisionEnvironment function")
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": "Internal server error",
            }),
            status_code=500,
            headers={"Content-Type": "application/json"},
        )
