"""Integration checks for the repository plugin scaffolder."""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path

from scaffold_plugin import REPO_ROOT, scaffold


class ScaffoldPluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".scaffold-check-", dir=REPO_ROOT)
        self.output_root = Path(self.temporary.name).resolve()
        self.assertTrue(self.output_root.is_relative_to(REPO_ROOT))

    def tearDown(self) -> None:
        self.assertTrue(self.output_root.is_relative_to(REPO_ROOT))
        self.temporary.cleanup()

    def test_named_command_in_default_folder(self) -> None:
        original_cwd = Path.cwd()
        try:
            os.chdir(self.output_root)
            destination, slug = scaffold("command", "Port Scan", None)
        finally:
            os.chdir(original_cwd)
        self.assertEqual(slug, "port-scan")
        self.assertEqual(destination, self.output_root / "command_port-scan")

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
        original_cwd = Path.cwd()
        try:
            os.chdir(self.output_root)
            destination, slug = scaffold("command", None, None)
        finally:
            os.chdir(original_cwd)
        self.assertEqual(slug, "new-command")
        self.assertEqual(destination, self.output_root / "command_new-command")
        self.assertTrue(
            (destination / "java-plugin/src/main/java/com/example/tuoni/command/new_command/NewCommand.java").is_file()
        )

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
        for href in re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown.read_text(encoding="utf-8")):
            href = href.strip("<>")
            if "://" in href or href.startswith("#"):
                continue
            target = (markdown.parent / href.split("#", 1)[0]).resolve()
            self.assertTrue(target.is_relative_to(boundary), (markdown, href))
            self.assertTrue(target.is_file(), (markdown, href))

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
                for suffix in ("conf", "logic", "output"):
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


if __name__ == "__main__":
    unittest.main()
