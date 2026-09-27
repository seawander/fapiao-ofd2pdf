from __future__ import annotations

import os
import plistlib

try:  # PyMuPDF >= 1.24.3 is imported as `pymupdf`
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz
import pytest

from ofd2pdf import convert, macos
from ofd2pdf.model import (Annotation, Document, DrawParam, Layer, Page,
                           PathObject, TextCode, TextObject, Color)
from ofd2pdf.renderer import render_to_pdf


class _EmptyPackage:
    def has(self, name):
        return False

    def read(self, name):
        return b""


def _document(layer: Layer) -> Document:
    document = Document(page_area=(120, 120))
    document.pages.append(Page(id="1", width=120, height=120, layers=[layer]))
    return document


def test_ttc_uses_regular_face():
    from ofd2pdf import fonts as fonts_module

    path = "/System/Library/Fonts/Supplemental/Songti.ttc"
    if not os.path.exists(path):
        pytest.skip("Songti.ttc not available")
    pytest.importorskip("fontTools.ttLib")
    from fontTools.ttLib import TTFont

    resolved = fonts_module._extract_regular_face(path)
    assert resolved != path
    face = (TTFont(resolved, lazy=True)["name"].getDebugName(4) or "").lower()
    assert "black" not in face
    assert "bold" not in face
    assert "medium" not in face


def test_parse_delta_array_g_repeat():
    from ofd2pdf.parser import parse_delta_array

    # `g N v` repeats the single following value N times.
    assert parse_delta_array("g 9 7.07") == [7.07] * 9
    assert parse_delta_array("g 4 1.585 3.17 g 2 1.585 3.17 g 2 1.585") == [
        1.585, 1.585, 1.585, 1.585, 3.17, 1.585, 1.585, 3.17, 1.585, 1.585,
    ]
    assert parse_delta_array("1.59 g 6 3.18 1.59 g 3 3.18") == [
        1.59, 3.18, 3.18, 3.18, 3.18, 3.18, 3.18, 1.59, 3.18, 3.18, 3.18,
    ]


