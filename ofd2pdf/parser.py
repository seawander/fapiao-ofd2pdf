"""Parse an OFD package into the :mod:`ofd2pdf.model` structures."""

from __future__ import annotations

import posixpath
import re
from typing import List, Optional, Tuple
from xml.etree import ElementTree as ET

from .container import (OfdPackage, child, children, descendants, local_name,
                        resolve_loc, text_of)
from .exceptions import OfdFormatError
from .model import (Annotation, Attachment, Color, CompositeObject, Document,
                    DrawParam, FontRes, GraphicObject, ImageObject, Layer,
                    MediaRes, Page, PathObject, TextCode, TextObject)

_HEX_ESCAPE = re.compile(r"\\([0-9A-Fa-f]{4})")


def decode_text(value: Optional[str]) -> str:
    r"""Decode OFD text escapes.

    Characters outside the XML range and spaces are written as a backslash
    followed by four hexadecimal digits (for example ``\0020`` for a space).
    """

    if not value:
        return ""
    return _HEX_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), value)


def parse_floats(value: Optional[str]) -> List[float]:
    if not value:
        return []
    return [float(token) for token in value.replace(",", " ").split()]


def parse_box(value: Optional[str]):
    if not value:
        return None
    numbers = parse_floats(value)
    if len(numbers) < 4:
        return None
    x, y, w, h = numbers[:4]
    if w <= 0 or h <= 0:
        return None
    return (x, y, w, h)


def parse_ctm(value: Optional[str]):
    if not value:
        return None
    numbers = parse_floats(value)
    return tuple(numbers[:6]) if len(numbers) >= 6 else None


def parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    return value.strip().lower() == "true"


def parse_array(value: Optional[str]) -> tuple:
    return tuple(parse_floats(value))


def parse_color(element: Optional[ET.Element]) -> Optional[Color]:
    if element is None:
        return None
    raw = element.get("Value")
    if raw is None:
        return None
    numbers = parse_floats(raw)
    if not numbers:
        return None
    alpha = 1.0
    raw_alpha = element.get("Alpha")
    if raw_alpha is not None:
        try:
            alpha = max(0.0, min(1.0, float(raw_alpha) / 255.0))
        except ValueError:
            alpha = 1.0
    values = tuple(number / 255.0 for number in numbers)
    if len(numbers) == 1:
        space = "gray"
    elif len(numbers) == 3:
        space = "rgb"
    elif len(numbers) == 4:
        space = "cmyk"
    else:
        space = "rgb"
        values = values[:3]
    return Color(space=space, values=values, alpha=alpha)


def parse_delta_array(value: Optional[str]) -> List[float]:
    """Parse a ``DeltaX``/``DeltaY`` array, supporting the ``g`` repeat form."""

    if not value:
        return []
    tokens = value.split()
    result: List[float] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("g", "G"):
            index += 1
            if index >= len(tokens):
                break
            try:
                count = int(float(tokens[index]))
            except ValueError:
                break
            index += 1
            pattern: List[float] = []
            while index < len(tokens) and tokens[index] not in ("g", "G"):
                try:
                    pattern.append(float(tokens[index]))
                except ValueError:
                    pass
                index += 1
            if not pattern:
                continue
            for step in range(count):
                result.append(pattern[step % len(pattern)])
        else:
            try:
                result.append(float(token))
            except ValueError:
                pass
            index += 1
    return result


