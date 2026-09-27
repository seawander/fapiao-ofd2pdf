"""Command line interface: ``ofd2pdf``."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List, Optional

from . import __version__, macos
from .converter import convert, open_pdf
from .exceptions import OfdError


def _output_for(input_path: str, output: Optional[str], multiple: bool) -> str:
    default = os.path.splitext(input_path)[0] + ".pdf"
    if not output:
        return default
    if multiple or os.path.isdir(output) or output.endswith(os.sep):
        base = os.path.splitext(os.path.basename(input_path))[0] + ".pdf"
        return os.path.join(output, base)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]) or "ofd2pdf",
        description="Convert OFD documents to PDF.",
    )
    parser.add_argument("inputs", nargs="*", help="input .ofd file(s)")
    parser.add_argument("-o", "--output",
                        help="output .pdf file, or a directory for multiple inputs")
    parser.add_argument("--overwrite", action="store_true",
                        help="overwrite existing PDF files")
    parser.add_argument("--open", action="store_true",
                        help="open the PDF in the default viewer without saving "
                             "it next to the source (uses a temporary file)")
    parser.add_argument("--clear-quarantine", action="store_true",
                        help="remove the macOS quarantine flag from the given "
                             "files/folders (prevents Gatekeeper prompts)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    finder = parser.add_argument_group("macOS Finder integration")
    finder.add_argument("--install-finder-action", "--install", action="store_true",
                        dest="install_finder_action",
                        help='install right-click integration ("Open With > OFD to PDF")')
    finder.add_argument("--uninstall-finder-action", "--uninstall",
                        action="store_true", dest="uninstall_finder_action",
                        help="remove the macOS integration (app, service, temp previews)")
    finder.add_argument("--purge", action="store_true",
                        help="with --uninstall, also uninstall the Python package")
    return parser


def _run_finder_action(args: argparse.Namespace) -> Optional[int]:
    if not (args.install_finder_action or args.uninstall_finder_action):
        return None
    if not macos.is_supported():
        print("error: Finder integration is only available on macOS", file=sys.stderr)
        return 1
    if args.uninstall_finder_action:
        removed = macos.clean_uninstall()
        if removed["apps"] or removed["workflows"] or removed["temp"]:
            print("Removed macOS right-click integration:")
            for path in removed["apps"]:
                print(f"  app:      {path}")
            for path in removed["workflows"]:
                print(f"  workflow: {path}")
            if removed["temp"]:
                print("  temporary previews")
        else:
            print("macOS right-click integration was not installed.")
        if args.purge:
            print("Removing the Python package…")
            for name in ("fapiao-ofd2pdf", "ofd2pdf"):
                subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", name],
                               check=False)
        else:
            print("To remove the Python package as well: "
                  "ofd2pdf --uninstall --purge")
    if args.install_finder_action:
        app_path = macos.install_app()
        macos.install()  # Automator service, used on older macOS versions
        print(f'Installed "{macos.APP_NAME}" handler app.')
        print(f"  bundle: {app_path}")
        print('Right-click an .ofd file in Finder > Open With > "OFD to PDF".')
        print("Tip: choose that once from the \"Other…\" list to keep it on the menu.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    finder_result = _run_finder_action(args)
    if finder_result is not None:
        return finder_result

    if args.clear_quarantine:
        if not macos.is_supported():
            print("error: --clear-quarantine is only available on macOS",
                  file=sys.stderr)
            return 1
        if not args.inputs:
            print("error: provide one or more files or folders", file=sys.stderr)
            return 2
        count = macos.clear_quarantine(args.inputs)
        print(f"Cleared the quarantine flag on {count} path(s).")
        return 0

    if not args.inputs:
        build_parser().print_help()
        return 2

    multiple = len(args.inputs) > 1
    failures = 0
    for input_path in args.inputs:
        try:
            if args.open:
                result = open_pdf(input_path)
                print(f"{input_path} -> opened {result}")
            else:
                output_path = _output_for(input_path, args.output, multiple)
                result = convert(input_path, output_path, overwrite=args.overwrite)
                print(f"{input_path} -> {result}")
        except (OfdError, OSError, FileExistsError) as error:
            failures += 1
            print(f"error: {input_path}: {error}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
