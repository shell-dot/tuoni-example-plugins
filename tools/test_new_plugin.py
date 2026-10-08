"""Creation, validation, and real terminal interaction checks for the plugin wizard."""

from __future__ import annotations

import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import new_plugin
from new_plugin import PluginPlan, complete_directory
import scaffold_plugin


ROOT = scaffold_plugin.REPO_ROOT
SCRIPT = ROOT / "tools/new_plugin.py"
DOWN = b"\x1bOB"


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".wizard-check-", dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        workspace = patch.object(scaffold_plugin, "DEFAULT_WORKSPACE_ROOT", self.directory / "workspace")
        workspace.start()
        self.addCleanup(workspace.stop)

    def test_default_selection_matches_make_defaults_and_name_updates_destination(self) -> None:
        plan = PluginPlan(name="Daily Check")
        self.assertEqual(plan.selection_arguments(), (None, None))
        self.assertEqual(plan.matrix, scaffold_plugin.support_matrix(None, None))
        self.assertEqual(plan.destination, self.directory / "workspace/commands/daily-check")
        plan.kind = "listener"
        plan.name = "Event Relay"
        self.assertEqual(plan.destination, self.directory / "workspace/listeners/event-relay")

    def test_linux_only_filters_formats_and_cannot_lose_native_support(self) -> None:
        plan = PluginPlan(name="Check")
        plan.toggle_system("windows")
        self.assertEqual(plan.available_formats, ("native-lib",))
        self.assertEqual(plan.matrix, {"linux": {"native-lib"}})
        with self.assertRaisesRegex(ValueError, "Linux requires"):
            plan.toggle_format("native-lib")
        with self.assertRaisesRegex(ValueError, "at least one target"):
            plan.toggle_system("linux")

    def test_managed_only_then_adding_linux_preserves_a_compatible_matrix(self) -> None:
        plan = PluginPlan(name="Relay", systems={"windows"}, formats={"dotnet-dll"})
        with self.assertRaisesRegex(ValueError, "at least one execution"):
            plan.toggle_format("dotnet-dll")
        plan.toggle_system("linux")
        self.assertEqual(plan.matrix, {"windows": {"dotnet-dll", "native-lib"}, "linux": {"native-lib"}})

    def test_custom_paths_expand_home_and_resolve_relative_to_launch_directory(self) -> None:
        with patch.dict(os.environ, {"HOME": str(self.directory)}):
            plan = PluginPlan(name="Check", folder="~/custom plugins/check")
            self.assertEqual(plan.destination, self.directory / "custom plugins/check")
        original = Path.cwd()
        try:
            os.chdir(self.directory)
            plan.folder = "custom plugins/it's $(touch should-not-exist)"
            destination, _ = plan.create()
        finally:
            os.chdir(original)
        self.assertEqual(destination, self.directory / plan.folder)
        self.assertTrue((destination / "Makefile").is_file())
        self.assertFalse((self.directory / "should-not-exist").exists())

    def test_both_templates_keep_make_install_and_selected_support(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                plan = PluginPlan(kind=kind, name="Native Check", systems={"linux"}, formats={"native-lib"})
                destination, slug = plan.create()
                self.assertEqual(slug, "native-check")
                makefile = (destination / "Makefile").read_text()
                self.assertIn("install:", makefile)
                self.assertIn("scripts/install/install-plugin.sh", makefile)
                self.assertTrue((destination / "scripts/install/install-plugin.sh").is_file())
                scope = (destination / "docs/support-scope.md").read_text()
                self.assertIn("| Linux | x64 | `NATIVE_LIB` |", scope)
                self.assertNotIn("| Windows |", scope)
                self.assertTrue((destination / "java-plugin/settings.gradle.kts").is_file())

    def test_validation_does_not_modify_existing_destinations_or_templates(self) -> None:
        existing = self.directory / "existing"
        existing.mkdir()
        sentinel = existing / "keep"
        sentinel.write_text("preserve")
        plan = PluginPlan(name="Check", folder=str(existing))
        with self.assertRaisesRegex(ValueError, "already exists"):
            plan.create()
        self.assertEqual(sentinel.read_text(), "preserve")
        plan.folder = str(ROOT / "templates/command/new-child")
        with self.assertRaisesRegex(ValueError, "outside the source template"):
            plan.create()
        self.assertFalse(Path(plan.folder).exists())
        with self.assertRaises(ValueError):
            PluginPlan(name="---").create()

    @unittest.skipUnless(os.name == "posix", "Symlinks required")
    def test_broken_destination_symlink_is_preserved(self) -> None:
        link = self.directory / "broken"
        link.symlink_to(self.directory / "missing")
        with self.assertRaisesRegex(ValueError, "already exists"):
            PluginPlan(name="Check", folder=str(link)).create()
        self.assertTrue(link.is_symlink())

    def test_directory_completion_keeps_spaces_and_handles_multiple_matches(self) -> None:
        for name in ("custom plugins", "custom projects", ".hidden"):
            (self.directory / name).mkdir()
        prefix = str(self.directory) + "/custom"
        result, hint = complete_directory(prefix)
        self.assertEqual(result, prefix + " p")
        self.assertIn("custom plugins", hint)
        self.assertEqual(complete_directory(prefix + " pl")[0], str(self.directory / "custom plugins") + "/")
        self.assertEqual(complete_directory(str(self.directory) + "/.h")[0], str(self.directory / ".hidden") + "/")
        missing = str(self.directory / "new-folder")
        self.assertEqual(complete_directory(missing)[0], missing)

    def test_noninteractive_invocation_explains_how_to_launch(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("interactive terminal", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        help_result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, timeout=10)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("Interactively create", help_result.stdout)


@unittest.skipUnless(os.name == "posix" and new_plugin.curses, "A POSIX terminal with curses is required")
class TerminalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".wizard-terminal-", dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.process = None

    def start(self, use_make: bool = False, size: tuple[int, int] = (28, 100), term: str = "xterm-256color") -> None:
        import fcntl
        import pty
        import struct
        import termios

        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", *size, 0, 0))
        self.original_flags = termios.tcgetattr(slave)[3]
        env = os.environ.copy()
        env["TERM"] = term
        env.pop("LINES", None)
        env.pop("COLUMNS", None)
        command = [sys.executable, str(SCRIPT)]
        cwd = self.directory
        if use_make:
            command = [shutil.which("make"), "new", f"PYTHON={sys.executable}"]
            cwd = ROOT
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        self.addCleanup(self.close_terminal)

    def close_terminal(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=5)
        os.close(self.master)

    def read_until(self, marker: bytes) -> bytes:
        output = b""
        deadline = time.monotonic() + 10
        while marker not in output:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.fail(f"Timed out waiting for {marker!r}: {output!r}")
            ready, _, _ = select.select([self.master], [], [], remaining)
            if ready:
                try:
                    chunk = os.read(self.master, 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    self.fail(f"Terminal closed waiting for {marker!r}: {output!r}")
                output += chunk
        return output

    def send(self, keys: bytes, marker: bytes) -> bytes:
        os.write(self.master, keys)
        return self.read_until(marker)

    def assert_restored(self, code: int) -> None:
        import termios

        self.assertEqual(self.process.wait(timeout=10), code)
        flags = termios.tcgetattr(self.master)[3]
        self.assertEqual(flags & (termios.ECHO | termios.ICANON),
                         self.original_flags & (termios.ECHO | termios.ICANON))

    @unittest.skipUnless(shutil.which("make"), "Make is required")
    def test_make_launch_creates_linux_command_after_fixing_conflict_and_completing_path(self) -> None:
        existing = self.directory / "existing"
        existing.mkdir()
        (existing / "keep").write_text("preserve")
        parent = self.directory / "custom plugins"
        parent.mkdir()
        self.start(use_make=True)
        self.read_until(b"Choose the plugin template.")
        self.send(b"\r", b"descriptive name.")
        self.send(b"Daily Check\r", b"target operating systems")
        self.send(b" \r", b"execution formats to build")
        self.send(b"\r", b"directory for the new plugin")
        self.send(str(existing).encode() + b"\r", b"already exists")
        prefix = str(self.directory / "custom")
        self.send(b"\x15" + prefix.encode() + b"\t", b"completed; add")
        destination = parent / "it's $(touch should-not-exist)"
        self.send(destination.name.encode() + b"\r", b"press Enter to create it")
        self.send(b"\r", b"Created plugin 'daily-check'")
        self.assert_restored(0)
        self.assertTrue((destination / "Makefile").is_file())
        self.assertEqual((existing / "keep").read_text(), "preserve")
        self.assertFalse((ROOT / "should-not-exist").exists())
        scope = (destination / "docs/support-scope.md").read_text()
        self.assertIn("| Linux | x64 | `NATIVE_LIB` |", scope)
        self.assertNotIn("| Windows |", scope)

    def test_listener_windows_managed_only_and_back_navigation(self) -> None:
        self.start()
        self.read_until(b"Choose the plugin template.")
        self.send(DOWN + b"\r", b"descriptive name.")
        self.send(b"Event Relay\r", b"target operating systems")
        self.send(DOWN + b" \r", b"execution formats to build")
        # Keep dotnet-dll; deselect shellcode-native, dotnet-exe, native-lib.
        self.send(b" " + DOWN + DOWN + b" " + DOWN + b" \r", b"directory for the new plugin")
        old_destination = self.directory / "old"
        self.send(str(old_destination).encode() + b"\r", b"press Enter to create it")
        self.assertFalse(old_destination.exists())
        self.send(b"\x1b", b"directory for the new plugin")
        destination = self.directory / "relay"
        self.send(b"\x15" + str(destination).encode() + b"\r", b"press Enter to create it")
        self.send(b"\r", b"Created plugin 'event-relay'")
        self.assert_restored(0)
        self.assertFalse(old_destination.exists())
        scope = (destination / "docs/support-scope.md").read_text()
        self.assertIn("| Windows | x86, x64 | `DOTNET_DLL` |", scope)
        self.assertNotIn("| Linux |", scope)
        self.assertIn("install:", (destination / "Makefile").read_text())

    def test_escape_cancels_without_creating_files_and_restores_terminal(self) -> None:
        self.start()
        self.read_until(b"Choose the plugin template.")
        self.send(b"\x1b", b"Plugin creation cancelled.")
        self.assert_restored(0)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_minimum_terminal_validates_edits_and_scrolls_review_before_creation(self) -> None:
        import signal

        self.start(size=(22, 64))
        self.read_until(b"Choose the plugin template.")
        self.send(b"\r", b"descriptive name.")
        self.send(b"---\r", b"ASCII letter or digit")
        # Clear the invalid name, then insert the missing 'c' before the final 'k'.
        self.send(b"\x15" + "Däily Chek".encode() + b"\x02c\r", b"target operating systems")
        self.send(b" \r", b"execution formats to build")
        self.send(b" ", b"Linux requires native-lib")
        self.send(b"\r", b"directory for the new plugin")
        destination = self.directory / ("folder with spaces " * 5) / "check"
        self.send(str(destination).encode() + b"\r", b"press Enter to create it")
        self.send(b"\x1b[6~", b"Includes Makefile targets")
        self.assertFalse(destination.parent.exists())
        os.kill(self.process.pid, signal.SIGINT)
        self.read_until(b"Plugin creation cancelled.")
        self.assert_restored(130)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_resize_recovers_and_ctrl_c_restores_terminal(self) -> None:
        import fcntl
        import signal
        import struct
        import termios

        self.start(size=(10, 40))
        self.read_until(b"Resize to at least")
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack("HHHH", 28, 100, 0, 0))
        os.kill(self.process.pid, signal.SIGWINCH)
        self.read_until(b"Choose the plugin template.")
        # This child has no controlling terminal; send SIGINT as a real terminal would.
        os.kill(self.process.pid, signal.SIGINT)
        self.read_until(b"Plugin creation cancelled.")
        self.assert_restored(130)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_unknown_terminal_has_a_readable_error(self) -> None:
        self.start(term="tuoni-nonexistent-terminal")
        self.read_until(b"Cannot open the terminal UI")
        self.assert_restored(1)


if __name__ == "__main__":
    unittest.main()
