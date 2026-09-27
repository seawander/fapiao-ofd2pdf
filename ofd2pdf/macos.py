"""macOS Finder integration: install a "Convert to PDF" Quick Action.

A Quick Action is an Automator ``.workflow`` bundle stored under
``~/Library/Services``.  We generate one whose single action is a *Run Shell
Script* step that calls :mod:`ofd2pdf` for every selected ``.ofd`` file and
opens the resulting PDF.
"""

from __future__ import annotations

import os
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Dict, List, Optional

WORKFLOW_NAME = "Convert OFD to PDF"
MENU_TITLE = "Convert to PDF"
WORKFLOW_FILENAME = WORKFLOW_NAME + ".workflow"

APP_NAME = "OFD to PDF"
APP_FILENAME = APP_NAME + ".app"

SERVICES_DIR = os.path.expanduser("~/Library/Services")


def _default_app_dir() -> str:
    """Prefer /Applications so the app is visible in Finder's sidebar."""

    system = "/Applications"
    if os.path.isdir(system) and os.access(system, os.W_OK):
        return system
    return os.path.expanduser("~/Applications")


APP_DIR = _default_app_dir()
PBS = "/System/Library/CoreServices/pbs"
OPEN = "/usr/bin/open"
OSACOMPILE = "/usr/bin/osacompile"
CODESIGN = "/usr/bin/codesign"  # absolute: some toolchains shadow `codesign`
XATTR = "/usr/bin/xattr"
LSREGISTER = (
    "/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/"
    "LaunchServices.framework/Versions/A/Support/lsregister"
)


def is_supported() -> bool:
    return sys.platform == "darwin"


def workflow_path() -> str:
    return os.path.join(SERVICES_DIR, WORKFLOW_FILENAME)


def converter_command() -> str:
    """Return the absolute command used to invoke the converter."""

    executable = shutil.which("ofd2pdf")
    if executable:
        return shlex.quote(executable)
    return f"{shlex.quote(sys.executable)} -m ofd2pdf"


def _shell_script() -> str:
    command = converter_command()
    return (
        "for f in \"$@\"; do\n"
        "  case \"$f\" in\n"
        "    *.ofd|*.OFD) ;;\n"
        "    *) continue ;;\n"
        "  esac\n"
        f"  {command} --open \"$f\" || continue\n"
        "done"
    )


def _action(command: str) -> Dict[str, Any]:
    return {
        "isViewVisible": 1,
        "action": {
            "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
            "ActionName": "Run Shell Script",
            "ActionParameters": {
                "CheckedForUserDefaultShell": True,
                "COMMAND_STRING": command,
                "inputMethod": 1,
                "shell": "/bin/zsh",
                "source": "",
            },
            "AMAccepts": {
                "Container": "List",
                "Optional": True,
                "Types": ["com.apple.cocoa.string"],
            },
            "AMActionVersion": "2.0.3",
            "AMApplication": ["Automator"],
            "AMParameterProperties": {
                "CheckedForUserDefaultShell": {},
                "COMMAND_STRING": {},
                "inputMethod": {},
                "shell": {},
                "source": {},
            },
            "AMProvides": {
                "Container": "List",
                "Types": ["com.apple.cocoa.string"],
            },
            "arguments": {
                "0": {"default value": 0, "name": "inputMethod", "required": "0",
                      "type": "0", "uuid": "0"},
                "1": {"default value": False, "name": "CheckedForUserDefaultShell",
                      "required": "0", "type": "0", "uuid": "1"},
                "2": {"default value": "", "name": "source", "required": "0",
                      "type": "0", "uuid": "2"},
                "3": {"default value": "", "name": "COMMAND_STRING",
                      "required": "0", "type": "0", "uuid": "3"},
                "4": {"default value": "/bin/sh", "name": "shell", "required": "0",
                      "type": "0", "uuid": "4"},
            },
            "BundleIdentifier": "com.apple.RunShellScript",
            "CanShowSelectedItemsWhenRun": False,
            "CanShowWhenRun": True,
            "Category": ["AMCategoryUtilities"],
            "CFBundleVersion": "2.0.3",
            "Class Name": "RunShellScriptAction",
            "InputUUID": str(uuid.uuid4()).upper(),
            "Keywords": ["Shell", "Script", "Command", "Run", "Unix"],
            "location": "309.000000:305.000000",
            "nibPath": "/System/Library/Automator/Run Shell Script.action/"
                       "Contents/Resources/Base.lproj/main.nib",
            "OutputUUID": str(uuid.uuid4()).upper(),
            "UnlocalizedApplications": ["Automator"],
            "UUID": str(uuid.uuid4()).upper(),
        },
    }


