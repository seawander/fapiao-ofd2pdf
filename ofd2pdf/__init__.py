"""Convert OFD (GB/T 33190-2016) documents to PDF.

Typical usage::

    from ofd2pdf import convert

    convert("invoice.ofd", "invoice.pdf")
"""

from __future__ import annotations

from . import macos
from .converter import convert, convert_bytes, open_pdf
from .exceptions import OfdError, OfdFormatError, OfdNotFoundError

__version__ = "0.4.1"

__all__ = [
    "convert",
    "convert_bytes",
    "open_pdf",
    "macos",
    "OfdError",
    "OfdFormatError",
    "OfdNotFoundError",
    "__version__",
]
