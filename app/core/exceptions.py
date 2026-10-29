class AppError(Exception):
    """Base application exception."""


class ScrapeLockError(AppError):
    """Raised when an advisory lock cannot be acquired because a scrape is already running."""


class ParseError(AppError):
    """Raised when required fields are missing or cannot be parsed from a book page."""


class BookNotFoundError(AppError):
    """Raised when a book with the requested ID is not found."""


class DuplicateSourceUrlError(AppError):
    """Raised when attempting to insert a book with a source_url that already exists."""


class CheckViolationError(AppError):
    """Raised when a database check constraint is violated."""


class ScrapeRunNotFoundError(AppError):
    """Raised when a scrape run with the requested ID is not found."""