def test_composite_graphic_unit_is_expanded(tmp_path):
    """A CompositeObject that points at a unit resource must be rendered."""
    import zipfile

    ns = "http://www.ofdspec.org/2016"
    ofd = tmp_path / "seal.ofd"
    with zipfile.ZipFile(ofd, "w") as zf:
        zf.writestr("OFD.xml", f'<?xml version="1.0" encoding="UTF-8"?>'
                                f'<ofd:OFD xmlns:ofd="{ns}" Version="1.0">'
                                f'<ofd:DocBody><ofd:DocInfo><ofd:DocID>1</ofd:DocID>'
                                f'</ofd:DocInfo><ofd:DocRoot>Doc_0/Document.xml'
                                f'</ofd:DocRoot></ofd:DocBody></ofd:OFD>')
        zf.writestr("Doc_0/Document.xml", f'<?xml version="1.0" encoding="UTF-8"?>'
                                          f'<ofd:Document xmlns:ofd="{ns}"><ofd:CommonData>'
                                          f'<ofd:DocumentRes>DocumentRes.xml</ofd:DocumentRes>'
                                          f'<ofd:MaxUnitID>99</ofd:MaxUnitID>'
                                          f'<ofd:PageArea><ofd:PhysicalBox>0 0 210 297'
                                          f'</ofd:PhysicalBox></ofd:PageArea></ofd:CommonData>'
                                          f'<ofd:Pages><ofd:Page ID="1" BaseLoc="Pages/Page_0/Content.xml"/>'
                                          f'</ofd:Pages></ofd:Document>')
        zf.writestr("Doc_0/DocumentRes.xml", f'<?xml version="1.0" encoding="UTF-8"?>'
                                             f'<ofd:Res xmlns:ofd="{ns}"><ofd:CompositeGraphicUnits>'
                                             f'<ofd:CompositeGraphicUnit ID="1111" Width="210" Height="297">'
                                             f'<ofd:Content ID="1005" Type="Body"><ofd:PageBlock ID="1006">'
                                             f'<ofd:PathObject ID="3" Boundary="0 0 30 20" LineWidth="1" '
                                             f'Stroke="true" Fill="false">'
                                             f'<ofd:StrokeColor ColorSpace="4" Value="255 0 0"/>'
                                             f'<ofd:AbbreviatedData>M 15 0 B 30 10 15 20 0 10 C</ofd:AbbreviatedData>'
                                             f'</ofd:PathObject></ofd:PageBlock></ofd:Content>'
                                             f'</ofd:CompositeGraphicUnit></ofd:CompositeGraphicUnits></ofd:Res>')
        zf.writestr("Doc_0/Pages/Page_0/Content.xml", f'<?xml version="1.0" encoding="UTF-8"?>'
                                                     f'<ofd:Page xmlns:ofd="{ns}"><ofd:Area>'
                                                     f'<ofd:PhysicalBox>0 0 210 297</ofd:PhysicalBox></ofd:Area>'
                                                     f'<ofd:Content><ofd:Layer ID="7" Type="Body">'
                                                     f'<ofd:CompositeObject ID="1001" Boundary="90 4 30 20" '
                                                     f'ResourceID="1111"/>'
                                                     f'</ofd:Layer></ofd:Content></ofd:Page>')

    output = tmp_path / "seal.pdf"
    convert(ofd, output)
    pdf = fitz.open(output)
    try:
        drawings = pdf[0].get_drawings()
        assert drawings, "composite unit content should be drawn"
        rect = drawings[0]["rect"]
        # The unit is placed at the referencing object's boundary origin.
        assert rect.x0 == pytest.approx(90 * 72 / 25.4, abs=1.0)
        assert rect.y0 == pytest.approx(4 * 72 / 25.4, abs=1.0)
        assert rect.width == pytest.approx(30 * 72 / 25.4, abs=1.0)
        assert rect.height == pytest.approx(20 * 72 / 25.4, abs=1.0)
    finally:
        pdf.close()


def _glyph_positions(pdf, page_index=0):
    """Return ``{character: (x0, y0)}`` for every glyph drawn on a page."""
    positions = {}
    for block in pdf[page_index].get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span["chars"]:
                    positions.setdefault(char["c"], []).append(char["bbox"][:2])
    return positions


def test_read_direction_rotates_the_advance():
    """`DeltaX` follows the reading axis, so rotated text is not horizontal."""
    layer = Layer(type="Body")
    for index, direction in enumerate((0, 90, 180, 270)):
        layer.objects.append(TextObject(
            id=f"r{direction}", boundary=(20, 10 + index * 24, 60, 12), size=6,
            read_direction=direction,
            codes=[TextCode(x=0, y=6, text="AB", delta_x=[6, 6])],
        ))
    pdf = render_to_pdf(_document(layer), _EmptyPackage())
    try:
        spots = _glyph_positions(pdf)
        # 0: left to right, 90: bottom to top, 180: right to left, 270: top to bottom
        assert spots["A"][0][0] < spots["B"][0][0]
        assert spots["A"][1][1] > spots["B"][1][1]        # 90 climbs
        assert spots["A"][2][0] > spots["B"][2][0]        # 180 goes left
        assert spots["A"][3][1] < spots["B"][3][1]        # 270 descends
    finally:
        pdf.close()


def test_char_direction_slants_the_advance():
    layer = Layer(type="Body")
    layer.objects.append(TextObject(
        id="slant", boundary=(20, 20, 40, 20), size=6, char_direction=45,
        codes=[TextCode(x=0, y=0, text="AB", delta_x=[8, 8])],
    ))
    pdf = render_to_pdf(_document(layer), _EmptyPackage())
    try:
        spots = _glyph_positions(pdf)
        (ax, ay), (bx, by) = spots["A"][0], spots["B"][0]
        assert bx > ax, "advance should move right"
        assert by < ay, "advance should also move up (45 degrees)"
    finally:
        pdf.close()


