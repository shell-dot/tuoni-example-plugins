"""Exercise install recipes with isolated CLIs and sudo; never restart a server."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

from scaffold_plugin import scaffold
from test_docker_runner import BASH, PROJECTS, REPO_ROOT


HELPER = Path("scripts/install/install-plugin.sh")
MAKE = shutil.which("make")
CP = shutil.which("cp")
CHMOD = shutil.which("chmod")

TUONI_STUB = r'''#!/bin/sh
set -eu
printf '%s\000' tuoni "${TEST_UID:-1000}" "$0" "$@" __END__ >> "$TEST_LOG"
test -f "$TEST_INSTALLED_JAR"
exit "${TEST_RESTART_STATUS:-0}"
'''

CP_STUB = r'''#!/bin/sh
set -eu
printf '%s\000' cp "${TEST_UID:-1000}" "$@" __END__ >> "$TEST_LOG"
if [ "${TEST_COPY_STATUS:-0}" != 0 ]; then exit "$TEST_COPY_STATUS"; fi
exec "$TEST_CP_BIN" "$@"
'''

# Simulate the PATH added by a user's .bashrc and a login-shell directory change.
BASH_STUB = r'''#!/bin/sh
set -eu
printf '%s\000' bash "${TEST_UID:-1000}" "$@" __END__ >> "$TEST_LOG"
if [ "${TEST_UID:-1000}" = 0 ]; then
    PATH="$TEST_ROOT_BIN:$PATH"
else
    PATH="$TEST_USER_LOGIN_BIN:$PATH"
fi
export PATH
cd "$TEST_LOGIN_DIR"
shift
exec /bin/sh -c "$@"
'''

SUDO_STUB = r'''#!/bin/sh
set -eu
printf '%s\000' sudo "$@" __END__ >> "$TEST_LOG"
if [ "${TEST_SUDO_STATUS:-0}" != 0 ]; then exit "$TEST_SUDO_STATUS"; fi
export TEST_UID=0
if [ "$1" = -H ]; then
    shift
else
    # Our fixture owns these files; model root's write access without real sudo.
    "$TEST_CHMOD_BIN" u+w "$TEST_PLUGIN_DIR"
    if [ -f "$TEST_INSTALLED_JAR" ]; then "$TEST_CHMOD_BIN" u+w "$TEST_INSTALLED_JAR"; fi
fi
exec "$@"
'''


@unittest.skipUnless(BASH and CP and CHMOD, "POSIX shell and file utilities are required")
class InstallPluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".install-", dir=REPO_ROOT)
        self.directory = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        self.bin = self.directory / "bin"
        self.root_bin = self.directory / "root bin"
        self.user_login_bin = self.directory / "user login bin"
        self.login_dir = self.directory / "login directory"
        for directory in (self.bin, self.root_bin, self.user_login_bin, self.login_dir):
            directory.mkdir()
        self.log = self.directory / "calls"
        self.log.write_bytes(b"")
        self.write_stub(self.bin / "id", '#!/bin/sh\nprintf "%s\\n" "${TEST_UID:-1000}"\n')
        self.write_stub(self.bin / "bash", BASH_STUB)
        self.write_stub(self.bin / "sudo", SUDO_STUB)
        self.write_stub(self.bin / "cp", CP_STUB)
        self.write_stub(self.bin / "sh", '#!/bin/sh\nexec /bin/sh "$@"\n')
        self.project = self.copy_project("templates/command", "plugin with spaces")
        self.plugin_dir = self.project / "installed plugins"
        self.plugin_dir.mkdir()

    def write_stub(self, path: Path, source: str) -> None:
        path.write_bytes(source.encode("utf-8"))
        path.chmod(0o755)

    def shell_path(self, path: Path) -> str:
        value = path.as_posix()
        if os.name == "nt" and path.drive:
            return "/" + value[0].lower() + value[2:]
        return value

    def copy_project(self, source: str, name: str) -> Path:
        project = self.directory / name
        (project / HELPER.parent).mkdir(parents=True)
        shutil.copyfile(REPO_ROOT / source / "Makefile", project / "Makefile")
        shutil.copyfile(REPO_ROOT / source / HELPER, project / HELPER)
        self.create_jar(project)
        return project

    def create_jar(self, project: Path) -> Path:
        makefile = (project / "Makefile").read_text(encoding="utf-8")
        match = re.search(r"(?m)^JAR_NAME\s*:=\s*(\S+)$", makefile)
        self.assertIsNotNone(match)
        jar = project / "build" / match.group(1)
        jar.parent.mkdir(exist_ok=True)
        jar.write_bytes(b"fixture plugin artifact")
        return jar

    def environment(self, project: Path, **overrides: str) -> dict[str, str]:
        env = os.environ.copy()
        for name in list(env):
            if name.startswith(("TEST_", "TUONI", "DOCKER_", "MAKE")) or name in ("BASH_ENV", "ENV"):
                env.pop(name)
        env.update({
            "PATH": self.shell_path(self.bin),
            "TEST_LOG": self.shell_path(self.log),
            "TEST_ROOT_BIN": self.shell_path(self.root_bin),
            "TEST_USER_LOGIN_BIN": self.shell_path(self.user_login_bin),
            "TEST_LOGIN_DIR": self.shell_path(self.login_dir),
            "TEST_PLUGIN_DIR": self.shell_path(self.plugin_dir),
            "TEST_INSTALLED_JAR": self.shell_path(self.plugin_dir / self.jar(project).name),
            "TEST_CP_BIN": self.shell_path(Path(CP)),
            "TEST_CHMOD_BIN": self.shell_path(Path(CHMOD)),
            "MSYS2_ARG_CONV_EXCL": "*",
        })
        env.update(overrides)
        return env

    def jar(self, project: Path) -> Path:
        return next((project / "build").glob("*.jar"))

    def run_helper(self, tuoni: str = "tuoni", *, jar_path: str | None = None,
                   **environment: str) -> subprocess.CompletedProcess[str]:
        arguments = (self.shell_path(self.project / HELPER), jar_path or str(self.jar(self.project).relative_to(self.project)),
                     "installed plugins", tuoni)
        launch = self.directory / "launch.sh"
        launch.write_text("exec /bin/sh " + " ".join(shlex.quote(arg) for arg in arguments) + "\n", encoding="utf-8")
        return subprocess.run(
            [str(BASH), "--noprofile", "--norc", self.shell_path(launch)],
            cwd=self.project, env=self.environment(self.project, **environment),
            capture_output=True, text=True, timeout=20, check=False,
        )

    def calls(self, name: str) -> list[list[str]]:
        calls = []
        for entry in self.log.read_bytes().decode("utf-8").split("__END__\0"):
            tokens = entry.rstrip("\0").split("\0")
            if tokens[0] == name:
                calls.append(tokens)
        return calls

    def assert_installed(self, project: Path | None = None) -> None:
        jar = self.jar(project or self.project)
        self.assertEqual((self.plugin_dir / jar.name).read_bytes(), jar.read_bytes())
        self.assertEqual(self.calls("tuoni")[-1][-1:], ["restart"])

    def test_current_user_cli_is_preferred_and_copy_precedes_restart(self) -> None:
        self.write_stub(self.bin / "tuoni", TUONI_STUB)
        self.write_stub(self.root_bin / "tuoni", TUONI_STUB)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls("sudo"), [])
        self.assertEqual(self.calls("bash"), [])
        self.assertEqual(self.calls("tuoni")[0][1], "1000")
        self.assert_installed()

    def test_current_user_shell_path_is_detected(self) -> None:
        self.write_stub(self.user_login_bin / "tuoni", TUONI_STUB)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls("sudo"), [])
        self.assertEqual(self.calls("tuoni")[0][1:3], ["1000", self.shell_path(self.user_login_bin / "tuoni")])
        self.assert_installed()

    def test_root_shell_path_is_detected_and_executed_as_root(self) -> None:
        self.write_stub(self.root_bin / "tuoni", TUONI_STUB)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls("sudo")), 1)
        self.assertEqual(self.calls("sudo")[0][1:4], ["-H", "bash", "-lic"])
        self.assertEqual(self.calls("tuoni")[0][1:3], ["0", self.shell_path(self.root_bin / "tuoni")])
        self.assertEqual(self.calls("cp")[0][1], "0")
        self.assert_installed()

    def test_real_bash_startup_output_does_not_break_resolution(self) -> None:
        wrapper = r'''#!/bin/sh
set -eu
shift
if [ "${TEST_UID:-1000}" = 0 ]; then rc=$TEST_ROOT_RC; else rc=$TEST_USER_RC; fi
exec "$TEST_BASH_BIN" --noprofile --rcfile "$rc" -ic "$@"
'''
        self.write_stub(self.bin / "bash", wrapper)
        user_rc = self.directory / "user.bashrc"
        root_rc = self.directory / "root.bashrc"
        for rc, path in ((user_rc, "$TEST_USER_LOGIN_BIN"), (root_rc, "$TEST_ROOT_BIN")):
            rc.write_text(f'export PATH="{path}:$PATH"\nprintf "shell startup output\\n"\ncd "$TEST_LOGIN_DIR"\n',
                          encoding="utf-8")
        for root in (False, True):
            with self.subTest(root=root):
                cli = (self.root_bin if root else self.user_login_bin) / "tuoni"
                self.write_stub(cli, TUONI_STUB)
                self.log.write_bytes(b"")
                result = self.run_helper(TEST_BASH_BIN=self.shell_path(Path(BASH)),
                                         TEST_USER_RC=self.shell_path(user_rc), TEST_ROOT_RC=self.shell_path(root_rc))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("shell startup output", result.stdout)
                self.assertEqual(self.calls("tuoni")[0][1], "0" if root else "1000")
                self.assert_installed()
                cli.unlink()

    def test_explicit_cli_path_with_spaces_is_preserved(self) -> None:
        cli = self.directory / "custom tuoni"
        self.write_stub(cli, TUONI_STUB)
        result = self.run_helper(self.shell_path(cli))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls("tuoni")[0][2:], [self.shell_path(cli), "restart"])
        self.assert_installed()

    def test_root_invocation_needs_no_sudo(self) -> None:
        self.write_stub(self.bin / "tuoni", TUONI_STUB)
        (self.bin / "sudo").unlink()
        result = self.run_helper(TEST_UID="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls("sudo"), [])
        self.assert_installed()

    def test_writable_user_install_needs_no_sudo(self) -> None:
        self.write_stub(self.bin / "tuoni", TUONI_STUB)
        (self.bin / "sudo").unlink()
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed()

    @unittest.skipIf(os.name == "nt", "Unix permission bits are required")
    def test_protected_directory_uses_sudo_for_copy_only(self) -> None:
        self.write_stub(self.bin / "tuoni", TUONI_STUB)
        self.plugin_dir.chmod(0o555)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls("sudo")[0][1:3], ["cp", "--"])
        self.assertEqual(self.calls("cp")[0][1], "0")
        self.assertEqual(self.calls("tuoni")[0][1], "1000")
        self.assert_installed()

    @unittest.skipIf(os.name == "nt", "Unix permission bits are required")
    def test_existing_protected_jar_uses_sudo(self) -> None:
        self.write_stub(self.bin / "tuoni", TUONI_STUB)
        destination = self.plugin_dir / self.jar(self.project).name
        destination.write_bytes(b"old artifact")
        destination.chmod(0o444)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls("sudo")[0][1:3], ["cp", "--"])
        self.assert_installed()

    def test_missing_cli_fails_before_copying(self) -> None:
        # Use a unique name so a real /srv/tuoni installation cannot be invoked.
        result = self.run_helper("fixture-missing-tuoni")
        self.assertEqual(result.returncode, 127, result.stderr)
        self.assertIn("Tuoni command not found", result.stderr)
        self.assertEqual(self.calls("cp"), [])
        self.assertEqual(self.calls("tuoni"), [])
        self.assertEqual(list(self.plugin_dir.iterdir()), [])

    def test_missing_sudo_reports_root_detection_failure(self) -> None:
        (self.bin / "sudo").unlink()
        result = self.run_helper("fixture-missing-tuoni")
        self.assertEqual(result.returncode, 127, result.stderr)
        self.assertIn("sudo", result.stderr)
        self.assertEqual(self.calls("cp"), [])

    def test_missing_jar_fails_before_detection_or_copy(self) -> None:
        result = self.run_helper(jar_path="build/missing.jar")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Plugin JAR not found", result.stderr)
        for command in ("cp", "tuoni", "sudo", "bash"):
            self.assertEqual(self.calls(command), [])

    def test_copy_failure_prevents_restart(self) -> None:
        self.write_stub(self.bin / "tuoni", TUONI_STUB)
        result = self.run_helper(TEST_COPY_STATUS="21")
        self.assertEqual(result.returncode, 21, result.stderr)
        self.assertEqual(self.calls("tuoni"), [])
        self.assertNotIn("[+] Installed", result.stdout)

    def test_sudo_failure_is_preserved(self) -> None:
        result = self.run_helper("fixture-missing-tuoni", TEST_SUDO_STATUS="17")
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertEqual(self.calls("cp"), [])
        self.assertEqual(self.calls("tuoni"), [])

    def test_restart_failure_is_preserved_and_never_retried(self) -> None:
        self.write_stub(self.bin / "tuoni", TUONI_STUB)
        result = self.run_helper(TEST_RESTART_STATUS="29")
        self.assertEqual(result.returncode, 29, result.stderr)
        self.assertEqual(len(self.calls("tuoni")), 1)
        self.assertEqual(self.calls("sudo"), [])
        self.assertNotIn("[+] Installed", result.stdout)

    @unittest.skipUnless(MAKE, "GNU Make is required")
    def test_all_project_install_recipes_and_dry_runs(self) -> None:
        expected = (REPO_ROOT / "templates/command" / HELPER).read_bytes()
        self.write_stub(self.bin / "tuoni", TUONI_STUB)
        for index, source in enumerate(PROJECTS):
            with self.subTest(project=source):
                project = self.copy_project(source, f"example {index}")
                self.assertEqual((project / HELPER).read_bytes(), expected)
                self.log.write_bytes(b"")
                dry = subprocess.run([MAKE, "-n", "install"], cwd=project, env=self.environment(project),
                                     capture_output=True, text=True, timeout=20)
                self.assertEqual(dry.returncode, 0, dry.stderr)
                self.assertEqual(self.log.read_bytes(), b"")
                result = subprocess.run([MAKE, "-o", "build", "install", f"PLUGIN_DIR={self.plugin_dir}"],
                                        cwd=project, env=self.environment(project), capture_output=True,
                                        text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_installed(project)

    @unittest.skipUnless(MAKE, "GNU Make is required")
    def test_generated_default_and_restricted_plugins_can_install(self) -> None:
        self.write_stub(self.root_bin / "tuoni", TUONI_STUB)
        for kind in ("command", "listener"):
            for restricted in (False, True):
                with self.subTest(kind=kind, restricted=restricted):
                    project, _ = scaffold(kind, "Install Demo", str(self.directory / f"{kind}-{restricted}"),
                                          "native-lib" if restricted else None, "linux" if restricted else None)
                    self.create_jar(project)
                    readme = (project / "README.md").read_text(encoding="utf-8")
                    self.assertIn("`make install`", readme)
                    self.assertIn("scripts/install/install-plugin.sh", readme)
                    self.log.write_bytes(b"")
                    result = subprocess.run([MAKE, "-o", "build", "install", f"PLUGIN_DIR={self.plugin_dir}"],
                                            cwd=project, env=self.environment(project), capture_output=True,
                                            text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual((project / HELPER).read_bytes(), (REPO_ROOT / "templates" / kind / HELPER).read_bytes())
                    self.assertEqual(self.calls("tuoni")[0][1], "0")
                    self.assert_installed(project)

    @unittest.skipUnless(MAKE, "GNU Make is required")
    def test_repository_install_forwards_directory_and_cli_overrides(self) -> None:
        root = self.directory / "repository"
        root.mkdir()
        shutil.copyfile(REPO_ROOT / "Makefile", root / "Makefile")
        cli = self.directory / "custom tuoni"
        self.write_stub(cli, TUONI_STUB)
        projects = [self.copy_project(source, f"repository/{source}") for source in PROJECTS[:3]]
        for project in projects:
            makefile = project / "Makefile"
            # Recursive make does not inherit -o build. Keep its prerequisite
            # in place while replacing the fixture's Docker recipe with a no-op.
            source = makefile.read_text(encoding="utf-8")
            makefile.write_text(re.sub(r"(?m)^build:\n(?:\t.*\n)+", "build:\n\t@:\n", source), encoding="utf-8")
        result = subprocess.run(
            [MAKE, "install", f"PLUGIN_DIR={self.plugin_dir}", f"TUONI={self.shell_path(cli)}"],
            cwd=root, env=self.environment(self.project, TEST_INSTALLED_JAR=self.shell_path(self.plugin_dir / self.jar(projects[0]).name)),
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls("tuoni")), 3)
        for call in self.calls("tuoni"):
            self.assertEqual(call[2:], [self.shell_path(cli), "restart"])
        for project in projects:
            self.assert_installed(project)


if __name__ == "__main__":
    unittest.main()
