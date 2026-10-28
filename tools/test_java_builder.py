"""Check build interfaces without starting Docker or contacting a registry."""
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

from scaffold_plugin import scaffold
from test_docker_runner import PROJECTS, REPO_ROOT


class JavaBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tuoni java builder ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = self.root / 'docker-calls'
        self.docker = self.root / 'docker'
        self.docker.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$DOCKER_CALLS"
if [ "$1" = 'info' ]; then
    if [ "${INFO_STATUS:-0}" != 0 ]; then printf '%s\\n' 'permission denied while trying to connect to the docker API at unix:///var/run/docker.sock' >&2; fi
    exit "${INFO_STATUS:-0}"
fi
if [ "$1 $2" = 'buildx version' ]; then exit "${BUILDX_STATUS:-0}"; fi
if [ "$1 $2" = 'image inspect' ]; then exit "${IMAGE_STATUS:-0}"; fi
if [ "$1" = 'pull' ]; then exit "${PULL_STATUS:-0}"; fi
exit "${BUILD_STATUS:-0}"
''')
        self.docker.chmod(0o755)

    def copy_project(self, name):
        project = self.root / name
        project.mkdir(parents=True)
        shutil.copyfile(REPO_ROOT / name / 'Makefile', project / 'Makefile')
        shutil.copytree(REPO_ROOT / name / 'scripts/docker', project / 'scripts/docker')
        return project

    def make(self, project, *args, **environment):
        return subprocess.run(['make', f'DOCKER=sh {shlex.quote(str(self.docker))}', *args], cwd=project,
                              env={**os.environ, 'DOCKER_CALLS': str(self.calls),
                                   'BUILDX_INSTALL': '0', **environment},
                              capture_output=True, text=True, timeout=15)

    def operations(self):
        return [line for line in self.calls.read_text().splitlines()
                if line not in ('info', 'buildx version')]

    def test_missing_buildx_stops_before_image_pull_or_build(self):
        for name in PROJECTS:
            with self.subTest(project=name):
                project = self.copy_project(name)
                self.calls.unlink(missing_ok=True)
                result = self.make(project, 'build', BUILDX_STATUS='1', IMAGE_STATUS='1')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Docker Buildx is required', result.stderr)
                self.assertIn('docker-buildx', result.stderr)
                self.assertEqual(self.calls.read_text().splitlines(), ['info', 'buildx version'])
                self.assertFalse((project / 'build').exists())

    def test_socket_failure_is_not_reported_as_registry_failure(self):
        project = self.copy_project('templates/command')
        result = self.make(project, 'build', INFO_STATUS='13')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('permission denied', result.stderr)
        self.assertNotIn('registry access', result.stderr)
        self.assertEqual(self.calls.read_text().splitlines(), ['info'])

    def test_shared_configuration_and_native_stages(self):
        config = (REPO_ROOT / 'tools/docker/java-builder.mk').read_bytes()
        for name in PROJECTS:
            with self.subTest(project=name):
                root = REPO_ROOT / name
                self.assertEqual((root / 'scripts/docker/java-builder.mk').read_bytes(), config)
                docker = (root / 'scripts/docker/Dockerfile').read_text()
                self.assertIn('FROM mono:6', docker.replace('--platform=linux/amd64 ', ''))
                self.assertIn('from=gradle-seed,source=/opt/gradle-home,sharing=locked', docker)
                self.assertIn('    sh ./gradlew build --no-daemon --build-cache\n', docker)
                self.assertIn('COPY --from=java-build', docker)
                self.assertNotIn('toolchains/', docker)
                native, java = docker.split('FROM ${BUILDER_IMAGE} AS gradle-seed')
                native_runs = re.findall(r'^RUN .+$', native, re.MULTILINE)
                self.assertTrue(native_runs)
                self.assertTrue(all('--network=' not in line for line in native_runs))
                self.assertIn('RUN --mount=type=cache,', java)

    def test_help_clean_and_dry_runs_do_not_contact_docker(self):
        for name in PROJECTS:
            project = self.copy_project(name)
            for args in (('help',), ('clean',), ('-n', 'build')):
                with self.subTest(project=name, args=args):
                    result = self.make(project, *args)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse(self.calls.exists())

    def test_missing_image_is_pulled_before_build(self):
        for name in PROJECTS:
            with self.subTest(project=name):
                project = self.copy_project(name)
                self.calls.unlink(missing_ok=True)
                result = self.make(project, 'build', IMAGE_STATUS='1')
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.operations()
                self.assertEqual(calls[0], 'image inspect ghcr.io/shell-dot/tuoni-java-builder:0.15.0')
                self.assertEqual(calls[1], 'pull --platform linux/amd64 ghcr.io/shell-dot/tuoni-java-builder:0.15.0')
                self.assertTrue(calls[2].startswith('build '))
                self.assertEqual(len(calls), 3)

    def test_failed_pull_stops_before_build_with_registry_instructions(self):
        project = self.copy_project('templates/command')
        result = self.make(project, 'build', IMAGE_STATUS='1', PULL_STATUS='7')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Could not pull the Java builder image', result.stderr)
        self.assertIn('Check the image reference and registry access.', result.stderr)
        calls = self.operations()
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1].startswith('pull '))
        self.assertFalse((project / 'build').exists())

    def test_missing_override_image_is_pulled(self):
        project = self.copy_project('templates/command')
        result = self.make(project, 'build', 'BUILDER_IMAGE=registry.example/training:custom', IMAGE_STATUS='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.operations()
        self.assertEqual(calls[1], 'pull --platform linux/amd64 registry.example/training:custom')
        self.assertIn('--build-arg BUILDER_IMAGE=registry.example/training:custom', calls[2])

    def test_image_cache_and_output_overrides_reach_docker(self):
        project = self.copy_project('templates/command')
        result = self.make(project, 'build', 'BUILDER_IMAGE=local:test',
                           'GRADLE_CACHE_ID=shared-test', 'BUILD_DIR=build/output with spaces')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.operations()
        self.assertEqual(calls[0], 'image inspect local:test')
        self.assertIn('--build-arg BUILDER_IMAGE=local:test', calls[1])
        self.assertIn('--build-arg GRADLE_CACHE_ID=shared-test', calls[1])
        self.assertIn('type=local,dest=build/output with spaces/', calls[1])

    def test_build_failures_preserve_previous_jar(self):
        project = self.copy_project('templates/command')
        jar = project / 'build/command-plugin-template-0.0.1.jar'
        jar.parent.mkdir()
        jar.write_bytes(b'previous successful build')
        result = self.make(project, 'build', BUILD_STATUS='7')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(jar.read_bytes(), b'previous successful build')
        self.assertNotIn('pull ', self.calls.read_text())

    def test_focused_native_target_does_not_require_java_image(self):
        project = self.copy_project('templates/command')
        result = self.make(project, 'build-dotnet', IMAGE_STATUS='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('image inspect', self.calls.read_text())

    def test_generated_plugins_keep_configuration_and_selected_pipeline(self):
        for kind, formats, systems in [('command', None, None), ('listener', None, None),
                                       ('command', 'native-lib', 'linux'), ('listener', 'dotnet-dll', 'windows')]:
            project, _ = scaffold(kind, 'Cache Demo', str(self.root / f'{kind}-{formats}'), formats, systems)
            self.assertEqual((project / 'scripts/docker/java-builder.mk').read_bytes(),
                             (REPO_ROOT / 'tools/docker/java-builder.mk').read_bytes())
            result = self.make(project, '-n', 'build')
            self.assertEqual(result.returncode, 0, result.stderr)
            docker = (project / 'scripts/docker/Dockerfile').read_text()
            self.assertIn('FROM ${BUILDER_IMAGE} AS gradle-seed', docker)
            self.assertIn('sharing=locked', docker)
            self.assertIn('RUN --mount=type=cache,', docker)
            self.assertEqual('$(MAKE) clean' in (project / 'Makefile').read_text(), formats is not None)

    def test_selected_builds_remove_stale_outputs_before_docker(self):
        for kind, formats, systems in [('command', 'native-lib', 'linux'),
                                       ('listener', 'dotnet-dll', 'windows')]:
            for status in ('0', '7'):
                with self.subTest(kind=kind, build_status=status):
                    project, _ = scaffold(kind, 'Clean Outputs', str(self.root / f'{kind}-{status}'), formats, systems)
                    build_dir = 'build/output with spaces'
                    stale = [project / build_dir / 'previous-version.jar',
                             project / build_dir / 'obsolete.native32_dll',
                             project / 'exec-code/linux/build/obsolete.native64_so',
                             project / 'exec-code/win-native/build/obsolete.native64_dll']
                    for path in stale:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(b'previous build')
                    self.calls.unlink(missing_ok=True)
                    dry_run = self.make(project, '-n', 'build', f'BUILD_DIR={build_dir}')
                    self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
                    self.assertTrue(all(path.exists() for path in stale))
                    self.assertFalse(self.calls.exists())
                    result = self.make(project, 'build', f'BUILD_DIR={build_dir}', BUILD_STATUS=status)
                    self.assertEqual(result.returncode == 0, status == '0', result.stderr)
                    self.assertTrue(all(not path.exists() for path in stale))
                    self.assertTrue((project / 'java-plugin/build.gradle.kts').is_file())
                    calls = self.operations()
                    self.assertEqual(len(calls), 2)
                    self.assertTrue(calls[0].startswith('image inspect '))
                    self.assertTrue(calls[1].startswith('build '))
                    self.assertIn('--build-arg GRADLE_CACHE_ID=tuoni-gradle-9.8.2-v3', calls[1])


if __name__ == '__main__':
    unittest.main()
