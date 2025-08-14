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
