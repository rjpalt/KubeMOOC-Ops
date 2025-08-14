# KubernetesMOOC Configuration Repository

This repository contains automation functions and Kubernetes manifests for the KubernetesMOOC project.

## Structure

```
KubernetesMOOC-Conf/
├── functions/                    # Azure Functions for automation
│   └── provisioning-function/    # Environment provisioning function
│       └── README.md            # Detailed documentation
├── kubernetes/                   # Kubernetes manifests
│   ├── base/                    # Base Kustomize configuration
│   └── overlays/                # Environment-specific overlays
└── README.md                    # This overview
```

## Functions

### [Provisioning Function](functions/provisioning-function/)

Automated provisioning of feature branch environments including:
- PostgreSQL database creation
- Managed identity federated credentials
- Kubernetes namespace creation

**See [functions/provisioning-function/README.md](functions/provisioning-function/README.md) for detailed documentation.**

## Kubernetes Manifests

Kustomize-based configuration for deploying applications across different environments.

## Security Notes

- All sensitive configuration is managed via environment variables
- No credentials are stored in code or configuration files
- Each function has its own security documentation

# Azure Resource Naming Conventions

## Overview

This document defines strict naming conventions for Azure resources to enable reliable automation and cleanup. **All automated tooling depends on these naming patterns.**

## Branch Environment Resources

### PostgreSQL Databases
- **Pattern**: `{branch_name}` → sanitized to `{branch_name_sanitized}`
- **Sanitization Rule**: Replace hyphens (`-`) with underscores (`_`)
- **Examples**:
  - `feature-login` → `feature_login`
  - `bugfix-auth-fix` → `bugfix_auth_fix`
  - `ex-3-9` → `ex_3_9`

### Federated Credentials
- **Pattern**: `cred-{branch_name}`
- **Examples**:
  - `cred-feature-login`
  - `cred-bugfix-auth-fix`
  - `cred-ex-3-9`

### Kubernetes Namespaces
- **Pattern**: `{branch_name}` (no sanitization)
- **Required Labels**:
  - `app.kubernetes.io/managed-by=provisioning-function`
  - `provisioning.kubernetes.io/branch={branch_name}`
  - `dev-gateway-access=allowed`
- **Examples**:
  - `feature-login`
  - `bugfix-auth-fix`
  - `ex-3-9`

## Core Infrastructure Resources

### Resource Groups
- **Automation**: `kubemooc-automation-rg`
- **Application Infrastructure**: `kubernetes-learning`
- **PostgreSQL**: `kubernetes-learning` (shared with AKS)

### PostgreSQL Servers
- **Production**: `kubemooc-postgres-prod`
- **Feature Environments**: `kubemooc-postgres-feature`

### Managed Identities
- **Application Workload Identity**: `mi-todo-app-dev`
- **Provisioning Function Identity**: `mi-provisioning-function`

### Azure Function App
- **Pattern**: `kubemooc-provisioning-func`

### AKS Cluster
- **Pattern**: `kube-mooc`

## Cleanup Automation Dependencies

### Database Cleanup
Automated cleanup tools must:
1. List databases matching pattern: `{branch_name_sanitized}`
2. Exclude system databases (`postgres`, `azure_maintenance`, `azure_sys`)
3. Drop databases created by provisioning function

### Federated Credential Cleanup
Automated cleanup tools must:
1. List federated credentials matching pattern: `cred-{branch_name}`
2. Delete credentials for specific branch
3. Verify deletion success

### Namespace Cleanup
Automated cleanup tools must:
1. List namespaces with label: `app.kubernetes.io/managed-by=provisioning-function`
2. Filter by label: `provisioning.kubernetes.io/branch={branch_name}`
3. Delete namespace and all contained resources

## Security Considerations

### Naming Pattern Validation
- Branch names must match pattern: `^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}[a-zA-Z0-9]$`
- No special characters except hyphens
- Maximum 63 characters (Kubernetes namespace limit)

### Resource Isolation
- Each branch gets isolated database, credentials, and namespace
- No shared resources between branches except core infrastructure
- Cleanup removes all branch-specific resources

## Environment Variables Reference

All actual resource names and IDs are stored in `.project/context.yaml`:

```yaml
azure:
  subscriptionId: <AZURE_SUBSCRIPTION_ID>
  resourceGroups:
    automation: <AUTOMATION_RESOURCE_GROUP>
    infrastructure: <INFRASTRUCTURE_RESOURCE_GROUP>
  postgres:
    serverName: <POSTGRES_SERVER_NAME>
    adminUser: <POSTGRES_ADMIN_USER>
  managedIdentities:
    appIdentity:
      name: <APP_MANAGED_IDENTITY_NAME>
      clientId: <APP_MANAGED_IDENTITY_CLIENT_ID>
    provisioningIdentity:
      name: <PROVISIONING_MANAGED_IDENTITY_NAME>
      clientId: <PROVISIONING_MANAGED_IDENTITY_CLIENT_ID>
  aks:
    clusterName: <AKS_CLUSTER_NAME>
    resourceGroup: <AKS_RESOURCE_GROUP>
```

## Implementation Notes

### Branch Name Validation
The provisioning function validates branch names to ensure they:
- Create valid PostgreSQL database names
- Create valid Kubernetes namespace names  
- Don't conflict with system resources

### Cleanup Verification
Before cleanup operations:
1. Verify resource belongs to provisioning system (check labels/tags)
2. Confirm no production resources match cleanup pattern
3. Log all cleanup operations for audit trail

## Critical Dependencies

**⚠️ WARNING**: Changing these naming conventions will break:
- Automated cleanup scripts
- CI/CD integration workflows
- Monitoring and alerting systems
- Resource discovery tools

Any changes must be coordinated across all automation systems.
