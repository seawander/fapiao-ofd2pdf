"""Exceptions raised by :mod:`ofd2pdf`."""

from __future__ import annotations


class OfdError(Exception):
    """Base class for all OFD related errors."""


class OfdFormatError(OfdError):
    """Raised when an OFD package is malformed or cannot be understood."""


class OfdNotFoundError(OfdError):
    """Raised when a referenced entry is missing from the OFD package."""
