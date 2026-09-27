"""Resolve OFD fonts to something MuPDF can draw with.

Resolution order for a given OFD ``Font``:

1. an embedded font file (``FontFile``), read from the OFD package;
2. a system font matched by ``FontName``/``FamilyName`` aliases;
3. a built-in fallback (a CJK font for CJK text, a base-14 font otherwise).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .container import OfdPackage
from .model import Document, FontRes

CJK_BUILTIN = "china-s"

# Regular-weight CJK fonts to prefer when a referenced font is not installed.
# PyMuPDF's built-in CJK font renders noticeably heavy, so we look for a normal
# system font first and only fall back to the built-in one as a last resort.
CJK_FALLBACK_FONTS = [
    "PingFang SC",
    "STHeiti Light",
    "Heiti SC",
    "Songti SC",
    "Songti",
    "Hiragino Sans GB",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
]

_FONT_DIRS = (
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/usr/share/fonts/truetype",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/.local/share/fonts"),
    "C:\\Windows\\Fonts",
)

_FONT_SUFFIXES = (".ttf", ".ttc", ".otf", ".otc")

# OFD font name -> ordered list of system font family names to look for.
FONT_ALIASES: Dict[str, List[str]] = {
    "宋体": ["Songti SC", "Songti", "STSong", "SimSun", "Noto Serif CJK SC"],
    "simsun": ["SimSun", "Songti", "STSong", "Noto Serif CJK SC"],
    "新宋体": ["SimSun", "Songti", "Noto Serif CJK SC"],
    "黑体": ["PingFang SC", "STHeiti Light", "Heiti SC", "SimHei", "Noto Sans CJK SC"],
    "simhei": ["SimHei", "PingFang SC", "STHeiti Light", "Noto Sans CJK SC"],
    "楷体": ["Kaiti SC", "STKaiti", "KaiTi", "PingFang SC", "STHeiti Light"],
    "kaiti": ["KaiTi", "Kaiti SC", "STKaiti", "STHeiti Light"],
    "仿宋": ["STFangsong", "FangSong", "Songti SC", "Noto Serif CJK SC"],
    "仿宋_gb2312": ["STFangsong", "FangSong"],
    "微软雅黑": ["Microsoft YaHei", "PingFang SC", "STHeiti Light", "Noto Sans CJK SC"],
    "微软雅黑light": ["Microsoft YaHei", "PingFang SC", "STHeiti Light"],
    "等线": ["DengXian", "PingFang SC", "STHeiti Light"],
    "方正书宋": ["Songti SC", "Songti", "Noto Serif CJK SC"],
    "方正黑体": ["PingFang SC", "STHeiti Light", "Heiti SC", "Noto Sans CJK SC"],
    "方正楷体": ["Kaiti SC", "STKaiti", "STHeiti Light"],
    "times new roman": ["Times New Roman", "Times"],
    "times": ["Times", "Times New Roman"],
    "courier new": ["Courier New", "Courier"],
    "courier": ["Courier", "Courier New"],
    "arial": ["Arial", "Helvetica"],
    "helvetica": ["Helvetica", "Arial"],
    "calibri": ["Calibri", "Carlito", "Arial"],
    "symbol": ["Symbol"],
}

_CJK_RANGES = (
    (0x2E80, 0x2EFF),
    (0x3000, 0x303F),
    (0x3040, 0x30FF),
    (0x3100, 0x312F),
    (0x31F0, 0x31FF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xAC00, 0xD7AF),
    (0xF900, 0xFAFF),
    (0xFE30, 0xFE4F),
    (0xFF00, 0xFFEF),
)


def has_cjk(text: str) -> bool:
    for char in text:
        code = ord(char)
        for low, high in _CJK_RANGES:
            if low <= code <= high:
                return True
    return False


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


# Font families we avoid by default so text is not rendered bold/black.
_HEAVY_WEIGHTS = ("bold", "medium", "semibold", "black", "heavy", "ultra", "extrabold")


def _weight_penalty(name: str) -> int:
    return 1 if any(weight in name for weight in _HEAVY_WEIGHTS) else 0


@dataclass
class RegisteredFont:
    """A concrete font ready to be handed to MuPDF."""

    key: str
    fontfile: Optional[str] = None
    fontbuffer: Optional[bytes] = None
    builtin: Optional[str] = None


class SystemFontIndex:
    """Lazily built index of installed font files, keyed by normalised name."""

    def __init__(self, directories: Iterable[str] = _FONT_DIRS) -> None:
        self._directories = list(directories)
        self._index: Optional[Dict[str, str]] = None

    def _build(self) -> None:
        index: Dict[str, str] = {}
        for directory in self._directories:
            if not os.path.isdir(directory):
                continue
            for root, _dirs, files in os.walk(directory):
                for name in files:
                    if not name.lower().endswith(_FONT_SUFFIXES):
                        continue
                    base = os.path.splitext(name)[0]
                    key = _normalize(base)
                    index.setdefault(key, os.path.join(root, name))
        self._index = index

    def find(self, candidates: Iterable[str]) -> Optional[str]:
        if self._index is None:
            self._build()
        assert self._index is not None
        for candidate in candidates:
            key = _normalize(candidate)
            if key and key in self._index:
                return self._index[key]
        for candidate in candidates:
            key = _normalize(candidate)
            if not key:
                continue
            matches = [
                (indexed_key, path)
                for indexed_key, path in self._index.items()
                if key in indexed_key or indexed_key in key
            ]
            if matches:
                # Prefer a regular/light face over a bold/medium one.
                matches.sort(key=lambda item: _weight_penalty(item[0]))
                return matches[0][1]
        return None


class FontRegistry:
    """Resolve :class:`FontRes` objects (and fallbacks) to usable fonts."""

    def __init__(self, document: Document, package: OfdPackage) -> None:
        self.document = document
        self.package = package
        self._system = SystemFontIndex()
        self._cache: Dict[str, RegisteredFont] = {}

    def resolve(self, font_id: str, text: str) -> RegisteredFont:
        font = self.document.fonts.get(font_id)
        if font is not None:
            embedded = self._embedded(font)
            if embedded is not None:
                return embedded
            system = self._system_for(font)
            if system is not None:
                return system
        return self._fallback(text)

    def _embedded(self, font: FontRes) -> Optional[RegisteredFont]:
        path = font.embedded_path
        if not path or not self.package.has(path):
            return None
        if path in self._cache:
            return self._cache[path]
        registered = RegisteredFont(key="embedded:" + path, fontbuffer=self.package.read(path))
        self._cache[path] = registered
        return registered

    def _system_for(self, font: FontRes) -> Optional[RegisteredFont]:
        candidates: List[str] = []
        for raw in (font.font_name, font.family_name):
            if not raw:
                continue
            candidates.extend(FONT_ALIASES.get(raw.strip().lower(), [raw]))
        if not candidates:
            return None
        path = self._system.find(candidates)
        if not path:
            return None
        if path in self._cache:
            return self._cache[path]
        registered = RegisteredFont(key="system:" + path, fontfile=path)
        self._cache[path] = registered
        return registered

    def _fallback(self, text: str) -> RegisteredFont:
        if has_cjk(text):
            path = self._system.find(CJK_FALLBACK_FONTS)
            if path:
                if path not in self._cache:
                    self._cache[path] = RegisteredFont(
                        key="system:" + path, fontfile=path)
                return self._cache[path]
            key = "builtin:" + CJK_BUILTIN
            if key not in self._cache:
                self._cache[key] = RegisteredFont(key=key, builtin=CJK_BUILTIN)
            return self._cache[key]
        key = "builtin:helv"
        if key not in self._cache:
            self._cache[key] = RegisteredFont(key=key, builtin="helv")
        return self._cache[key]
