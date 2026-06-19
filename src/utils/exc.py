class AppError(Exception):
    """Base application error."""


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""


class ConflictError(AppError):
    """Raised when a resource conflicts with existing state."""


class ValidationError(AppError):
    """Raised when input fails business rule validation."""
