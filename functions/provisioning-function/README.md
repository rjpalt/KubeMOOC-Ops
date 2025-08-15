# Secure Environment Provisioning and Deployment

Configuration, Azure Function, and Kubernetes manifests for secure environment provisioning and deployment.

## Overview

This repository contains an Azure Function for automated provisioning of feature branch environments, including PostgreSQL database creation, managed identity federation, and Kubernetes namespace management.

## Architecture

### Azure Function (`functions/provisioning-function/`)

Modern Python-based Azure Function using:
- **uv** for dependency management and virtual environments
- **ruff** for code quality and formatting
- **pytest** for comprehensive testing
- **pydantic-settings** for configuration management
- **Azure SDK** for cloud resource management

### Project Structure

```
functions/provisioning-function/
├── function_app.py               # Azure Function entry point (modern v2 model)
├── config.py                     # Environment-based settings (no defaults)
├── models/                       # Request/response models
│   ├── __init__.py              # Empty (proper Azure Function structure)
│   └── requests.py              # Pydantic validation models
├── services/                     # Business logic
│   ├── __init__.py              # Empty (proper Azure Function structure)
│   └── provisioning_service.py  # Core provisioning logic
├── tests/                        # Test suite
│   ├── test_config.py           # Configuration tests (mock values only)
│   └── test_models.py           # Model validation tests
├── .env                         # Environment variables (gitignored)
├── .env.example                 # Environment template
├── .funcignore                  # Deployment exclusions
├── pyproject.toml               # Project configuration
├── host.json                    # Azure Function runtime config
├── local.settings.json          # Local development settings
├── requirements.txt             # Python dependencies
└── uv.lock                      # Dependency lock file
```

## Functionality

The provisioning function handles three core operations for feature branch environments:

1. **PostgreSQL Database Creation**: Creates isolated databases on existing PostgreSQL Flexible Server
2. **Dual Federated Credential Management**: Sets up OIDC-based authentication for both database and Key Vault access
   - **Database Access**: Creates federated credential on `mi-todo-app-dev` for PostgreSQL connectivity
   - **Key Vault Access**: Creates federated credential on `keyvault-identity-kube-mooc` for secret management
3. **Kubernetes Namespace Creation**: Creates labeled namespaces for workload isolation

### API Contract

**Endpoint**: `POST /api/provision`

**Request**:
```json
{
  "branch_name": "feature-xyz"
}
```

**Response** (Success):
```json
{
  "status": "success",
  "branch_name": "feature-xyz",
  "database_created": true,
  "credential_created": true,
  "namespace_created": true,
  "message": "Environment for branch 'feature-xyz' provisioned successfully"
}
```

**Response** (Error):
```json
{
  "status": "error",
  "branch_name": "feature-xyz",
  "error": "Provisioning failed for branch 'feature-xyz': [error details]"
}
```

### Validation Rules

Branch names must conform to DNS-1123 label standards:
- Lowercase alphanumeric characters and hyphens only
- Cannot start or end with hyphens
- Maximum 63 characters
- Minimum 1 character

## Configuration

**⚠️ Security Notice**: All configuration values must be provided via environment variables. No default values are set in code.

