class PosSystemError(Exception):
    """Base domain exception for the POS system."""


class ApiClientError(PosSystemError):
    """Raised when external API communication fails."""


class PaymentError(PosSystemError):
    """Raised when payment processing fails."""


class StorageError(PosSystemError):
    """Raised when local persistence operations fail."""
