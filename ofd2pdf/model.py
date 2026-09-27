"""In-memory representation of the parts of an OFD document we render."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Boundary = Tuple[float, float, float, float]
Matrix = Tuple[float, float, float, float, float, float]


@dataclass
class Color:
    """An OFD colour.

    *space* is one of ``gray``, ``rgb`` or ``cmyk`` and *values* holds the
    original components normalised to ``0..1``.  *alpha* is likewise ``0..1``.
    """

    space: str
    values: Tuple[float, ...]
    alpha: float = 1.0

    @property
    def visible(self) -> bool:
        return self.alpha > 0.0

    def to_rgb(self) -> Tuple[float, float, float]:
        if self.space == "gray":
            value = self.values[0]
            return (value, value, value)
        if self.space == "cmyk":
            c, m, y, k = self.values
            return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
        r, g, b = self.values[:3]
        return (r, g, b)


@dataclass
class DrawParam:
    """Reusable drawing attributes (``CT_DrawParam``)."""

    id: str = ""
    line_width: Optional[float] = None
    stroke_color: Optional[Color] = None
    fill_color: Optional[Color] = None
    dash_pattern: Tuple[float, ...] = ()
    dash_offset: float = 0.0
    cap: str = "Butt"
    join: str = "Miter"
    miter_limit: float = 10.0


@dataclass
class FontRes:
    """A font declared in ``PublicRes.xml``."""

    id: str = ""
    font_name: str = ""
    family_name: str = ""
    embedded_path: Optional[str] = None
    bold: bool = False
    italic: bool = False
    serif: bool = False
    fixed_width: bool = False


@dataclass
class MediaRes:
    """A multimedia resource declared in ``DocumentRes.xml``."""

    id: str = ""
    type: str = ""
    format: str = ""
    path: Optional[str] = None


@dataclass
class TextCode:
    """A run of glyphs with explicit positioning (``CT_TextCode``)."""

    x: float = 0.0
    y: float = 0.0
    text: str = ""
    delta_x: List[float] = field(default_factory=list)
    delta_y: List[float] = field(default_factory=list)


@dataclass
class GraphicObject:
    """Attributes shared by every graphic object."""

    id: str = ""
    boundary: Optional[Boundary] = None
    ctm: Optional[Matrix] = None
    draw_param_id: Optional[str] = None
    line_width: Optional[float] = None
    fill: Optional[bool] = None
    stroke: Optional[bool] = None
    fill_color: Optional[Color] = None
    stroke_color: Optional[Color] = None
    rule: str = "NonZero"


@dataclass
class TextObject(GraphicObject):
    font_id: str = ""
    size: float = 0.0
    hscale: float = 1.0
    read_direction: int = 0
    char_direction: int = 0
    codes: List[TextCode] = field(default_factory=list)

    def all_text(self) -> str:
        return "".join(code.text for code in self.codes)


@dataclass
class PathObject(GraphicObject):
    data: str = ""


@dataclass
class ImageObject(GraphicObject):
    resource_id: str = ""
    image_mask: Optional[str] = None
    substitution: Optional[str] = None


@dataclass
class CompositeObject(GraphicObject):
    objects: List[GraphicObject] = field(default_factory=list)


@dataclass
class Layer:
    type: str = ""
    draw_param_id: Optional[str] = None
    objects: List[GraphicObject] = field(default_factory=list)


@dataclass
class Annotation:
    id: str = ""
    type: str = ""
    subtype: str = ""
    boundary: Optional[Boundary] = None
    objects: List[GraphicObject] = field(default_factory=list)


@dataclass
class Page:
    id: str = ""
    width: float = 0.0
    height: float = 0.0
    layers: List[Layer] = field(default_factory=list)
    templates: List[Tuple[str, str]] = field(default_factory=list)
    annotations: List[Annotation] = field(default_factory=list)


@dataclass
class Attachment:
    id: str = ""
    name: str = ""
    format: str = ""
    path: Optional[str] = None


@dataclass
class Document:
    version: str = ""
    doc_type: str = "OFD"
    metadata: Dict[str, str] = field(default_factory=dict)
    page_area: Tuple[float, float] = (210.0, 297.0)
    draw_params: Dict[str, DrawParam] = field(default_factory=dict)
    fonts: Dict[str, FontRes] = field(default_factory=dict)
    medias: Dict[str, MediaRes] = field(default_factory=dict)
    templates: Dict[str, Page] = field(default_factory=dict)
    pages: List[Page] = field(default_factory=list)
    attachments: List[Attachment] = field(default_factory=list)