def test_delta_y_stacks_glyphs_down_the_page():
    """`DeltaY` stays a page-axis offset, so vertical runs read top to bottom."""
    layer = Layer(type="Body")
    layer.objects.append(TextObject(
        id="v", boundary=(20, 20, 10, 30), size=6,
        codes=[TextCode(x=0, y=0, text="AB", delta_y=[6, 6])],
    ))
    pdf = render_to_pdf(_document(layer), _EmptyPackage())
    try:
        spots = _glyph_positions(pdf)
        assert spots["B"][0][1] > spots["A"][0][1]
        assert spots["B"][0][0] == pytest.approx(spots["A"][0][0], abs=0.5)
    finally:
        pdf.close()


def test_dash_pattern_is_a_child_element():
    from ofd2pdf.model import PathObject

    layer = Layer(type="Body")
    layer.objects.append(PathObject(
        id="p", boundary=(10, 10, 40, 10), data="M 0 0 L 40 0", stroke=True,
        fill=False, draw_param_id="dp",
    ))
    document = _document(layer)
    document.draw_params["dp"] = DrawParam(
        id="dp", line_width=0.4, stroke_color=Color("rgb", (1.0, 0.0, 0.0)),
        dash_pattern=(2.0, 1.0), dash_offset=0.0,
    )
    pdf = render_to_pdf(document, _EmptyPackage())
    try:
        spec = pdf[0].get_drawings()[0]["dashes"]
        assert spec and "[" in spec, f"dash pattern missing: {spec!r}"
        values = [float(v) for v in spec.split("[")[1].split("]")[0].split()]
        assert values == pytest.approx([2.0 * 72 / 25.4, 1.0 * 72 / 25.4], abs=0.01)
    finally:
        pdf.close()


def test_dash_pattern_child_element_is_parsed():
    """CT_DashPattern is a child element carrying Array/Offset."""
    import xml.etree.ElementTree as ET

    from ofd2pdf.parser import OfdParser

    ns = "http://www.ofdspec.org/2016"
    element = ET.fromstring(
        f'<ofd:DrawParam xmlns:ofd="{ns}" ID="7">'
        f'<ofd:DashPattern Offset="0.5" Array="1.2 0.8 0.4"/>'
        f"</ofd:DrawParam>"
    )
    param = OfdParser.__new__(OfdParser)._parse_draw_param(element)
    assert param.dash_pattern == (1.2, 0.8, 0.4)
    assert param.dash_offset == pytest.approx(0.5)


def test_text_directions_and_hscale_render():
    layer = Layer(type="Body")
    layer.objects.append(TextObject(
        id="h", boundary=(10, 10, 60, 10), size=8, hscale=0.5,
        codes=[TextCode(x=0, y=8, text="HSCALE", delta_x=[4.0] * 5)],
    ))
    for index, direction in enumerate((0, 90, 180, 270)):
        layer.objects.append(TextObject(
            id=f"c{direction}", boundary=(10, 30 + index * 16, 60, 14), size=8,
            char_direction=direction,
            codes=[TextCode(x=0, y=0, text="F", delta_x=[])],
        ))
    layer.objects.append(TextObject(
        id="v", boundary=(90, 10, 20, 90), size=8, read_direction=90,
        codes=[TextCode(x=0, y=0, text="ABC", delta_y=[8.0] * 3)],
    ))
    pdf = render_to_pdf(_document(layer), _EmptyPackage())
    try:
        assert pdf.page_count == 1
        assert pdf[0].get_text().strip() != ""
    finally:
        pdf.close()


