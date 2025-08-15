"""Request and response models for deployment operations."""

from pydantic import BaseModel, Field, field_validator


class DeploymentRequest(BaseModel):
    """Request model for deployment operations."""

    branch_name: str = Field(..., description="Feature branch name to deploy")
    commit_sha: str = Field(..., description="Git commit SHA for the deployment")

    @field_validator("branch_name")
    @classmethod
    def validate_branch_name(cls, v: str) -> str:
        """Validate branch name is not empty."""
        if not v or not v.strip():
            msg = "Branch name cannot be empty"
            raise ValueError(msg)
        return v.strip()

    @field_validator("commit_sha")
    @classmethod
    def validate_commit_sha(cls, v: str) -> str:
        """Validate commit SHA is not empty."""
        if not v or not v.strip():
            msg = "Commit SHA cannot be empty"
            raise ValueError(msg)
        return v.strip()

    @property
    def namespace(self) -> str:
        """Generate Kubernetes namespace from branch name."""
        return f"feature-{self.branch_name}"

    @property
    def image_tag_suffix(self) -> str:
        """Generate image tag suffix from branch and commit."""
        return f"{self.branch_name}-{self.commit_sha}"


class HealthCheck(BaseModel):
    """Health check result for a deployed resource."""

    resource_type: str
    resource_name: str
    status: str
    ready: bool
    message: str | None = None


class DeploymentResponse(BaseModel):
    """Response model for deployment operations."""

    success: bool
    message: str
    namespace: str
    deployment_url: str | None = None
    health_checks: list[HealthCheck] = Field(default_factory=list)
    error_details: str | None = None
    deployed_resources: list[str] = Field(default_factory=list)
