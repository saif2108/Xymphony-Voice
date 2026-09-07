"""Shared provider port primitives. No vendor SDKs."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class ProviderErrorCode(StrEnum):
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    INVALID_REQUEST = "invalid_request"
    PROVIDER = "provider"
    UNKNOWN = "unknown"


class ProviderError(Exception):
    """Normalized provider failure surfaced to the runtime."""

    def __init__(
        self,
        *,
        code: ProviderErrorCode,
        message: str,
        provider_key: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider_key = provider_key
        self.retryable = retryable


class CancellationToken(Protocol):
    @property
    def cancelled(self) -> bool: ...
