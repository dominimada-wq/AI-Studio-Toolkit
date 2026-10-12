"""
Coverage for the local name and the creation contract of
ComfyUIEngine.download_output(): the local file never takes its name
(or its location) from the remote filename/subfolder/type, is created
exclusively under a random identifier, retries only on a name
collision, and cleans up only its own file when writing or closing
fails, keeping the initial ordinary error.

The classes are written so that the same file can be run against the
previous implementation (which opened the remote name with "wb") and
against the current one, and so that the results can be read by nature:

  * DownloadInvariantsTest - what must hold before AND after (request
    parameters, bytes, network and local error propagation, handle
    release). A failure here is a regression, or a mounting error.
  * DownloadDefectScenariosTest and
    AcceptedImageSurvivesRejectedRegenerationTest - scenarios that
    expose the defect: expected to FAIL on the previous implementation
    and to pass on the current one. They assert outcomes (a file keeps
    its content, the private tree changes only by one new file inside
    outputs/, no alternate stream appears), never the new name format.
  * DownloadNewContractTest and DownloadNewContractFailureTest -
    assertions of the new contract itself (name format, extension,
    exclusive mode, eight attempts, cleanup, notes): expected to fail
    on the previous implementation by construction. They are not
    evidence about the previous behaviour.
A failure of a test is only evidence once its mounting is known to be
correct: an error raised by the fixture itself proves nothing.

Isolation: every scenario runs inside a private temporary tree and
never contacts a network (urllib.request.urlopen is replaced). The
"dangerous" remote names resolve, if honoured, to sentinel files inside
that same private tree - never outside it, never to a device or a
network share. Alternate-stream names are exercised only inside it.

Declared limits:
  * Write, close and removal failures are INJECTED around a real file
    (a wrapper that behaves like a file object, context-manager
    protocol included, and whose close() always releases the real
    handle first) and through a replacement of os.unlink; no real
    disk-full or I/O error occurs.
  * The "add_note unavailable" scenarios use exception objects whose
    add_note is missing or failing. That simulates the absence of the
    method on the error being handled; it is NOT a run under Python 3.10.
  * Directory/junction collisions and alternate streams are
    Windows-only; the junction case is skipped when it cannot be created.
  * Signature-only payloads (SIGNATURE_PNG_BYTES...) are NOT decodable
    images: they serve the byte/extension tests only. The Qt scenario
    uses two real, decodable PNG images.
  * The Qt test class assembles real widgets and managers but
    substitutes the network and several collaborators; see its
    docstring. It is not an end-to-end test with a real ComfyUI.
"""

import contextlib
import errno
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QBuffer, QByteArray, QEvent, QIODevice, QObject, Qt, Signal
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.engines.comfyui_engine import ComfyUIEngine, ComfyUIEngineError
from src.managers.generation_manager import GenerationManager
from src.managers.workspace_manager import (
    WORKSPACE_CLOSED,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_RENAMED,
    WORKSPACE_SAVED,
    WorkspaceManager,
)
from src.ui.comfyui_lifecycle_manager import RUNNING_OWNED
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.inference_page import InferencePage

from tests.integration._qt_dialog_safety_net import start_dialog_guard, stop_dialog_guard

_app = QApplication.instance() or QApplication([])

LOCAL_NAME = re.compile(r"^[0-9a-f]{32}\.(png|jpg|webp)$")

# Signature-only payloads: enough for the byte and extension tests, NOT decodable images.
SIGNATURE_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"png-payload"
SIGNATURE_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"jpeg-payload"
SIGNATURE_WEBP_BYTES = b"RIFF" + b"\x10\x00\x00\x00" + b"WEBP" + b"webp-payload"

HAS_ADD_NOTE = hasattr(BaseException, "add_note")

_REAL_UNLINK = os.unlink


def _uuid_for(number: int) -> uuid.UUID:
    return uuid.UUID(int=number)


def _name(number: int, extension: str = "png") -> str:
    return f"{_uuid_for(number).hex}.{extension}"


def _notes(error: BaseException) -> list:
    return list(getattr(error, "__notes__", []))


def _tree(root: Path) -> dict:
    """Every file (with its bytes) and directory under root, keyed by relative path."""
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for directory in dirnames:
            result[str(Path(dirpath, directory).relative_to(root)) + os.sep] = None
        for filename in filenames:
            path = Path(dirpath, filename)
            result[str(path.relative_to(root))] = path.read_bytes()
    return result