def test_annotation_appearance_is_rendered():
    layer = Layer(type="Body")
    document = _document(layer)
    document.draw_params["dp"] = DrawParam(
        id="dp", line_width=0.5, stroke_color=Color("rgb", (1.0, 0.0, 0.0))
    )
    annotation = Annotation(
        id="1", type="Stamp", boundary=(20, 20, 50, 20),
        objects=[PathObject(id="r", boundary=(0, 0, 50, 20),
                            data="M 0 0 L 50 0 L 50 20 L 0 20 C",
                            draw_param_id="dp", stroke=True, fill=False)],
    )
    document.pages[0].annotations.append(annotation)
    pdf = render_to_pdf(document, _EmptyPackage())
    try:
        drawings = pdf[0].get_drawings()
        assert drawings, "annotation path should be drawn"
    finally:
        pdf.close()


def test_macos_handler_app_install(tmp_path, monkeypatch):
    if not macos.is_supported():
        pytest.skip("macOS only")
    monkeypatch.setattr(macos, "APP_DIR", str(tmp_path))
    monkeypatch.setattr(macos, "_search_dirs", lambda: [str(tmp_path)])
    monkeypatch.setattr(macos, "_unregister", lambda path: None)
    bundle = macos.install_app(register=False)

    info_file = os.path.join(bundle, "Contents", "Info.plist")
    with open(info_file, "rb") as stream:
        info = plistlib.load(stream)
    assert info["CFBundleDocumentTypes"][0]["LSItemContentTypes"] == ["public.ofd"]
    assert info["LSUIElement"] is True
    assert info["CFBundleIdentifier"] == "org.ofd2pdf.handler"

    assert macos.uninstall_app() is True
    assert not os.path.exists(bundle)
    assert macos.uninstall_app() is False


def test_macos_clean_uninstall(tmp_path, monkeypatch):
    if not macos.is_supported():
        pytest.skip("macOS only")
    apps = tmp_path / "apps"
    services = tmp_path / "services"
    apps.mkdir()
    services.mkdir()
    monkeypatch.setattr(macos, "APP_DIR", str(apps))
    monkeypatch.setattr(macos, "SERVICES_DIR", str(services))
    monkeypatch.setattr(macos, "_search_dirs", lambda: [str(apps)])
    monkeypatch.setattr(macos, "_unregister", lambda path: None)
    monkeypatch.setattr(macos, "refresh_services", lambda: None)
    monkeypatch.setattr(macos, "_clear_temp_previews", lambda: True)

    bundle = macos.install_app(register=False)
    macos.install(refresh=False)

    removed = macos.clean_uninstall()
    assert str(bundle) in removed["apps"]
    assert removed["workflows"]
    assert removed["temp"] is True
    assert not os.path.exists(bundle)
    assert not os.path.isdir(os.path.join(str(services), macos.WORKFLOW_FILENAME))

    empty = macos.clean_uninstall()
    assert empty["apps"] == []
    assert empty["workflows"] == []


def test_macos_workflow_install_and_uninstall(tmp_path, monkeypatch):
    if not macos.is_supported():
        pytest.skip("macOS only")
    monkeypatch.setattr(macos, "SERVICES_DIR", str(tmp_path))
    monkeypatch.setattr(macos, "refresh_services", lambda: None)

    bundle = macos.install(refresh=False)
    workflow_file = os.path.join(bundle, "Contents", "document.wflow")
    info_file = os.path.join(bundle, "Contents", "Info.plist")
    assert os.path.isfile(workflow_file)
    assert os.path.isfile(info_file)

    with open(workflow_file, "rb") as stream:
        workflow = plistlib.load(stream)
    command = workflow["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]
    assert "ofd2pdf" in command
    assert "--open" in command
    assert workflow["workflowMetaData"]["workflowTypeIdentifier"] == \
        "com.apple.Automator.servicesMenu"

    with open(info_file, "rb") as stream:
        info = plistlib.load(stream)
    service = info["NSServices"][0]
    assert service["NSMenuItem"]["default"] == macos.MENU_TITLE
    assert "public.item" in service["NSSendFileTypes"]

    assert macos.uninstall() is True
    assert not os.path.exists(bundle)
    assert macos.uninstall() is False
