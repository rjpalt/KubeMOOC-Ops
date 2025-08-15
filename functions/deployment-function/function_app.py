"""Azure Function App for deployment operations."""

import json
import logging

import azure.functions as func

from models.requests import DeploymentRequest
from services.deployment_service import DeploymentService

app = func.FunctionApp()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.function_name(name="deploy")
@app.route(route="deploy", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def deploy_function(req: func.HttpRequest) -> func.HttpResponse:
    """Deploy a feature branch to AKS."""
    logger.info("Deploy function triggered")

    try:
        # Parse request
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                json.dumps({"error": "Request body is required"}),
                status_code=400,
                headers={"Content-Type": "application/json"},
            )

        # Validate request model
        deployment_request = DeploymentRequest(**req_body)

        # Execute deployment
        deployment_service = DeploymentService()
        result = await deployment_service.deploy(deployment_request)

        # Return response
        return func.HttpResponse(
            result.model_dump_json(),
            status_code=200 if result.success else 500,
            headers={"Content-Type": "application/json"},
        )

    except ValueError as e:
        logger.error(f"Validation error: {e!s}")
        return func.HttpResponse(
            json.dumps({"error": f"Validation error: {e!s}"}),
            status_code=400,
            headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e!s}")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error"}),
            status_code=500,
            headers={"Content-Type": "application/json"},
        )


@app.function_name(name="health")
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return func.HttpResponse(
        json.dumps({"status": "healthy", "service": "deployment-function"}),
        status_code=200,
        headers={"Content-Type": "application/json"},
    )
