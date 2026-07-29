"""User-facing error types and stable CLI exit codes."""


class HelixError(Exception):
    """Base class for expected, user-actionable failures."""

    exit_code = 1


class ConfigurationError(HelixError):
    """Invalid or missing user configuration."""

    exit_code = 2


class ContextError(HelixError):
    """Invalid, unreadable, or unsafe context input."""

    exit_code = 3


class ProviderError(HelixError):
    """A configured model endpoint could not return a usable response."""

    exit_code = 4
