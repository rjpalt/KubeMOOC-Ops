"""Test request models for the deprovisioning function."""

import pytest

from models_requests import DeprovisionRequest


def test_valid_branch_name() -> None:
    """Test that valid branch names are accepted."""
    valid_names = [
        "feature-123",
        "ex-c3-e11",
        "hotfix-urgent",
        "test",
        "a",
        "feature-very-long-name-but-still-under-limit-123456789012345",
    ]

    for name in valid_names:
        request = DeprovisionRequest(branch_name=name)
        assert request.branch_name == name


def test_invalid_branch_name_characters() -> None:
    """Test that invalid characters in branch names are rejected."""
    invalid_names = [
        "Feature-123",  # uppercase
        "feature_123",  # underscore
        "feature.123",  # period
        "feature@123",  # special character
        "feature 123",  # space
        "feature/123",  # slash
        "-feature",     # starts with hyphen
        "feature-",     # ends with hyphen
        "",             # empty
        "123-feature-", # ends with hyphen
    ]

    for name in invalid_names:
        with pytest.raises(ValueError):
            DeprovisionRequest(branch_name=name)


def test_branch_name_length_limits() -> None:
    """Test that branch name length limits are enforced."""
    # Too long (64 characters)
    too_long = "a" * 64
    with pytest.raises(ValueError):
        DeprovisionRequest(branch_name=too_long)

    # Maximum allowed (63 characters)
    max_length = "a" * 63
    request = DeprovisionRequest(branch_name=max_length)
    assert request.branch_name == max_length

    # Minimum allowed (1 character)
    min_length = "a"
    request = DeprovisionRequest(branch_name=min_length)
    assert request.branch_name == min_length


def test_dns_1123_compliance() -> None:
    """Test that branch names comply with DNS-1123 label standard."""
    # Valid DNS-1123 labels
    valid_dns_names = [
        "ex-c3-e11",
        "feature-xyz",
        "test123",
        "a1b2c3",
        "hotfix-2024",
    ]

    for name in valid_dns_names:
        request = DeprovisionRequest(branch_name=name)
        assert request.branch_name == name

    # Invalid DNS-1123 labels
    invalid_dns_names = [
        "-abc",         # starts with hyphen
        "abc-",         # ends with hyphen
        "ABC",          # uppercase
        "a_b",          # underscore
    ]

    for name in invalid_dns_names:
        with pytest.raises(ValueError):
            DeprovisionRequest(branch_name=name)


def test_common_branch_patterns() -> None:
    """Test common branch naming patterns used in the project."""
    # Patterns based on the GitHub Actions workflow filter: startsWith(github.ref_name, 'ex-')
    common_patterns = [
        "ex-c1-e1",
        "ex-c2-e5",
        "ex-c3-e11",
        "ex-final-project",
        "feature-auth",
        "feature-api-v2",
        "hotfix-security",
        "bugfix-123",
    ]

    for pattern in common_patterns:
        request = DeprovisionRequest(branch_name=pattern)
        assert request.branch_name == pattern
        # Verify these would create valid namespace names
        namespace = f"feature-{pattern}"
        assert len(namespace) <= 63  # Kubernetes namespace limit
        # Verify they would create valid database names (after sanitization)
        db_name = pattern.replace("-", "_")
        assert db_name.replace("_", "").isalnum()  # Valid PostgreSQL identifier
