# ofd2pdf

[![CI](https://github.com/seawander/fapiao-ofd2pdf/actions/workflows/ci.yml/badge.svg)](https://github.com/seawander/fapiao-ofd2pdf/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

将 OFD 文档（中国国家标准 GB/T 33190-2016，常用于电子发票、电子证照和公文）转换为 PDF。
Convert **OFD** (GB/T 33190-2016) documents to **PDF**.

- 纯 Python，基于 [PyMuPDF](https://pymupdf.readthedocs.io/)
- 提供命令行工具和 Python API
- macOS 上可右键直接以 PDF 打开

[中文](#中文) | [English](#english)

> 请将命令中的 `OWNER` 替换为托管本仓库的 GitHub 账号或组织。
> Replace `OWNER` with the GitHub account or organisation hosting this repository.

## ⚠️ 免责声明 / Disclaimer

> **本项目由 AI 辅助生成（使用 [OpenCode](https://opencode.ai) 与 DeepSeek V4.1 Flash 模型），未经专业审计或全面测试。**
> 软件按「原样」提供，不提供任何明示或暗示的保证——包括但不限于正确性、完整性、
> 适用性或安全性。请自行核对转换结果，尤其是发票、公文等具有法律或财务效力的文件。
> 使用本软件所产生的任何风险与损失，由使用者自行承担。本项目与 OFD 标准的任何
> 标准组织或厂商均无关联。
>
> **This project was generated with AI ([OpenCode](https://opencode.ai) + DeepSeek V4.1 Flash) and has not
> been professionally audited or exhaustively tested.** It is provided "as is", without warranty of any kind,
> express or implied — including correctness, completeness, fitness or security.
> Verify the output yourself, especially for invoices or official documents that
> carry legal or financial weight. Use it at your own risk. This project is not
> affiliated with any standards body or vendor of the OFD format.

---

## 中文

**ofd2pdf** 可以把 **OFD** 文件转换为 **PDF**。大多数情况下，你只想打开一个 OFD
文件——在 macOS 上无需敲命令，直接在访达里右键即可。

[安装](#安装) · [命令行](#命令行) · [Python API](#python-api)

### 在访达中右键打开（macOS，最简单）

1. 安装一次：

   ```bash
   pip install "git+https://github.com/seawander/fapiao-ofd2pdf.git"
   ofd2pdf --install-finder-action
   ```

2. 在访达中右键点击 `.ofd` 文件 → **打开方式** → **OFD to PDF**。

PDF 会立即在查看器中打开，且不会在源文件旁另存文件。首次使用时，「OFD to PDF」可能
藏在 **打开方式 → 其他…** 里，选择一次即可常驻菜单。若希望双击就打开，可在
**显示简介 → 打开方式 → 全部更改…** 中设为默认。

如果 macOS 提示 *「Apple 无法验证……是否包含恶意软件」*，说明该文件是从网上下载的
（带有隔离标记）。清除一次即可不再提示：

```bash
ofd2pdf --clear-quarantine ~/Documents/invoices   # 文件夹……
ofd2pdf --clear-quarantine invoice.ofd            # 或单个文件
```

卸载集成：

```bash
ofd2pdf --uninstall-finder-action          # 应用 + 服务 + 临时预览
ofd2pdf --uninstall-finder-action --purge  # 同时卸载 Python 包
```

> 不是 macOS？请使用下面的[命令行](#命令行)方式。

### 安装

需要 Python 3.9 或更高版本。PyMuPDF 会自动安装，Pillow 为可选项。

```bash
# 从 GitHub 安装（推荐）
pip install "git+https://github.com/seawander/fapiao-ofd2pdf.git"

# 安装指定版本
pip install "git+https://github.com/seawander/fapiao-ofd2pdf.git@v0.2.0"

# 需要支持不常见的图像格式时
pip install "ofd2pdf[image] @ git+https://github.com/seawander/fapiao-ofd2pdf.git"

# 从本地源码安装
git clone https://github.com/seawander/fapiao-ofd2pdf.git
cd ofd2pdf
pip install .
```

以上任一方式都会安装 `ofd2pdf` 命令。

> **macOS 提示：** 访达集成会启动 `/Applications` 下的应用，而 macOS 会阻止它读取
> 位于 `~/Documents` 下的*可编辑（editable）*安装。使用右键集成时请用 `pip install .`
> （而不是 `pip install -e .`），修改源码后重新安装一次。

### 命令行

```bash
ofd2pdf invoice.ofd                      # 默认在源文件旁生成 invoice.pdf
ofd2pdf invoice.ofd -o out.pdf           # 指定输出路径
ofd2pdf invoice.ofd --open               # 仅查看，不保存任何文件
ofd2pdf a.ofd b.ofd c.ofd --overwrite    # 转换多个文件
ofd2pdf a.ofd b.ofd -o out/ --overwrite  # 将所有结果输出到目录
python -m ofd2pdf invoice.ofd            # 以模块方式运行
```

| 选项 | 说明 |
| --- | --- |
| `-o, --output PATH` | 输出 `.pdf` 文件；转换多个输入时可为目录 |
| `--overwrite` | 覆盖已存在的 PDF 文件 |
| `--open` | 用默认查看器打开 PDF，不在源文件旁保存 |
| `--clear-quarantine` | 清除指定文件/文件夹的 macOS 隔离（quarantine）标记 |
| `--version` | 显示版本号 |
| `--install-finder-action`、`--install` | 安装 macOS 右键集成 |
| `--uninstall-finder-action`、`--uninstall` | 移除 macOS 集成 |
| `--purge` | 配合 `--uninstall`，同时卸载 Python 包 |

### Python API

```python
from ofd2pdf import convert, convert_bytes, open_pdf

convert("invoice.ofd", "invoice.pdf")           # 文件 -> 文件，返回输出路径
convert("invoice.ofd", "invoice.pdf", overwrite=True)

with open("invoice.ofd", "rb") as fh:           # 字节 -> 文件
    convert_bytes(fh.read(), "invoice.pdf")

open_pdf("invoice.ofd")                          # 渲染到临时文件并打开
open_pdf("invoice.ofd", open_viewer=False)       # 仅转换，不启动查看器
open_pdf("invoice.ofd", viewer="Preview")        # 指定用于打开的应用
```

如需自定义渲染，也可以直接使用底层组件：

```python
from ofd2pdf.container import OfdPackage
from ofd2pdf.parser import parse_ofd
from ofd2pdf.renderer import render_to_pdf

with OfdPackage("invoice.ofd") as package:
    document = parse_ofd(package)
    pdf = render_to_pdf(document, package)
    pdf.save("invoice.pdf")
```

### 渲染内容

- `TextObject`——按 `TextCode`（`X`、`Y`、`DeltaX`、`DeltaY`，含 `g` 重复写法与
  `\XXXX` 转义）逐字定位，并支持 `HScale` 与 `ReadDirection` / `CharDirection`
  实现旋转和竖排
- `PathObject`——完整的路径缩写指令 `S / M / L / Q / B / A / C`（含椭圆弧）
- `ImageObject` 以及可递归的 `CompositeObject`
- 页面模板（`Background` / `Foreground` 前后层序）
- 注释外观内容（自带绘制内容的图章/签章）
- 填充/描边颜色（`gray` / `rgb` / `cmyk`）、透明度、线端/连接样式、虚线以及
  `DrawParam` 继承
- 文档元数据和内嵌附件

### 字体

OFD 文档通常引用中文字体（宋体/SimSun、黑体/SimHei、楷体/KaiTi 等）。匹配顺序为：

1. 内嵌字体文件（`<ofd:FontFile>`），优先使用；
2. 通过 `FontName`/`FamilyName` 别名匹配到的系统字体（Songti、STHeiti、
   Courier New、Times New Roman 等）；
3. 中文文本使用内置 CJK 字体，纯拉丁文本使用基础 14 号字体。

### 限制

- 色彩管理为简化实现（不支持 ICC 配置文件）。
- 仅渲染包含绘制内容的注释外观；以独立签名图像呈现的电子签章不会校验或重绘。
- 不支持文本重排/编辑——输出为固定版式的还原结果。

### 常见问题

**为什么访达里没有「快速操作」？**
在较新的 macOS 上，*快速操作*子菜单只由应用扩展和「快捷指令」填充，复制到
`~/Library/Services` 的 Automator 工作流已不再显示。因此本工具改用「打开方式」中的
文档处理应用，这是可靠的方式。

**可以用 `pip install -e .` 吗？**
开发时可以用。但若同时使用访达集成，请改用 `pip install .`，否则应用无法读取
位于 `~/Documents` 下的可编辑安装。

### 开发

```bash
git clone https://github.com/seawander/fapiao-ofd2pdf.git
cd ofd2pdf
pip install -e ".[dev]"
pytest
```

项目结构：

```
ofd2pdf/
├── ofd2pdf/
│   ├── container.py   # ZIP 包访问 + XML/ST_Loc 辅助函数
│   ├── model.py       # 解析后的文档数据类
│   ├── parser.py      # OFD.xml -> Document（页面、资源、注释）
│   ├── fonts.py       # 字体解析与回退
│   ├── renderer.py    # 使用 PyMuPDF 绘制
│   ├── converter.py   # convert() / convert_bytes() / open_pdf()
│   ├── macos.py       # 访达集成（处理应用 + Automator 后备）
│   └── cli.py         # 命令行入口
├── tests/
│   ├── make_sample.py     # 重新生成下面的测试样本
│   └── data/sample.ofd    # 合成测试样本（假数据，无个人信息）
├── pyproject.toml
└── README.md
```

> 测试样本由脚本从零生成（假发票、合成图像、无真实数据）。可随时运行
> `python tests/make_sample.py` 重新生成。

### 许可证

MIT。本项目由 AI 辅助生成（OpenCode + DeepSeek V4.1 Flash），未经专业审计或全面测试，按「原样」提供，不附带任何保证。
请自行验证转换结果；对因使用本软件造成的任何损失不承担责任。详见文首的「免责声明」。

---

## English

**ofd2pdf** converts **OFD** files to **PDF**. Most of the time you just want to
open an OFD — on macOS you can do that from Finder, no commands needed.

[Installation](#installation) · [Command line](#command-line) · [Python API](#python-api)

### Open from Finder (macOS — easiest)

1. Install once:

   ```bash
   pip install "git+https://github.com/seawander/fapiao-ofd2pdf.git"
   ofd2pdf --install-finder-action
   ```

2. Right-click an `.ofd` file in Finder → **Open With** → **OFD to PDF**.

The PDF opens straight away in your viewer and is not saved next to the source.
The first time, "OFD to PDF" may be under **Open With → Other…**; pick it once and
it stays on the menu. To open on double-click, use
**Get Info → Open with → Change All…**.

If macOS says *"Apple could not verify … is free of malware"*, the file was
downloaded from the internet (it carries a quarantine flag). Clear it once and
the warning stops:

```bash
ofd2pdf --clear-quarantine ~/Documents/invoices   # a folder…
ofd2pdf --clear-quarantine invoice.ofd            # …or a single file
```

Uninstall the integration:

```bash
ofd2pdf --uninstall-finder-action          # app + service + temp previews
ofd2pdf --uninstall-finder-action --purge  # also uninstall the Python package
```

> Not on macOS? Use the [command line](#command-line) below.

### Installation

Requires Python 3.9 or newer. PyMuPDF is installed automatically; Pillow is
optional.

```bash
# from GitHub (recommended)
pip install "git+https://github.com/seawander/fapiao-ofd2pdf.git"

# a specific release
pip install "git+https://github.com/seawander/fapiao-ofd2pdf.git@v0.2.0"

# with support for uncommon image formats
pip install "ofd2pdf[image] @ git+https://github.com/seawander/fapiao-ofd2pdf.git"

# from a local checkout
git clone https://github.com/seawander/fapiao-ofd2pdf.git
cd ofd2pdf
pip install .
```

Either way this installs the `ofd2pdf` command.

> **macOS note:** the Finder integration launches an app in `/Applications`, and
> macOS privacy protection stops it from importing an *editable* install that
> lives under `~/Documents`. Use `pip install .` (not `pip install -e .`) when
> you rely on the Finder integration, and re-install after editing the source.

### Command line

```bash
ofd2pdf invoice.ofd                      # writes invoice.pdf next to the source
ofd2pdf invoice.ofd -o out.pdf           # choose the output path
ofd2pdf invoice.ofd --open               # view only, nothing saved
ofd2pdf a.ofd b.ofd c.ofd --overwrite    # convert several files
ofd2pdf a.ofd b.ofd -o out/ --overwrite  # write all outputs into a directory
python -m ofd2pdf invoice.ofd            # run as a module
```

| Option | Description |
| --- | --- |
| `-o, --output PATH` | Output `.pdf` file, or a directory when converting several inputs |
| `--overwrite` | Overwrite existing PDF files |
| `--open` | Open the PDF in the default viewer without saving it next to the source |
| `--clear-quarantine` | Remove the macOS quarantine flag from the given files/folders |
| `--version` | Print the version |
| `--install-finder-action`, `--install` | Install the macOS right-click integration |
| `--uninstall-finder-action`, `--uninstall` | Remove the macOS integration |
| `--purge` | With `--uninstall`, also uninstall the Python package |

### Python API

```python
from ofd2pdf import convert, convert_bytes, open_pdf

convert("invoice.ofd", "invoice.pdf")           # file -> file; returns the path
convert("invoice.ofd", "invoice.pdf", overwrite=True)

with open("invoice.ofd", "rb") as fh:           # bytes -> file
    convert_bytes(fh.read(), "invoice.pdf")

open_pdf("invoice.ofd")                          # render to a temp file and open
open_pdf("invoice.ofd", open_viewer=False)       # convert only
open_pdf("invoice.ofd", viewer="Preview")        # choose the app to open with
```

The low-level pieces are importable if you want to customise rendering:

```python
from ofd2pdf.container import OfdPackage
from ofd2pdf.parser import parse_ofd
from ofd2pdf.renderer import render_to_pdf

with OfdPackage("invoice.ofd") as package:
    document = parse_ofd(package)
    pdf = render_to_pdf(document, package)
    pdf.save("invoice.pdf")
```

### What it renders

- `TextObject` — glyph-by-glyph positioning from `TextCode` (`X`, `Y`, `DeltaX`,
  `DeltaY`, including the `g` repeat form and `\XXXX` escapes), plus `HScale` and
  `ReadDirection` / `CharDirection` for rotated and vertical text
- `PathObject` — the full path mini-language `S / M / L / Q / B / A / C`
  (elliptical arcs included)
- `ImageObject` and recursive `CompositeObject`
- Page templates (`Background` / `Foreground` z-order)
- Annotation appearance content (stamps/signatures with drawn appearances)
- Fill/stroke colours (`gray` / `rgb` / `cmyk`), alpha, line caps/joins, dashes
  and `DrawParam` inheritance
- Document metadata and embedded attachments

### Fonts

OFD documents usually reference Chinese fonts (宋体/SimSun, 黑体/SimHei,
楷体/KaiTi, …). Resolution order is:

1. an embedded font file (`<ofd:FontFile>`), used first;
2. a matching system font, by `FontName`/`FamilyName` aliases (Songti, STHeiti,
   Courier New, Times New Roman, …);
3. a built-in CJK font for CJK text, or a base-14 font for Latin-only text.

### Limitations

- Colour management is simplified (no ICC profiles).
- Only annotation appearances that contain drawn content are rendered; electronic
  signatures whose visual is carried by a separate signature image are not
  verified or redrawn.
- No text reflow/editing — the output is a fixed-layout reproduction.

### FAQ

**Why is there no "Quick Actions" entry?**
On recent macOS the *Quick Actions* submenu is populated only from app extensions
and Shortcuts; Automator workflows copied to `~/Library/Services` are no longer
shown there. That is why this project uses a document handler app under
"Open With", which is reliable.

**Can I use `pip install -e .`?**
Yes, for development. But if you also use the Finder integration, use
`pip install .` instead — otherwise the app cannot import an editable install
that lives under `~/Documents`.

### Development

```bash
git clone https://github.com/seawander/fapiao-ofd2pdf.git
cd ofd2pdf
pip install -e ".[dev]"
pytest
```

Project layout:

```
ofd2pdf/
├── ofd2pdf/
│   ├── container.py   # ZIP package access + XML/ST_Loc helpers
│   ├── model.py       # dataclasses for the parsed document
│   ├── parser.py      # OFD.xml -> Document (pages, resources, annotations)
│   ├── fonts.py       # font resolution and fallbacks
│   ├── renderer.py    # drawing with PyMuPDF
│   ├── converter.py   # convert() / convert_bytes() / open_pdf()
│   ├── macos.py       # Finder integration (handler app + Automator fallback)
│   └── cli.py         # command line entry point
├── tests/
│   ├── make_sample.py     # regenerates the fixture below
│   └── data/sample.ofd    # synthetic test fixture (fake data, no PII)
├── pyproject.toml
└── README.md
```

> The test fixture is generated from scratch (fake invoice, synthetic image,
> no real data). Regenerate it any time with `python tests/make_sample.py`.

### License

MIT. This project was generated with AI (OpenCode + DeepSeek V4.1 Flash), has not
been professionally audited or exhaustively tested, and is provided "as is"
without warranty of any kind. Verify the output yourself; the authors accept no liability for any loss
arising from its use. See the Disclaimer at the top of this document.