def _workflow() -> Dict[str, Any]:
    return {
        "AMApplicationBuild": "534",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [_action(_shell_script())],
        "connectors": {},
        "workflowMetaData": {
            "applicationBundleIDsByPath": {},
            "applicationPaths": [],
            "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "outputTypeIdentifier": "com.apple.Automator.nothing",
            "presentationMode": 15,
            "processesInput": False,
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": False,
            "systemImageName": "NSActionTemplate",
            "useAutomaticInputType": False,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }


def _info_plist() -> Dict[str, Any]:
    return {
        "CFBundleDevelopmentRegion": "en_US",
        "CFBundleIdentifier": "org.ofd2pdf.convert-to-pdf",
        "CFBundleName": MENU_TITLE,
        "CFBundleShortVersionString": "1.0",
        "NSServices": [
            {
                "NSBackgroundColorName": "background",
                "NSIconName": "NSActionTemplate",
                "NSMenuItem": {"default": MENU_TITLE},
                "NSMessage": "runWorkflowAsService",
                "NSSendFileTypes": ["public.item"],
            }
        ],
    }


def install(*, refresh: bool = True) -> str:
    """Create the Quick Action and return the bundle path.

    Raises :class:`RuntimeError` when not running on macOS.
    """

    if not is_supported():
        raise RuntimeError("Finder Quick Actions are only available on macOS")

    bundle = workflow_path()
    contents = os.path.join(bundle, "Contents")
    os.makedirs(contents, exist_ok=True)

    with open(os.path.join(contents, "document.wflow"), "wb") as stream:
        plistlib.dump(_workflow(), stream)
    with open(os.path.join(contents, "Info.plist"), "wb") as stream:
        plistlib.dump(_info_plist(), stream)

    if refresh:
        refresh_services()
    return bundle


def uninstall() -> bool:
    """Remove the Quick Action.  Returns ``True`` if something was removed."""

    bundle = workflow_path()
    if os.path.isdir(bundle):
        shutil.rmtree(bundle)
        refresh_services()
        return True
    return False


def refresh_services() -> None:
    """Ask the system to re-scan the Services folder."""

    if os.path.exists(PBS):
        try:
            subprocess.run([PBS, "-flush"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


# -- "Open With" handler app ------------------------------------------------
#
# Finder's *Quick Actions* menu on recent macOS only lists app extensions and
# Shortcuts, so an Automator workflow is not offered there.  A document handler
# application, on the other hand, is offered under the Finder's "Open With"
# menu as soon as it declares support for the ``public.ofd`` type.  We build a
# tiny AppleScript droplet that converts the files it is asked to open.

def app_bundle_path() -> str:
    return os.path.join(APP_DIR, APP_FILENAME)


def _applescript(converter: str) -> str:
    command = converter.replace("\\", "\\\\").replace('"', '\\"')
    return (
        "on open theFiles\n"
        f'\tset converter to "{command}"\n'
        "\trepeat with currentFile in theFiles\n"
        "\t\tset thePath to POSIX path of currentFile\n"
        "\t\tif thePath ends with \".ofd\" or thePath ends with \".OFD\" then\n"
        "\t\t\ttry\n"
        "\t\t\t\tdo shell script converter & \" --open \" & "
        "quoted form of thePath\n"
        "\t\t\tend try\n"
        "\t\tend if\n"
        "\tend repeat\n"
        "end open\n"
    )


def _register(path: str) -> None:
    if os.path.exists(LSREGISTER):
        try:
            subprocess.run([LSREGISTER, "-f", path], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def _unregister(path: str) -> None:
    if os.path.exists(LSREGISTER):
        try:
            subprocess.run([LSREGISTER, "-u", path], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def _search_dirs() -> List[str]:
    """Every place the handler app may have been installed to."""

    directories = [APP_DIR, "/Applications", os.path.expanduser("~/Applications")]
    unique: List[str] = []
    for directory in directories:
        if directory and directory not in unique:
            unique.append(directory)
    return unique


def _clear_temp_previews() -> bool:
    from .converter import clear_temp_previews

    return clear_temp_previews()


def install_app(*, register: bool = True) -> str:
    """Build the "Open With" handler app and return its bundle path."""

    if not is_supported():
        raise RuntimeError("the Finder handler app is only available on macOS")

    bundle = app_bundle_path()
    shutil.rmtree(bundle, ignore_errors=True)
    os.makedirs(APP_DIR, exist_ok=True)

    for directory in _search_dirs():
        stale = os.path.join(directory, APP_FILENAME)
        if stale != bundle and os.path.isdir(stale):
            _unregister(stale)
            shutil.rmtree(stale, ignore_errors=True)

    handle, script_path = tempfile.mkstemp(suffix=".applescript")
    os.close(handle)
    try:
        with open(script_path, "w", encoding="utf-8") as stream:
            stream.write(_applescript(converter_command()))
        result = subprocess.run([OSACOMPILE, "-o", bundle, script_path],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "osacompile failed")
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    info_path = os.path.join(bundle, "Contents", "Info.plist")
    with open(info_path, "rb") as stream:
        info = plistlib.load(stream)
    info.update({
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": "org.ofd2pdf.handler",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "OFD Document",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["public.ofd"],
            }
        ],
    })
    with open(info_path, "wb") as stream:
        plistlib.dump(info, stream)

    _sign(bundle)

    if register:
        _register(bundle)
    return bundle


def _sign(path: str) -> None:
    """Ad-hoc sign the bundle with Apple's codesign (not any PATH shadow)."""

    if os.path.exists(CODESIGN):
        try:
            subprocess.run([CODESIGN, "--force", "-s", "-", path], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def clear_quarantine(paths) -> int:
    """Remove the ``com.apple.quarantine`` flag so Gatekeeper stops asking.

    Downloaded OFD files (e.g. e-invoices received by Mail) carry this flag;
    opening them with a non-notarized helper app makes macOS show the
    "could not verify ... is free of malware" dialog.  Returns the number of
    paths processed.
    """

    if isinstance(paths, (str, bytes, os.PathLike)):
        paths = [paths]
    count = 0
    for path in paths:
        path = os.fspath(path)
        command = [XATTR]
        if os.path.isdir(path):
            command.append("-r")
        command += ["-d", "com.apple.quarantine", path]
        try:
            subprocess.run(command, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            count += 1
        except OSError:
            continue
    return count


def uninstall_app() -> bool:
    """Remove the handler app from every location and unregister it."""

    removed = False
    for directory in _search_dirs():
        bundle = os.path.join(directory, APP_FILENAME)
        if os.path.isdir(bundle):
            _unregister(bundle)
            shutil.rmtree(bundle, ignore_errors=True)
            removed = True
    return removed


def clean_uninstall() -> Dict[str, Any]:
    """Remove every trace of the macOS integration.

    Deletes the handler app (all locations) and its Launch Services
    registration, the Automator fallback workflow, the Services cache entry,
    and any temporary preview files.  The Python package itself is left alone.
    """

    removed: Dict[str, Any] = {"apps": [], "workflows": [], "temp": False}

    for directory in _search_dirs():
        bundle = os.path.join(directory, APP_FILENAME)
        if os.path.isdir(bundle):
            _unregister(bundle)
            shutil.rmtree(bundle, ignore_errors=True)
            removed["apps"].append(bundle)

    workflow = os.path.join(SERVICES_DIR, WORKFLOW_FILENAME)
    if os.path.isdir(workflow):
        shutil.rmtree(workflow, ignore_errors=True)
        removed["workflows"].append(workflow)
        refresh_services()

    removed["temp"] = _clear_temp_previews()
    return removed


def run_app(inputs) -> subprocess.CompletedProcess:
    """Launch the handler app as Finder would (for testing)."""

    if isinstance(inputs, (str, bytes, os.PathLike)):
        inputs = [inputs]
    arguments = [OPEN, "-a", app_bundle_path(), *map(os.fspath, inputs)]
    return subprocess.run(arguments, check=False, capture_output=True, text=True)


def run_workflow(inputs, workflow: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run the installed Quick Action from the command line (for testing)."""

    path = workflow or workflow_path()
    if isinstance(inputs, (str, bytes, os.PathLike)):
        inputs = [inputs]
    arguments = ["/usr/bin/automator", "-i", *map(os.fspath, inputs), path]
    return subprocess.run(arguments, check=False, capture_output=True, text=True)
