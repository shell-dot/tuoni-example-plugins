"""Check the standalone build interface without starting Docker."""
from pathlib import Path
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class BuilderTests(unittest.TestCase):
    def test_local_build_and_check_never_publish(self):
        with tempfile.TemporaryDirectory(prefix='java builder ') as directory:
            root = Path(directory)
            shutil.copyfile(ROOT / 'Makefile', root / 'Makefile')
            calls = root / 'calls'
            docker = root / 'docker'
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_CALLS"\n')
            command = ['make', f'DOCKER=sh {shlex.quote(str(docker))}', 'BUILDER_IMAGE=local:test']
            env = dict(os.environ, DOCKER_CALLS=str(calls))
            for arguments in [('help',), ('-n', 'build'), ('-n', 'check')]:
                result = subprocess.run(command + list(arguments), cwd=root, env=env,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(calls.exists())
            result = subprocess.run(command + ['build', 'check'], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            actual = calls.read_text().splitlines()
            self.assertEqual(len(actual), 3)
            self.assertEqual(actual[0], 'build --platform linux/amd64 -t local:test .')
            self.assertTrue(actual[1].startswith('image inspect --format '))
            self.assertIn('--network none', actual[2])
            self.assertIn('local:test sh ./gradlew resolveDependencies --no-daemon --offline', actual[2])

    def test_workflow_is_manual_and_publish_is_explicit_opt_in(self):
        workflow = (ROOT.parents[1] / '.github/workflows/java-builder.yml').read_text()
        self.assertIn('on:\n  workflow_dispatch:', workflow)
        triggers = re.findall(r'^  ([\w-]+):', workflow.split('\npermissions:', 1)[0], re.MULTILINE)
        self.assertEqual(triggers, ['workflow_dispatch'])
        self.assertRegex(workflow, r'type: boolean\s+required: true\s+default: false')
        publish = workflow.split('\n  publish:\n', 1)[1]
        self.assertRegex(publish, r'(?m)^    if: \$\{\{ inputs\.publish \}\}$')

    def test_build_is_read_only_and_does_not_keep_checkout_credentials(self):
        workflow = (ROOT.parents[1] / '.github/workflows/java-builder.yml').read_text()
        build = workflow.split('\n  publish:\n', 1)[0]
        self.assertIn('permissions:\n  contents: read\n', build)
        self.assertIn('    permissions:\n      contents: read\n', build)
        self.assertNotIn('packages:', build)
        self.assertNotIn('secrets.', build)
        self.assertNotIn('docker login ', build)
        self.assertNotIn('docker push ', build)
        self.assertRegex(build, r'uses: actions/checkout@[^\n]+\n        with:\n          persist-credentials: false')

    def test_publishing_loads_the_validated_image_without_running_repository_code(self):
        workflow = (ROOT.parents[1] / '.github/workflows/java-builder.yml').read_text()
        build, publish = workflow.split('\n  publish:\n', 1)
        self.assertIn('    needs: build-and-validate\n', publish)
        self.assertIn('    permissions:\n      packages: write\n', publish)
        self.assertIn('artifact-id: ${{ steps.archive.outputs.artifact-id }}', build)
        self.assertIn('artifact-ids: ${{ needs.build-and-validate.outputs.artifact-id }}', publish)
        self.assertIn('BUILDER_IMAGE: ${{ needs.build-and-validate.outputs.image }}', publish)
        self.assertLess(build.index('run: make check'), build.index('run: docker save '))
        self.assertIn('docker load --input "$RUNNER_TEMP/java-builder/java-builder.tar"', publish)
        self.assertIn('docker push "$BUILDER_IMAGE"', publish)
        self.assertNotIn('actions/checkout', publish)
        self.assertNotIn('make ', publish)
        self.assertNotIn('gradlew', publish)
        self.assertNotIn('docker run ', publish)
        self.assertNotIn('docker build ', publish)

    def test_actions_are_pinned_to_full_commit_ids(self):
        workflow = (ROOT.parents[1] / '.github/workflows/java-builder.yml').read_text()
        actions = re.findall(r'uses: (\S+)', workflow)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r'^actions/[\w-]+@[0-9a-f]{40}$')


if __name__ == '__main__':
    unittest.main()
