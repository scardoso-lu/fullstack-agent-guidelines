class AppError(Exception):
    """Base application error."""


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""
