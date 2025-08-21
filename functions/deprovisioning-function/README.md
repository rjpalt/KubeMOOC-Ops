# Secure Environment Deprovisioning Function

Azure Function for automated cleanup of feature branch environments, including PostgreSQL database deletion, managed identity federation cleanup, and Kubernetes namespace removal.

## Overview

This function reverses all operations performed by the provisioning function, ensuring complete cleanup of feature branch environments when branches are deleted.

## Architecture

### Azure Function (`functions/deprovisioning-function/`)

Modern Python-based Azure Function using:
- **uv** for dependency management and virtual environments
- **ruff** for code quality and formatting
- **pytest** for comprehensive testing
- **pydantic-settings** for configuration management
- **Azure SDK** for cloud resource management

### Project Structure

```
functions/deprovisioning-function/
├── function_app.py               # Azure Function entry point (modern v2 model)
├── config.py                     # Environment-based settings (no defaults)
├── models/                       # Request/response models
│   ├── __init__.py              # Empty (proper Azure Function structure)
│   └── requests.py              # Pydantic validation models
├── services/                     # Business logic
│   ├── __init__.py              # Empty (proper Azure Function structure)
│   └── deprovisioning_service.py # Core deprovisioning logic
├── tests/                        # Test suite
│   ├── test_config.py           # Configuration tests (mock values only)
│   ├── test_models.py           # Model validation tests
│   └── test_deprovisioning_service.py # Service logic tests
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

The deprovisioning function reverses three core operations from feature branch environments:

1. **PostgreSQL Database Deletion**: Removes isolated databases from existing PostgreSQL Flexible Server
   - Handles name sanitization (ex-c3-e11 → ex_c3_e11)
   - Graceful handling of already-deleted databases
   
2. **Dual Federated Credential Cleanup**: Removes OIDC-based authentication for both database and Key Vault access
   - **Database Access**: Deletes federated credential `database-workload-identity-{branch}` from `mi-todo-app-dev`
   - **Key Vault Access**: Deletes federated credential `keyvault-workload-identity-{branch}` from `keyvault-identity-kube-mooc`
   
3. **Kubernetes Namespace Deletion**: Removes namespaces with proper resource cleanup
   - Suspends CronJobs before deletion to prevent resource leaks
   - Removes namespace `feature-{branch}` and all contained resources
   - Verifies deletion completion

### API Contract

**Endpoint**: `POST /api/deprovision`

**Request**:
```json
{
  "branch_name": "ex-c3-e11"
}
```

**Response** (Success):
```json
{

  ## Overview

  This function reverses all operations performed by the provisioning function, ensuring complete cleanup of feature branch environments when branches are deleted.

  ## Architecture & Azure Infrastructure

  ### Azure Function (`functions/deprovisioning-function/`)

  Modern Python-based Azure Function using:
  - **uv** for dependency management and virtual environments
  - **ruff** for code quality and formatting
  - **pytest** for comprehensive testing
  - **pydantic-settings** for configuration management
  - **Azure SDK** for cloud resource management

  ### Project Structure

  ```
  functions/deprovisioning-function/
  ├── function_app.py               # Azure Function entry point (modern v2 model)
  ├── config.py                     # Environment-based settings (no defaults)
  ├── models/                       # Request/response models
  │   ├── __init__.py              # Empty (proper Azure Function structure)
  │   └── requests.py              # Pydantic validation models
  ├── services/                     # Business logic
  │   ├── __init__.py              # Empty (proper Azure Function structure)
  │   └── deprovisioning_service.py # Core deprovisioning logic
  ├── tests/                        # Test suite
  │   ├── test_config.py           # Configuration tests (mock values only)
  │   ├── test_models.py           # Model validation tests
  │   └── test_deprovisioning_service.py # Service logic tests
  ├── .env                         # Environment variables (gitignored)
  ├── .env.example                 # Environment template
  ├── .funcignore                  # Deployment exclusions
  ├── pyproject.toml               # Project configuration
  ├── host.json                    # Azure Function runtime config
  ├── local.settings.json          # Local development settings
  ├── requirements.txt             # Python dependencies
  └── uv.lock                      # Dependency lock file
  ```

  ### Azure Infrastructure Setup

  #### Managed Identity
  - **Name**: `mi-deprovisioning-function`
  - **Resource Group**: `kubemooc-automation-rg`
  - **Location**: `northeurope`
  - **Client ID**: `[REDACTED - Check Azure Portal]`
  - **Principal ID**: `[REDACTED - Check Azure Portal]`

  #### RBAC Permissions Assigned
  The managed identity is granted least-privilege access for all required operations:

  1. **PostgreSQL Database Deletion**
    - Role: `Contributor`
    - Scope: `/subscriptions/ede18d8a-a758-4a40-b15e-6eded5264b93/resourceGroups/kubernetes-learning/providers/Microsoft.DBforPostgreSQL/flexibleServers/kubemooc-postgres-feature`

  2. **Federated Credential Cleanup**
    - Role: `Managed Identity Contributor`
    - Scope: `/subscriptions/ede18d8a-a758-4a40-b15e-6eded5264b93/resourceGroups/kubemooc-automation-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/mi-todo-app-dev`
    - Scope: `/subscriptions/ede18d8a-a758-4a40-b15e-6eded5264b93/resourceGroups/kubernetes-learning/providers/Microsoft.ManagedIdentity/userAssignedIdentities/keyvault-identity-kube-mooc`
    - Scope: `/subscriptions/ede18d8a-a758-4a40-b15e-6eded5264b93/resourceGroups/kubemooc-automation-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/mi-deprovisioning-function`

  3. **AKS Namespace and Resource Management**
    - Role: `Azure Kubernetes Service RBAC Writer`
    - Scope: `/subscriptions/ede18d8a-a758-4a40-b15e-6eded5264b93/resourcegroups/kubernetes-learning/providers/Microsoft.ContainerService/managedClusters/kube-mooc`

  #### Kubernetes RBAC Configuration
  **Applied**: August 19, 2025 ✅
  
  Additional cluster-level RBAC provides fine-grained namespace deletion control:
  
  - **ClusterRole**: `namespace-manager`
    - **Namespace Operations**: delete, get, list
    - **CronJob Management**: get, list, patch (for suspension before deletion)
    - **Resource Inspection**: get, list pods, services, configmaps, secrets
  
  - **ClusterRoleBinding**: `deprovisioning-function-binding`
    - **Subject**: `41ed2068-1c66-4911-9345-1b413cb9a21c` (mi-deprovisioning-function principal ID)
    - **Security**: Only the deprovisioning function can delete namespaces via Kubernetes API
  
  **Manifest Location**: `/cluster-manifests/cluster-protection-rbac.yaml`
  
  ```bash
  # Applied with:
  kubectl apply -f cluster-manifests/cluster-protection-rbac.yaml
  # Output:
  # clusterrole.rbac.authorization.k8s.io/namespace-manager created
  # clusterrolebinding.rbac.authorization.k8s.io/deprovisioning-function-binding created
  ```

  #### Rationale for Choices
  - **Independent managed identity**: Ensures separation of duties and least-privilege principle
  - **Explicit RBAC assignments**: Only the required scopes and roles are granted
  - **Consistent resource group and location**: Matches existing automation and AKS infrastructure

  #### Command History (for reproducibility)
  ```bash
  # Managed identity creation
  az identity create \
      "error": "Federated credential 'keyvault-workload-identity-ex-c3-e11' not found",
      "severity": "warning"
    },

  # PostgreSQL Contributor role
  az role assignment create \
    {
      "operation": "database_deletion", 
      "error": "Connection timeout to PostgreSQL server",

  # Managed Identity Contributor roles
  az role assignment create \
      "severity": "critical"
    }
  ],
  az role assignment create \
  "correlation_id": "deprov-ex-c3-e11-20250819-143052",
  "message": "Deprovisioning completed with errors"
}
  az role assignment create \
```

### Validation Rules

  # AKS RBAC Writer role
  az role assignment create \

Branch names must conform to DNS-1123 label standards:
- Lowercase alphanumeric characters and hyphens only
  ```
- Cannot start or end with hyphens
- Maximum 63 characters
- Minimum 1 character

### Safety Features

#### Protected Namespace Validation
The function prevents deletion of critical system namespaces:
- `default`, `kube-system`, `azure-alb-system`
- `project`, `kube-public`, `kube-node-lease`
- `azure-system`, `gatekeeper-system`

#### Error Handling Strategy
- **Continue on non-critical errors**: Missing credentials, already-deleted resources
- **Abort on critical errors**: Authentication failures, protected namespace attempts
- **Detailed logging**: All operations tracked with correlation IDs

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
| `DEPROVISIONING_FUNCTION_IDENTITY_NAME` | **Yes** | Deprovisioning function managed identity name |
| `DEPROVISIONING_FUNCTION_CLIENT_ID` | **Yes** | Deprovisioning function managed identity client ID |
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
   cd functions/deprovisioning-function
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
   
   # Deprovisioning Function Identity (authenticates this function)
   DEPROVISIONING_FUNCTION_IDENTITY_NAME=your-deprovisioning-function-identity
   DEPROVISIONING_FUNCTION_CLIENT_ID=your-deprovisioning-function-client-id
   
   # Database Access Identity (target for federation deletion)
   DATABASE_IDENTITY_NAME=your-database-access-identity
   DATABASE_IDENTITY_CLIENT_ID=your-database-access-client-id
   DATABASE_IDENTITY_RESOURCE_GROUP=your-database-identity-resource-group
   
   # Key Vault Access Identity (target for federation deletion)
   KEYVAULT_IDENTITY_NAME=your-keyvault-access-identity
   KEYVAULT_IDENTITY_CLIENT_ID=your-keyvault-access-client-id
   KEYVAULT_IDENTITY_RESOURCE_GROUP=your-keyvault-identity-resource-group
   
   # Kubernetes Configuration
   AKS_RESOURCE_GROUP=your-aks-resource-group
   AKS_CLUSTER_NAME=your-aks-cluster-name
   ```

## Development Setup

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Azure CLI (authenticated)
- Access to target Azure subscription and resources

### Quick Start

1. **Navigate to the function directory**:
   ```bash
   cd functions/deprovisioning-function
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

## Status

**Implementation**: ✅ **COMPLETE** (August 20, 2025)
**Tests**: ✅ All 19 tests passing
**Security**: ✅ No secrets in public repository
**Deployment**: 🚀 Ready for Azure deployment

### Implementation Summary
- ✅ Complete Azure Function entry point (`function_app.py`)
- ✅ Full deprovisioning service logic (`services/deprovisioning_service.py`)
- ✅ Comprehensive test suite (19 tests: 5 config + 5 models + 9 service tests)
- ✅ Security hardening (no real secrets, proper `__init__.py` files)
- ✅ Deployment configuration (Makefile with `uv export`)

### Next Steps
1. **Deploy to Azure**: Deploy function to `Deprovisioning-Function` Azure Function App
2. **Integration Testing**: Test with real feature branch cleanup
3. **GitHub Actions**: Update workflow to use Azure Function instead of manual cleanup
4. **Production Validation**: Verify with actual feature branch lifecycle

## Testing

Comprehensive test suite covering:

### Test Coverage (19 tests passing)
```bash
# Run all tests
uv run pytest tests/ -v

# Recent test results:
# =================== 19 passed in 0.37s ===================
# All tests: configuration (5), models (5), service logic (9)
```

### Configuration Tests (`test_config.py`)
- Environment variable loading validation
- Mock value testing (no real credentials)
- Computed property functionality

### Model Tests (`test_models.py`)
- Valid branch name patterns
- DNS-1123 compliance validation
- Length constraints (1-63 characters)
- Invalid character handling
- Common project branch patterns

### Service Tests (`test_deprovisioning_service.py`)
- Database deletion logic
- Federated credential cleanup
- Kubernetes namespace operations
- Error handling scenarios
- Safety validations

## Security

### Managed Identity
Uses independent `mi-deprovisioning-function` identity with least-privilege permissions:
- PostgreSQL database management
- Managed identity federation cleanup
- AKS namespace operations

### Safety Measures
- Protected namespace validation
- Branch name pattern enforcement
- Comprehensive audit logging
- Graceful error handling for missing resources

## Monitoring & Logging

### Application Insights Integration
- **Correlation IDs**: Track complete deprovisioning workflows
- **Custom Metrics**: Success rates, duration distributions, error patterns
- **Structured Logging**: JSON format for efficient querying
- **Error Classification**: Critical, Warning, Info severity levels

### Sample Log Query (KQL)
```kusto
traces
| where customDimensions.correlation_id == "deprov-ex-c3-e11-20250819-143052"
| project timestamp, message, customDimensions
| order by timestamp asc
```
