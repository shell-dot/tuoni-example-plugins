"""Check completion through real Bash Readline, without running typed commands."""

from __future__ import annotations

import os
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from install_make_completion import SOURCE, install
from scaffold_plugin import REPO_ROOT


BASH = shutil.which("bash")
MAKE = shutil.which("make")
PACKAGE = Path("/usr/share/bash-completion/bash_completion")


class CompletionInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".completion-", dir=REPO_ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def test_install_and_update_owned_completion(self) -> None:
        destination = self.directory / "bash-completion/completions/make"
        self.assertEqual(install(destination), destination)
        self.assertEqual(destination.read_bytes(), SOURCE.read_bytes())
        self.assertEqual(install(destination), destination)
        self.assertEqual(destination.read_bytes(), SOURCE.read_bytes())

    def test_existing_custom_completion_is_preserved(self) -> None:
        destination = self.directory / "make"
        destination.write_text("# My own Make completion\n")
        with self.assertRaises(FileExistsError):
            install(destination)
        self.assertEqual(destination.read_text(), "# My own Make completion\n")

    @unittest.skipUnless(MAKE and BASH and PACKAGE.is_file(), "Bash completion and GNU Make are required")
    def test_make_installation_is_loaded_by_bash_completion(self) -> None:
        env = os.environ.copy()
        env["XDG_DATA_HOME"] = str(self.directory)
        subprocess.run([MAKE, "install-completion", "COMPLETION_SHELL=bash"], cwd=REPO_ROOT, env=env,
                       capture_output=True, text=True, check=True, timeout=20)
        result = subprocess.run(
            [BASH, "--noprofile", "--norc", "-c",
             f'source {shlex.quote(str(PACKAGE))}; _comp_load make; complete -p make; declare -F "$_tuoni_make_fallback"'],
            env=env, capture_output=True, text=True, timeout=20,
        )
        self.assertIn("-F _tuoni_make make", result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.directory / "bash-completion/completions/make").read_bytes(), SOURCE.read_bytes())

    def test_empty_data_home_uses_normal_home_directory(self) -> None:
        with patch.dict(os.environ, {"XDG_DATA_HOME": ""}), patch("install_make_completion.Path.home", return_value=self.directory):
            self.assertEqual(install(), self.directory / ".local/share/bash-completion/completions/make")

    @unittest.skipUnless(BASH and PACKAGE.is_file(), "Bash completion is required")
    def test_can_source_with_errexit_enabled(self) -> None:
        result = subprocess.run([BASH, "--noprofile", "--norc", "-ec",
                                 f"source {shlex.quote(str(SOURCE))}; complete -p make"],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-F _tuoni_make make", result.stdout)

    @unittest.skipUnless(BASH and PACKAGE.is_file(), "Bash completion is required")
    def test_homebrew_library_and_standard_make_completion_are_found(self) -> None:
        prefix = self.directory / "custom brew prefix"
        data = prefix / "share/bash-completion"
        (data / "completions").mkdir(parents=True)
        (data / "bash_completion").write_text(
            f"source {shlex.quote(str(PACKAGE))}\nTUONI_TEST_BREW_LIBRARY=loaded\n")
        (data / "completions/make").write_text(
            (PACKAGE.parent / "completions/make").read_text() + "\nTUONI_TEST_BREW_MAKE=loaded\n")
        executables = self.directory / "bin"
        executables.mkdir()
        brew = executables / "brew"
        brew.write_text(f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(str(prefix))}\n")
        brew.chmod(0o755)
        for detection in ("HOMEBREW_PREFIX", "brew --prefix"):
            with self.subTest(detection=detection):
                env = os.environ.copy()
                env.pop("HOMEBREW_PREFIX", None)
                env["PATH"] = str(executables) + os.pathsep + env["PATH"]
                if detection == "HOMEBREW_PREFIX":
                    env["HOMEBREW_PREFIX"] = str(prefix)
                result = subprocess.run(
                    [BASH, "--noprofile", "--norc", "-ec",
                     f"source {shlex.quote(str(SOURCE))}; "
                     '[[ $TUONI_TEST_BREW_LIBRARY == loaded && $TUONI_TEST_BREW_MAKE == loaded ]]; '
                     'declare -F "$_tuoni_make_fallback"; complete -p make'],
                    env=env, capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("-F _tuoni_make make", result.stdout)


@unittest.skipUnless(os.name == "posix" and BASH and MAKE and PACKAGE.is_file(),
                     "POSIX Bash Readline and bash-completion are required")
class MakeReadlineCompletionTests(unittest.TestCase):
    shell_source = SOURCE

    def setUp(self) -> None:
        import pty

        self.temporary = tempfile.TemporaryDirectory(prefix=".readline-", dir=REPO_ROOT)
        self.directory = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        self.master, slave = pty.openpty()
        env = os.environ.copy()
        env.update({"PS1": "__READY__ ", "TERM": "dumb", "INPUTRC": "/dev/null"})
        for name in ("BASH_ENV", "ENV", "PROMPT_COMMAND"):
            env.pop(name, None)
        self.shell = subprocess.Popen(
            [BASH, "--noprofile", "--norc", "-i"], cwd=REPO_ROOT, env=env,
            stdin=slave, stdout=slave, stderr=slave, close_fds=True,
        )
        os.close(slave)
        self.addCleanup(self.close_shell)
        self.read_until(b"__READY__ ")
        setup = (
            f"source {shlex.quote(str(self.shell_source))}; "
            "bind 'set bell-style none'; "
            "_completion_snapshot() { printf '\\n__BUFFER__%s\\0' \"$READLINE_LINE\"; READLINE_LINE=; READLINE_POINT=0; }; "
            "bind -x '\"\\C-g\": _completion_snapshot'\n"
        )
        os.write(self.master, setup.encode())
        self.read_until(b"__READY__ ")

    def close_shell(self) -> None:
        if self.shell.poll() is None:
            os.write(self.master, b"\x15exit\n")
            try:
                self.shell.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.shell.kill()
                self.shell.wait(timeout=5)
        os.close(self.master)

    def read_until(self, marker: bytes) -> bytes:
        output = b""
        deadline = time.monotonic() + 8
        while marker not in output:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.fail(f"Timed out waiting for {marker!r}: {output!r}")
            ready, _, _ = select.select([self.master], [], [], remaining)
            if ready:
                output += os.read(self.master, 65536)
        return output

    def complete(self, line: str) -> str:
        os.write(self.master, line.encode() + b"\t\x07")
        output = self.read_until(b"\0")
        # The snapshot clears Readline instead of executing the command.
        return output.rsplit(b"__BUFFER__", 1)[1].split(b"\0", 1)[0].decode()

    def test_argument_name_completion_keeps_equals_attached(self) -> None:
        self.assertEqual(self.complete("make new-command EX"), "make new-command EXECUNITS=")

    def test_execunit_completion_and_comma_lists(self) -> None:
        self.assertEqual(self.complete("make new-command EXECUNITS=nat"), "make new-command EXECUNITS=native-lib")
        self.assertEqual(self.complete("make new-command EXECUNITS=native-lib,dotnet-dl"),
                         "make new-command EXECUNITS=native-lib,dotnet-dll")

    def test_os_completion_and_comma_lists(self) -> None:
        self.assertEqual(self.complete("make new-listener OS=li"), "make new-listener OS=linux")
        self.assertEqual(self.complete("make new-listener OS=linux,win"), "make new-listener OS=linux,windows")

    def test_linux_filters_execunit_choices(self) -> None:
        self.assertEqual(self.complete("make new-command OS=linux EXECUNITS="),
                         "make new-command OS=linux EXECUNITS=native-lib")

    def test_managed_formats_filter_os_choices(self) -> None:
        self.assertEqual(self.complete("make new-command EXECUNITS=dotnet-dll OS="),
                         "make new-command EXECUNITS=dotnet-dll OS=windows")

    def test_compatibility_matches_backend_input_normalization(self) -> None:
        self.assertEqual(self.complete('make new-command OS=" LINUX " EXECUNITS='),
                         'make new-command OS=" LINUX " EXECUNITS=native-lib')
        self.assertEqual(self.complete("make new-command EXECUNITS=NATIVE_LIB OS=li"),
                         "make new-command EXECUNITS=NATIVE_LIB OS=linux")

    def test_existing_options_and_list_values_are_not_repeated(self) -> None:
        for line in ("make new-command NAME=Demo N", "make new-command EXECUNITS=native-lib,nat",
                     "make new-command EXECUNITS=NATIVE_LIB,nat"):
            with self.subTest(line=line):
                self.assertEqual(self.complete(line), line)

    def test_names_remain_free_text(self) -> None:
        (REPO_ROOT / self.directory.name / "SomeName").mkdir()
        line = "make new-command NAME=SomeN"
        self.assertEqual(self.complete(line), line)

    def test_directory_completion_quotes_spaces(self) -> None:
        (self.directory / "custom plugins").mkdir()
        prefix = f"make new-command FOLDER={self.directory}/custom"
        self.assertEqual(self.complete(prefix), prefix + "\\ plugins/")

    def test_quoted_directory_completion(self) -> None:
        (self.directory / "custom plugins").mkdir()
        line = f'make new-command FOLDER="{self.directory}/custom'
        self.assertIn(f'{self.directory}/custom plugins/', self.complete(line))

    def test_quoted_space_list_completion(self) -> None:
        result = self.complete('make new-command EXECUNITS="native-lib dotnet-dl')
        self.assertIn('EXECUNITS="native-lib dotnet-dll', result)

    def test_make_directory_option_changes_path_completion_base(self) -> None:
        project = self.directory / "repo with spaces"
        (project / "tools").mkdir(parents=True)
        (project / "tools/scaffold_plugin.py").touch()
        shutil.copyfile(REPO_ROOT / "Makefile", project / "Makefile")
        (project / "parent folder").mkdir()
        line = f"make -C {shlex.quote(str(project))} new-command FOLDER=par"
        self.assertEqual(self.complete(line), line[:-3] + "parent\\ folder/")

    def test_target_completion_still_uses_standard_make_completion(self) -> None:
        self.assertEqual(self.complete("make new-c"), "make new-command ")

    def test_other_repositories_keep_standard_make_completion(self) -> None:
        (self.directory / "Makefile").write_text(".PHONY: special-target\nspecial-target:\n\t@:\n")
        line = f"make -C {self.directory} special-t"
        self.assertEqual(self.complete(line), line[:-9] + "special-target ")

    def test_completion_does_not_execute_name_contents(self) -> None:
        sentinel = self.directory / "must-not-exist"
        line = f"make new-command NAME='$(touch {sentinel})' EX"
        self.assertEqual(self.complete(line), line[:-2] + "EXECUNITS=")
        self.assertFalse(sentinel.exists())

    def test_reload_preserves_standard_target_completion(self) -> None:
        os.write(self.master, f"source {shlex.quote(str(self.shell_source))}\n".encode())
        self.read_until(b"__READY__ ")
        self.assertEqual(self.complete("make new-c"), "make new-command ")

    def test_equal_sign_can_be_removed_from_word_breaks(self) -> None:
        os.write(self.master, b'COMP_WORDBREAKS=${COMP_WORDBREAKS//=/}\n')
        self.read_until(b"__READY__ ")
        self.assertEqual(self.complete("make new-command EXECUNITS=nat"),
                         "make new-command EXECUNITS=native-lib")


if __name__ == "__main__":
    unittest.main()
