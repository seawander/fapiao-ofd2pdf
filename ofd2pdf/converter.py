"""High level ``.ofd`` -> ``.pdf`` conversion entry points."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from typing import Optional, Union

from .container import OfdPackage
from .parser import parse_ofd
from .renderer import render_to_pdf

_TEMP_SUBDIR = "ofd2pdf"
_TEMP_MAX_AGE = 60 * 60  # seconds before an orphaned preview is cleaned up


def _temp_dir() -> str:
    directory = os.path.join(tempfile.gettempdir(), _TEMP_SUBDIR)
    os.makedirs(directory, exist_ok=True)
    return directory


def clear_temp_previews() -> bool:
    """Delete the temporary preview directory.  Returns ``True`` if it existed."""

    directory = os.path.join(tempfile.gettempdir(), _TEMP_SUBDIR)
    if os.path.isdir(directory):
        import shutil

        shutil.rmtree(directory, ignore_errors=True)
        return True
    return False


def _cleanup_temp(directory: str, max_age: float = _TEMP_MAX_AGE) -> None:
    """Remove PDFs left over from earlier previews."""

    now = time.time()
    try:
        names = os.listdir(directory)
    except OSError:
        return
    for name in names:
        path = os.path.join(directory, name)
        try:
            if os.path.isfile(path) and now - os.path.getmtime(path) > max_age:
                os.remove(path)
        except OSError:
            continue


def convert(input_path: Union[str, os.PathLike],
            output_path: Optional[Union[str, os.PathLike]] = None,
            *,
            overwrite: bool = False) -> str:
    """Convert a single OFD file to PDF and return the output path.

    :param input_path: path to the source ``.ofd`` file.
    :param output_path: destination ``.pdf`` path.  Defaults to the input path
        with its extension replaced by ``.pdf``.
    :param overwrite: when ``False`` (the default) an existing output file
        raises :class:`FileExistsError`.
    """

    input_path = os.fspath(input_path)
    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + ".pdf"
    output_path = os.fspath(output_path)

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(output_path)

    with OfdPackage(input_path) as package:
        document = parse_ofd(package)
        pdf = render_to_pdf(document, package)
        try:
            pdf.save(output_path, deflate=True, garbage=3)
        finally:
            pdf.close()
    return output_path


def open_pdf(input_path: Union[str, os.PathLike], *,
             viewer: Optional[str] = None, open_viewer: bool = True) -> str:
    """Convert *input_path* and open the PDF in the default viewer.

    The PDF is written to a temporary directory (never next to the source) and
    opened.  Returns the temporary file path.  Orphaned previews older than an
    hour are cleaned up on each call, so viewing does not consume disk space
    permanently.
    """

    input_path = os.fspath(input_path)
    directory = _temp_dir()
    handle, temporary = tempfile.mkstemp(
        prefix=os.path.splitext(os.path.basename(input_path))[0] + "-",
        suffix=".pdf",
        dir=directory,
    )
    os.close(handle)

    try:
        with OfdPackage(input_path) as package:
            document = parse_ofd(package)
            pdf = render_to_pdf(document, package)
            try:
                pdf.save(temporary, deflate=True, garbage=3)
            finally:
                pdf.close()
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise

    _cleanup_temp(directory)

    if open_viewer:
        _open_in_viewer(temporary, viewer)
    return temporary


def _open_in_viewer(path: str, viewer: Optional[str] = None) -> None:
    if sys.platform == "darwin":
        command = ["/usr/bin/open"]
        if viewer:
            command += ["-a", viewer]
        command.append(path)
    elif sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
        return
    else:
        command = ["xdg-open", path]
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError:
        pass


def convert_bytes(data: bytes, output_path: Union[str, os.PathLike],
                  *, overwrite: bool = False) -> str:
    """Convert OFD *data* held in memory to a PDF file."""

    import tempfile

    handle, temporary = tempfile.mkstemp(suffix=".ofd")
    os.close(handle)
    try:
        with open(temporary, "wb") as stream:
            stream.write(data)
        return convert(temporary, output_path, overwrite=overwrite)
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass
