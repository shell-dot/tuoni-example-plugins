"""Exercise portable Java builder recipes without downloading or running Docker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from scaffold_plugin import scaffold
from test_docker_runner import PROJECTS, REPO_ROOT


@unittest.skipUnless(shutil.which("make") and os.name == "posix", "GNU Make and a POSIX shell required")
class JavaBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".java-builder-", dir=REPO_ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.log = self.directory / "calls.jsonl"
        self.stub = self.directory / "docker stub.py"
        self.stub.write_text(
            "import json, os, sys\n"
            "with open(os.environ['BUILDER_TEST_LOG'], 'a') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1:3] == ['image', 'inspect'] and os.environ.get('BUILDER_TEST_MISSING'):\n"
            "    sys.exit(1)\n",
            encoding="utf-8",
        )

    def make(self, project: Path, *arguments: str, missing: bool = False) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for key in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES"):
            env.pop(key, None)
        env["BUILDER_TEST_LOG"] = str(self.log)
        if missing:
            env["BUILDER_TEST_MISSING"] = "1"
        return subprocess.run(
            ["make", "--no-print-directory", "-C", str(project), *arguments,
             "DOCKER=" + shlex.join([sys.executable, str(self.stub)])],
            env=env, text=True, capture_output=True, timeout=30,
        )

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def project_copy(self, project: str) -> Path:
        path = self.directory / project
        path.mkdir(parents=True)
        shutil.copyfile(REPO_ROOT / project / "Makefile", path / "Makefile")
        return path

    def test_save_load_preserve_archive_path_and_tag_without_rebuilding(self) -> None:
        archive = self.directory / "lab images" / "builder.tar"
        for target in ("builder-save", "builder-load"):
            result = self.make(REPO_ROOT, target, f"BUILDER_ARCHIVE={archive}", "BUILDER_IMAGE=lab/java:course2")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [
            ["image", "save", "-o", str(archive), "lab/java:course2"],
            ["image", "load", "-i", str(archive)],
            ["image", "inspect", "lab/java:course2"],
        ])

    def test_inventory_check_never_pulls_an_image_or_enables_network(self) -> None:
        result = self.make(REPO_ROOT, "builder-check", "BUILDER_IMAGE=lab/tools:course2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [[
            "run", "--rm", "--pull=never", "--platform", "linux/amd64",
            "--network", "none", "lab/tools:course2", "check-tuoni-builder",
        ]])

    def test_missing_builder_stops_all_projects_before_compilation(self) -> None:
        for project in PROJECTS:
            with self.subTest(project=project):
                self.log.unlink(missing_ok=True)
                result = self.make(self.project_copy(project), "build", missing=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("make builder-load", result.stderr)
                self.assertEqual(len(self.calls()), 1)
                self.assertEqual(self.calls()[0][:2], ["image", "inspect"])

    def test_aggregate_build_passes_custom_image_to_each_example(self) -> None:
        root = self.directory / "repo"
        root.mkdir()
        shutil.copyfile(REPO_ROOT / "Makefile", root / "Makefile")
        for project in PROJECTS[:3]:
            path = root / project
            path.mkdir()
            shutil.copyfile(REPO_ROOT / project / "Makefile", path / "Makefile")
        result = self.make(root, "build", "BUILDER_IMAGE=lab/java:course2")
        self.assertEqual(result.returncode, 0, result.stderr)
        builds = [args for args in self.calls() if args[0] == "build"]
        self.assertEqual(len(builds), 3)
        for args in builds:
            self.assertIn("BUILDER_IMAGE=lab/java:course2", args)

    def test_generated_selected_projects_use_imported_builder(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                self.log.unlink(missing_ok=True)
                project, _ = scaffold(kind, "Lab Demo", str(self.directory / kind), "native-lib", "linux")
                result = self.make(project, "build", "BUILDER_IMAGE=lab/java:course2")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.calls()[0], ["image", "inspect", "lab/java:course2"])
                self.assertIn("BUILDER_IMAGE=lab/java:course2", self.calls()[1])
                dockerfile = (project / "scripts/docker/Dockerfile").read_text()
                self.assertIn("ARG BUILDER_IMAGE=", dockerfile.split("FROM ")[0])
                self.assertIn("${BUILDER_IMAGE} AS toolchains", dockerfile)
                self.assertIn("FROM toolchains AS java-build", dockerfile)
                self.assertIn("RUN --network=none", dockerfile)
                self.assertIn("./gradlew build --offline --no-daemon", dockerfile)


if __name__ == "__main__":
    unittest.main()
