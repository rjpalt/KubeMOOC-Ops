"""Test cases for request models."""


import pytest
from pydantic import ValidationError

from models.requests import ProvisionRequest


def test_provision_request_valid() -> None:
    """Test valid provision request creation."""
    request = ProvisionRequest(branch_name="test-branch")
    assert request.branch_name == "test-branch"


def test_provision_request_valid_alphanumeric() -> None:
    """Test provision request with valid alphanumeric name."""
    request = ProvisionRequest(branch_name="feature123")
    assert request.branch_name == "feature123"


def test_provision_request_valid_with_hyphens() -> None:
    """Test provision request with valid hyphenated name."""
    request = ProvisionRequest(branch_name="feature-branch-name")
    assert request.branch_name == "feature-branch-name"


def test_provision_request_empty_name() -> None:
    """Test that empty branch name raises validation error."""
    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        ProvisionRequest(branch_name="")


def test_provision_request_invalid_characters() -> None:
    """Test that invalid characters raise validation error."""
    with pytest.raises(ValueError, match="must be a valid DNS-1123 label"):
        ProvisionRequest(branch_name="UPPERCASE")


def test_provision_request_starts_with_hyphen() -> None:
    """Test that name starting with hyphen raises validation error."""
    with pytest.raises(ValueError, match="must be a valid DNS-1123 label"):
        ProvisionRequest(branch_name="-invalid")


def test_provision_request_ends_with_hyphen() -> None:
    """Test that name ending with hyphen raises validation error."""
    with pytest.raises(ValueError, match="must be a valid DNS-1123 label"):
        ProvisionRequest(branch_name="invalid-")


def test_provision_request_too_long() -> None:
    """Test that name exceeding 63 characters raises validation error."""
    long_name = "a" * 64  # 64 characters
    with pytest.raises(ValidationError, match="String should have at most 63 characters"):
        ProvisionRequest(branch_name=long_name)


def test_provision_request_max_length() -> None:
    """Test that name of exactly 63 characters is valid."""
    max_name = "a" * 63  # 63 characters
    request = ProvisionRequest(branch_name=max_name)
    assert request.branch_name == max_name
