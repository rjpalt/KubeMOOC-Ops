"""Request models for the deprovisioning function."""

import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

# Constants
MAX_BRANCH_NAME_LENGTH = 63
MIN_BRANCH_NAME_LENGTH = 1


class DeprovisionRequest(BaseModel):
    """Request model for environment deprovisioning."""

    branch_name: Annotated[
        str,
        Field(
            description="Name of the branch to deprovision environment for",
            min_length=MIN_BRANCH_NAME_LENGTH,
            max_length=MAX_BRANCH_NAME_LENGTH,
        ),
    ]

    @field_validator("branch_name")
    @classmethod
    def validate_branch_name(cls, v: str) -> str:
        """Validate branch name for Kubernetes and PostgreSQL compatibility.

        Args:
            v: The branch name to validate

        Returns:
            The validated branch name

        Raises:
            ValueError: If the branch name is invalid
        """
        if not v:
            msg = "branch_name cannot be empty"
            raise ValueError(msg)

        # Ensure valid Kubernetes namespace name (DNS-1123 label)
        if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", v):
            msg = (
                "branch_name must be a valid DNS-1123 label "
                "(lowercase alphanumeric characters or hyphens, "
                "cannot start or end with hyphen)"
            )
            raise ValueError(msg)

        if len(v) > MAX_BRANCH_NAME_LENGTH:
            msg = f"branch_name cannot exceed {MAX_BRANCH_NAME_LENGTH} characters"
            raise ValueError(msg)

        return v
