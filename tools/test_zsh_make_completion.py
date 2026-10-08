"""Exercise native Zsh Tab completion through ZLE and an isolated startup file."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_make_completion as bash_tests
from install_make_completion import RC_BEGIN, ZSH_SOURCE, configure_zsh, install
from scaffold_plugin import REPO_ROOT


ZSH = shutil.which("zsh")


class ZshInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".zsh-install-", dir=REPO_ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.environment = patch.dict(os.environ, {"XDG_DATA_HOME": str(self.directory / "data"),
                                                   "ZDOTDIR": str(self.directory / "config")})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_native_script_installation(self) -> None:
        destination = install(shell="zsh")
        self.assertEqual(destination, self.directory / "data/zsh/tuoni-make-completion.zsh")
        self.assertEqual(destination.read_bytes(), ZSH_SOURCE.read_bytes())

    def test_startup_preserves_existing_content_and_is_idempotent(self) -> None:
        rc = self.directory / "config/.zshrc"
        rc.parent.mkdir()
        rc.write_text("# existing config\nexport MY_SETTING=keep-me")
        rc.chmod(0o640)
        destination = install(shell="zsh")
        self.assertEqual(configure_zsh(destination), rc)
        first = rc.read_text()
        self.assertTrue(first.startswith("# existing config\nexport MY_SETTING=keep-me\n"))
        self.assertEqual(first.count(RC_BEGIN), 1)
        configure_zsh(destination)
        self.assertEqual(rc.read_text(), first)
        self.assertEqual(rc.stat().st_mode & 0o777, 0o640)

    def test_startup_updates_path_and_preserves_symlink(self) -> None:
        target = self.directory / "dotfiles.zshrc"
        target.write_text("# symlinked settings\n")
        rc = self.directory / "config/.zshrc"
        rc.parent.mkdir()
        rc.symlink_to(target)
        configure_zsh(self.directory / "old-completion.zsh")
        destination = self.directory / "new completion's.zsh"
        configure_zsh(destination)
        self.assertTrue(rc.is_symlink())
        self.assertEqual(target.read_text().count(RC_BEGIN), 1)
        self.assertNotIn("old-completion.zsh", target.read_text())
        self.assertIn(shlex.quote(str(destination)), target.read_text())

    def test_incomplete_startup_block_is_preserved(self) -> None:
        rc = self.directory / "config/.zshrc"
        rc.parent.mkdir()
        rc.write_text(RC_BEGIN + "\n# unfinished\n")
        with self.assertRaises(OSError):
            configure_zsh(self.directory / "completion.zsh")
        self.assertEqual(rc.read_text(), RC_BEGIN + "\n# unfinished\n")

    @unittest.skipUnless(ZSH and bash_tests.MAKE, "Zsh and Make are required")
    def test_make_detects_zsh_and_new_shell_loads_completion(self) -> None:
        env = os.environ.copy()
        env["SHELL"] = ZSH
        # Exercise the default home layout and quoting for macOS-style users.
        home = self.directory / "Users/Test User"
        env["HOME"] = str(home)
        env.pop("XDG_DATA_HOME", None)
        env.pop("ZDOTDIR", None)
        subprocess.run([bash_tests.MAKE, "install-completion"], cwd=REPO_ROOT, env=env,
                       capture_output=True, text=True, check=True, timeout=20)
        result = subprocess.run([ZSH, "-ic", 'print -r -- $_comps[make]; print -r -- $_tuoni_make_zsh_fallback'],
                                env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["_tuoni_make_zsh", "_make"])
        self.assertEqual((home / ".local/share/zsh/tuoni-make-completion.zsh").read_bytes(), ZSH_SOURCE.read_bytes())
        self.assertIn("source ", (home / ".zshrc").read_text())


@unittest.skipUnless(os.name == "posix" and ZSH and bash_tests.MAKE, "POSIX Zsh ZLE and Make are required")
class MakeZleCompletionTests(bash_tests.MakeReadlineCompletionTests):
    # Native Zsh tests do not require the parent's bash-completion package.
    __unittest_skip__ = False
    shell_source = ZSH_SOURCE

    def setUp(self) -> None:
        import pty

        self.temporary = tempfile.TemporaryDirectory(prefix=".zle-", dir=REPO_ROOT)
        self.directory = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        self.master, slave = pty.openpty()
        env = os.environ.copy()
        env.update({"PROMPT": "__READY__ ", "RPROMPT": "", "TERM": "dumb",
                    "ZDOTDIR": str(self.directory)})
        self.shell = subprocess.Popen([ZSH, "-f", "-i"], cwd=REPO_ROOT, env=env,
                                      stdin=slave, stdout=slave, stderr=slave, close_fds=True)
        os.close(slave)
        self.addCleanup(self.close_shell)
        self.read_until(b"__READY__ ")
        setup = (
            f"source {shlex.quote(str(self.shell_source))}; "
            "bindkey -e; unsetopt BEEP; "
            "_completion_snapshot() { print -rn -- $'\\n__BUFFER__'$BUFFER$'\\0'; BUFFER=; CURSOR=0; }; "
            "zle -N _completion_snapshot; bindkey '^G' _completion_snapshot\n"
        )
        os.write(self.master, setup.encode())
        self.read_until(b"__READY__ ")

    def test_equal_sign_can_be_removed_from_word_breaks(self) -> None:
        # Zsh has no Readline word breaks; assignment completion is native.
        self.assertEqual(self.complete("make new-command EXECUNITS=nat"),
                         "make new-command EXECUNITS=native-lib")

    def test_quoted_directory_completion(self) -> None:
        (self.directory / "custom plugins").mkdir()
        line = f'make new-command FOLDER="{self.directory}/custom'
        self.assertEqual(shlex.split(self.complete(line)),
                         ["make", "new-command", f"FOLDER={self.directory}/custom plugins/"])

    def test_quoted_space_list_completion(self) -> None:
        result = self.complete('make new-command EXECUNITS="native-lib dotnet-dl')
        self.assertEqual(shlex.split(result), ["make", "new-command", "EXECUNITS=native-lib dotnet-dll"])


if __name__ == "__main__":
    unittest.main()
