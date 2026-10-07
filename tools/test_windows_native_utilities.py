"""Check copied utility provenance and example/template consistency."""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def utilities(project):
    return ROOT / project / "exec-code/win-native/exec-unit-utils"


def normalized_hash(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class WindowsNativeUtilityTests(unittest.TestCase):
    def test_command_sources_match_recorded_reference(self):
        for project in ("echo-command-plugin", "templates/command"):
            folder = utilities(project)
            manifest = json.loads((folder / "UPSTREAM.json").read_text())
            self.assertEqual(manifest["source"], "commands_default/common/CommonCppExecUnit")
            modified = set(manifest.get("locally_modified", []))
            expected_modified = {"CommunicationNamedPipes.h"} if project == "echo-command-plugin" else set()
            self.assertEqual(modified, expected_modified)
            for name, expected in manifest["files"].items():
                with self.subTest(project=project, file=name):
                    if name in modified:
                        self.assertNotEqual(normalized_hash(folder / name), expected)
                    else:
                        self.assertEqual(normalized_hash(folder / name), expected)

    def test_listener_changes_are_explicit(self):
        for project in ("tcp-listener-plugin", "templates/listener"):
            folder = utilities(project)
            manifest = json.loads((folder / "UPSTREAM.json").read_text())
            modified = set(manifest["locally_modified"])
            self.assertEqual(modified, {"CommunicationNamedPipes.h", "CommunicationNamedPipes.cpp",
                                        "TLV.h", "TLV.cpp", "Conversions.h", "RaiiHelpers.h"})
            for name, expected in manifest["files"].items():
                with self.subTest(project=project, file=name):
                    if name in modified:
                        self.assertNotEqual(normalized_hash(folder / name), expected)
                    else:
                        self.assertEqual(normalized_hash(folder / name), expected)

    def test_shared_example_and_template_utility_sources_match(self):
        for example, template in (("echo-command-plugin", "templates/command"),
                                  ("tcp-listener-plugin", "templates/listener")):
            first, second = utilities(example), utilities(template)
            files = {path.name for path in first.iterdir() if path.suffix in {".h", ".cpp", ".tpp"}}
            self.assertEqual(files, {path.name for path in second.iterdir()
                                     if path.suffix in {".h", ".cpp", ".tpp"}})
            if example == "echo-command-plugin":
                local_header = (first / "CommunicationNamedPipes.h").read_bytes().replace(b"\r\n", b"\n")
                reference_header = (second / "CommunicationNamedPipes.h").read_bytes().replace(b"\r\n", b"\n")
                accessor = b"        bool isConnected() const noexcept { return _active.load() && !_cancelRequested.load(); }\n"
                self.assertEqual(local_header.count(accessor), 1)
                self.assertEqual(local_header.replace(accessor, b""), reference_header)
                files.remove("CommunicationNamedPipes.h")
            else:
                # The working TCP listener has additional request/stop behavior.
                files -= {"CommunicationNamedPipes.h", "CommunicationNamedPipes.cpp"}
            for name in files:
                with self.subTest(example=example, file=name):
                    self.assertEqual(normalized_hash(first / name), normalized_hash(second / name))


if __name__ == "__main__":
    unittest.main()