class OfdParser:
    """Turn an :class:`OfdPackage` into a :class:`Document`."""

    def __init__(self, package: OfdPackage) -> None:
        self.pkg = package
        self.doc = Document()

    # -- top level ---------------------------------------------------------
    def parse(self) -> Document:
        root = self.pkg.read_xml(OfdPackage.ENTRY_POINT)
        self.doc.version = root.get("Version", "")
        self.doc.doc_type = root.get("DocType", "OFD")

        doc_root = None
        for body in children(root, "DocBody"):
            location = text_of(body, "DocRoot")
            if location:
                doc_root = location
                self._parse_doc_info(body)
                break
        if not doc_root:
            raise OfdFormatError("OFD.xml does not reference a document root")

        document_entry = resolve_loc("", doc_root)
        if not self.pkg.has(document_entry):
            raise OfdFormatError(f"missing document root: {document_entry}")
        document_dir = posixpath.dirname(document_entry)

        document = self.pkg.read_xml(document_entry)
        common = child(document, "CommonData")
        if common is not None:
            self._parse_common(common, document_dir)

        pages_node = child(document, "Pages")
        if pages_node is not None:
            for page_node in children(pages_node, "Page"):
                location = page_node.get("BaseLoc")
                if not location:
                    continue
                entry = resolve_loc(document_dir, location)
                self.doc.pages.append(
                    self._parse_page_content(entry, page_node.get("ID", ""))
                )
        if not self.doc.pages:
            raise OfdFormatError("document does not define any page")

        annotations = child(document, "Annotations")
        if annotations is not None and annotations.text:
            entry = resolve_loc(document_dir, annotations.text)
            if self.pkg.has(entry):
                self._parse_annotations(entry)

        attachments = child(document, "Attachments")
        if attachments is not None and attachments.text:
            entry = resolve_loc(document_dir, attachments.text)
            if self.pkg.has(entry):
                self._parse_attachments(entry)
        return self.doc

    def _parse_doc_info(self, body: ET.Element) -> None:
        info = child(body, "DocInfo")
        if info is None:
            return
        for key in ("Title", "Author", "Subject", "Abstract", "CreationDate",
                    "ModDate", "Creator", "CreatorVersion"):
            value = text_of(info, key)
            if value:
                self.doc.metadata[key] = value

    def _parse_common(self, common: ET.Element, document_dir: str) -> None:
        area = child(common, "PageArea")
        if area is not None:
            box = parse_box(text_of(area, "PhysicalBox"))
            if box:
                self.doc.page_area = (box[2], box[3])

        public_res = text_of(common, "PublicRes")
        if public_res:
            entry = resolve_loc(document_dir, public_res)
            if self.pkg.has(entry):
                self._parse_res_entry(entry)

        document_res = text_of(common, "DocumentRes")
        if document_res:
            entry = resolve_loc(document_dir, document_res)
            if self.pkg.has(entry):
                self._parse_res_entry(entry)

        for template in children(common, "TemplatePage"):
            template_id = template.get("ID")
            location = template.get("BaseLoc")
            if not template_id or not location:
                continue
            entry = resolve_loc(document_dir, location)
            if self.pkg.has(entry):
                self.doc.templates[template_id] = self._parse_page_content(entry, template_id)

    # -- resources ---------------------------------------------------------
    def _parse_res_entry(self, entry: str) -> None:
        root = self.pkg.read_xml(entry)
        self._parse_res_element(root, posixpath.dirname(entry))

    def _parse_res_element(self, root: ET.Element, base_dir: str) -> None:
        res_base = root.get("BaseLoc") or ""
        res_dir = resolve_loc(base_dir, res_base) if res_base else base_dir

        for param in descendants(root, "DrawParam"):
            parsed = self._parse_draw_param(param)
            if parsed.id:
                self.doc.draw_params[parsed.id] = parsed

        for font in descendants(root, "Font"):
            parsed_font = FontRes(
                id=font.get("ID", ""),
                font_name=font.get("FontName") or font.get("FamilyName") or "",
                family_name=font.get("FamilyName", ""),
                bold=parse_bool(font.get("Bold")) or False,
                italic=parse_bool(font.get("Italic")) or False,
                serif=parse_bool(font.get("Serif")) or False,
                fixed_width=parse_bool(font.get("FixedWidth")) or False,
            )
            font_file = child(font, "FontFile")
            if font_file is not None and font_file.text:
                parsed_font.embedded_path = resolve_loc(res_dir, font_file.text)
            if parsed_font.id:
                self.doc.fonts[parsed_font.id] = parsed_font

        for media in descendants(root, "MultiMedia"):
            media_file = child(media, "MediaFile")
            path = None
            if media_file is not None and media_file.text:
                path = resolve_loc(res_dir, media_file.text)
            parsed_media = MediaRes(
                id=media.get("ID", ""),
                type=media.get("Type", ""),
                format=media.get("Format", ""),
                path=path,
            )
            if parsed_media.id:
                self.doc.medias[parsed_media.id] = parsed_media

    def _parse_draw_param(self, element: ET.Element) -> DrawParam:
        param = DrawParam(id=element.get("ID", ""))
        line_width = element.get("LineWidth")
        if line_width:
            try:
                param.line_width = float(line_width)
            except ValueError:
                pass
        param.dash_pattern = parse_array(element.get("DashPattern"))
        dash_offset = element.get("DashOffset")
        if dash_offset:
            try:
                param.dash_offset = float(dash_offset)
            except ValueError:
                pass
        param.cap = element.get("Cap", "Butt")
        param.join = element.get("Join", "Miter")
        miter = element.get("MiterLimit")
        if miter:
            try:
                param.miter_limit = float(miter)
            except ValueError:
                pass
        param.stroke_color = parse_color(child(element, "StrokeColor"))
        param.fill_color = parse_color(child(element, "FillColor"))
        return param

    # -- page content ------------------------------------------------------
    def _parse_page_content(self, entry: str, page_id: str) -> Page:
        if not self.pkg.has(entry):
            raise OfdFormatError(f"missing page content: {entry}")
        root = self.pkg.read_xml(entry)
        base_dir = posixpath.dirname(entry)
        page = Page(id=page_id)

        for res in children(root, "Res"):
            self._parse_res_element(res, base_dir)

        area = child(root, "Area")
        if area is not None:
            box = parse_box(text_of(area, "PhysicalBox"))
            if box:
                page.width, page.height = box[2], box[3]
        if not page.width or not page.height:
            page.width, page.height = self.doc.page_area

        for template in children(root, "Template"):
            page.templates.append(
                (template.get("TemplateID", ""), template.get("ZOrder", "Background"))
            )

        content = child(root, "Content")
        if content is not None:
            for layer in children(content, "Layer"):
                page.layers.append(self._parse_layer(layer))
        return page

    def _parse_layer(self, element: ET.Element) -> Layer:
        layer = Layer(
            type=element.get("Type", ""),
            draw_param_id=element.get("DrawParam"),
        )
        for node in element:
            parsed = self._parse_object(node)
            if parsed is not None:
                layer.objects.append(parsed)
        return layer

    def _parse_object(self, node: ET.Element):
        name = local_name(node.tag)
        if name == "TextObject":
            return self._parse_text(node)
        if name == "PathObject":
            return self._parse_path(node)
        if name == "ImageObject":
            return self._parse_image(node)
        if name == "CompositeObject":
            return self._parse_composite(node)
        return None

    def _parse_common_object(self, node: ET.Element, obj: GraphicObject) -> None:
        obj.id = node.get("ID", "")
        obj.boundary = parse_box(node.get("Boundary"))
        obj.ctm = parse_ctm(node.get("CTM"))
        obj.draw_param_id = node.get("DrawParam")
        line_width = node.get("LineWidth")
        if line_width:
            try:
                obj.line_width = float(line_width)
            except ValueError:
                pass
        obj.fill = parse_bool(node.get("Fill"))
        obj.stroke = parse_bool(node.get("Stroke"))
        obj.fill_color = parse_color(child(node, "FillColor"))
        obj.stroke_color = parse_color(child(node, "StrokeColor"))
        obj.rule = node.get("FillRule") or node.get("Rule") or "NonZero"

    def _parse_text(self, node: ET.Element) -> TextObject:
        obj = TextObject()
        self._parse_common_object(node, obj)
        obj.font_id = node.get("Font", "")
        size = node.get("Size")
        if size:
            try:
                obj.size = float(size)
            except ValueError:
                pass
        hscale = node.get("HScale")
        if hscale:
            try:
                obj.hscale = float(hscale)
            except ValueError:
                pass
        obj.read_direction = int(node.get("ReadDirection") or 0)
        obj.char_direction = int(node.get("CharDirection") or 0)
        obj.codes = self._parse_text_codes(node)
        return obj

    def _parse_text_codes(self, node: ET.Element) -> List[TextCode]:
        codes: List[TextCode] = []
        last_x: Optional[float] = None
        last_y: Optional[float] = None
        for element in children(node, "TextCode"):
            raw_x = element.get("X")
            raw_y = element.get("Y")
            if raw_x is not None:
                last_x = float(raw_x)
            if raw_y is not None:
                last_y = float(raw_y)
            code = TextCode(
                x=last_x or 0.0,
                y=last_y or 0.0,
                text=decode_text(element.text),
                delta_x=parse_delta_array(element.get("DeltaX")),
                delta_y=parse_delta_array(element.get("DeltaY")),
            )
            codes.append(code)
        return codes

    def _parse_path(self, node: ET.Element) -> PathObject:
        obj = PathObject()
        self._parse_common_object(node, obj)
        data = child(node, "AbbreviatedData")
        if data is not None and data.text:
            obj.data = data.text.strip()
        return obj

    def _parse_image(self, node: ET.Element) -> ImageObject:
        obj = ImageObject()
        self._parse_common_object(node, obj)
        obj.resource_id = node.get("ResourceID", "")
        obj.image_mask = node.get("ImageMask")
        obj.substitution = node.get("Substitution")
        return obj

    def _parse_composite(self, node: ET.Element) -> CompositeObject:
        obj = CompositeObject()
        self._parse_common_object(node, obj)
        for child_node in node:
            parsed = self._parse_object(child_node)
            if parsed is not None:
                obj.objects.append(parsed)
        return obj

    # -- annotations -------------------------------------------------------
    def _parse_annotations(self, entry: str) -> None:
        root = self.pkg.read_xml(entry)
        base_dir = posixpath.dirname(entry)
        planned: List[Tuple[str, str]] = []
        for page_node in children(root, "Page"):
            location = text_of(page_node, "FileLoc")
            if location:
                planned.append((page_node.get("PageID", ""), resolve_loc(base_dir, location)))

        by_id = {}
        ordered: List[List[Annotation]] = []
        for page_id, page_entry in planned:
            annotations = self._parse_page_annotations(page_entry)
            ordered.append(annotations)
            if page_id:
                by_id[page_id] = annotations

        for index, page in enumerate(self.doc.pages):
            if page.id and page.id in by_id:
                page.annotations = by_id[page.id]
            elif index < len(ordered):
                page.annotations = ordered[index]

    def _parse_page_annotations(self, entry: str) -> List[Annotation]:
        if not self.pkg.has(entry):
            return []
        root = self.pkg.read_xml(entry)
        annotations: List[Annotation] = []
        for annot in descendants(root, "Annot"):
            annotation = Annotation(
                id=annot.get("ID", ""),
                type=annot.get("Type", ""),
                subtype=annot.get("Subtype", ""),
            )
            appearance = child(annot, "Appearance")
            if appearance is None:
                annotations.append(annotation)
                continue
            annotation.boundary = parse_box(appearance.get("Boundary"))
            annotation.objects = self._parse_appearance(appearance)
            annotations.append(annotation)
        return annotations

    def _parse_appearance(self, appearance: ET.Element) -> List[GraphicObject]:
        objects: List[GraphicObject] = []
        for node in appearance:
            name = local_name(node.tag)
            if name == "PageBlock":
                for inner in node:
                    parsed = self._parse_object(inner)
                    if parsed is not None:
                        objects.append(parsed)
            else:
                parsed = self._parse_object(node)
                if parsed is not None:
                    objects.append(parsed)
        return objects

    # -- attachments -------------------------------------------------------
    def _parse_attachments(self, entry: str) -> None:
        root = self.pkg.read_xml(entry)
        base = posixpath.dirname(entry)
        for element in descendants(root, "Attachment"):
            location = text_of(element, "FileLoc")
            path = resolve_loc(base, location) if location else None
            self.doc.attachments.append(
                Attachment(
                    id=element.get("ID", ""),
                    name=element.get("Name", ""),
                    format=element.get("Format", ""),
                    path=path,
                )
            )


def parse_ofd(package: OfdPackage) -> Document:
    """Parse *package* and return the rendered document model."""

    return OfdParser(package).parse()
