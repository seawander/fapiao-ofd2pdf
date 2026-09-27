"""Low level access to an OFD package (a ZIP container).

An OFD file is a ZIP archive whose entries are XML documents and resources.
This module wraps :mod:`zipfile` and provides small, namespace tolerant XML
helpers.  OFD documents are defined by ``GB/T 33190-2016``.
"""

from __future__ import annotations

import posixpath
import zipfile
from typing import Iterable, List, Optional
from xml.etree import ElementTree as ET

OFD_NS = "http://www.ofdspec.org/2016"


def local_name(tag: str) -> str:
    """Return the local (namespace stripped) name of an XML tag."""

    return tag.rsplit("}", 1)[-1]


def parse_xml(data: bytes) -> ET.Element:
    """Parse XML bytes into an :class:`ElementTree.Element`."""

    return ET.fromstring(data)


def child(element: ET.Element, name: str) -> Optional[ET.Element]:
    """Return the first direct child whose local name is *name*."""

    for node in element:
        if local_name(node.tag) == name:
            return node
    return None


def children(element: ET.Element, name: str) -> List[ET.Element]:
    """Return all direct children whose local name is *name*."""

    return [node for node in element if local_name(node.tag) == name]


def descendants(element: ET.Element, name: str) -> List[ET.Element]:
    """Return all descendant elements (in document order) named *name*."""

    return [node for node in element.iter() if local_name(node.tag) == name]


def text_of(element: ET.Element, name: str, default: Optional[str] = None) -> Optional[str]:
    """Return the stripped text of the first child named *name*."""

    node = child(element, name)
    if node is None or node.text is None:
        return default
    value = node.text.strip()
    return value if value else default


def resolve_loc(base_dir: str, loc: str) -> str:
    """Resolve an OFD ``ST_Loc`` against the directory *base_dir*.

    A leading ``/`` means "relative to the package root", otherwise the path
    is relative to the directory of the referencing file.  Paths always use
    forward slashes and are case sensitive.
    """

    loc = loc.strip().replace("\\", "/")
    if loc.startswith("/"):
        return posixpath.normpath(loc[1:])
    if not base_dir:
        return posixpath.normpath(loc)
    return posixpath.normpath(posixpath.join(base_dir, loc))


class OfdPackage:
    """Read-only view over the entries of an OFD (ZIP) file."""

    ENTRY_POINT = "OFD.xml"

    def __init__(self, path: str) -> None:
        self.path = str(path)
        self._zip = zipfile.ZipFile(self.path)
        self._names = set(self._zip.namelist())

    def namelist(self) -> List[str]:
        return list(self._names)

    def has(self, name: str) -> bool:
        return name in self._names

    def read(self, name: str) -> bytes:
        return self._zip.read(name)

    def read_xml(self, name: str) -> ET.Element:
        return parse_xml(self._zip.read(name))

    def close(self) -> None:
        self._zip.close()

    def __enter__(self) -> "OfdPackage":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def first_existing(package: OfdPackage, candidates: Iterable[str]) -> Optional[str]:
    """Return the first candidate that exists in the package."""

    for candidate in candidates:
        if package.has(candidate):
            return candidate
    return None
