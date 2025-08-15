# Deployment Function

Azure Function for automated deployment of feature branch environments to AKS (Azure Kubernetes Service).

## Overview

This function converts the GitHub Actions workflow logic into a secure Azure Function that can be called by CI pipelines. It handles:

- **ACR Image Verification**: Verifies that required container images exist in Azure Container Registry
- **Kubernetes Manifest Download**: Fetches manifests from the GitHub repository  
- **AKS Deployment**: Deploys applications to Azure Kubernetes Service using kustomize patterns
- **Health Checking**: Validates deployment status and resource health
- **URL Generation**: Provides access URLs for deployed feature environments

## API Endpoints

### `POST /api/deploy`
Deploys a feature branch to AKS.

**Request Body:**
```json
{
  "branch_name": "my-feature",
  "commit_sha": "abc123def456"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully deployed branch my-feature to namespace feature-my-feature",
  "namespace": "feature-my-feature",
  "deployment_url": "https://feature-my-feature.kubemooc.dev",
  "health_checks": [
    {
      "resource_type": "deployment",
      "resource_name": "todo-app", 
      "status": "ready",
      "ready": true,
      "message": "1/1 pods ready"
    }
  ],
  "deployed_resources": [
    "namespace/feature-my-feature",
    "deployment/todo-app",
    "service/todo-app-service"
  ]
}
```

### `GET /api/health`
Health check endpoint (anonymous access).

## Project Structure

```
deployment-function/
├── .env.example              # Environment variables template
├── .python-version           # Python version (3.12)
├── pyproject.toml           # Project configuration and dependencies
├── Makefile                 # Development commands
├── function_app.py          # Main Azure Function app
├── config.py                # Application settings
├── host.json                # Azure Functions host configuration
├── local.settings.json      # Local development settings
├── requirements.txt         # Generated Python dependencies
├── models/
│   ├── __init__.py
│   └── requests.py          # Request/response models
├── services/
│   ├── __init__.py
│   └── deployment_service.py # Core deployment logic
└── tests/
    ├── __init__.py
    ├── test_config.py
    └── test_deployment_service.py
```

## Development Commands

All commands are available via the Makefile:

```bash
# Install dependencies
make install

# Run tests
make test

# Run code quality checks
make quality

# Generate requirements.txt
make reqs

# Deploy to Azure (runs tests, quality, reqs first)
make deploy

# Clean up generated files
make clean
```

## Local Development

1. **Install dependencies:**
   ```bash
   make install
   ```

2. **Copy environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

3. **Run tests:**
   ```bash
   make test
   ```

4. **Run locally:**
   ```bash
   func start
   ```

## Configuration

The function uses the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ACR_LOGIN_SERVER` | `kubemooc.azurecr.io` | Azure Container Registry server |
| `ACR_NAME` | `kubemooc` | ACR name |
| `AKS_CLUSTER_NAME` | `kube-mooc` | AKS cluster name |
| `AKS_RESOURCE_GROUP` | `kubernetes-learning` | Resource group containing AKS |
| `AZURE_SUBSCRIPTION_ID` | (from config) | Azure subscription ID |
| `GITHUB_REPOSITORY_URL` | (from config) | GitHub repo URL for manifests |
| `AZURE_CLIENT_ID` | (from config) | Managed identity client ID |

## Azure Resources

The function requires these Azure resources:

- **Function App**: `kubemooc-deployment-func`
- **Storage Account**: `kubemoocdeploymentst` 
- **Application Insights**: `kubemooc-deployment-func`
- **Managed Identity**: `mi-deployment-function`

### Required Permissions

The managed identity needs these role assignments:

- **AcrPull**: Read access to Azure Container Registry
- **AKS Contributor**: Deploy to AKS cluster
- **AKS RBAC Writer**: Manage Kubernetes resources

## Deployment

Deploy manually using:

```bash
make deploy
```

This will:
1. Run all tests
2. Run code quality checks  
3. Generate requirements.txt
4. Deploy to Azure Function App

## Architecture

The function follows this flow:

1. **Validate Request** → Parse and validate deployment request
2. **Verify Images** → Check ACR for required container images
3. **Download Manifests** → Fetch Kubernetes manifests from GitHub
4. **Configure K8s Client** → Set up AKS authentication
5. **Deploy Resources** → Apply manifests to AKS cluster
6. **Health Check** → Verify deployment status
7. **Return Response** → Provide deployment details and URL

## Security

- Uses Azure Managed Identity for authentication
- Function key required for API access
- Read-only access to GitHub repository
- Namespace isolation (feature-* pattern)
- No sensitive data in logs

## Monitoring

- Application Insights integration
- Structured logging throughout
- Health check endpoint for monitoring
- Error details in responses (dev mode)

## Testing

The test suite includes:

- **Unit tests** for models and services
- **Integration tests** for Azure service clients
- **Mock tests** for external dependencies
- **Configuration tests** for environment variables

Run with: `make test`

## Contributing

1. Install development dependencies: `make install`
2. Make changes
3. Run tests: `make test`  
4. Run quality checks: `make quality`
5. Create pull request

## Related Documentation

- [Implementation Plan](../../DEPLOYMENT_FUNCTION_IMPLEMENTATION_PLAN.md)
- [Azure Setup Guide](../../../KubernetesMOOC/docs/azure/Azure-memos.md)
- [Project Context](../../.project/context.yaml)
