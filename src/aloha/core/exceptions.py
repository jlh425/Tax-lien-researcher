"""Custom exception hierarchy for the Aloha platform."""


class AlohaError(Exception):
    """Base exception for all Aloha-specific errors."""

    def __init__(self, message: str = "", *, detail: str | None = None) -> None:
        self.detail = detail or message
        super().__init__(message)


class ScrapingError(AlohaError):
    """Raised when a scraper fails to retrieve or parse a page."""


class ParsingError(AlohaError):
    """Raised when raw data cannot be parsed into the expected structure."""


class AgentError(AlohaError):
    """Raised when an agent encounters an unrecoverable problem."""


class AuthenticationError(AlohaError):
    """Raised when authentication or authorisation fails."""


class NotFoundError(AlohaError):
    """Raised when a requested resource does not exist."""


class RateLimitError(AlohaError):
    """Raised when an external service rate-limits our request."""
