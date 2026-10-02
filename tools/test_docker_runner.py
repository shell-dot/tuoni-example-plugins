"""Execute Docker launchers against isolated stubs; never run Docker or sudo."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

from scaffold_plugin import scaffold


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTS = (
    "echo-command-plugin",
    "tcp-listener-plugin",
    "dotnet-payload-plugin",
    "templates/command",
    "templates/listener",
    "templates/payloads",
)
HELPER = Path("scripts/docker/run-docker.sh")
BASH = shutil.which("bash")
if os.name == "nt":
    # Git's bin/bash.exe launcher prepends real utilities to PATH. Invoke the
    # actual shell so even the missing-sudo test sees only our isolated stubs.
    git_bash = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/usr/bin/bash.exe"
    if git_bash.is_file():
        BASH = str(git_bash)


DOCKER_STUB = r'''#!/bin/sh
set -eu
printf '%s\000' docker "${DOCKER_BUILDKIT-}" "${DOCKER_CONTEXT-}" "${DOCKER_HOST-}" "$@" __END__ >> "$TEST_LOG"
case "${1-}" in
    info)
        if [ "${TEST_INFO_STATUS:-0}" != 0 ]; then
            printf '%s\n' "${TEST_INFO_ERROR:-permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock}" >&2
        fi
        exit "${TEST_INFO_STATUS:-0}"
        ;;
    context)
        case "${2-}" in
            show) printf '%s\n' "${TEST_CONTEXT:-fixture-context}" ;;
            inspect)
                if [ "${TEST_CONTEXT_STATUS:-0}" != 0 ]; then
                    printf '%s\n' 'fixture context lookup failed' >&2
                    exit "$TEST_CONTEXT_STATUS"
                fi
                printf '%s\n' "${TEST_ENDPOINT:-unix:///var/run/docker.sock}"
                ;;
        esac
        exit 0
        ;;
esac
exit "${TEST_BUILD_STATUS:-0}"
'''

SUDO_STUB = r'''#!/bin/sh
set -eu
printf '%s\000' sudo "$@" __END__ >> "$TEST_LOG"
if [ "${TEST_SUDO_STATUS:-0}" != 0 ]; then
    printf '%s\n' 'fixture sudo denied' >&2
    exit "$TEST_SUDO_STATUS"
fi
unset DOCKER_BUILDKIT DOCKER_CONTEXT DOCKER_HOST
exec "$@"
'''

ENV_STUB = r'''#!/bin/sh
set -eu
while [ "$#" -gt 0 ]; do
    case "$1" in
        *=*) export "$1"; shift ;;
        *) break ;;
    esac
done
exec "$@"
'''


@unittest.skipUnless(BASH, "A POSIX shell is required for Docker launcher tests")
class DockerRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".d-", dir=REPO_ROOT)
        self.directory = Path(self.temporary.name).resolve()
        self.assertTrue(self.directory.is_relative_to(REPO_ROOT))
        self.addCleanup(self.temporary.cleanup)
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        self.log = self.directory / "calls"
        self.write_stub("docker", DOCKER_STUB)
        self.write_stub("sudo", SUDO_STUB)
        self.write_stub("env", ENV_STUB)
        self.write_stub("id", '#!/bin/sh\nprintf "%s\\n" "${TEST_UID:-1000}"\n')

    def write_stub(self, name: str, text: str) -> None:
        path = self.bin / name
        path.write_bytes(text.encode("utf-8"))
        path.chmod(0o755)

    def shell_path(self, path: Path) -> str:
        value = path.as_posix()
        if os.name == "nt" and path.drive:
            return "/" + value[0].lower() + value[2:]
        return value

    def run_helper(
        self,
        *arguments: str,
        project: Path | None = None,
        **environment: str,
    ) -> subprocess.CompletedProcess[str]:
        self.log.write_bytes(b"")
        env = os.environ.copy()
        for name in list(env):
            if name.startswith(("DOCKER_", "TEST_")) or name in ("BASH_ENV", "ENV"):
                env.pop(name)
        env.update({
            "PATH": self.shell_path(self.bin),
            "TEST_LOG": self.shell_path(self.log),
            "DOCKER_BUILDKIT": "1",
            "MSYS2_ARG_CONV_EXCL": "*",
        })
        env.update(environment)
        helper = (project or REPO_ROOT / "templates/command") / HELPER
        # Keep test arguments inside POSIX syntax: Windows/MSYS command-line
        # translation would otherwise alter embedded quotes before our test.
        launch = self.directory / "launch.sh"
        launch.write_bytes((
            "exec /bin/sh " + " ".join(
                shlex.quote(argument)
                for argument in (self.shell_path(helper), *(arguments or ("build",)))
            ) + "\n"
        ).encode("utf-8"))
        return subprocess.run(
            [str(BASH), "--noprofile", "--norc", self.shell_path(launch)],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    def calls(self, executable: str | None = None) -> list[list[str]]:
        calls: list[list[str]] = []
        current: list[str] = []
        for token in self.log.read_bytes().decode("utf-8").split("\0"):
            if token == "__END__":
                if executable is None or current[0] == executable:
                    calls.append(current)
                current = []
            else:
                current.append(token)
        return calls

    def docker_arguments(self) -> list[list[str]]:
        return [call[4:] for call in self.calls("docker")]

    def test_accessible_docker_uses_no_sudo_and_preserves_arguments(self) -> None:
        arguments = ("build", "--output", "type=local,dest=build with spaces/", "--build-arg", "VALUE=a'b\"c", ".")
        result = self.run_helper(*arguments, DOCKER_HOST="unix:///run/user/1000/docker.sock")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.docker_arguments(), [["info"], list(arguments)])
        self.assertEqual(self.calls("sudo"), [])

    def test_permission_denial_uses_sudo_for_same_socket(self) -> None:
        endpoint = "unix:///run/fixture/docker.sock"
        result = self.run_helper("build", ".", TEST_INFO_STATUS="13", DOCKER_HOST=endpoint)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls("sudo")), 1)
        self.assertEqual(self.docker_arguments()[-1], ["--host", endpoint, "build", "."])
        self.assertEqual(self.calls("docker")[-1][1:4], ["1", "", endpoint])

    def test_sudo_restores_buildkit_default_and_explicit_setting(self) -> None:
        for setting, expected in (("", "1"), ("0", "0")):
            with self.subTest(setting=setting):
                result = self.run_helper(TEST_INFO_STATUS="13", DOCKER_BUILDKIT=setting, DOCKER_HOST="unix:///var/run/docker.sock")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.calls("docker")[-1][1], expected)

    def test_context_overrides_host_for_sudo_endpoint(self) -> None:
        endpoint = "unix:///run/context/docker.sock"
        result = self.run_helper(
            TEST_INFO_STATUS="13", DOCKER_CONTEXT="my-context",
            DOCKER_HOST="unix:///wrong/docker.sock", TEST_ENDPOINT=endpoint,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        inspections = [args for args in self.docker_arguments() if args[:2] == ["context", "inspect"]]
        self.assertEqual(len(inspections), 1)
        self.assertIn("my-context", inspections[0])
        self.assertEqual(self.docker_arguments()[-1], ["--host", endpoint, "build"])
        self.assertEqual(self.calls("docker")[-1][2:4], ["", endpoint])

    def test_current_context_endpoint_is_preserved(self) -> None:
        endpoint = "unix:///custom/current.sock"
        result = self.run_helper(TEST_INFO_STATUS="13", TEST_ENDPOINT=endpoint)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any(args[:2] == ["context", "inspect"] for args in self.docker_arguments()))
        self.assertEqual(self.docker_arguments()[-1], ["--host", endpoint, "build"])

    def test_daemon_unavailable_is_not_retried_with_sudo(self) -> None:
        error = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?"
        result = self.run_helper(TEST_INFO_STATUS="23", TEST_INFO_ERROR=error)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertIn(error, result.stderr)
        self.assertEqual(self.calls("sudo"), [])
        self.assertEqual(self.docker_arguments(), [["info"]])

    def test_config_file_permission_denial_does_not_use_sudo(self) -> None:
        result = self.run_helper(TEST_INFO_STATUS="13", TEST_INFO_ERROR="open /home/test/.docker/config.json: permission denied")
        self.assertEqual(result.returncode, 13, result.stderr)
        self.assertEqual(self.calls("sudo"), [])
        self.assertEqual(self.docker_arguments(), [["info"]])

    def test_remote_permission_denial_does_not_use_sudo(self) -> None:
        for endpoint in ("tcp://host:2376", "ssh://user@host"):
            with self.subTest(endpoint=endpoint):
                result = self.run_helper(TEST_INFO_STATUS="13", DOCKER_HOST=endpoint)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.calls("sudo"), [])
                self.assertEqual(self.docker_arguments(), [["info"]])

    def test_root_does_not_retry_permission_denial_with_sudo(self) -> None:
        result = self.run_helper(TEST_INFO_STATUS="13", TEST_UID="0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls("sudo"), [])
        self.assertFalse(any(args and args[-1] == "build" for args in self.docker_arguments()))

    def test_missing_docker_exits_without_sudo(self) -> None:
        (self.bin / "docker").unlink()
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("docker", result.stderr.lower())
        self.assertEqual(self.calls(), [])

    def test_missing_sudo_reports_permission_failure(self) -> None:
        (self.bin / "sudo").unlink()
        result = self.run_helper(TEST_INFO_STATUS="13", DOCKER_HOST="unix:///var/run/docker.sock")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sudo", result.stderr.lower())
        self.assertEqual(self.calls("sudo"), [])
        self.assertEqual(self.docker_arguments(), [["info"]])

    def test_failed_context_lookup_never_switches_to_root_default(self) -> None:
        result = self.run_helper(TEST_INFO_STATUS="13", DOCKER_CONTEXT="broken", TEST_CONTEXT_STATUS="19")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls("sudo"), [])
        self.assertFalse(any(args and args[-1] == "build" for args in self.docker_arguments()))

    def test_sudo_failure_is_preserved_without_running_build(self) -> None:
        result = self.run_helper(TEST_INFO_STATUS="13", TEST_SUDO_STATUS="17", DOCKER_HOST="unix:///var/run/docker.sock")
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertEqual(len(self.calls("sudo")), 1)
        self.assertEqual(self.docker_arguments(), [["info"]])

    def test_build_failure_is_preserved_and_never_retried(self) -> None:
        for denied in (False, True):
            with self.subTest(denied=denied):
                result = self.run_helper(TEST_INFO_STATUS="13" if denied else "0", TEST_BUILD_STATUS="29", DOCKER_HOST="unix:///var/run/docker.sock")
                self.assertEqual(result.returncode, 29, result.stderr)
                builds = [args for args in self.docker_arguments() if "build" in args]
                self.assertEqual(len(builds), 1)
                self.assertEqual(len(self.calls("sudo")), int(denied))

    def test_all_project_helpers_match_and_defaults_remain_overridable(self) -> None:
        expected = (REPO_ROOT / "templates/command" / HELPER).read_bytes()
        for project in PROJECTS:
            with self.subTest(project=project):
                self.assertEqual((REPO_ROOT / project / HELPER).read_bytes(), expected)
                makefile = (REPO_ROOT / project / "Makefile").read_text(encoding="utf-8")
                self.assertIn("DOCKER ?= sh scripts/docker/run-docker.sh", makefile)
                self.assertNotIn("$(shell", makefile)
                self.assertNotIn("$(eval", makefile)
                self.assertIn("$(DOCKER) build", makefile)

    def test_generated_projects_include_working_standalone_helper(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                project, _ = scaffold(kind, "Demo", str(self.directory / kind[0]))
                result = self.run_helper("build", ".", project=project, TEST_INFO_STATUS="13", DOCKER_HOST="unix:///fixture/socket")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.docker_arguments()[-1], ["--host", "unix:///fixture/socket", "build", "."])
                self.assertEqual((project / HELPER).read_bytes(), (REPO_ROOT / "templates" / kind / HELPER).read_bytes())


if __name__ == "__main__":
    unittest.main()