Environment-based configuration using Pydantic Settings:

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_SUBSCRIPTION_ID` | **Yes** | Target Azure subscription ID |
| `POSTGRES_RESOURCE_GROUP` | **Yes** | PostgreSQL server resource group |
| `POSTGRES_SERVER_NAME` | **Yes** | PostgreSQL server name |
| `POSTGRES_ADMIN_USER` | **Yes** | PostgreSQL admin username |
| `POSTGRES_ADMIN_PASSWORD` | **Yes** | PostgreSQL admin password |
| `PROVISIONING_FUNCTION_IDENTITY_NAME` | **Yes** | Provisioning function managed identity name |
| `PROVISIONING_FUNCTION_CLIENT_ID` | **Yes** | Provisioning function managed identity client ID |
| `DATABASE_IDENTITY_NAME` | **Yes** | Database access managed identity name |
| `DATABASE_IDENTITY_CLIENT_ID` | **Yes** | Database access managed identity client ID |
| `DATABASE_IDENTITY_RESOURCE_GROUP` | **Yes** | Database identity resource group |
| `KEYVAULT_IDENTITY_NAME` | **Yes** | Key Vault access managed identity name |
| `KEYVAULT_IDENTITY_CLIENT_ID` | **Yes** | Key Vault access managed identity client ID |
| `KEYVAULT_IDENTITY_RESOURCE_GROUP` | **Yes** | Key Vault identity resource group |
| `AKS_RESOURCE_GROUP` | **Yes** | AKS cluster resource group |
| `AKS_CLUSTER_NAME` | **Yes** | AKS cluster name |

### Environment Setup

1. **Copy the environment template**:
   ```bash
   cd functions/provisioning-function
   cp .env.example .env
   ```

2. **Edit `.env` with your actual values**:
   ```bash
   # Example .env file structure (replace ALL values with your actual Azure resources)
   AZURE_SUBSCRIPTION_ID=your-subscription-id-here
   POSTGRES_RESOURCE_GROUP=your-postgres-resource-group
   POSTGRES_SERVER_NAME=your-postgres-server-name
   POSTGRES_ADMIN_USER=postgres
   POSTGRES_ADMIN_PASSWORD=your-secure-password
   
   # Provisioning Function Identity (authenticates this function)
   PROVISIONING_FUNCTION_IDENTITY_NAME=your-provisioning-function-identity
   PROVISIONING_FUNCTION_CLIENT_ID=your-provisioning-function-client-id
   
   # Database Access Identity (used by pods for PostgreSQL)
   DATABASE_IDENTITY_NAME=your-database-access-identity
   DATABASE_IDENTITY_CLIENT_ID=your-database-access-client-id
   DATABASE_IDENTITY_RESOURCE_GROUP=your-database-identity-resource-group
   
   # Key Vault Access Identity (used by pods for Key Vault)
   KEYVAULT_IDENTITY_NAME=your-keyvault-access-identity
   KEYVAULT_IDENTITY_CLIENT_ID=your-keyvault-access-client-id
   KEYVAULT_IDENTITY_RESOURCE_GROUP=your-keyvault-identity-resource-group
   
   # Kubernetes Configuration
   AKS_RESOURCE_GROUP=your-aks-resource-group
   AKS_CLUSTER_NAME=your-aks-cluster-name
   ```

## Development Setup

### Prerequisites
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Azure CLI (authenticated)
- Access to target Azure subscription and resources

### Quick Start

1. **Navigate to the function directory**:
   ```bash
   cd functions/provisioning-function
   ```

2. **Install dependencies**:
   ```bash
   uv sync --group dev
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual Azure resource details
   ```

4. **Run tests**:
   ```bash
   uv run pytest tests/ -v
   ```

5. **Run locally** (requires Azure Function Core Tools):
   ```bash
   uv run func start
   ```

## Testing

Comprehensive test suite with **12 test cases** covering:

### Configuration Tests (`test_config.py`)
- Environment variable loading validation
- Mock value testing (no real credentials)
- Computed property functionality

### Model Tests (`test_models.py`)
- Valid branch name patterns
- DNS-1123 compliance validation
- Length constraints (1-63 characters)
- Invalid character handling
- Edge case validation

### Test Coverage
- **Unit Tests**: Configuration and model validation
- **Security**: All tests use mock values, no real credentials
- **Validation**: Pydantic-based request validation with comprehensive error handling

### Run Tests

```bash
cd functions/provisioning-function

# Install dependencies (including dev dependencies)
uv sync --group dev

# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_config.py -v

# Run with coverage
uv run pytest tests/ --cov=. --cov-report=html
```

**Current Status**: ✅ All 12 tests passing

## Security Features

1. **No Hard-coded Credentials**: All sensitive values come from environment variables
2. **Input Validation**: DNS-1123 compliant branch names prevent injection attacks
3. **Error Sanitization**: Generic error messages prevent information disclosure
4. **Managed Identity**: OIDC-based authentication without credential management
5. **Environment Variables**: Sensitive configuration externalized and gitignored
6. **SQL Injection Prevention**: Parameterized queries and name sanitization
7. **Test Security**: All tests use mock values, no real credentials in test code

### Security Improvements Made
- ✅ Removed all default values containing real Azure resource information
- ✅ Updated tests to use mock UUIDs and resource names
- ✅ Created proper `.env.example` template
- ✅ Ensured `.env` is gitignored
- ✅ Followed Azure Function best practices for structure

## Code Quality

Production-ready code with modern Python standards:
- **Type Safety**: Full type annotations with mypy compatibility
- **Code Quality**: Ruff linting and formatting
- **Documentation**: Comprehensive docstrings and inline comments
- **Error Handling**: Structured exception handling with proper logging
- **Testing**: 100% test success rate (12/12 tests passing)
- **Security**: No hard-coded credentials, environment-based configuration
- **Structure**: Follows Azure Functions v2 programming model best practices

## Project Structure Notes

This project has been restructured to follow Azure Functions best practices:

### ✅ Correct Structure (Current)
- `function_app.py` at root level (Azure Functions v2 model)
- Flat module structure (`config.py`, `models/`, `services/` at root)
- Empty `__init__.py` files
- Environment-based configuration with `.env` support
- Proper `.funcignore` for deployment exclusions

### ❌ Previous Issues (Fixed)
- ~~Nested `ProvisionEnvironment/` directory~~
- ~~Non-empty `__init__.py` files with imports~~
- ~~Hard-coded credentials in configuration~~
- ~~Real Azure subscription IDs in tests~~
- ~~Missing `.env` example file~~

## Dependencies

### Core Runtime
- `azure-functions`: Azure Function runtime
- `azure-identity`: Managed identity authentication
- `azure-mgmt-*`: Azure resource management SDKs
- `kubernetes`: Kubernetes API client
- `psycopg2-binary`: PostgreSQL connectivity
- `pydantic`: Data validation and settings
- `pydantic-settings`: Environment-based configuration

### Development Tools
- `pytest`: Testing framework
- `ruff`: Code quality and formatting
- `mypy`: Static type checking
- `uv`: Package management and virtual environments

## Deployment

### Local Development
```bash
cd functions/provisioning-function
uv sync --group dev
cp .env.example .env
# Edit .env with your Azure resource details
uv run func start
```

### Azure Deployment

The function has been deployed to Azure Function App with managed identity authentication.

**Deployment Status**: ✅ **DEPLOYED** (August 15, 2025)
- **Function App**: `kubemooc-provisioning-func`
- **Endpoint**: `https://kubemooc-provisioning-func-cmgzbegwhghddtby.northeurope-01.azurewebsites.net/api/provision`
- **Authentication**: User-assigned managed identity (`mi-provisioning-function`)
- **Environment**: All required variables configured in Azure Portal
- **Federation**: Dual identity setup for database and Key Vault access

