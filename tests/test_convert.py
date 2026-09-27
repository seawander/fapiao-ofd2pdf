from __future__ import annotations

import os
import pathlib
import tempfile

import fitz
import pytest

from ofd2pdf import convert, open_pdf

SAMPLE = pathlib.Path(__file__).resolve().parent / "data" / "sample.ofd"


def test_convert_sample(tmp_path):
    output = tmp_path / "out.pdf"
    result = convert(SAMPLE, output)
    assert result == str(output)
    assert output.exists()

    pdf = fitz.open(output)
    try:
        assert pdf.page_count == 1
        page = pdf[0]
        assert page.rect.width == pytest.approx(150 * 72 / 25.4, abs=0.5)
        assert page.rect.height == pytest.approx(80 * 72 / 25.4, abs=0.5)

        # Glyphs are positioned individually, so some extractors insert spaces
        # between them; compare with whitespace removed.
        text = page.get_text()
        compact = "".join(text.split())
        assert "测试发票" in compact
        assert "OFDTEST" in compact
        assert "TESTUSER" in compact
        assert "INV000000001" in compact
        assert "CNY123.45" in compact
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
            assert pdf.page_count == 1
        finally:
            pdf.close()
    finally:
        os.remove(path)
