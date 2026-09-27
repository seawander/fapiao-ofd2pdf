#!/usr/bin/env python3
"""Generate the synthetic OFD fixture used by the test suite.

Run ``python tests/make_sample.py`` to (re)build ``tests/data/sample.ofd``.
Everything here is fake — no real personal data — and uses only the standard
library so the fixture can be regenerated anywhere.

The sample deliberately exercises the features ofd2pdf renders:

* a background template with stroke paths (table lines) and a filled band,
* text objects using both a CJK and a Latin font, with ``DeltaX`` positioning,
* an ``ImageObject`` referencing a generated PNG,
* a filled ``PathObject``.

Layout (page is 150 x 80 mm)::

    +--------------------------------------------------+
    | [ band ]  测试发票   OFD TEST               [logo]|
    +--------------------------------------------------+
    | NAME       TEST USER      INVOICE INV000000001   |
    | AMOUNT     CNY 123.45     备注    样例文件          |
    +--------------------------------------------------+
"""

from __future__ import annotations

import os
import struct
import zlib
import zipfile

OUTPUT = os.path.join(os.path.dirname(__file__), "data", "sample.ofd")

NS = "http://www.ofdspec.org/2016"


# -- tiny PNG encoder -------------------------------------------------------
def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _make_png(width: int, height: int, pixel) -> bytes:
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0
        for x in range(width):
            raw += bytes(pixel(x, y))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _png_chunk(b"IEND", b"")
    )


