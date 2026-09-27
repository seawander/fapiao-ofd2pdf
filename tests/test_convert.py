from __future__ import annotations

import os
import pathlib
import re
import tempfile

try:  # PyMuPDF >= 1.24.3 is imported as `pymupdf`
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz
import pytest

from ofd2pdf import convert, open_pdf

SAMPLE = pathlib.Path(__file__).resolve().parent / "data" / "sample.ofd"

MM = 72 / 25.4


def _compact(page) -> str:
    """Glyphs are placed individually, so extractors may insert spaces."""
    return "".join(page.get_text().split())


def test_convert_sample(tmp_path):
    output = tmp_path / "out.pdf"
    result = convert(SAMPLE, output)
    assert result == str(output)
    assert output.exists()

    pdf = fitz.open(output)
    try:
        assert pdf.page_count == 2

        page = pdf[0]
        assert page.rect.width == pytest.approx(150 * MM, abs=0.5)
        assert page.rect.height == pytest.approx(100 * MM, abs=0.5)
        text = _compact(page)
        assert "测试发票" in text
        assert "OFDTEST" in text
        assert "TESTUSER" in text
        assert "INV000000001" in text
        assert "CNY123.45" not in text  # replaced by the g-repeat digit run
        assert "1234567890" in text          # DeltaX="g 10 2"
        assert "￥123" in text                # \XXXX escapes
        assert "SQUEEZED" in text            # HScale
        assert "OUTLINE" in text             # stroke-only text
        assert "透明文字" in text              # cmyk fill with alpha
        assert "竖排文字示例" in text           # vertical run driven by DeltaY
        assert "B2UP" in text                # ReadDirection 90
        assert "RTL180" in text              # ReadDirection 180
        assert "嵌套组合" in text              # inline CompositeObject
        assert "已认证" in text               # Stamp annotation appearance

        second = pdf[1]
        assert second.rect.width == pytest.approx(120 * MM, abs=0.5)
        assert second.rect.height == pytest.approx(70 * MM, abs=0.5)
        text2 = _compact(second)
        assert "第二页明细" in text2
        assert "PAGETWO" in text2
        assert "样例印章" in text2            # CompositeGraphicUnit by ResourceID
        assert "第二页竖排" in text2
        assert "270" in text2
        assert "斜排文字" in text2            # CharDirection 45
        assert "多行文字" in text2 and "第二行文字" in text2
        assert "附注" in text2                # annotation on page 2
    finally:
        pdf.close()


def test_sample_metadata_and_attachments(tmp_path):
    output = tmp_path / "out.pdf"
    convert(SAMPLE, output)
    pdf = fitz.open(output)
    try:
        meta = pdf.metadata
        assert meta["title"] == "合成测试发票"
        assert meta["author"] == "ofd2pdf test"
        assert meta["subject"] == "OFD rendering fixture"
        assert meta["creator"] == "ofd2pdf tests"
        assert set(pdf.embfile_names()) == {"readme.txt", "data.csv"}
    finally:
        pdf.close()


def test_sample_graphics(tmp_path):
    output = tmp_path / "out.pdf"
    convert(SAMPLE, output)
    pdf = fitz.open(output)
    try:
        page = pdf[0]
        # two logos plus the ImageMask stencil
        assert len(page.get_images()) == 3

        drawings = page.get_drawings()
        assert len(drawings) >= 12, "template, shapes, composite and stamp"

        # a dash pattern reaches the PDF (1.2 mm / 0.8 mm -> 3.40 / 2.27 pt)
        def dash_values(drawing):
            """PyMuPDF reports dashes as ``"[d d ...] phase"`` (or ``"[] 0"``)."""
            spec = drawing.get("dashes")
            if not spec:
                return []
            if isinstance(spec, (list, tuple)):
                spec = spec[0]
            inner = re.search(r"\[([^\]]*)\]", str(spec))
            return [float(v) for v in inner.group(1).split()] if inner else []

        dashed = [d for d in drawings if len(dash_values(d)) == 2]
        assert dashed, "DashPattern should be applied"
        assert dash_values(dashed[0]) == pytest.approx([1.2 * MM, 0.8 * MM], abs=0.01)

        # curves survive: the cubic+quadratic dome on page 2 has many segments
        dome = pdf[1].get_drawings()
        assert any(len(d["items"]) > 50 for d in dome), "bezier dome should render"

        # the seal (composite unit) is two red circles
        reds = [d for d in dome
                if d.get("color") and d["color"][0] > 0.6 and d["color"][1] < 0.4]
        assert len(reds) == 2
    finally:
        pdf.close()


def test_overwrite_guard(tmp_path):
    output = tmp_path / "out.pdf"
    convert(SAMPLE, output)
    with pytest.raises(FileExistsError):
        convert(SAMPLE, output)
    convert(SAMPLE, output, overwrite=True)


def test_missing_input(tmp_path):
    with pytest.raises(OSError):
        convert(tmp_path / "does-not-exist.ofd", tmp_path / "out.pdf")


def test_open_pdf_uses_temp_file():
    path = open_pdf(SAMPLE, open_viewer=False)
    try:
        assert os.path.isfile(path)
        expected_dir = os.path.join(tempfile.gettempdir(), "ofd2pdf")
        assert os.path.dirname(path) == expected_dir
        assert path.endswith(".pdf")
        pdf = fitz.open(path)
        try:
            assert pdf.page_count == 2
        finally:
            pdf.close()
    finally:
        os.remove(path)
