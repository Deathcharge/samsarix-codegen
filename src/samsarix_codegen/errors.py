# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: Apache-2.0

"""User-facing error types and stable CLI exit codes."""


class SamsarixError(Exception):
    """Base class for expected, user-actionable failures."""

    exit_code = 1


class ConfigurationError(SamsarixError):
    """Invalid or missing user configuration."""

    exit_code = 2


class ContextError(SamsarixError):
    """Invalid, unreadable, or unsafe context input."""

    exit_code = 3


class ProviderError(SamsarixError):
    """A configured model endpoint could not return a usable response."""

    exit_code = 4


class ArtifactError(SamsarixError):
    """A stored request artifact is invalid, unsupported, or unapproved."""

    exit_code = 5
