"""Render a parsed OFD document to PDF using PyMuPDF."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

try:  # PyMuPDF >= 1.24.3 is imported as `pymupdf`; `fitz` is deprecated
    import pymupdf as fitz
except ImportError:  # pragma: no cover - older PyMuPDF releases
    import fitz

from .container import OfdPackage
from .fonts import FontRegistry, RegisteredFont
from .model import (Annotation, Color, CompositeObject, Document, DrawParam,
                    GraphicObject, ImageObject, Layer, Matrix, Page, PathObject,
                    TextObject)

MM2PT = 72.0 / 25.4
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

_METRIC_FONTS: Dict[str, Optional[fitz.Font]] = {}


def _metrics_font(registered: RegisteredFont) -> Optional[fitz.Font]:
    """Return (and cache) a :class:`fitz.Font` used for advance measurements."""

    if registered.key in _METRIC_FONTS:
        return _METRIC_FONTS[registered.key]
    font: Optional[fitz.Font] = None
    try:
        if registered.builtin:
            font = fitz.Font(registered.builtin)
        elif registered.fontfile:
            font = fitz.Font(fontfile=registered.fontfile)
        elif registered.fontbuffer:
            font = fitz.Font(fontbuffer=registered.fontbuffer)
    except Exception:
        font = None
    _METRIC_FONTS[registered.key] = font
    return font


def mm2pt(value: float) -> float:
    return value * MM2PT


def compose(outer: Matrix, inner: Matrix) -> Matrix:
    """Return the matrix that applies *inner* first, then *outer*."""

    a1, b1, c1, d1, e1, f1 = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def apply_matrix(matrix: Matrix, x: float, y: float) -> Tuple[float, float]:
    return (matrix[0] * x + matrix[2] * y + matrix[4],
            matrix[1] * x + matrix[3] * y + matrix[5])


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def arc_points(x0: float, y0: float, rx: float, ry: float, angle: float,
               large_arc: float, sweep: float, x1: float, y1: float,
               segments: int = 32) -> List[Tuple[float, float]]:
    """Approximate an elliptical arc with a list of points (SVG algorithm)."""

    if rx == 0 or ry == 0 or (x0 == x1 and y0 == y1):
        return [(x1, y1)]
    phi = math.radians(angle)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    dx2, dy2 = (x0 - x1) / 2.0, (y0 - y1) / 2.0
    x1p = cos_phi * dx2 + sin_phi * dy2
    y1p = -sin_phi * dx2 + cos_phi * dy2
    rx, ry = abs(rx), abs(ry)
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        scale = math.sqrt(lam)
        rx *= scale
        ry *= scale
    sign = -1.0 if (bool(large_arc) == bool(sweep)) else 1.0
    numerator = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    denominator = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coefficient = 0.0
    if denominator > 0:
        coefficient = sign * math.sqrt(max(0.0, numerator / denominator))
    cxp = coefficient * (rx * y1p / ry)
    cyp = coefficient * (-ry * x1p / rx)
    cx = cos_phi * cxp - sin_phi * cyp + (x0 + x1) / 2.0
    cy = sin_phi * cxp + cos_phi * cyp + (y0 + y1) / 2.0

    def angle_between(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        length = math.hypot(ux, uy) * math.hypot(vx, vy)
        if length == 0:
            return 0.0
        value = _clamp(dot / length, -1.0, 1.0)
        result = math.acos(value)
        if ux * vy - uy * vx < 0:
            result = -result
        return result

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    theta1 = angle_between(1.0, 0.0, ux, uy)
    delta = angle_between(ux, uy, vx, vy)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi

    points: List[Tuple[float, float]] = []
    for step in range(1, segments + 1):
        theta = theta1 + delta * step / segments
        px = cos_phi * rx * math.cos(theta) - sin_phi * ry * math.sin(theta) + cx
        py = sin_phi * rx * math.cos(theta) + cos_phi * ry * math.sin(theta) + cy
        points.append((px, py))
    return points


def parse_abbreviated_data(data: str):
    """Parse OFD path data into a list of sub-paths.

    Operators (GB/T 33190-2016): ``S`` start, ``M`` move, ``L`` line,
    ``Q`` quadratic, ``B`` cubic, ``A`` arc, ``C``/``Z`` close.
    """

    tokens = data.replace(",", " ").split()
    subpaths: List[dict] = []
    current: Optional[dict] = None
    current_point = (0.0, 0.0)
    index = 0

    def ensure() -> dict:
        nonlocal current
        if current is None:
            current = {"start": current_point, "segments": []}
            subpaths.append(current)
        return current

    while index < len(tokens):
        operator = tokens[index].upper()
        index += 1
        if operator in ("S", "M"):
            x = float(tokens[index])
            y = float(tokens[index + 1])
            index += 2
            current_point = (x, y)
            current = {"start": (x, y), "segments": []}
            subpaths.append(current)
        elif operator == "L":
            x = float(tokens[index])
            y = float(tokens[index + 1])
            index += 2
            ensure()["segments"].append(("L", (x, y)))
            current_point = (x, y)
        elif operator == "Q":
            values = [float(v) for v in tokens[index:index + 4]]
            index += 4
            ensure()["segments"].append(("Q", tuple(values)))
            current_point = (values[2], values[3])
        elif operator == "B":
            values = [float(v) for v in tokens[index:index + 6]]
            index += 6
            ensure()["segments"].append(("B", tuple(values)))
            current_point = (values[4], values[5])
        elif operator == "A":
            values = [float(v) for v in tokens[index:index + 7]]
            index += 7
            ensure()["segments"].append(("A", tuple(values)))
            current_point = (values[5], values[6])
        elif operator in ("C", "Z"):
            ensure()["segments"].append(("Z", None))
            current_point = current["start"]
        else:
            # Unknown operator: stop parsing to avoid an infinite loop.
            break
    return subpaths


_CAP = {"butt": 0, "round": 1, "square": 2}
_JOIN = {"miter": 0, "round": 1, "bevel": 2}


class PageFonts:
    """Per-page font alias manager."""

    def __init__(self, page: fitz.Page) -> None:
        self.page = page
        self._aliases: Dict[str, str] = {}
        self._counter = 0

    def alias(self, registered: RegisteredFont) -> str:
        if registered.builtin:
            return registered.builtin
        if registered.key in self._aliases:
            return self._aliases[registered.key]
        self._counter += 1
        name = f"OFDF{self._counter}"
        self.page.insert_font(fontname=name, fontfile=registered.fontfile,
                              fontbuffer=registered.fontbuffer)
        self._aliases[registered.key] = name
        return name


class PdfRenderer:
    """Render a :class:`Document` into a :class:`fitz.Document`."""

    def __init__(self, document: Document, package: OfdPackage) -> None:
        self.document = document
        self.package = package
        self.fonts = FontRegistry(document, package)

    # -- public API --------------------------------------------------------
    def render(self) -> fitz.Document:
        pdf = fitz.open()
        for page_model in self.document.pages:
            pdf_page = pdf.new_page(width=mm2pt(page_model.width),
                                    height=mm2pt(page_model.height))
            self._render_page(page_model, pdf_page)
        self._apply_metadata(pdf)
        self._embed_attachments(pdf)
        try:
            pdf.subset_fonts()
        except Exception:
            pass
        return pdf

    # -- page --------------------------------------------------------------
    def _render_page(self, page_model: Page, pdf_page: fitz.Page) -> None:
        fonts = PageFonts(pdf_page)
        for template_id, zorder in page_model.templates:
            if zorder.lower() == "background":
                self._render_template(template_id, pdf_page, fonts)
        for layer in page_model.layers:
            self._render_layer(layer, pdf_page, fonts)
        for template_id, zorder in page_model.templates:
            if zorder.lower() != "background":
                self._render_template(template_id, pdf_page, fonts)
        for annotation in page_model.annotations:
            self._render_annotation(annotation, pdf_page, fonts)

    def _render_annotation(self, annotation: Annotation, pdf_page: fitz.Page,
                           fonts: PageFonts) -> None:
        if not annotation.objects:
            return
        if annotation.boundary:
            offset = (1.0, 0.0, 0.0, 1.0, annotation.boundary[0], annotation.boundary[1])
        else:
            offset = IDENTITY
        layer = Layer()
        for obj in annotation.objects:
            self._render_object(obj, layer, pdf_page, fonts, offset)

    def _render_template(self, template_id: str, pdf_page: fitz.Page,
                         fonts: PageFonts) -> None:
        template = self.document.templates.get(template_id)
        if template is None:
            return
        for layer in template.layers:
            self._render_layer(layer, pdf_page, fonts)

    def _render_layer(self, layer: Layer, pdf_page: fitz.Page,
                      fonts: PageFonts) -> None:
        for obj in layer.objects:
            self._render_object(obj, layer, pdf_page, fonts, IDENTITY)

    # -- dispatch ----------------------------------------------------------
    def _render_object(self, obj: GraphicObject, layer: Layer,
                       pdf_page: fitz.Page, fonts: PageFonts,
                       parent: Matrix) -> None:
        if isinstance(obj, TextObject):
            self._render_text(obj, layer, pdf_page, fonts, parent)
        elif isinstance(obj, PathObject):
            self._render_path(obj, layer, pdf_page, parent)
        elif isinstance(obj, ImageObject):
            self._render_image(obj, pdf_page, parent)
        elif isinstance(obj, CompositeObject):
            matrix = compose(parent, self._object_matrix(obj))
            for child in obj.objects:
                self._render_object(child, layer, pdf_page, fonts, matrix)

    def _object_matrix(self, obj: GraphicObject) -> Matrix:
        bx = obj.boundary[0] if obj.boundary else 0.0
        by = obj.boundary[1] if obj.boundary else 0.0
        if obj.ctm:
            a, b, c, d, e, f = obj.ctm
        else:
            a, b, c, d, e, f = IDENTITY
        return (a, b, c, d, e + bx, f + by)

    def _draw_param(self, obj: GraphicObject, layer: Layer) -> Optional[DrawParam]:
        key = obj.draw_param_id or layer.draw_param_id
        if key:
            return self.document.draw_params.get(key)
        return None

    # -- text --------------------------------------------------------------
    def _render_text(self, obj: TextObject, layer: Layer, pdf_page: fitz.Page,
                     fonts: PageFonts, parent: Matrix) -> None:
        if not obj.codes or not obj.size:
            return
        font = self.fonts.resolve(obj.font_id, obj.all_text())
        alias = fonts.alias(font)
        fontsize = mm2pt(obj.size)

        draw_param = self._draw_param(obj, layer)
        fill_color = obj.fill_color or (draw_param.fill_color if draw_param else None)
        stroke_color = obj.stroke_color or (draw_param.stroke_color if draw_param else None)
        if fill_color is None:
            fill_color = Color("gray", (0.0,), 1.0)

        fill_on = obj.fill is not False and fill_color.visible
        stroke_on = obj.stroke is True and stroke_color is not None and stroke_color.visible
        if not fill_on and not stroke_on:
            return

        if fill_on and stroke_on:
            render_mode, _fill, _stroke = 2, fill_color, stroke_color
        elif stroke_on:
            render_mode, _fill, _stroke = 1, None, stroke_color
        else:
            render_mode, _fill, _stroke = 0, fill_color, None

        hscale = obj.hscale if obj.hscale else 1.0
        char_direction = obj.char_direction % 360
        theta = math.radians(char_direction)
        cos_theta, sin_theta = math.cos(theta), math.sin(theta)
        read_phi = math.radians(obj.read_direction)
        cos_read, sin_read = math.cos(read_phi), math.sin(read_phi)
        metric_font = _metrics_font(font)

        matrix = compose(parent, self._object_matrix(obj))
        # Glyph outlines must be transformed by the object's CTM (and any parent
        # transform), not just their positions -- otherwise a scaling CTM leaves
        # the advances scaled but the glyphs full width, so they overlap.
        linear = (matrix[0], matrix[1], matrix[2], matrix[3], 0.0, 0.0)

        for code in obj.codes:
            has_delta = bool(code.delta_x) or bool(code.delta_y)
            cursor_x = code.x
            cursor_y = code.y
            advance_x = code.delta_x[-1] if code.delta_x else 0.0
            advance_y = code.delta_y[-1] if code.delta_y else 0.0
            for i, character in enumerate(code.text):
                natural_mm = None
                if metric_font is not None:
                    try:
                        natural_mm = metric_font.text_length(
                            character, fontsize=fontsize) / MM2PT
                    except Exception:
                        natural_mm = None

                if has_delta:
                    base = code.delta_x[i] if i < len(code.delta_x) else advance_x
                    offset = code.delta_y[i] if i < len(code.delta_y) else advance_y
                elif natural_mm is not None:
                    base = natural_mm * hscale
                    offset = 0.0
                else:
                    base = (fontsize / MM2PT) * hscale
                    offset = 0.0

                # `DeltaX` is the advance along the baseline, so the reading and
                # character directions turn it: ReadDirection 90 reads
                # bottom-to-top, 180 right-to-left, 270 top-to-bottom, and
                # CharDirection slants the run.  Previously an explicit DeltaX
                # ignored both, so `ReadDirection="90"` (the usual encoding of
                # rotated text) came out horizontal and slanted text overlapped.
                # `DeltaY` stays a page-axis offset, which is how vertical runs
                # step from glyph to glyph.
                phi = read_phi + theta
                step_x = base * math.cos(phi)
                step_y = -base * math.sin(phi) + offset

                if character not in (" ", "\u3000"):
                    # Compress a glyph whose natural width exceeds the advance the
                    # document gives it (e.g. proportional Latin in a CJK font asked
                    # to be half width), so glyphs never overlap.  Only applies when
                    # there is an explicit advance and a following glyph: the last
                    # glyph of a run has no width constraint.
                    fit = 1.0
                    if (has_delta and i < len(code.delta_x)
                            and i < len(code.text) - 1
                            and natural_mm and abs(base) > 1e-9):
                        natural_eff = natural_mm * hscale
                        if natural_eff > abs(base) * 1.001:
                            fit = abs(base) / natural_eff
                    glyph = compose(linear, (cos_theta * hscale * fit,
                                             sin_theta * hscale * fit,
                                             -sin_theta, cos_theta, 0.0, 0.0))
                    px, py = apply_matrix(matrix, cursor_x, cursor_y)
                    morph = None
                    if any(abs(glyph[k] - IDENTITY[k]) > 1e-9 for k in range(4)):
                        # PyMuPDF's morph matrix is the transpose of the usual
                        # (a b c d) convention, so swap b and c.
                        morph = (fitz.Point(mm2pt(px), mm2pt(py)),
                                 fitz.Matrix(glyph[0], glyph[2], glyph[1], glyph[3], 0, 0))
                    pdf_page.insert_text(
                        (mm2pt(px), mm2pt(py)),
                        character,
                        fontname=alias,
                        fontsize=fontsize,
                        render_mode=render_mode,
                        fill=_fill.to_rgb() if _fill else None,
                        color=_stroke.to_rgb() if _stroke else None,
                        fill_opacity=_fill.alpha if _fill else 1.0,
                        stroke_opacity=_stroke.alpha if _stroke else 1.0,
                        morph=morph,
                    )
                cursor_x += step_x
                cursor_y += step_y

    # -- paths -------------------------------------------------------------
    def _render_path(self, obj: PathObject, layer: Layer, pdf_page: fitz.Page,
                     parent: Matrix) -> None:
        if not obj.data or not obj.boundary:
            return
        draw_param = self._draw_param(obj, layer)
        stroke_color = obj.stroke_color or (draw_param.stroke_color if draw_param else None)
        fill_color = obj.fill_color or (draw_param.fill_color if draw_param else None)
        if stroke_color is None and obj.stroke is not False:
            stroke_color = Color("gray", (0.0,), 1.0)

        fill_on = obj.fill is not False and fill_color is not None and fill_color.visible
        stroke_on = obj.stroke is not False and stroke_color is not None and stroke_color.visible
        if not fill_on and not stroke_on:
            return

        line_width = obj.line_width
        if line_width is None and draw_param is not None:
            line_width = draw_param.line_width
        if line_width is None:
            line_width = 0.353

        matrix = compose(parent, self._object_matrix(obj))

        def point(x: float, y: float):
            px, py = apply_matrix(matrix, x, y)
            return (mm2pt(px), mm2pt(py))

        shape = pdf_page.new_shape()
        for subpath in parse_abbreviated_data(obj.data):
            previous = subpath["start"]
            for kind, params in subpath["segments"]:
                if kind == "L":
                    shape.draw_line(point(*previous), point(*params))
                    previous = params
                elif kind == "Q":
                    x1, y1, x2, y2 = params
                    c1 = (previous[0] + 2.0 / 3.0 * (x1 - previous[0]),
                          previous[1] + 2.0 / 3.0 * (y1 - previous[1]))
                    c2 = (x2 + 2.0 / 3.0 * (x1 - x2), y2 + 2.0 / 3.0 * (y1 - y2))
                    shape.draw_bezier(point(*previous), point(*c1), point(*c2), point(x2, y2))
                    previous = (x2, y2)
                elif kind == "B":
                    x1, y1, x2, y2, x3, y3 = params
                    shape.draw_bezier(point(*previous), point(x1, y1),
                                      point(x2, y2), point(x3, y3))
                    previous = (x3, y3)
                elif kind == "A":
                    rx, ry, angle, large, sweep, x, y = params
                    for pt in arc_points(previous[0], previous[1], rx, ry, angle,
                                         large, sweep, x, y):
                        shape.draw_line(point(*previous), point(*pt))
                        previous = pt
                elif kind == "Z":
                    shape.draw_line(point(*previous), point(*subpath["start"]))
                    previous = subpath["start"]

        dashes = None
        if draw_param is not None and draw_param.dash_pattern:
            values = " ".join(f"{mm2pt(v):g}" for v in draw_param.dash_pattern)
            dashes = f"[{values}] {mm2pt(draw_param.dash_offset):g}"

        shape.finish(
            color=stroke_color.to_rgb() if stroke_on else None,
            fill=fill_color.to_rgb() if fill_on else None,
            width=mm2pt(line_width),
            lineCap=_CAP.get((draw_param.cap if draw_param else "Butt").lower(), 0),
            lineJoin=_JOIN.get((draw_param.join if draw_param else "Miter").lower(), 0),
            dashes=dashes,
            even_odd=obj.rule.lower() in ("even-odd", "evenodd"),
            closePath=False,
            fill_opacity=fill_color.alpha if (fill_on and fill_color) else 1.0,
            stroke_opacity=stroke_color.alpha if (stroke_on and stroke_color) else 1.0,
        )
        shape.commit()

    # -- images ------------------------------------------------------------
    def _render_image(self, obj: ImageObject, pdf_page: fitz.Page,
                      parent: Matrix) -> None:
        media = self.document.medias.get(obj.resource_id)
        if media is None or not media.path or not self.package.has(media.path):
            return
        if not obj.boundary:
            return
        x, y, w, h = obj.boundary
        p0 = apply_matrix(parent, x, y)
        p1 = apply_matrix(parent, x + w, y + h)
        rect = fitz.Rect(mm2pt(p0[0]), mm2pt(p0[1]), mm2pt(p1[0]), mm2pt(p1[1]))
        if rect.is_empty:
            return
        data = self.package.read(media.path)
        try:
            pdf_page.insert_image(rect, stream=data, keep_proportion=False)
        except Exception:
            converted = self._convert_image(data)
            if converted is not None:
                pdf_page.insert_image(rect, stream=converted, keep_proportion=False)

    @staticmethod
    def _convert_image(data: bytes) -> Optional[bytes]:
        try:
            import io

            from PIL import Image
        except Exception:
            return None
        try:
            with Image.open(io.BytesIO(data)) as image:
                buffer = io.BytesIO()
                image.convert("RGBA").save(buffer, format="PNG")
                return buffer.getvalue()
        except Exception:
            return None

    # -- document level ----------------------------------------------------
    def _apply_metadata(self, pdf: fitz.Document) -> None:
        meta = self.document.metadata
        values = {}
        if meta.get("Title"):
            values["title"] = meta["Title"]
        if meta.get("Author"):
            values["author"] = meta["Author"]
        if meta.get("Subject"):
            values["subject"] = meta["Subject"]
        if meta.get("CreationDate"):
            values["creationDate"] = meta["CreationDate"]
        if meta.get("Creator"):
            values["creator"] = meta["Creator"]
        if values:
            pdf.set_metadata(values)

    def _embed_attachments(self, pdf: fitz.Document) -> None:
        for attachment in self.document.attachments:
            if not attachment.path or not self.package.has(attachment.path):
                continue
            try:
                name = attachment.name or attachment.path.rsplit("/", 1)[-1]
                pdf.embfile_add(name, self.package.read(attachment.path))
            except Exception:
                continue


def render_to_pdf(document: Document, package: OfdPackage) -> fitz.Document:
    return PdfRenderer(document, package).render()
