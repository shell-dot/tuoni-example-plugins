"""Exercise Buildx installation decisions with isolated OS/package/CLI fixtures."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

from scaffold_plugin import scaffold
from test_docker_runner import REPO_ROOT, RUNNER_PROJECTS


@unittest.skipUnless(os.name == 'posix', 'Requires a POSIX shell and terminal')
class BuildxPrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tuoni buildx ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name in ('sh', 'mkdir'):
            (self.bin / name).symlink_to(shutil.which(name))
        self.log = self.root / 'calls'
        self.log.touch()
        self.os_release = self.root / 'os-release'
        self.os_release.write_text('ID=kali\nID_LIKE=debian\nPRETTY_NAME="Kali GNU/Linux"\n')
        self.helper = self.root / 'check-buildx.sh'
        source = (REPO_ROOT / 'tools/docker/check-buildx.sh').read_text()
        # Redirect the fixed OS file only in this test copy, never on the host.
        self.helper.write_text(source.replace('/etc/os-release', shlex.quote(str(self.os_release))))
        self.stub('docker', '''printf '%s\\n' "docker $*" >> "$FIXTURE_LOG"
if [ "$1" = info ]; then exit "${FIXTURE_INFO_STATUS:-0}"; fi
if [ "$1 $2" = 'buildx version' ]; then
    [ "${FIXTURE_BUILDX_PRESENT:-0}" = 1 ] || [ -e "$FIXTURE_INSTALLED" ]
    exit $?
fi
''')
        self.stub('uname', 'printf "%s\\n" "${FIXTURE_KERNEL:-Linux}"\n')
        self.stub('readlink', 'printf "%s\\n" "${FIXTURE_DOCKER_PATH:-$2}"\n')
        self.stub('dpkg-query', '''printf '%s\\n' "dpkg-query $*" >> "$FIXTURE_LOG"
[ "${FIXTURE_OWNER:-docker-ce-cli}" != unknown ] || exit 1
printf '%s: %s\\n' "${FIXTURE_OWNER:-docker-ce-cli}" "$2"
''')
        self.stub('id', 'printf "%s\\n" "${FIXTURE_UID:-1000}"\n')
        self.stub('sudo', '''printf '%s\\n' "sudo $*" >> "$FIXTURE_LOG"
[ "${FIXTURE_SUDO_STATUS:-0}" = 0 ] || exit "$FIXTURE_SUDO_STATUS"
exec "$@"
''')
        self.stub('apt-get', '''printf '%s\\n' "apt-get $*" >> "$FIXTURE_LOG"
if [ "$1" = update ]; then exit "${FIXTURE_UPDATE_STATUS:-0}"; fi
[ "${FIXTURE_INSTALL_STATUS:-0}" = 0 ] || exit "$FIXTURE_INSTALL_STATUS"
if [ "${FIXTURE_INSTALL_WORKS:-1}" = 1 ]; then : > "$FIXTURE_INSTALLED"; fi
''')
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(('BUILDX_', 'FIXTURE_'))}
        self.env.update(PATH=str(self.bin), FIXTURE_LOG=str(self.log),
                        FIXTURE_INSTALLED=str(self.root / 'installed'))

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/sh\nset -eu\n' + body)
        path.chmod(0o755)

    def run_check(self, answer=None, command=None, **environment):
        env = dict(self.env, **environment)
        arguments = command or ['/bin/sh', str(self.helper), 'docker']
        if answer is None:
            return subprocess.run(arguments, env=env, input='', capture_output=True,
                                  text=True, timeout=10)
        master, slave = os.openpty()
        try:
            process = subprocess.Popen(arguments, env=env, stdin=slave,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            os.close(slave)
            slave = None
            os.write(master, answer.encode())
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise
            return subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)
        finally:
            os.close(master)
            if slave is not None:
                os.close(slave)

    def calls(self):
        return self.log.read_text().splitlines()

    def test_existing_buildx_skips_detection_and_install_even_when_opted_in(self):
        result = self.run_check(FIXTURE_BUILDX_PRESENT='1', BUILDX_INSTALL='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ['docker info', 'docker buildx version'])
        self.assertEqual(result.stderr, '')

    def test_daemon_failure_stops_without_package_operations(self):
        result = self.run_check(FIXTURE_INFO_STATUS='13', BUILDX_INSTALL='1')
        self.assertEqual(result.returncode, 13)
        self.assertEqual(self.calls(), ['docker info'])

    def test_kali_ce_offers_matching_package_and_continues_after_yes(self):
        result = self.run_check(answer='y\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Detected Kali GNU/Linux, Docker CLI package docker-ce-cli', result.stderr)
        self.assertIn('Install docker-buildx-plugin now', result.stderr)
        self.assertIn('sudo apt-get install -y --no-remove docker-buildx-plugin', self.calls())
        self.assertEqual(self.calls()[-1], 'docker buildx version')

    def test_distro_and_cli_package_detection(self):
        for distro, like, owner, package in [
            ('kali', 'debian', 'docker.io', 'docker-buildx'),
            ('debian', '', 'docker.io:amd64', 'docker-buildx'),
            ('ubuntu', 'debian', 'docker-ce-cli', 'docker-buildx-plugin'),
            ('mint', 'ubuntu debian', 'docker.io', 'docker-buildx'),
        ]:
            with self.subTest(distro=distro, owner=owner):
                self.os_release.write_text(f'ID={distro}\nID_LIKE="{like}"\n')
                result = self.run_check(FIXTURE_OWNER=owner)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'Buildx package: {package}.', result.stderr)
                self.assertIn('No interactive input', result.stderr)
                self.assertFalse(any(call.startswith('apt-get ') for call in self.calls()))

    def test_no_and_default_answer_leave_packages_untouched(self):
        for answer in ('n\n', '\n'):
            with self.subTest(answer=answer):
                result = self.run_check(answer=answer)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('installation declined', result.stderr)
                self.assertFalse(any(call.startswith(('apt-get ', 'sudo ')) for call in self.calls()))

    def test_noninteractive_default_and_explicit_disable_never_install(self):
        for mode in ('ask', '0'):
            with self.subTest(mode=mode):
                result = self.run_check(answer='y\n' if mode == '0' else None, BUILDX_INSTALL=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(call.startswith(('apt-get ', 'sudo ')) for call in self.calls()))

    def test_explicit_noninteractive_opt_in_installs_without_sudo_as_root(self):
        (self.bin / 'sudo').unlink()
        result = self.run_check(BUILDX_INSTALL='1', FIXTURE_UID='0', FIXTURE_OWNER='docker.io')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('apt-get install -y --no-remove docker-buildx', self.calls())
        self.assertFalse(any(call.startswith('sudo ') for call in self.calls()))

    def test_unknown_os_or_cli_source_does_not_guess_even_with_opt_in(self):
        for kernel, owner in [('Darwin', 'docker-ce-cli'), ('Linux', 'unknown'),
                              ('Linux', 'docker-desktop')]:
            with self.subTest(kernel=kernel, owner=owner):
                result = self.run_check(BUILDX_INSTALL='1', FIXTURE_KERNEL=kernel, FIXTURE_OWNER=owner)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Could not select an automatic', result.stderr)
                self.assertFalse(any(call.startswith(('apt-get ', 'sudo ')) for call in self.calls()))

    def test_missing_package_tools_or_sudo_fail_with_instructions(self):
        for name in ('apt-get', 'dpkg-query', 'sudo'):
            with self.subTest(tool=name):
                path = self.bin / name
                saved = path.read_text()
                path.unlink()
                result = self.run_check(BUILDX_INSTALL='1')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Buildx', result.stderr)
                self.assertFalse(any(call.startswith(('apt-get ', 'sudo ')) for call in self.calls()))
                self.stub(name, saved.split('\n', 2)[2])

    def test_update_install_and_sudo_failure_stop_without_recheck(self):
        for variable in ('FIXTURE_UPDATE_STATUS', 'FIXTURE_INSTALL_STATUS', 'FIXTURE_SUDO_STATUS'):
            with self.subTest(failure=variable):
                self.log.write_text('')
                result = self.run_check(BUILDX_INSTALL='1', **{variable: '23'})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('installation failed', result.stderr)
                self.assertEqual(self.calls().count('docker buildx version'), 1)
                if variable != 'FIXTURE_INSTALL_STATUS':
                    self.assertFalse(any(call.startswith('apt-get install ') for call in self.calls()))

    def test_successful_apt_is_not_enough_without_working_buildx(self):
        result = self.run_check(BUILDX_INSTALL='1', FIXTURE_INSTALL_WORKS='0')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('still unavailable', result.stderr)
        self.assertEqual(self.calls().count('docker buildx version'), 2)

    def test_cli_symlink_is_resolved_for_package_ownership(self):
        result = self.run_check(FIXTURE_DOCKER_PATH='/usr/bin/docker')
        self.assertIn('dpkg-query -S /usr/bin/docker', self.calls())
        self.assertNotEqual(result.returncode, 0)

    def test_make_build_continues_after_install_and_forwards_opt_in(self):
        project = self.root / 'project'
        project.mkdir()
        shutil.copyfile(REPO_ROOT / 'echo-command-plugin/Makefile', project / 'Makefile')
        shutil.copytree(REPO_ROOT / 'echo-command-plugin/scripts/docker', project / 'scripts/docker')
        shutil.copyfile(self.helper, project / 'scripts/docker/check-buildx.sh')
        make = shutil.which('make')
        if not make:
            self.skipTest('Requires GNU Make')
        for mode, answer in [('1', None), ('ask', 'y\n')]:
            with self.subTest(mode=mode):
                self.log.write_text('')
                (self.root / 'installed').unlink(missing_ok=True)
                result = self.run_check(answer=answer, command=[make, '-C', str(project), 'build',
                                                               'DOCKER=docker', f'BUILDX_INSTALL={mode}'])
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                self.assertLess(calls.index('apt-get install -y --no-remove docker-buildx-plugin'),
                                calls.index('docker image inspect ghcr.io/shell-dot/tuoni-java-builder:0.15.0'))
                self.assertTrue(any(call.startswith('docker build ') for call in calls))

    def test_configured_docker_wrapper_is_used_before_and_after_install(self):
        self.stub('docker-wrapper', '''printf '%s\\n' "wrapper $*" >> "$FIXTURE_LOG"
exec docker "$@"
''')
        result = self.run_check(command=['/bin/sh', str(self.helper), 'docker-wrapper'], BUILDX_INSTALL='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls().count('wrapper info'), 1)
        self.assertEqual(self.calls().count('wrapper buildx version'), 2)

    def test_all_shipped_and_generated_helpers_are_self_contained(self):
        expected = (REPO_ROOT / 'tools/docker/check-buildx.sh').read_bytes()
        for name in RUNNER_PROJECTS:
            with self.subTest(project=name):
                self.assertEqual((REPO_ROOT / name / 'scripts/docker/check-buildx.sh').read_bytes(), expected)
        for kind, formats, systems in [('command', None, None), ('listener', 'native-lib', 'linux')]:
            project, _ = scaffold(kind, 'Buildx Demo', str(self.root / kind), formats, systems)
            self.assertEqual((project / 'scripts/docker/check-buildx.sh').read_bytes(), expected)


if __name__ == '__main__':
    unittest.main()
