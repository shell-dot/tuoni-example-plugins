"""Integration checks for the repository plugin scaffolder."""

from __future__ import annotations

import os
import html
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

import scaffold_plugin
from scaffold_plugin import REPO_ROOT, scaffold, support_matrix


def markdown_prose(content: str) -> str:
    """Ignore fenced examples when checking real headings and links."""
    lines = []
    fence = None
    for line in content.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is None:
            if marker:
                fence = marker.group(1)
            else:
                lines.append(line)
        elif (marker and marker.group(1)[0] == fence[0]
              and len(marker.group(1)) >= len(fence) and not marker.group(2).strip()):
            fence = None
    return "\n".join(lines)


def markdown_anchors(content: str) -> set[str]:
    content = markdown_prose(content)
    anchors = set(re.findall(r'<[^>]+\b(?:id|name)=["\']([^"\']+)["\']', content))
    used = set()
    for heading in re.findall(r"^ {0,3}#{1,6}\s+(.+)$", content, re.MULTILINE):
        heading = re.sub(r"\s+#+\s*$", "", heading)
        heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
        heading = re.sub(r"<[^>]*>", "", heading)
        base = re.sub(r"[^\w\- ]", "", html.unescape(heading).lower()).strip().replace(" ", "-")
        anchor = base
        suffix = 0
        while anchor in used:
            suffix += 1
            anchor = f"{base}-{suffix}"
        used.add(anchor)
        anchors.add(anchor)
    return anchors


class ScaffoldPluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".scaffold-check-", dir=REPO_ROOT)
        self.output_root = Path(self.temporary.name).resolve()
        self.assertTrue(self.output_root.is_relative_to(REPO_ROOT))
        self.workspace_root = self.output_root / "workspace"
        self.workspace_patch = patch.object(scaffold_plugin, "DEFAULT_WORKSPACE_ROOT", self.workspace_root)
        self.workspace_patch.start()
        self.addCleanup(self.workspace_patch.stop)

    def tearDown(self) -> None:
        self.assertTrue(self.output_root.is_relative_to(REPO_ROOT))
        self.temporary.cleanup()

    def test_named_command_in_default_folder(self) -> None:
        original_cwd = Path.cwd()
        try:
            os.chdir(REPO_ROOT.parent)
            destination, slug = scaffold("command", "Port Scan", None)
        finally:
            os.chdir(original_cwd)
        self.assertEqual(slug, "port-scan")
        self.assertEqual(destination, self.workspace_root / "commands/port-scan")

        java_root = destination / "java-plugin/src/main/java/com/example/tuoni/command/port_scan"
        template = java_root / "PortScanCommandTemplate.java"
        self.assertIn('NAME = "port-scan"', template.read_text(encoding="utf-8"))
        self.assertIn("package com.example.tuoni.command.port_scan;", template.read_text(encoding="utf-8"))
        self.assertTrue((java_root / "PortScanCommandPlugin.java").is_file())
        self.assertTrue((java_root / "PortScanCommandConfigurationSchema.java").is_file())
        service = destination / "java-plugin/src/main/resources/META-INF/services/com.shelldot.tuoni.plugin.sdk.command.CommandPlugin"
        self.assertEqual(service.read_text(encoding="utf-8").strip(), "com.example.tuoni.command.port_scan.PortScanCommandPlugin")
        gradle = (destination / "java-plugin/build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn('group = "com.example.tuoni.command.port_scan"', gradle)
        self.assertNotIn("port_scan.port_scan", gradle)
        self.assertIn("command-port-scan-linux.native64_so", gradle)
        self.assertIn('rootProject.name = "command-plugin-port-scan"', (destination / "java-plugin/settings.gradle.kts").read_text(encoding="utf-8"))

        win = destination / "exec-code/win"
        self.assertTrue((win / "command-port-scan-execunit.sln").is_file())
        project = (win / "command-port-scan-execunit.csproj").read_text(encoding="utf-8")
        self.assertIn("<AssemblyName>command-port-scan-execunit</AssemblyName>", project)
        self.assertIn("../../java-plugin/src/main/resources/command-port-scan.shellcode", project)
        project_guid = re.search(r"<ProjectGuid>(\{[0-9A-F-]+\})</ProjectGuid>", project).group(1)
        self.assertIn(project_guid, (win / "command-port-scan-execunit.sln").read_text(encoding="utf-8"))
        self.assertNotEqual(project_guid, "{F2DFB624-6F58-42CC-B4CF-9C245E68DA61}")
        self.assertIn("namespace PortScanCommandExecUnit", (win / "Program.cs").read_text(encoding="utf-8"))
        self.assertTrue((win / "donut.exe").is_file())
        self.assertFalse((win / "bin").exists())

        linux = destination / "exec-code/linux"
        self.assertTrue((linux / "command-port-scan/Main.cpp").is_file())
        self.assertIn("command-port-scan/Main.cpp", (linux / "build_linux.sh").read_text(encoding="utf-8"))
        self.assertIn("command-port-scan-execunit.shellcode", (destination / "scripts/docker/Dockerfile").read_text(encoding="utf-8"))
        self.assertIn("command-plugin-port-scan-0.0.1.jar", (destination / "Makefile").read_text(encoding="utf-8"))
        self.assertNotIn("../README.md", (destination / "README.md").read_text(encoding="utf-8"))

    def test_named_listener_in_default_folder(self) -> None:
        original_cwd = Path.cwd()
        try:
            os.chdir(REPO_ROOT.parent)
            destination, slug = scaffold("listener", "Event Relay", None)
        finally:
            os.chdir(original_cwd)
        self.assertEqual(slug, "event-relay")
        self.assertEqual(destination, self.workspace_root / "listeners/event-relay")
        self.assertTrue(
            (destination / "java-plugin/src/main/java/com/example/tuoni/listener/event_relay/EventRelayListener.java").is_file()
        )

    def test_selected_support_changes_generated_command_and_listener(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                destination, _ = scaffold(
                    kind, "Selected Native", str(self.output_root / kind),
                    "native-lib", "linux",
                )
                package = destination / f"java-plugin/src/main/java/com/example/tuoni/{kind}/selected_native"
                main = (package / f"SelectedNative{kind.capitalize()}.java").read_text(encoding="utf-8")
                check = (destination / f"java-plugin/src/test/java/com/example/tuoni/{kind}/selected_native/ExecUnitFormatsCheck.java").read_text(encoding="utf-8")
                if kind == "command":
                    self.assertIn("case WINDOWS ->", main)
                else:
                    self.assertNotIn("PayloadType.of(OperatingSystem.WINDOWS, Architecture.X64),", main)
                self.assertIn("? Set.of() : Set.of();", main)
                self.assertNotIn("ShellcodeCommand {", main)
                self.assertNotIn("ShellcodeListener {", main)
                self.assertNotIn("generateShellCode(", main)
                self.assertIn("? Set.of()", check)
                self.assertIn("? Set.of(ExecUnitType.NATIVE_LIB)", check)
                for doc in ("AGENTS.md", "README.md", "docs/support-scope.md"):
                    content = (destination / doc).read_text(encoding="utf-8")
                    self.assertIn("## Generated support", content)
                    self.assertIn("| Linux | x64 | `NATIVE_LIB` |", content)
                    self.assertNotIn("| Windows | x86, x64 |", content)
                if kind == "command":
                    template = (package / "SelectedNativeCommandTemplate.java").read_text(encoding="utf-8")
                    self.assertIn("return Set.of(ExecUnitType.NATIVE_LIB);", template)

    def test_format_only_infers_compatible_os_and_mixed_selection(self) -> None:
        self.assertEqual(support_matrix(None, "linux"), {"linux": {"native-lib"}})
        self.assertEqual(support_matrix("dotnet-dll", None), {"windows": {"dotnet-dll"}})
        self.assertEqual(
            support_matrix("native-lib, dotnet-exe", "windows linux"),
            {"windows": {"native-lib", "dotnet-exe"}, "linux": {"native-lib"}},
        )
        destination, _ = scaffold(
            "listener", "Mixed Scope", str(self.output_root / "mixed"),
            "NATIVE_LIB, DOTNET_EXE", "windows linux",
        )
        main = (destination / "java-plugin/src/main/java/com/example/tuoni/listener/mixed_scope/MixedScopeListener.java").read_text(encoding="utf-8")
        self.assertIn("Set.of(ExecUnitType.DOTNET_EXE, ExecUnitType.NATIVE_LIB)", main)
        self.assertIn("return Set.of(ExecUnitType.NATIVE_LIB);", main)
        self.assertNotIn("generateShellCode(", main)

    def test_invalid_selection_fails_before_creating_destination(self) -> None:
        cases = (("dotnet-dll", "linux"), ("shellcode-native", "linux"),
                 ("bogus", "windows"), ("native-lib", "plan9"), ("", "windows"))
        for index, (execunits, oses) in enumerate(cases):
            with self.subTest(execunits=execunits, oses=oses):
                destination = self.output_root / f"invalid-{index}"
                with self.assertRaises(ValueError):
                    scaffold("command", "Invalid", str(destination), execunits, oses)
                self.assertFalse(destination.exists())

    def test_cli_passes_selected_support_to_generated_plugin(self) -> None:
        destination = self.output_root / "cli-selected"
        result = subprocess.run(
            [sys.executable, "-B", str(REPO_ROOT / "tools/scaffold_plugin.py"),
             "command", "--name=CLI Selected", f"--folder={destination}",
             "--execunits=dotnet-dll,dotnet-exe", "--os=windows"],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True,
        )
        self.assertIn("Created command 'cli-selected'", result.stdout)
        main = (destination / "java-plugin/src/main/java/com/example/tuoni/command/cli_selected/CliSelectedCommand.java").read_text(encoding="utf-8")
        self.assertIn("Set.of(ExecUnitType.DOTNET_DLL, ExecUnitType.DOTNET_EXE)", main)
        self.assertNotIn("generateShellCode(", main)

    def test_selected_builds_package_only_supported_formats(self) -> None:
        cases = (
            ("command", "Linux Native", "native-lib", "linux", {"linux-build", "linux-artifacts", "java-build", "artifacts"},
             {"linux.native64_so"}, {".shellcode", ".dotnet_exe", ".dotnet_dll", ".native32_dll"}),
            ("listener", "Managed Only", "dotnet-dll", "windows", {"csharp-build", "java-build", "dotnet-artifacts", "artifacts"},
             {".dotnet_dll", ".dotnet_dll_method"}, {".shellcode", ".dotnet_exe", ".native32_dll", "linux.native64_so"}),
            ("command", "Shellcode Only", "shellcode-native", "windows", {"csharp-build", "shellcode-build", "java-build", "artifacts"},
             {".shellcode"}, {".dotnet_exe", ".dotnet_dll", ".native32_dll", "linux.native64_so"}),
            ("listener", "Native Both", "native-lib", "windows linux", {"linux-build", "linux-artifacts", "windows-native-build", "windows-native-artifacts", "java-build", "artifacts"},
             {".native32_dll", ".native64_dll", "linux.native64_so"}, {".shellcode", ".dotnet_exe", ".dotnet_dll"}),
            ("command", "Every Format", "shellcode-native dotnet-dll dotnet-exe native-lib", "windows linux",
             {"csharp-build", "shellcode-build", "linux-build", "linux-artifacts", "windows-native-build", "windows-native-artifacts", "java-build", "dotnet-artifacts", "artifacts"},
             {".shellcode", ".dotnet_exe", ".dotnet_dll", ".dotnet_dll_method", ".native32_dll", ".native64_dll", "linux.native64_so"}, set()),
        )
        for index, (kind, name, formats, systems, stages, included, excluded) in enumerate(cases):
            with self.subTest(kind=kind, name=name):
                destination, slug = scaffold(kind, name, str(self.output_root / f"selected-{index}"), formats, systems)
                artifact = f"{kind}-{slug}"
                docker = (destination / "scripts/docker/Dockerfile").read_text(encoding="utf-8")
                gradle = (destination / "java-plugin/build.gradle.kts").read_text(encoding="utf-8")
                makefile = (destination / "Makefile").read_text(encoding="utf-8")
                actual_stages = set(re.findall(r"(?m)^FROM [^\n]+ AS ([\w-]+)$", docker))
                self.assertEqual(actual_stages, stages)
                self.assertTrue(set(re.findall(r"--from=([\w-]+)", docker)) <= stages)
                for suffix in included:
                    resource = artifact + ("-" if suffix.startswith("linux") else "") + suffix
                    self.assertIn(resource, gradle)
                    if suffix.startswith("linux"):
                        self.assertIn(resource, docker)
                    elif suffix.startswith((".dotnet", ".shellcode")):
                        self.assertIn(f"{artifact}-execunit{suffix}", docker)
                for suffix in excluded:
                    resource = artifact + ("-" if suffix.startswith("linux") else "") + suffix
                    self.assertNotIn(resource, gradle)
                self.assertIn("--target artifacts", makefile)
                self.assertIn("\t@$(MAKE) clean\n", makefile)
                self.assertIn("build-windows-native:", makefile)
                context = (destination / "AGENTS.md").read_text(encoding="utf-8")
                self.assertIn("- Packaged execution resources:", context)
                self.assertNotIn("This is the current source-template snapshot", context)
                self.assertNotIn("- Both generation methods", context)
                self.assert_local_links_resolve(destination / "README.md", destination)
                self.assert_local_links_resolve(destination / "AGENTS.md", destination)
                if systems == "linux":
                    self.assertNotIn("msbuild", (destination / "README.md").read_text(encoding="utf-8"))

    def test_reserved_sdk_class_names_are_disambiguated(self) -> None:
        cases = (("command", "Command"), ("listener", "Listener"),
                 ("command", "Shellcode"), ("listener", "Exec Unit"))
        for index, (kind, name) in enumerate(cases):
            with self.subTest(kind=kind, name=name):
                destination, _ = scaffold(kind, name, str(self.output_root / f"sdk-name-{index}"))
                java_root = destination / "java-plugin/src/main/java"
                for source in java_root.rglob("*.java"):
                    content = source.read_text(encoding="utf-8")
                    self.assertNotRegex(content, rf"(?m)^public class {re.escape(source.stem)} implements [^\n]*\b{re.escape(source.stem)}\b")
                    imports = set(re.findall(r"(?m)^import [\w.]+\.([A-Za-z_$][\w$]*);$", content))
                    self.assertNotIn(source.stem, imports)

    @unittest.skipUnless(shutil.which("make"), "GNU Make is unavailable")
    def test_make_target_forwards_support_options(self) -> None:
        destination = self.output_root / "make-selected"
        subprocess.run(
            ["make", "new-command", "NAME=Make Selected", f"FOLDER={destination}",
             "EXECUNITS=dotnet-dll", "OS=windows", f"PYTHON={sys.executable}"],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True,
        )
        main = (destination / "java-plugin/src/main/java/com/example/tuoni/command/make_selected/MakeSelectedCommand.java").read_text(encoding="utf-8")
        self.assertIn("Set.of(ExecUnitType.DOTNET_DLL)", main)
        self.assertNotIn("generateShellCode(", main)

    def test_default_reuses_existing_workspace_and_category_directories(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                category = self.workspace_root / f"{kind}s"
                sibling = category / "existing-plugin"
                sibling.mkdir(parents=True)
                marker = sibling / "keep.txt"
                marker.write_text("existing plugin", encoding="utf-8")
                destination, slug = scaffold(kind, "Another Plugin", None)
                self.assertEqual((destination, slug), (category / "another-plugin", "another-plugin"))
                self.assertEqual(marker.read_text(encoding="utf-8"), "existing plugin")

    def test_explicit_destination_overrides_workspace_default(self) -> None:
        invocation = self.output_root / "invocation"
        invocation.mkdir()
        original_cwd = Path.cwd()
        try:
            os.chdir(invocation)
            for kind in ("command", "listener"):
                for relative in (True, False):
                    with self.subTest(kind=kind, relative=relative):
                        folder = Path("chosen") / f"{kind}-relative" if relative else self.output_root / f"{kind}-absolute"
                        expected = (invocation / folder).resolve() if relative else folder
                        destination, slug = scaffold(kind, "Explicit Name", str(folder))
                        self.assertEqual((destination, slug), (expected, "explicit-name"))
                        self.assertTrue((destination / "AGENTS.md").is_file())
        finally:
            os.chdir(original_cwd)
        self.assertFalse(self.workspace_root.exists())

    def test_default_destination_refuses_overwrite(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                destination, _ = scaffold(kind, "Keep Plugin", None)
                marker = destination / "keep.txt"
                marker.write_text("user changes", encoding="utf-8")
                java_file = next((destination / "java-plugin/src/main/java").rglob("*.java"))
                original_source = java_file.read_bytes()
                with self.assertRaises(FileExistsError):
                    scaffold(kind, "keep-plugin", None)
                self.assertEqual(marker.read_text(encoding="utf-8"), "user changes")
                self.assertEqual(java_file.read_bytes(), original_source)
                self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_listener_uses_folder_name_and_refuses_overwrite(self) -> None:
        destination = self.output_root / "listener_beacon"
        created, slug = scaffold("listener", None, str(destination))
        self.assertEqual((created, slug), (destination, "beacon"))
        java_root = destination / "java-plugin/src/main/java/com/example/tuoni/listener/beacon"
        self.assertTrue((java_root / "BeaconListener.java").is_file())
        service = destination / "java-plugin/src/main/resources/META-INF/services/com.shelldot.tuoni.plugin.sdk.listener.ListenerPlugin"
        self.assertEqual(service.read_text(encoding="utf-8").strip(), "com.example.tuoni.listener.beacon.BeaconListenerPlugin")
        self.assertTrue((destination / "exec-code/win/listener-beacon-execunit.sln").is_file())
        self.assertTrue((destination / "exec-code/linux/listener-beacon/Main.cpp").is_file())
        linux_source = (destination / "exec-code/linux/listener-beacon/Main.cpp").read_text(encoding="utf-8")
        self.assertIn("tcp-listener-plugin/exec-code/linux/tcp-listener/Main.cpp", linux_source)
        self.assertIn("listener-beacon-linux.native64_so", (destination / "Makefile").read_text(encoding="utf-8"))

        with self.assertRaises(FileExistsError):
            scaffold("listener", "Other", str(destination))
        self.assertTrue((java_root / "BeaconListener.java").is_file())

    def test_missing_name_uses_default(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                destination, slug = scaffold(kind, None, None)
                self.assertEqual(slug, f"new-{kind}")
                self.assertEqual(destination, self.workspace_root / f"{kind}s" / f"new-{kind}")
                java_file = f"java-plugin/src/main/java/com/example/tuoni/{kind}/new_{kind}/New{kind.capitalize()}.java"
                self.assertTrue((destination / java_file).is_file())

    def test_reserved_words_and_leading_digits_use_valid_java_packages(self) -> None:
        cases = {
            "class": "plugin_class",
            "Switch": "plugin_switch",
            "true": "plugin_true",
            "false": "plugin_false",
            "null": "plugin_null",
            "123 Job": "n_123_job",
        }
        for kind in ("command", "listener"):
            for name, component in cases.items():
                with self.subTest(kind=kind, name=name):
                    destination, _ = scaffold(kind, name, str(self.output_root / f"{kind}-{component}"))
                    package = f"com.example.tuoni.{kind}.{component}"
                    java_root = destination / "java-plugin/src/main/java" / package.replace(".", "/")
                    self.assertTrue(java_root.is_dir())
                    for source in java_root.glob("*.java"):
                        self.assertIn(f"package {package};", source.read_text(encoding="utf-8"))
                    service = destination / "java-plugin/src/main/resources/META-INF/services" / (
                        f"com.shelldot.tuoni.plugin.sdk.{kind}.{kind.capitalize()}Plugin"
                    )
                    provider = service.read_text(encoding="utf-8").strip()
                    self.assertTrue(provider.startswith(package + "."))
                    self.assertTrue((java_root / (provider.rsplit(".", 1)[1] + ".java")).is_file())
                    self.assertIn(f'group = "{package}"', (destination / "java-plugin/build.gradle.kts").read_text(encoding="utf-8"))

    def test_generated_names_are_not_replaced_again(self) -> None:
        for kind in ("command", "listener"):
            title = kind.capitalize()
            for name in (f"MyTemplate{title}", "execunit"):
                with self.subTest(kind=kind, name=name):
                    destination, slug = scaffold(kind, name, str(self.output_root / f"{kind}-{name}"))
                    java_root = destination / "java-plugin/src/main/java"
                    for source in java_root.rglob("*.java"):
                        declaration = re.search(
                            r"^(?:public\s+)?(?:final\s+)?(?:class|record)\s+(\w+)",
                            source.read_text(encoding="utf-8"),
                            re.MULTILINE,
                        )
                        self.assertIsNotNone(declaration, source)
                        self.assertEqual(declaration.group(1), source.stem)
                    if name.startswith("MyTemplate"):
                        expected_provider = f"{name}Plugin"
                        services = destination / "java-plugin/src/main/resources/META-INF/services"
                        provider = next(services.iterdir()).read_text(encoding="utf-8").strip()
                        self.assertEqual(provider.rsplit(".", 1)[1], expected_provider)
                    executable = f"{kind}-{slug}-execunit"
                    win = destination / "exec-code/win"
                    project = win / f"{executable}.csproj"
                    self.assertTrue(project.is_file())
                    self.assertIn(f"<AssemblyName>{executable}</AssemblyName>", project.read_text(encoding="utf-8"))
                    self.assertIn(f'"{executable}.csproj"', (win / f"{executable}.sln").read_text(encoding="utf-8"))
                    self.assertIn(f"{executable}.exe", (destination / "scripts/docker/Dockerfile").read_text(encoding="utf-8"))

    def assert_local_links_resolve(self, markdown: Path, boundary: Path) -> None:
        content = markdown_prose(markdown.read_text(encoding="utf-8"))
        for href in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content):
            href = href.strip("<>")
            if "://" in href:
                continue
            relative, _, fragment = href.partition("#")
            target = (markdown.parent / unquote(relative)).resolve() if relative else markdown.resolve()
            self.assertTrue(target.is_relative_to(boundary), (markdown, href))
            self.assertTrue(target.is_file(), (markdown, href))
            if fragment:
                self.assertIn(unquote(fragment), markdown_anchors(target.read_text(encoding="utf-8")),
                              (markdown, href))

    def test_local_links_validate_section_fragments(self) -> None:
        target = self.output_root / "target.md"
        target.write_text(
            "# Shared heading\n## Shared heading\n## Shared heading-1\n"
            "## A `code` &amp; text heading\n<a id=\"explicit-section\"></a>\n"
            "```markdown\n## Example only\n[not a link](missing.md)\n```\n"
            "~~~~\n## Also an example\n~~~\n~~~~\n",
            encoding="utf-8",
        )
        source = self.output_root / "links.md"
        source.write_text(
            "# Local heading\n[local](#local-heading)\n"
            "[first](target.md#shared-heading)\n[second](target.md#shared-heading-1)\n"
            "[collision](target.md#shared-heading-1-1)\n"
            "[formatted](target.md#a-code--text-heading)\n"
            "[explicit](target.md#explicit%2Dsection)\n"
            "```markdown\n[example](missing.md#section)\n```\n",
            encoding="utf-8",
        )
        self.assert_local_links_resolve(source, self.output_root)
        self.assert_local_links_resolve(target, self.output_root)
        for href in ("#absent", "target.md#absent", "target.md#shared-heading-2",
                     "target.md#example-only", "target.md#also-an-example"):
            with self.subTest(href=href):
                source.write_text(f"[broken]({href})\n", encoding="utf-8")
                with self.assertRaises(AssertionError):
                    self.assert_local_links_resolve(source, self.output_root)

    def test_skills_and_references_survive_scaffolding(self) -> None:
        for kind in ("command", "listener"):
            destination, _ = scaffold(kind, "Skill Copy", str(self.output_root / kind))
            main_class = f"SkillCopy{kind.capitalize()}"
            java_file = destination / f"java-plugin/src/main/java/com/example/tuoni/{kind}/skill_copy/{main_class}.java"
            self.assertTrue(java_file.is_file())
            source_docs = REPO_ROOT / "templates" / kind / "docs"
            self.assertEqual(
                {path.relative_to(source_docs) for path in source_docs.rglob("*") if path.is_file()},
                {path.relative_to(destination / "docs") for path in (destination / "docs").rglob("*") if path.is_file()},
            )
            for client in (".agents", ".claude"):
                for suffix in ("implement", "conf", "logic", "output"):
                    name = f"{kind}-{suffix}"
                    skill = destination / client / "skills" / name / "SKILL.md"
                    self.assertTrue(skill.is_file(), skill)
                    content = skill.read_text(encoding="utf-8")
                    self.assertIn(f"name: {name}\n", content)
                    self.assertNotIn(f"Template{kind.capitalize()}", content)
                    self.assertIn(main_class, content)
                    self.assert_local_links_resolve(skill, destination)
                    if suffix in ("logic", "output"):
                        self.assertIn(java_file.relative_to(destination).as_posix(), content)
                    mirror = destination / (".claude" if client == ".agents" else ".agents") / "skills" / name / "SKILL.md"
                    self.assertEqual(skill.read_bytes(), mirror.read_bytes())
            for document in (destination / "docs").rglob("*.md"):
                self.assert_local_links_resolve(document, destination)
                content = document.read_text(encoding="utf-8")
                for original in (
                    f"{kind}-plugin-template",
                    f"Template{kind.capitalize()}",
                    "TemplateConfigurationSchema",
                    f"exec-code/linux/{kind}/Main.cpp",
                ):
                    self.assertNotIn(original, content, document)
            self.assert_local_links_resolve(destination / "README.md", destination)

    def test_plugin_context_survives_scaffolding(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                destination, slug = scaffold(kind, "Context Copy", str(self.output_root / kind))
                source = REPO_ROOT / "templates" / kind
                for relative in ("AGENTS.md", "CLAUDE.md", "docs/project-context.md"):
                    self.assertTrue((source / relative).is_file(), source / relative)
                    copied = destination / relative
                    self.assertTrue(copied.is_file(), copied)
                    self.assert_local_links_resolve(copied, destination)

                agents = destination / "AGENTS.md"
                claude = destination / "CLAUDE.md"
                claude_targets = {
                    (claude.parent / href.strip("<>").split("#", 1)[0]).resolve()
                    for href in re.findall(r"\[[^\]]+\]\(([^)]+)\)", claude.read_text(encoding="utf-8"))
                    if "://" not in href and not href.startswith("#")
                }
                self.assertIn(agents.resolve(), claude_targets)
                self.assertIn((destination / "docs/project-context.md").resolve(), claude_targets)

                context = agents.read_text(encoding="utf-8")
                gradle = (destination / "java-plugin/build.gradle.kts").read_text(encoding="utf-8")
                identity = re.search(r'"Plugin-Id"\s+to\s+"([^"]+)"', gradle)
                self.assertIsNotNone(identity)
                self.assertIn(identity.group(1), context)
                main_class = f"ContextCopy{kind.capitalize()}"
                expected_sources = (
                    f"java-plugin/src/main/java/com/example/tuoni/{kind}/context_copy/{main_class}.java",
                    f"exec-code/win/{kind}-{slug}-execunit.csproj",
                    f"exec-code/win-native/{kind}-{slug}/Main.cpp",
                    f"exec-code/linux/{kind}-{slug}/Main.cpp",
                )
                for relative in expected_sources:
                    self.assertTrue((destination / relative).is_file(), relative)
                    self.assertIn(relative, context)
                for artifact in (f"{kind}-{slug}.shellcode", f"{kind}-{slug}-linux.native64_so"):
                    self.assertIn(artifact, gradle)
                    self.assertIn(artifact, context)
                for original in (
                    f"Template{kind.capitalize()}",
                    "TemplateConfigurationSchema",
                    f"example.{kind}.template",
                    f"{kind}-plugin-template",
                    f"exec-code/linux/{kind}/Main.cpp",
                ):
                    self.assertNotIn(original, context)

    def test_generated_context_does_not_inherit_template_verification(self) -> None:
        for kind in ("command", "listener"):
            for restricted in (False, True):
                with self.subTest(kind=kind, restricted=restricted):
                    folder = self.output_root / f"{kind}-{restricted}"
                    destination, slug = scaffold(
                        kind, "Fresh Context", str(folder),
                        "native-lib" if restricted else None,
                        "linux" if restricted else None,
                    )
                    context = (destination / "AGENTS.md").read_text(encoding="utf-8")
                    self.assertIn("This is a generated plugin.", context)
                    self.assertIn("## Generated-plugin verification", context)
                    self.assertIn("checks have not been run for this generated copy", context)
                    for stale in ("source-template snapshot", "## Source-template verification",
                                  "template-verification:", "- Template-source verification:",
                                  "- Native memory-safety guidance:",
                                  "- Documentation-only orientation and support-scope checks:",
                                  "repository tooling suite ran", "- Creation-skill audit:"):
                        self.assertNotIn(stale, context)
                    self.assertIn("- Required workflow:", context)
                    self.assertIn("make build", context)
                    self.assertIn("docs/java-verification.md", context)
                    self.assertIn(f"exec-code/win-native/{kind}-{slug}/Main.cpp", context)
                    self.assertNotIn(f"`{kind}/Main.cpp`", context)
                    if kind == "command":
                        self.assertIn("Linux optional callback helpers still detach", context)
                    else:
                        self.assertIn("No application transport is implemented", context)
                    self.assertEqual("## Generated support" in context, restricted)

    def test_codex_and_claude_skill_trees_match(self) -> None:
        for root in (REPO_ROOT, REPO_ROOT / "templates/command", REPO_ROOT / "templates/listener"):
            with self.subTest(root=root):
                canonical = root / ".agents/skills"
                mirror = root / ".claude/skills"
                sources = {path.relative_to(canonical): path for path in canonical.rglob("*") if path.is_file()}
                copies = {path.relative_to(mirror): path for path in mirror.rglob("*") if path.is_file()}
                self.assertTrue(sources)
                self.assertEqual(sources.keys(), copies.keys())
                for relative, source in sources.items():
                    self.assertEqual(source.read_bytes(), copies[relative].read_bytes(), relative)
                    if source.suffix == ".md":
                        self.assert_local_links_resolve(source, REPO_ROOT)

    def test_managed_formats_and_checks_survive_scaffolding(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                destination, slug = scaffold(kind, "Format Copy", str(self.output_root / kind))
                executable = f"{kind}-{slug}-execunit"
                win = destination / "exec-code/win"
                project = ET.parse(win / f"{executable}.csproj")
                ns = {"m": "http://schemas.microsoft.com/developer/msbuild/2003"}
                namespace = project.find(".//m:RootNamespace", ns).text
                self.assertIn(f"namespace {namespace}", (win / "Program.cs").read_text())
                self.assertIn("public static void start(string[] args)", (win / "Program.cs").read_text())
                imports = [node.attrib["Project"] for node in project.findall("m:Import", ns)]
                self.assertIn("exec-unit-utils\\ExecUnitFormats.targets", imports)
                targets = win / "exec-unit-utils/ExecUnitFormats.targets"
                metadata = ET.parse(targets).find(".//m:WriteLinesToFile", ns)
                self.assertEqual(metadata.attrib["Lines"], "$(RootNamespace).Program::start")
                self.assertEqual(targets.read_bytes(), (REPO_ROOT / "templates" / kind / "exec-code/win/exec-unit-utils/ExecUnitFormats.targets").read_bytes())

                package = f"com.example.tuoni.{kind}.format_copy"
                check = destination / "java-plugin/src/test/java" / package.replace(".", "/") / "ExecUnitFormatsCheck.java"
                self.assertTrue(check.is_file())
                self.assertIn(f"package {package};", check.read_text())
                gradle = (destination / "java-plugin/build.gradle.kts").read_text()
                docker = (destination / "scripts/docker/Dockerfile").read_text()
                self.assertIn(f'{package}.ExecUnitFormatsCheck', gradle)
                for suffix in ("dotnet_exe", "dotnet_dll", "dotnet_dll_method"):
                    self.assertIn(f"{executable}.{suffix}", docker)
                    self.assertIn(f"{executable}.{suffix}", gradle)
                    self.assertIn(f"{kind}-{slug}.{suffix}", gradle)
                for suffix in ("dotnet_exe", "dotnet_dll"):
                    self.assertIn(f'/{kind}-{slug}.{suffix}', check.read_text())
                self.assertIn('for format in shellcode dotnet-exe dotnet-dll', docker)

    def test_windows_native_support_survives_scaffolding(self) -> None:
        for kind in ("command", "listener"):
            with self.subTest(kind=kind):
                destination, slug = scaffold(kind, "Native Copy", str(self.output_root / kind))
                artifact = f"{kind}-{slug}"
                native = destination / "exec-code/win-native"
                self.assertTrue((native / artifact / "Main.cpp").is_file())
                self.assertIn(f"units=({artifact})", (native / "build_windows.sh").read_text())
                self.assertEqual((native / "exports.def").read_text().split(), ["EXPORTS", "start"])
                reference_utils = REPO_ROOT / "templates" / kind / "exec-code/win-native/exec-unit-utils"
                for source in reference_utils.iterdir():
                    if source.suffix in {".cpp", ".h", ".tpp", ".json"}:
                        self.assertEqual(source.read_bytes(), (native / "exec-unit-utils" / source.name).read_bytes())
                self.assertFalse((native / "common/WinPipe.h").exists())
                if kind == "command":
                    self.assertFalse((native / "common/CommandRuntime.h").exists())
                    compatibility = REPO_ROOT / "templates/command/exec-code/win-native/compat/mingw"
                    for header in compatibility.glob("*.h"):
                        self.assertEqual(header.read_bytes(), (native / "compat/mingw" / header.name).read_bytes())
                self.assertTrue((destination / "scripts/verify_windows_native.py").is_file())
                self.assertIn("windows-native-artifacts", (destination / "scripts/docker/Dockerfile").read_text())
                for suffix in ("native32_dll", "native64_dll"):
                    self.assertIn(f"{artifact}.{suffix}", (destination / "java-plugin/build.gradle.kts").read_text())
                    self.assertIn(f"{artifact}.{suffix}", (destination / "Makefile").read_text())
                    main = next((destination / "java-plugin/src/main/java").rglob(f"NativeCopy{kind.capitalize()}.java"))
                    self.assertIn(f"/{artifact}.{suffix}", main.read_text())


if __name__ == "__main__":
    unittest.main()