def _logo_png() -> bytes:
    size = 32

    def pixel(x: int, y: int):
        edge = x < 2 or y < 2 or x >= size - 2 or y >= size - 2
        if edge:
            return (200, 30, 30)
        if (x // 4 + y // 4) % 2 == 0:
            return (255, 240, 240)
        return (255, 255, 255)

    return _make_png(size, size, pixel)


# -- OFD XML documents ------------------------------------------------------
OFD_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<ofd:OFD Version="1.1" DocType="OFD" xmlns:ofd="{NS}">
  <ofd:DocBody>
    <ofd:DocInfo>
      <ofd:DocID>sample-ofd-0001</ofd:DocID>
      <ofd:Author>ofd2pdf test</ofd:Author>
      <ofd:CreationDate>2026-01-01</ofd:CreationDate>
      <ofd:ModDate>2026-01-01</ofd:ModDate>
    </ofd:DocInfo>
    <ofd:DocRoot>Doc_0/Document.xml</ofd:DocRoot>
  </ofd:DocBody>
</ofd:OFD>
"""

DOCUMENT_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<ofd:Document xmlns:ofd="{NS}">
  <ofd:CommonData>
    <ofd:MaxUnitID>100</ofd:MaxUnitID>
    <ofd:PageArea><ofd:PhysicalBox>0 0 150 80</ofd:PhysicalBox></ofd:PageArea>
    <ofd:PublicRes>PublicRes.xml</ofd:PublicRes>
    <ofd:DocumentRes>DocumentRes.xml</ofd:DocumentRes>
    <ofd:TemplatePage ID="1" BaseLoc="Tpls/Tpl_0/Content.xml" ZOrder="Background"/>
  </ofd:CommonData>
  <ofd:Pages>
    <ofd:Page ID="2" BaseLoc="Pages/Page_0/Content.xml"/>
  </ofd:Pages>
</ofd:Document>
"""

PUBLIC_RES_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<ofd:Res xmlns:ofd="{NS}" BaseLoc="Res">
  <ofd:DrawParams>
    <ofd:DrawParam ID="1" LineWidth="0.3"><ofd:StrokeColor Value="60 60 60"/></ofd:DrawParam>
    <ofd:DrawParam ID="2"><ofd:FillColor Value="240 240 245"/></ofd:DrawParam>
  </ofd:DrawParams>
  <ofd:Fonts>
    <ofd:Font ID="5" FontName="宋体" FamilyName="宋体"/>
    <ofd:Font ID="7" FontName="Courier New"/>
  </ofd:Fonts>
</ofd:Res>
"""

DOCUMENT_RES_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<ofd:Res xmlns:ofd="{NS}" BaseLoc="Res">
  <ofd:MultiMedias>
    <ofd:MultiMedia ID="9" Type="Image" Format="PNG">
      <ofd:MediaFile>logo.png</ofd:MediaFile>
    </ofd:MultiMedia>
  </ofd:MultiMedias>
</ofd:Res>
"""

TEMPLATE_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<ofd:Page xmlns:ofd="{NS}">
  <ofd:Content>
    <ofd:Layer ID="10" DrawParam="2">
      <ofd:PathObject ID="11" Boundary="10 4 130 10" Fill="true" Stroke="false">
        <ofd:AbbreviatedData>M 0 0 L 130 0 L 130 10 L 0 10 C</ofd:AbbreviatedData>
      </ofd:PathObject>
    </ofd:Layer>
    <ofd:Layer ID="12" DrawParam="1">
      <ofd:PathObject ID="13" Boundary="10 14 130 0.4">
        <ofd:AbbreviatedData>M 0 0.2 L 130 0.2</ofd:AbbreviatedData>
      </ofd:PathObject>
      <ofd:PathObject ID="14" Boundary="10 38 130 0.4">
        <ofd:AbbreviatedData>M 0 0.2 L 130 0.2</ofd:AbbreviatedData>
      </ofd:PathObject>
      <ofd:PathObject ID="15" Boundary="10 58 130 0.4">
        <ofd:AbbreviatedData>M 0 0.2 L 130 0.2</ofd:AbbreviatedData>
      </ofd:PathObject>
      <ofd:PathObject ID="16" Boundary="10 20 0.4 38">
        <ofd:AbbreviatedData>M 0.2 0 L 0.2 38</ofd:AbbreviatedData>
      </ofd:PathObject>
      <ofd:PathObject ID="17" Boundary="55 20 0.4 38">
        <ofd:AbbreviatedData>M 0.2 0 L 0.2 38</ofd:AbbreviatedData>
      </ofd:PathObject>
    </ofd:Layer>
  </ofd:Content>
</ofd:Page>
"""


def _text(oid, text, x, y, size, font, deltas, boundary):
    delta = " ".join(str(d) for d in deltas)
    return (
        f'      <ofd:TextObject ID="{oid}" Boundary="{boundary}" Font="{font}" Size="{size}">\n'
        f'        <ofd:FillColor Value="0 0 0"/>\n'
        f'        <ofd:TextCode X="{x}" Y="{y}" DeltaX="{delta}">{text}</ofd:TextCode>\n'
        f"      </ofd:TextObject>\n"
    )


def page_xml() -> str:
    parts = [
        # Title: CJK then Latin, with per-glyph advances.
        _text(20, "测试发票", 0, 4.2, 5, 5, [5, 5, 5, 5], "14 6 40 7"),
        _text(21, "OFD TEST", 0, 4.2, 4.5, 7, [2.25] * 8, "40 6 40 7"),
        # Name / invoice row.
        _text(22, "NAME", 0, 3.2, 3.5, 7, [1.75] * 4, "14 21 40 5"),
        _text(23, "TEST USER", 0, 3.2, 3.5, 7, [1.75] * 9, "60 21 40 5"),
        _text(24, "INVOICE", 0, 3.2, 3.5, 7, [1.75] * 7, "103 21 40 5"),
        _text(25, "INV000000001", 0, 3.2, 3.5, 7, [1.75] * 12, "60 30 80 5"),
        # Amount row.
        _text(26, "AMOUNT", 0, 3.2, 3.5, 7, [1.75] * 6, "14 41 40 5"),
        _text(27, "CNY 123.45", 0, 3.2, 3.5, 7, [1.75] * 10, "60 41 40 5"),
        _text(28, "备注", 0, 3.6, 4, 5, [4, 4], "103 41 20 5"),
        _text(29, "样例文件", 0, 3.6, 4, 5, [4, 4, 4, 4], "120 41 30 5"),
    ]
    body = "".join(parts)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ofd:Page xmlns:ofd="{NS}">
  <ofd:Area><ofd:PhysicalBox>0 0 150 80</ofd:PhysicalBox></ofd:Area>
  <ofd:Template TemplateID="1" ZOrder="Background"/>
  <ofd:Content>
    <ofd:Layer Type="Body">
      <ofd:ImageObject ID="90" CTM="20 0 0 20 0 0" Boundary="120 5 18 18" ResourceID="9"/>
{body}    </ofd:Layer>
  </ofd:Content>
</ofd:Page>
"""


def build(output: str = OUTPUT) -> str:
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("OFD.xml", OFD_XML)
        archive.writestr("Doc_0/Document.xml", DOCUMENT_XML)
        archive.writestr("Doc_0/PublicRes.xml", PUBLIC_RES_XML)
        archive.writestr("Doc_0/DocumentRes.xml", DOCUMENT_RES_XML)
        archive.writestr("Doc_0/Tpls/Tpl_0/Content.xml", TEMPLATE_XML)
        archive.writestr("Doc_0/Pages/Page_0/Content.xml", page_xml())
        archive.writestr("Doc_0/Res/logo.png", _logo_png())
    return output


if __name__ == "__main__":
    print("wrote", build())