class _FakeResponse:
    """Minimal stand-in for the object urllib.request.urlopen() returns."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self._body


class _NoteLessOSError(OSError):
    """An error object on which add_note is not available."""

    add_note = None


class _NoteRefusingOSError(OSError):
    """An error object whose add_note exists but fails."""

    def add_note(self, note):
        raise RuntimeError("note refused")


class _FaultyFile:
    """
    INJECTED faults around a REAL file created by the real exclusive
    (or truncating) open. It honours the file-object protocol the code
    under test may use - write(), close(), and the context manager,
    whose __exit__ closes exactly like a real file does, so a close
    error raised there replaces a pending error as it would for a real
    file. close() always releases the real handle first, so a removal
    that follows is never blocked by a handle this wrapper kept open.
    """

    def __init__(self, real, write_error=None, close_error=None):
        self._real = real
        self._write_error = write_error
        self._close_error = close_error
        self.write_calls = 0
        self.close_calls = 0

    @property
    def closed(self):
        return self._real.closed

    def write(self, data):
        self.write_calls += 1
        if self._write_error is not None:
            raise self._write_error
        return self._real.write(data)

    def close(self):
        self.close_calls += 1
        self._real.close()
        if self._close_error is not None:
            raise self._close_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


class _OpenSpy:
    """
    Replaces the open() the engine module looks up: records every call,
    optionally raises a given error for a given (1-based) call before
    anything is created, and otherwise delegates to the real open().
    Every real handle it creates is remembered so that the fixture can
    release (and report) whatever the code under test left open.
    """

    def __init__(self, open_errors=None, write_error=None, close_error=None):
        self.calls = []
        self.faulty_files = []
        self.real_files = []
        self._open_errors = open_errors or {}
        self._write_error = write_error
        self._close_error = close_error

    def __call__(self, path, mode="r", *args, **kwargs):
        self.calls.append((Path(path).name, mode))
        error = self._open_errors.get(len(self.calls))
        if error is not None:
            raise error
        real = open(path, mode, *args, **kwargs)
        self.real_files.append(real)
        if self._write_error is None and self._close_error is None:
            return real
        faulty = _FaultyFile(real, self._write_error, self._close_error)
        self.faulty_files.append(faulty)
        return faulty

    def release_leaked(self) -> list:
        """Closes every real handle still open and returns their names."""
        leaked = []
        for real in self.real_files:
            if not real.closed:
                leaked.append(Path(real.name).name)
                real.close()
        return leaked


class _UnlinkSpy:
    """Replaces os.unlink: records the names, optionally fails, otherwise really removes."""

    def __init__(self, error=None):
        self.paths = []
        self._error = error

    def __call__(self, path, *args, **kwargs):
        self.paths.append(Path(path).name)
        if self._error is not None:
            raise self._error
        _REAL_UNLINK(path, *args, **kwargs)


class _CheckedCleanupCase(unittest.TestCase):
    """
    Cleanup that never hides an incomplete release: every problem is
    recorded and reported as an error by the last cleanup to run
    (registered first, so executed last), after all other cleanups
    were attempted.
    """

    def setUp(self):
        super().setUp()
        self.cleanup_problems = []
        self.addCleanup(self._report_cleanup_problems)

    def _report_cleanup_problems(self):
        if self.cleanup_problems:
            raise AssertionError("incomplete cleanup: " + " | ".join(self.cleanup_problems))

    def make_private_dir(self) -> Path:
        path = Path(tempfile.mkdtemp())
        self.addCleanup(self._remove_tree, path)
        return path

    def _remove_tree(self, path: Path):
        try:
            shutil.rmtree(path)
        except OSError as error:
            self.cleanup_problems.append(f"could not remove {path}: {error!r}")


class _DownloadCase(_CheckedCleanupCase):

    def setUp(self):
        super().setUp()
        self.base = self.make_private_dir()
        self.out = self.base / "outputs"
        self.out.mkdir()
        self.engine = ComfyUIEngine()

    def make_hostile_cases(self):
        """
        Remote parameters that a previous implementation would have turned
        into a local path. Every destination exists INSIDE the private tree
        and holds a sentinel; nothing here points outside it.
        """
        sibling = self.base / "sibling"
        absolute_target = self.base / "absolute_target"
        sibling.mkdir()
        absolute_target.mkdir()
        (sibling / "hit_backslash.png").write_bytes(b"SENTINEL-1")
        (sibling / "hit_slash.png").write_bytes(b"SENTINEL-2")
        (absolute_target / "hit_absolute.png").write_bytes(b"SENTINEL-3")
        return [
            ("..\\sibling\\hit_backslash.png", "", "output"),
            ("../sibling/hit_slash.png", "", "output"),
            (str(absolute_target / "hit_absolute.png"), "", "output"),
            ("name.png", "..\\sibling", "temp"),
            ("my image (1).png", "café / sub", "output"),
            ("same.png", "", "output"),
        ]

    def download(self, data, filename="img.png", subfolder="", type_="output", directory=None):
        """Real download_output() against a replaced urlopen; returns (path, urlopen mock)."""
        with patch("urllib.request.urlopen", return_value=_FakeResponse(data)) as mock_urlopen:
            path = self.engine.download_output(
                filename, subfolder, type_, str(self.out if directory is None else directory)
            )
        return path, mock_urlopen

    @contextlib.contextmanager
    def instrumented(self, uuid_numbers, data=SIGNATURE_PNG_BYTES, spy=None, unlink=None):
        """
        Replaces the network, uuid4 (fixed sequence), the engine's open() and
        os.unlink. Whatever handle the code under test leaves open is closed
        on the way out and reported as a cleanup problem.
        """
        spy = _OpenSpy() if spy is None else spy
        unlink = _UnlinkSpy() if unlink is None else unlink
        values = [_uuid_for(number) for number in uuid_numbers]
        try:
            with patch("urllib.request.urlopen", return_value=_FakeResponse(data)), patch(
                "uuid.uuid4", side_effect=iter(values)
            ) as mock_uuid4, patch("src.engines.comfyui_engine.open", new=spy, create=True), patch(
                "os.unlink", new=unlink
            ):
                yield SimpleNamespace(spy=spy, unlink=unlink, uuid4=mock_uuid4)
        finally:
            leaked = spy.release_leaked()
            if leaked:
                self.cleanup_problems.append(f"handle(s) left open by the code under test: {leaked}")

    def download_expecting_error(self, uuid_numbers, **kwargs):
        """Runs download_output() under instrumented() and returns (error, context)."""
        with self.instrumented(uuid_numbers, **kwargs) as context:
            try:
                self.engine.download_output("img.png", "", "output", str(self.out))
            except BaseException as error:  # noqa: BLE001 - the error object itself is under test
                return error, context
        self.fail("download_output() returned instead of raising")


# ======================================================================================================== invariants
class DownloadInvariantsTest(_DownloadCase):
    """Must hold on the previous AND the current implementation."""

    def test_the_request_carries_the_three_remote_parameters_unchanged(self):
        for filename, subfolder, type_ in self.make_hostile_cases():
            with self.subTest(filename=filename, subfolder=subfolder):
                _, mock_urlopen = self.download(SIGNATURE_PNG_BYTES, filename, subfolder, type_)

                sent = urllib.parse.urlsplit(mock_urlopen.call_args[0][0].full_url)
                query = urllib.parse.parse_qs(sent.query, keep_blank_values=True)
                self.assertEqual(sent.path, "/view")
                self.assertEqual(set(query), {"filename", "subfolder", "type"})
                self.assertEqual(query["filename"], [filename])
                self.assertEqual(query["subfolder"], [subfolder])
                self.assertEqual(query["type"], [type_])

    def test_bytes_are_written_unchanged_and_the_returned_path_is_that_file(self):
        for data in (SIGNATURE_PNG_BYTES, SIGNATURE_JPEG_BYTES, SIGNATURE_WEBP_BYTES, b"", bytes(range(256))):
            with self.subTest(head=data[:8]):
                path, _ = self.download(data, "img.png")
                self.assertEqual(Path(path).parent, self.out)
                self.assertEqual(Path(path).read_bytes(), data)

    def test_network_errors_create_nothing_and_stay_engine_errors(self):
        for error in (urllib.error.URLError("Connection refused"), OSError("socket failure")):
            with self.subTest(error=repr(error)):
                with patch("urllib.request.urlopen", side_effect=error):
                    with self.assertRaises(ComfyUIEngineError):
                        self.engine.download_output("img.png", "", "output", str(self.out))
                self.assertEqual(os.listdir(self.out), [])

    def test_an_http_error_creates_nothing_and_stays_an_engine_error(self):
        http_error = urllib.error.HTTPError(
            url="http://127.0.0.1:8188/view", code=404, msg="not found", hdrs=None, fp=io.BytesIO(b"")
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaises(ComfyUIEngineError) as context:
                self.engine.download_output("missing.png", "", "output", str(self.out))
        self.assertIn("404", str(context.exception))
        self.assertEqual(os.listdir(self.out), [])

    def test_a_missing_output_directory_raises_the_normal_os_error(self):
        missing = self.base / "does_not_exist"
        with patch("urllib.request.urlopen", return_value=_FakeResponse(SIGNATURE_PNG_BYTES)):
            with self.assertRaises(FileNotFoundError):
                self.engine.download_output("img.png", "", "output", str(missing))
        self.assertFalse(missing.exists())

    def test_other_errors_on_creation_propagate_unchanged_without_removal(self):
        injected = [
            PermissionError(errno.EACCES, "INJECTED permission refused"),
            OSError(errno.ENOSPC, "INJECTED no space"),
            OSError(errno.EIO, "INJECTED I/O error"),
        ]
        for error_to_raise in injected:
            with self.subTest(error=repr(error_to_raise)):
                spy = _OpenSpy(open_errors={1: error_to_raise})
                error, context = self.download_expecting_error([1, 2, 3], spy=spy)

                self.assertIs(error, error_to_raise)
                self.assertEqual(len(context.spy.calls), 1)
                self.assertEqual(context.unlink.paths, [])
                self.assertEqual(os.listdir(self.out), [])

    def test_a_write_failure_raises_the_write_error_and_releases_the_handle(self):
        write_error = OSError(errno.ENOSPC, "INJECTED disk full")
        spy = _OpenSpy(write_error=write_error)

        error, _ = self.download_expecting_error([1, 2], spy=spy)

        self.assertIs(error, write_error)
        self.assertEqual(len(spy.faulty_files), 1)
        self.assertTrue(spy.faulty_files[0].closed)


# =================================================================================================== defect scenarios
class DownloadDefectScenariosTest(_DownloadCase):
    """
    Expected to FAIL on the previous implementation and pass on the
    current one. Outcomes only: no assertion on the new name format.
    """

    def test_two_downloads_of_the_same_remote_name_keep_the_first_file(self):
        first_bytes = SIGNATURE_PNG_BYTES + b"-first"
        second_bytes = SIGNATURE_PNG_BYTES + b"-second"
        with patch(
            "urllib.request.urlopen",
            side_effect=[_FakeResponse(first_bytes), _FakeResponse(second_bytes)],
        ):
            first = self.engine.download_output("AIStudioToolkit_00001_.png", "", "output", str(self.out))
            second = self.engine.download_output("AIStudioToolkit_00001_.png", "", "output", str(self.out))

        self.assertNotEqual(first, second)
        self.assertEqual(Path(first).read_bytes(), first_bytes)
        self.assertEqual(Path(second).read_bytes(), second_bytes)
        self.assertEqual(sorted(os.listdir(self.out)), sorted([Path(first).name, Path(second).name]))

    def test_hostile_remote_names_change_the_private_tree_by_one_new_file_inside_outputs_only(self):
        for filename, subfolder, type_ in self.make_hostile_cases():
            with self.subTest(filename=filename, subfolder=subfolder):
                before = _tree(self.base)
                path, _ = self.download(SIGNATURE_PNG_BYTES, filename, subfolder, type_)
                after = _tree(self.base)

                modified_or_removed = sorted(key for key in before if after.get(key) != before[key])
                added = sorted(set(after) - set(before))
                self.assertEqual(modified_or_removed, [], "an existing file or directory was changed")
                self.assertEqual(len(added), 1, f"expected exactly one new file, got {added}")
                self.assertTrue(added[0].startswith("outputs" + os.sep), added[0])
                self.assertEqual(Path(path).parent, self.out)

    @unittest.skipUnless(sys.platform == "win32", "alternate data streams are an NTFS/Windows feature")
    def test_alternate_stream_names_create_neither_a_base_file_nor_a_stream(self):
        # Everything stays inside the private outputs/ directory.
        (self.out / "with_base.png").write_bytes(b"SENTINEL-BASE")
        for remote_name, base_name in (
            ("stream_only.png:hidden", "stream_only.png"),
            ("with_base.png:hidden", "with_base.png"),
        ):
            with self.subTest(remote=remote_name):
                before = sorted(os.listdir(self.out))
                path, _ = self.download(SIGNATURE_PNG_BYTES, remote_name)
                after = sorted(os.listdir(self.out))

                self.assertEqual(Path(path).parent, self.out)
                self.assertEqual(Path(path).read_bytes(), SIGNATURE_PNG_BYTES)
                # The only new directory entry is the downloaded file itself.
                self.assertEqual(sorted(set(after) - set(before)), [Path(path).name])
                self.assertEqual(sorted(set(before) - set(after)), [])
                if base_name == "with_base.png":
                    self.assertEqual((self.out / base_name).read_bytes(), b"SENTINEL-BASE")
                else:
                    self.assertFalse((self.out / base_name).exists(), "a base file appeared under the stream's name")
                # No alternate stream under the remote name: opening it must fail.
                try:
                    handle = open(str(self.out / remote_name), "rb")
                except FileNotFoundError:
                    pass
                else:
                    handle.close()
                    self.fail(f"alternate stream {remote_name!r} exists")


# ================================================================================================ new contract (names)
class DownloadNewContractTest(_DownloadCase):
    """Assertions of the new contract; expected to fail on the previous implementation by construction."""

    def test_local_name_is_a_uuid4_hex_with_no_prefix_and_no_remote_name(self):
        with self.instrumented([0x1234]):
            path = self.engine.download_output("remote_name.png", "", "output", str(self.out))

        self.assertEqual(Path(path), self.out / _name(0x1234))
        self.assertNotIn("remote_name", Path(path).name)

    def test_every_remote_name_gets_a_name_of_the_new_format_inside_outputs(self):
        for filename, subfolder, type_ in self.make_hostile_cases():
            with self.subTest(filename=filename, subfolder=subfolder):
                path, _ = self.download(SIGNATURE_PNG_BYTES, filename, subfolder, type_)
                self.assertEqual(Path(path).parent, self.out)
                self.assertRegex(Path(path).name, LOCAL_NAME)

    def test_extension_follows_the_signature_and_the_bytes_are_unchanged(self):
        cases = [
            (SIGNATURE_PNG_BYTES, "png"),
            (SIGNATURE_JPEG_BYTES, "jpg"),
            (SIGNATURE_WEBP_BYTES, "webp"),
            (b"", "png"),
            (b"RIFF", "png"),
            (b"RIFF\x00\x00\x00\x00WAVE", "png"),
            (b"\xff", "png"),
            (b"GIF89a-not-in-the-list", "png"),
            (bytes(range(256)), "png"),
        ]
        for data, extension in cases:
            with self.subTest(extension=extension, head=data[:12]):
                # The remote name suggests another format: only the bytes decide.
                remote = "from_the_server.webp" if extension != "webp" else "from_the_server.jpg"
                path, _ = self.download(data, remote)
                self.assertEqual(Path(path).suffix, "." + extension)
                self.assertRegex(Path(path).name, LOCAL_NAME)
                self.assertEqual(Path(path).read_bytes(), data)

    def test_the_file_is_created_with_the_exclusive_binary_mode(self):
        with self.instrumented([1]) as context:
            path = self.engine.download_output("img.png", "", "output", str(self.out))

        self.assertEqual(context.spy.calls, [(_name(1), "xb")])
        self.assertEqual(Path(path).read_bytes(), SIGNATURE_PNG_BYTES)

    def test_existing_files_are_never_overwritten_and_the_next_name_is_used(self):
        for number in (1, 2, 3):
            (self.out / _name(number)).write_bytes(b"EXISTING-%d" % number)

        with self.instrumented([1, 2, 3, 4]) as context:
            path = self.engine.download_output("img.png", "", "output", str(self.out))

        self.assertEqual(Path(path), self.out / _name(4))
        self.assertEqual(Path(path).read_bytes(), SIGNATURE_PNG_BYTES)
        self.assertEqual(len(context.spy.calls), 4)
        self.assertEqual(context.uuid4.call_count, 4)
        for number in (1, 2, 3):
            self.assertEqual((self.out / _name(number)).read_bytes(), b"EXISTING-%d" % number)
        self.assertEqual(context.unlink.paths, [])

    def test_a_hard_link_collision_is_not_overwritten(self):
        source = self.base / "hardlink_source.bin"
        source.write_bytes(b"LINKED")
        try:
            os.link(source, self.out / _name(1))
        except (OSError, NotImplementedError, AttributeError) as error:
            self.skipTest(f"hard links unavailable here: {error!r}")

        with self.instrumented([1, 2]):
            path = self.engine.download_output("img.png", "", "output", str(self.out))

        self.assertEqual(Path(path), self.out / _name(2))
        self.assertEqual((self.out / _name(1)).read_bytes(), b"LINKED")
        self.assertEqual(source.read_bytes(), b"LINKED")

    def test_eight_collisions_stop_the_search_and_raise_file_exists(self):
        for number in range(1, 9):
            (self.out / _name(number)).write_bytes(b"EXISTING-%d" % number)

        # A ninth free name is available but must never be tried.
        error, context = self.download_expecting_error(list(range(1, 11)))

        self.assertIsInstance(error, FileExistsError)
        self.assertEqual(error.errno, errno.EEXIST)
        self.assertIsInstance(error.__cause__, FileExistsError)
        self.assertEqual(len(context.spy.calls), 8)
        self.assertEqual(context.uuid4.call_count, 8)
        self.assertEqual(context.unlink.paths, [])
        self.assertFalse((self.out / _name(9)).exists())
        self.assertEqual(sorted(os.listdir(self.out)), sorted(_name(number) for number in range(1, 9)))
        for number in range(1, 9):
            self.assertEqual((self.out / _name(number)).read_bytes(), b"EXISTING-%d" % number)

    def test_an_identifier_that_always_collides_makes_exactly_eight_attempts(self):
        (self.out / _name(7)).write_bytes(b"EXISTING")

        error, context = self.download_expecting_error([7] * 20)

        self.assertIsInstance(error, FileExistsError)
        self.assertEqual(len(context.spy.calls), 8)
        self.assertEqual(context.uuid4.call_count, 8)
        self.assertEqual(os.listdir(self.out), [_name(7)])
        self.assertEqual((self.out / _name(7)).read_bytes(), b"EXISTING")

    def test_other_creation_errors_are_not_retried_with_another_name(self):
        error_to_raise = PermissionError(errno.EACCES, "INJECTED permission refused")
        spy = _OpenSpy(open_errors={1: error_to_raise})

        error, context = self.download_expecting_error([1, 2, 3], spy=spy)

        self.assertIs(error, error_to_raise)
        self.assertEqual(context.uuid4.call_count, 1)

    @unittest.skipUnless(sys.platform == "win32", "directory collision behaviour observed on Windows")
    def test_a_directory_collision_is_not_treated_as_a_name_collision(self):
        (self.out / _name(1)).mkdir()

        error, context = self.download_expecting_error([1, 2])

        self.assertIsInstance(error, OSError)
        self.assertNotIsInstance(error, FileExistsError)
        self.assertEqual(len(context.spy.calls), 1)
        self.assertEqual(context.unlink.paths, [])
        self.assertTrue((self.out / _name(1)).is_dir())
        self.assertFalse((self.out / _name(2)).exists())

    @unittest.skipUnless(sys.platform == "win32", "junctions are a Windows feature")
    def test_a_junction_collision_is_not_followed_nor_retried(self):
        target = self.base / "junction_target"
        target.mkdir()
        link = self.out / _name(1)
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            self.skipTest(f"junction could not be created: exit {result.returncode}")
        self.addCleanup(self._remove_junction, link)

        error, context = self.download_expecting_error([1, 2])

        self.assertIsInstance(error, OSError)
        self.assertNotIsInstance(error, FileExistsError)
        self.assertEqual(len(context.spy.calls), 1)
        self.assertEqual(context.unlink.paths, [])
        self.assertEqual(os.listdir(target), [])
        self.assertFalse((self.out / _name(2)).exists())

    def _remove_junction(self, link):
        # Registered after the tree removal, so it runs before it: the
        # junction is detached without ever descending into its target.
        try:
            os.rmdir(link)
        except OSError as error:
            self.cleanup_problems.append(f"could not detach junction {link}: {error!r}")


class DownloadNewContractFailureTest(_DownloadCase):
    """Injected write/close/removal failures: new cleanup contract, initial ordinary error kept."""

    def test_a_write_failure_removes_only_the_new_file_and_raises_the_write_error(self):
        write_error = OSError(errno.ENOSPC, "INJECTED disk full")
        spy = _OpenSpy(write_error=write_error)

        error, context = self.download_expecting_error([1, 2], spy=spy)

        self.assertIs(error, write_error)
        self.assertEqual(context.unlink.paths, [_name(1)])
        self.assertEqual(spy.faulty_files[0].close_calls, 1)
        self.assertEqual(os.listdir(self.out), [])
        self.assertEqual(_notes(error), [])

    def test_a_close_failure_after_a_complete_write_removes_the_file_and_raises_the_close_error(self):
        close_error = OSError(errno.EIO, "INJECTED close failure")
        spy = _OpenSpy(close_error=close_error)

        error, context = self.download_expecting_error([1, 2], spy=spy)

        self.assertIs(error, close_error)
        self.assertEqual(spy.faulty_files[0].write_calls, 1)
        self.assertEqual(context.unlink.paths, [_name(1)])
        self.assertEqual(os.listdir(self.out), [])

    def test_a_double_failure_keeps_the_write_error_and_still_removes_the_file(self):
        write_error = OSError(errno.ENOSPC, "INJECTED disk full")
        close_error = OSError(errno.EIO, "INJECTED close failure")
        spy = _OpenSpy(write_error=write_error, close_error=close_error)

        error, context = self.download_expecting_error([1, 2], spy=spy)

        self.assertIs(error, write_error)
        self.assertEqual(spy.faulty_files[0].close_calls, 1)
        self.assertEqual(context.unlink.paths, [_name(1)])
        self.assertEqual(os.listdir(self.out), [])

    @unittest.skipUnless(HAS_ADD_NOTE, "Exception.add_note() needs Python 3.11+")
    def test_the_secondary_close_error_is_recorded_as_a_note_when_supported(self):
        write_error = OSError(errno.ENOSPC, "INJECTED disk full")
        close_error = OSError(errno.EIO, "INJECTED close failure")
        spy = _OpenSpy(write_error=write_error, close_error=close_error)

        error, _ = self.download_expecting_error([1], spy=spy)

        self.assertIs(error, write_error)
        notes = _notes(error)
        self.assertEqual(len(notes), 1)
        self.assertIn("INJECTED close failure", notes[0])

    def test_a_removal_failure_never_replaces_the_initial_error(self):
        write_error = OSError(errno.ENOSPC, "INJECTED disk full")
        unlink_error = PermissionError(errno.EACCES, "INJECTED removal refused")
        spy = _OpenSpy(write_error=write_error)

        error, context = self.download_expecting_error(
            [1, 2], spy=spy, unlink=_UnlinkSpy(error=unlink_error)
        )

        self.assertIs(error, write_error)
        self.assertEqual(context.unlink.paths, [_name(1)])
        # The removal was refused, so the attempt's own file is still there.
        self.assertEqual(os.listdir(self.out), [_name(1)])

    @unittest.skipUnless(HAS_ADD_NOTE, "Exception.add_note() needs Python 3.11+")
    def test_the_removal_error_is_recorded_as_a_note_when_supported(self):
        write_error = OSError(errno.ENOSPC, "INJECTED disk full")
        unlink_error = PermissionError(errno.EACCES, "INJECTED removal refused")
        spy = _OpenSpy(write_error=write_error)

        error, _ = self.download_expecting_error([1], spy=spy, unlink=_UnlinkSpy(error=unlink_error))

        self.assertIs(error, write_error)
        notes = _notes(error)
        self.assertEqual(len(notes), 1)
        self.assertIn("INJECTED removal refused", notes[0])

    def test_write_close_and_removal_all_failing_still_raises_the_write_error(self):
        write_error = OSError(errno.ENOSPC, "INJECTED disk full")
        close_error = OSError(errno.EIO, "INJECTED close failure")
        unlink_error = PermissionError(errno.EACCES, "INJECTED removal refused")
        spy = _OpenSpy(write_error=write_error, close_error=close_error)

        error, context = self.download_expecting_error(
            [1], spy=spy, unlink=_UnlinkSpy(error=unlink_error)
        )

        self.assertIs(error, write_error)
        self.assertEqual(context.unlink.paths, [_name(1)])

    def test_only_the_file_of_the_failing_attempt_is_removed(self):
        (self.out / _name(1)).write_bytes(b"EXISTING")
        write_error = OSError(errno.ENOSPC, "INJECTED disk full")
        spy = _OpenSpy(write_error=write_error)

        error, context = self.download_expecting_error([1, 2], spy=spy)

        self.assertIs(error, write_error)
        self.assertEqual(len(spy.calls), 2)
        self.assertEqual(context.unlink.paths, [_name(2)])
        self.assertEqual(os.listdir(self.out), [_name(1)])
        self.assertEqual((self.out / _name(1)).read_bytes(), b"EXISTING")

    def test_without_add_note_the_error_handling_path_still_works(self):
        # SIMULATION on the error objects (add_note missing or failing),
        # not an execution under Python 3.10.
        for error_class in (_NoteLessOSError, _NoteRefusingOSError):
            with self.subTest(error_class=error_class.__name__):
                for name in os.listdir(self.out):
                    os.unlink(self.out / name)
                write_error = error_class(errno.ENOSPC, "INJECTED disk full")
                close_error = error_class(errno.EIO, "INJECTED close failure")
                spy = _OpenSpy(write_error=write_error, close_error=close_error)

                error, context = self.download_expecting_error([1, 2], spy=spy)

                self.assertIs(error, write_error)
                self.assertEqual(spy.faulty_files[0].close_calls, 1)
                self.assertEqual(context.unlink.paths, [_name(1)])
                self.assertEqual(os.listdir(self.out), [])

    def test_without_add_note_a_removal_failure_still_leaves_the_initial_error(self):
        # SIMULATION on the error objects, not an execution under Python 3.10.
        for error_class in (_NoteLessOSError, _NoteRefusingOSError):
            with self.subTest(error_class=error_class.__name__):
                for name in os.listdir(self.out):
                    os.unlink(self.out / name)
                write_error = error_class(errno.ENOSPC, "INJECTED disk full")
                unlink_error = error_class(errno.EACCES, "INJECTED removal refused")
                spy = _OpenSpy(write_error=write_error)

                error, context = self.download_expecting_error(
                    [1], spy=spy, unlink=_UnlinkSpy(error=unlink_error)
                )

                self.assertIs(error, write_error)
                self.assertEqual(context.unlink.paths, [_name(1)])


# ============================================================================================ accept / reject scenario
def _pump(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)


def _wait_until(predicate, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        QApplication.processEvents()
        time.sleep(0.005)
    return predicate()


def _png_image_bytes(rgb) -> bytes:
    """A small, really decodable PNG image."""
    image = QImage(8, 8, QImage.Format_RGB32)
    image.fill(QColor(*rgb))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    saved = image.save(buffer, "PNG")
    buffer.close()
    if not saved:
        raise AssertionError("could not build a PNG fixture")
    return bytes(data)


class _FakeComfyUI:
    """
    Replacement for urllib.request.urlopen: answers the three requests
    a generation makes (POST /prompt, GET /history/<id>, GET /view) and
    refuses anything else. Both generations report the SAME remote file
    name; the bytes served by /view differ per generation.
    """

    REMOTE_NAME = "AIStudioToolkit_00001_.png"

    def __init__(self):
        self.images = []
        self.prompts = 0
        self.view_index = None
        self.unexpected = []

    def __call__(self, request, timeout=None):
        path = urllib.parse.urlsplit(request.full_url).path
        method = request.get_method()
        if method == "POST" and path == "/prompt":
            self.prompts += 1
            body = {"prompt_id": f"pid-{self.prompts}", "number": self.prompts, "node_errors": {}}
            return _FakeResponse(json.dumps(body).encode("utf-8"))
        if method == "GET" and path.startswith("/history/"):
            prompt_id = path.rsplit("/", 1)[1]
            self.view_index = int(prompt_id.split("-")[1]) - 1
            entry = {
                prompt_id: {
                    "outputs": {"9": {"images": [{"filename": self.REMOTE_NAME, "subfolder": "", "type": "output"}]}},
                    "status": {"status_str": "success", "completed": True, "messages": []},
                }
            }
            return _FakeResponse(json.dumps(entry).encode("utf-8"))
        if method == "GET" and path == "/view":
            return _FakeResponse(self.images[self.view_index])
        self.unexpected.append((method, request.full_url))
        raise urllib.error.URLError("unexpected request in test")


class _UnusedCollaborator:
    """
    Stands in for a collaborator the exercised path must never touch:
    any attribute access is recorded and refused, so a value is never
    silently fabricated (as a MagicMock would) and then consumed as a
    text, a path or a configuration value.
    """

    def __init__(self, label):
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "accessed", [])

    def __getattr__(self, attribute):
        self.accessed.append(attribute)
        raise AssertionError(f"{self.label}.{attribute} must not be reached in this scenario")


class _EmptyLoraLibrary(_UnusedCollaborator):
    """An empty LoRA library: the only call the page makes at construction is list_loras()."""

    def list_loras(self):
        return []


class _RunningLifecycleStub(QObject):
    """Lifecycle manager that is already running: exposes the signal and state the page reads, and refuses any start."""

    state_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.state = RUNNING_OWNED
        self.last_error_message = ""
        self.unexpected_calls = []

    def start(self, *args, **kwargs):
        self.unexpected_calls.append("start")
        raise AssertionError("the lifecycle start must not be reached in this scenario")


class AcceptedImageSurvivesRejectedRegenerationTest(_CheckedCleanupCase):
    """
    Defect scenario (expected to fail on the previous implementation,
    pass on the current one): an image accepted from a first generation
    must still be intact after a second generation that reports the
    same remote file name is rejected.

    Real: ComfyUIEngine, GenerationManager, GenerationWorker on a real
    QThread, InferencePage (generate, pending result, Accept, Reject),
    WorkspaceManager on a private temporary tree, EventBus, ImagesPage,
    and two really decodable PNG images.
    Substituted (declared): urllib.request.urlopen (no socket is ever
    opened; see _FakeComfyUI; active from before the widgets are built
    until after they are destroyed); the prompt manager, prompt
    assistant, character manager, application settings manager and
    Forge engine (_UnusedCollaborator: any access fails loudly); the
    LoRA library (empty, explicit list_loras()); the ComfyUI lifecycle
    manager (_RunningLifecycleStub, state RUNNING_OWNED, no process);
    and any real QMessageBox (the dialog safety net fails the test).
    No MainWindow, no real ComfyUI.

    Exceptions that escape a Qt slot reach sys.excepthook and the test
    would otherwise still report OK: they are recorded and fail the
    test. Qt log messages are not captured.

    Cleanup is registered as each resource is acquired, so a failing
    setUp() still releases what exists: the worker is stopped with a
    bounded wait (a QThread that is still running is never destroyed),
    the widgets are destroyed and checked, then the network
    substitution, the dialog safety net, the exception recorder and the
    temporary tree go, in that order. Anything incomplete is reported.
    """

    def setUp(self):
        super().setUp()
        self.escaped = []
        self.page = None
        self.images_page = None
        self.lifecycle = None
        self.unused = []
        self.addCleanup(self._check_escaped_exceptions)

        self.tmp_dir = self.make_private_dir()

        previous_hook = sys.excepthook
        sys.excepthook = lambda exc_type, exc_value, traceback: self.escaped.append(exc_value)
        self.addCleanup(setattr, sys, "excepthook", previous_hook)

        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)

        self.fake = _FakeComfyUI()
        network_patch = patch("urllib.request.urlopen", new=self.fake)
        network_patch.start()
        self.addCleanup(network_patch.stop)

        # Registered BEFORE the widgets exist: it tolerates a partial fixture.
        self.addCleanup(self._dispose_widgets)

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.workspace_manager.create(self.tmp_dir / "DownloadProject")
        self.outputs_dir = Path(self.workspace_manager.current_workspace.root) / "outputs"
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

        self.lifecycle = _RunningLifecycleStub()
        self.comfyui_engine = ComfyUIEngine(base_url="http://127.0.0.1:8188", timeout=5.0)
        self.images_page = ImagesPage(self.workspace_manager)
        self.unused = [
            _UnusedCollaborator("prompt_manager"),
            _UnusedCollaborator("prompt_assistant_manager"),
            _UnusedCollaborator("character_manager"),
            _UnusedCollaborator("application_settings_manager"),
            _UnusedCollaborator("forge_engine"),
        ]
        prompt_manager, assistant, characters, settings, forge = self.unused
        self.lora_library = _EmptyLoraLibrary("lora_library_manager")
        self.unused.append(self.lora_library)
        self.page = InferencePage(
            GenerationManager(self.comfyui_engine),
            self.workspace_manager,
            prompt_manager,
            assistant,
            characters,
            self.lora_library,
            settings,
            self.comfyui_engine,
            forge,
            comfyui_lifecycle_manager=self.lifecycle,
        )
        self.page.engine_combo.setCurrentIndex(self.page.engine_combo.findData("comfyui"))

        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED):
            self.event_bus.subscribe(event_name, self.images_page.update_images)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED, WORKSPACE_RENAMED):
            self.event_bus.subscribe(event_name, self.page.reset_for_workspace_change)

    def _check_escaped_exceptions(self):
        if self.escaped:
            self.cleanup_problems.append(f"exception(s) escaped a Qt slot: {self.escaped!r}")

    def _dispose_widgets(self):
        page, images_page, lifecycle = self.page, self.images_page, self.lifecycle
        _pump(0.05)  # delivers queued worker->page signals and the page's own deferred thread cleanup

        if page is not None and shiboken6.isValid(page):
            thread = getattr(page, "_thread", None)
            if thread is not None and shiboken6.isValid(thread) and thread.isRunning():
                thread.quit()
                if not thread.wait(20000):
                    self.cleanup_problems.append(
                        "worker thread still running after a 20 s bounded wait: the page and the "
                        "widgets were deliberately NOT shut down nor destroyed"
                    )
                    return
            try:
                page.shutdown()
            except Exception as error:  # noqa: BLE001 - reported, never hidden
                self.cleanup_problems.append(f"page.shutdown() raised {error!r}")
            _pump(0.05)

        targets = [("InferencePage", page), ("ImagesPage", images_page), ("lifecycle stub", lifecycle)]
        for _, widget in targets:
            if widget is not None and shiboken6.isValid(widget):
                widget.deleteLater()
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()
        survivors = [label for label, widget in targets if widget is not None and shiboken6.isValid(widget)]
        if survivors:
            self.cleanup_problems.append(f"Qt object(s) not destroyed: {survivors}")

    def _generate_until_pending(self, prompt_text):
        self.assertTrue(_wait_until(self.page.generate_button.isEnabled), "Generate never became available")
        self.page.prompt.setPlainText(prompt_text)
        self.page.generate_button.click()
        self.assertTrue(_wait_until(lambda: self.page._pending_path is not None), "no pending result")
        return self.page._pending_path

    def _gallery_paths(self):
        return [
            self.images_page.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.images_page.list_widget.count())
        ]

    def test_first_accepted_image_is_kept_when_the_second_generation_is_rejected(self):
        first_bytes = _png_image_bytes((255, 0, 0))
        second_bytes = _png_image_bytes((0, 0, 255))
        self.assertNotEqual(first_bytes, second_bytes)
        for data in (first_bytes, second_bytes):
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertFalse(QImage.fromData(data).isNull(), "fixture is not a decodable image")
        self.fake.images = [first_bytes, second_bytes]

        first_path = self._generate_until_pending("a red fox")
        self.assertEqual(Path(first_path).read_bytes(), first_bytes)
        self.page.accept_button.click()
        self.assertIsNone(self.page._pending_path)
        self.assertEqual(
            [image.file_path for image in self.workspace_manager.current_workspace.images],
            [first_path],
        )

        second_path = self._generate_until_pending("a blue fox")
        self.assertNotEqual(second_path, first_path)
        self.assertEqual(Path(second_path).read_bytes(), second_bytes)
        # While the second result is pending, the accepted file is untouched.
        self.assertEqual(Path(first_path).read_bytes(), first_bytes)

        self.page.reject_button.click()
        self.assertIsNone(self.page._pending_path)

        self.assertFalse(Path(second_path).exists())
        self.assertEqual(Path(first_path).read_bytes(), first_bytes)
        self.assertEqual(
            [image.file_path for image in self.workspace_manager.current_workspace.images],
            [first_path],
        )
        self.assertEqual(self._gallery_paths(), [first_path])
        self.assertEqual(os.listdir(self.outputs_dir), [Path(first_path).name])
        self.assertEqual(self.fake.prompts, 2)
        self.assertEqual(self.fake.unexpected, [])
        self.assertEqual(self.escaped, [], "an exception escaped a Qt slot")
        self.assertEqual([c.accessed for c in self.unused], [[] for _ in self.unused])
        self.assertEqual(self.lifecycle.unexpected_calls, [])


if __name__ == "__main__":
    unittest.main()
