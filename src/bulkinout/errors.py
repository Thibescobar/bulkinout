"""Application-level exceptions exposed by Bulkinout."""


class BulkinoutError(Exception):
    """Base class for expected Bulkinout failures."""


class ConfigurationError(BulkinoutError):
    """Raised when required runtime configuration is missing or invalid."""


class InputError(BulkinoutError):
    """Raised when an input cannot be processed."""


class ReferenceDataError(BulkinoutError):
    """Raised when reference data is missing or malformed."""
