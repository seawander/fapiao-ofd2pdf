from __future__ import annotations

import os
import plistlib

import fitz
import pytest

from ofd2pdf import macos
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
