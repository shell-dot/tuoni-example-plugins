"""Archive-only regression fixtures; these are not runnable Java plugins."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "templates/command/scripts/verify_java_artifact.py"
SPEC = importlib.util.spec_from_file_location("verify_java_artifact", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class VerifyJavaArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".artifact-check-", dir=REPO_ROOT)
        self.output_root = Path(self.temporary.name).resolve()
        self.assertTrue(self.output_root.is_relative_to(REPO_ROOT))
        self.archive = self.output_root / "plugin.jar"

    def tearDown(self) -> None:
        self.assertTrue(self.output_root.is_relative_to(REPO_ROOT))
        self.temporary.cleanup()

    @staticmethod
    def entries(kind: str = "command") -> dict[str, bytes]:
        manifest = "Manifest-Version: 1.0\r\n" + "".join(
            f"{name}: fixture\r\n" for name in checker.PLUGIN_ATTRIBUTES
        ) + "\r\n"
        return {
            "META-INF/MANIFEST.MF": manifest.encode(),
            f"META-INF/services/com.shelldot.tuoni.plugin.sdk.{kind}.{kind.title()}Plugin": b"example.FixturePlugin\n",
            "example/FixturePlugin.class": b"Archive-only fixture, not runnable bytecode",
        }

    def write_archive(self, entries: dict[str, bytes]) -> None:
        with ZipFile(self.archive, "w") as jar:
            for name, content in entries.items():
                jar.writestr(name, content)

    def with_jackson(self, kind: str = "command") -> dict[str, bytes]:
        entries = self.entries(kind)
        entries.update({name.replace(".", "/") + ".class": b"Archive-only fixture" for name in checker.JACKSON3_CLASSES})
        return entries

    def test_valid_command_and_listener_archives(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                self.write_archive(self.with_jackson(kind))
                self.assertEqual(checker.inspect_archive(self.archive, kind, jackson3=True), [])

    def test_databind_without_core_exception_fails(self) -> None:
        entries = self.with_jackson()
        del entries["tools/jackson/core/JacksonException.class"]
        self.write_archive(entries)
        errors = checker.inspect_archive(self.archive, "command", jackson3=True)
        self.assertEqual(len(errors), 1)
        self.assertIn("missing classpath-root class tools/jackson/core/JacksonException.class", errors[0])

    def test_nested_dependency_jar_does_not_supply_root_classes(self) -> None:
        entries = self.with_jackson()
        missing = "tools/jackson/core/JacksonException.class"
        nested = io.BytesIO()
        with ZipFile(nested, "w") as jar:
            jar.writestr(missing, entries.pop(missing))
        entries["lib/jackson-core.jar"] = nested.getvalue()
        self.write_archive(entries)
        errors = checker.inspect_archive(self.archive, "command", jackson3=True)
        self.assertEqual(len(errors), 1)
        self.assertIn("nested dependency JAR", errors[0])

    def test_spi_comments_blanks_and_multiple_providers(self) -> None:
        entries = self.entries()
        service = next(name for name in entries if name.startswith("META-INF/services/"))
        entries[service] = b"# Providers\n\n example.FixturePlugin # first\nexample.Second$Nested\nexample.FixturePlugin\n"
        entries["example/Second$Nested.class"] = b"Archive-only fixture"
        self.write_archive(entries)
        self.assertEqual(checker.inspect_archive(self.archive, "command"), [])

    def test_spi_provider_must_have_root_class(self) -> None:
        entries = self.entries()
        entries["BOOT-INF/classes/example/FixturePlugin.class"] = entries.pop("example/FixturePlugin.class")
        self.write_archive(entries)
        self.assertTrue(any("SPI provider: missing classpath-root class" in error for error in checker.inspect_archive(self.archive, "command")))

    def test_spi_requires_actual_valid_providers(self) -> None:
        for provider, message in ((b"# only a comment\n", "No providers"), (b"example/FixturePlugin.class", "Invalid SPI provider"), (b"example.Invalid Name", "Invalid Java binary")):
            with self.subTest(provider=provider):
                entries = self.entries()
                service = next(name for name in entries if name.startswith("META-INF/services/"))
                entries[service] = provider
                self.write_archive(entries)
                self.assertTrue(any(message in error for error in checker.inspect_archive(self.archive, "command")))

    def test_wrong_plugin_kind_does_not_match_spi(self) -> None:
        self.write_archive(self.entries("listener"))
        self.assertTrue(any("Missing SPI descriptor" in error for error in checker.inspect_archive(self.archive, "command")))

    def test_bundled_sdk_root_or_multirelease_class_fails(self) -> None:
        for prefix in ("", "META-INF/versions/21/"):
            with self.subTest(prefix=prefix):
                entries = self.entries()
                entries[prefix + "com/shelldot/tuoni/plugin/sdk/command/CommandPlugin.class"] = b"Archive-only fixture"
                self.write_archive(entries)
                self.assertTrue(any("Bundled SDK class" in error for error in checker.inspect_archive(self.archive, "command")))

    def test_manifest_folded_utf8_and_case_insensitive_attributes(self) -> None:
        entries = self.entries()
        entries["META-INF/MANIFEST.MF"] = entries["META-INF/MANIFEST.MF"].replace(
            b"Plugin-Description: fixture", b"plugin-description: caf\xc3\r\n \xa9"
        )
        self.write_archive(entries)
        self.assertEqual(checker.inspect_archive(self.archive, "command"), [])

    def test_manifest_named_section_cannot_supply_plugin_identity(self) -> None:
        entries = self.entries()
        entries["META-INF/MANIFEST.MF"] = b"Manifest-Version: 1.0\r\n\r\nName: example/FixturePlugin.class\r\n" + entries["META-INF/MANIFEST.MF"]
        self.write_archive(entries)
        errors = checker.inspect_archive(self.archive, "command")
        self.assertEqual(len(errors), len(checker.PLUGIN_ATTRIBUTES))
        self.assertTrue(all("Missing or empty main manifest attribute" in error for error in errors))

    def test_each_manifest_identity_attribute_must_be_nonempty(self) -> None:
        for name in checker.PLUGIN_ATTRIBUTES:
            with self.subTest(attribute=name):
                entries = self.entries()
                entries["META-INF/MANIFEST.MF"] = entries["META-INF/MANIFEST.MF"].replace(f"{name}: fixture".encode(), f"{name}: ".encode())
                self.write_archive(entries)
                self.assertEqual(checker.inspect_archive(self.archive, "command"), [f"Missing or empty main manifest attribute {name}"])

    def test_missing_or_invalid_archives_produce_actionable_cli_failure(self) -> None:
        for data in (None, b"not a ZIP archive"):
            with self.subTest(data=data):
                if data is not None:
                    self.archive.write_bytes(data)
                output, errors = io.StringIO(), io.StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    exit_code = checker.main([str(self.archive), "--kind", "command"])
                self.assertEqual(exit_code, 1)
                self.assertIn("Cannot inspect JAR", errors.getvalue())
                self.assertNotIn("passed", output.getvalue())

    def test_repeated_required_classes_and_success_limitations(self) -> None:
        entries = self.entries()
        entries["example/library/One.class"] = b"Archive-only fixture"
        entries["example/library/Two.class"] = b"Archive-only fixture"
        self.write_archive(entries)
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = checker.main([str(self.archive), "--kind", "command", "--require-class", "example.library.One", "--require-class", "example/library/Two.class"])
        self.assertEqual(exit_code, 0)
        self.assertIn("remain separate checks", output.getvalue())
        self.assertTrue(checker.inspect_archive(self.archive, "command", required_classes=["example.Missing"]))

    def test_template_checker_copies_are_identical(self) -> None:
        self.assertEqual(SCRIPT.read_bytes(), (REPO_ROOT / "templates/listener/scripts/verify_java_artifact.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