#### Deployment Command
```bash
# Deploy updated function code to Azure
func azure functionapp publish kubemooc-provisioning-func
```

#### Required Azure Configuration
The following environment variables are configured in the Azure Function App:
- `AZURE_SUBSCRIPTION_ID`
- `POSTGRES_RESOURCE_GROUP` 
- `POSTGRES_SERVER_NAME`
- `POSTGRES_ADMIN_USER`
- `POSTGRES_ADMIN_PASSWORD`
- `PROVISIONING_FUNCTION_IDENTITY_NAME` - Provisioning function managed identity
- `PROVISIONING_FUNCTION_CLIENT_ID` - Required for user-assigned managed identity authentication
- `DATABASE_IDENTITY_NAME` - Database access managed identity
- `DATABASE_IDENTITY_CLIENT_ID` - Database access client ID
- `DATABASE_IDENTITY_RESOURCE_GROUP` - Database identity resource group
- `KEYVAULT_IDENTITY_NAME` - Key Vault access managed identity
- `KEYVAULT_IDENTITY_CLIENT_ID` - Key Vault access client ID
- `KEYVAULT_IDENTITY_RESOURCE_GROUP` - Key Vault identity resource group
- `AKS_RESOURCE_GROUP`
- `AKS_CLUSTER_NAME`

### Manual Testing

#### Test Environment Provisioning
```bash
# Test the deployed function (replace YOUR_FUNCTION_KEY with actual key)
curl -X POST -i \
  -H "Content-Type: application/json" \
  -d '{ "branch_name": "test-feature-123" }' \
  "https://kubemooc-provisioning-func-cmgzbegwhghddtby.northeurope-01.azurewebsites.net/api/provision?code=YOUR_FUNCTION_KEY"
```

#### Expected Success Response
```json
{
  "status": "success",
  "branch_name": "test-feature-123",
  "database_created": true,
  "credential_created": true,
  "namespace_created": true,
  "message": "Environment for branch 'test-feature-123' provisioned successfully",
  "timing": {
    "total_duration_seconds": 8.49,
    "database_duration_seconds": 0.05,
    "credential_duration_seconds": 6.85,
    "namespace_duration_seconds": 1.59
  },
  "correlation_id": "uuid-here"
}
```

**What gets created**:
- **Database**: `test_feature_123` (sanitized name with underscores)
- **Namespace**: `feature-test-feature-123` with `dev-gateway-access=allowed` label
- **Database Federation**: `database-workload-identity-test-feature-123` on `mi-todo-app-dev`
- **Key Vault Federation**: `keyvault-workload-identity-test-feature-123` on `keyvault-identity-kube-mooc`
- **OIDC Subject**: `system:serviceaccount:feature-test-feature-123:postgres-service-account`

#### Function Key Retrieval
```bash
# Get the function key for manual testing
az functionapp keys list --name kubemooc-provisioning-func --resource-group kubemooc-automation-rg
```

#### Troubleshooting

**Common Issues**:
1. **404 Not Found**: Check endpoint URL and function name
2. **400 Bad Request**: Verify JSON payload has `branch_name` (not `branchName`)
3. **401 Unauthorized**: Function key required in query parameter `?code=`
4. **Authentication Errors**: Managed identity client ID must be configured

**Debugging with Application Insights**:
```kql
// Query function execution logs
traces
| where timestamp > ago(1h)
| where customDimensions.correlation_id != ""
| order by timestamp desc

// Query authentication errors  
exceptions
| where timestamp > ago(1h)
| where outerMessage contains "DefaultAzureCredential"
| order by timestamp desc
```

Resource provisioning follows the principle of idempotency - operations can be safely retried and will not create duplicate resources.
