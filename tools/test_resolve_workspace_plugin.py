"""Behavior checks for safe, read-only dispatch to generated plugin skills."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from resolve_workspace_plugin import ACTIONS, REPO_ROOT, resolve_workspace_plugin
from scaffold_plugin import scaffold


class WorkspacePluginResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix=".resolver-check-", dir=REPO_ROOT)
        self.scratch = Path(self.temporary.name).resolve()
        self.assertTrue(self.scratch.is_relative_to(REPO_ROOT))
        self.root = self.scratch / "repository"
        self.root.mkdir()

    def tearDown(self) -> None:
        self.assertTrue(self.scratch.is_relative_to(REPO_ROOT))
        self.temporary.cleanup()

    def plugin(self, name: str = "example", kind: str = "command", clients: tuple = ("agents", "claude")) -> Path:
        plugin = self.root / "workspace" / f"{kind}s" / name
        (plugin / "exec-code").mkdir(parents=True)
        service = plugin / "java-plugin/src/main/resources/META-INF/services" / (
            f"com.shelldot.tuoni.plugin.sdk.{kind}.{kind.capitalize()}Plugin"
        )
        service.parent.mkdir(parents=True)
        service.write_text(f"com.example.{kind}.ExamplePlugin\n", encoding="utf-8")
        for client in clients:
            for action in ACTIONS:
                skill = plugin / f".{client}/skills/{kind}-{action}/SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text(f"---\nname: {kind}-{action}\n---\nLocal implementation skill.\n", encoding="utf-8")
        return plugin

    def resolve(self, target: str | None = None, kind: str = "command", action: str = "logic", client: str = "agents", cwd: Path | None = None) -> dict:
        return resolve_workspace_plugin(kind, action, target, client, repo_root=self.root, cwd=cwd or self.root)

    def snapshot(self) -> dict:
        return {str(path.relative_to(self.scratch)): path.read_bytes() if path.is_file() else None for path in self.scratch.rglob("*")}

    def test_missing_and_empty_workspace_are_not_created_or_selected(self) -> None:
        before = self.snapshot()
        self.assertEqual(self.resolve()["status"], "no_plugins")
        self.assertEqual(before, self.snapshot())
        (self.root / "workspace/commands").mkdir(parents=True)
        self.assertEqual(self.resolve()["candidates"], [])
        self.assertEqual(self.resolve()["status"], "no_plugins")

    def test_single_candidate_still_requires_target(self) -> None:
        plugin = self.plugin()
        result = self.resolve()
        self.assertEqual(result["status"], "needs_target")
        self.assertNotIn("path", result)
        self.assertEqual([item["path"] for item in result["candidates"]], [str(plugin)])

    def test_multiple_candidates_are_sorted_without_selection(self) -> None:
        self.plugin("zebra")
        self.plugin("alpha")
        result = self.resolve()
        self.assertEqual(result["status"], "needs_target")
        self.assertEqual([item["name"] for item in result["candidates"]], ["alpha", "zebra"])

    def test_exact_folder_name_precedes_normalized_display_name(self) -> None:
        exact = self.plugin("Port Scan")
        normalized = self.plugin("port-scan")
        self.assertEqual(self.resolve("Port Scan")["path"], str(exact))
        self.assertEqual(self.resolve("PortScan")["path"], str(normalized))

    def test_all_local_actions_and_both_plugin_kinds(self) -> None:
        for kind in ("command", "listener"):
            plugin = self.plugin(kind=kind)
            for action in ACTIONS:
                with self.subTest(kind=kind, action=action):
                    result = self.resolve("example", kind, action)
                    self.assertEqual(result["status"], "ready")
                    self.assertEqual(result["path"], str(plugin))
                    self.assertEqual(result["skill_path"], str(plugin / f".agents/skills/{kind}-{action}/SKILL.md"))

    def test_real_scaffolds_route_to_their_copied_skills(self) -> None:
        # Keep the nested temporary scaffold below legacy Windows path limits.
        for kind in ("command", "listener"):
            destination, _ = scaffold(
                kind, "Demo", str(self.root / "workspace" / f"{kind}s" / "demo")
            )
            for action in ACTIONS:
                for client in ("agents", "claude"):
                    with self.subTest(kind=kind, action=action, client=client):
                        result = self.resolve("Demo", kind, action, client)
                        self.assertEqual(result["status"], "ready")
                        self.assertEqual(result["path"], str(destination))
                        local = destination / f".{client}/skills/{kind}-{action}/SKILL.md"
                        self.assertEqual(result["skill_path"], str(local))
                        self.assertIn(f"name: {kind}-{action}", local.read_text(encoding="utf-8"))

    def test_absolute_and_cwd_relative_plugin_paths(self) -> None:
        plugin = self.plugin()
        self.assertEqual(self.resolve(str(plugin))["path"], str(plugin))
        self.assertEqual(self.resolve("./example", cwd=plugin.parent)["path"], str(plugin))

    def test_repo_relative_workspace_path_from_other_directory(self) -> None:
        plugin = self.plugin()
        elsewhere = self.scratch / "elsewhere"
        elsewhere.mkdir()
        self.assertEqual(self.resolve("workspace/commands/example", cwd=elsewhere)["path"], str(plugin))

    def test_conflicting_cwd_and_repo_relative_paths_are_ambiguous(self) -> None:
        self.plugin()
        elsewhere = self.scratch / "elsewhere"
        (elsewhere / "workspace/commands/example").mkdir(parents=True)
        result = self.resolve("workspace/commands/example", cwd=elsewhere)
        self.assertEqual(result["status"], "invalid_target")
        self.assertEqual(result["reason"], "ambiguous_path")

    def test_wrong_kind_never_selects_another_plugin(self) -> None:
        self.plugin()
        listener = self.plugin(kind="listener")
        result = self.resolve(str(listener))
        self.assertEqual(result["status"], "invalid_target")
        self.assertNotIn("path", result)
        self.assertEqual(len(result["candidates"]), 1)

    def test_missing_explicit_target_never_falls_back(self) -> None:
        self.plugin()
        result = self.resolve("missing")
        self.assertEqual(result["status"], "invalid_target")
        self.assertNotIn("path", result)
        self.assertEqual(len(result["candidates"]), 1)

    def test_unrelated_and_incomplete_folders_are_excluded(self) -> None:
        category = self.root / "workspace/commands"
        (category / "notes").mkdir(parents=True)
        (category / "incomplete/java-plugin").mkdir(parents=True)
        (category / "incomplete/exec-code").mkdir()
        (category / "readme.txt").write_text("unrelated", encoding="utf-8")
        self.assertEqual(self.resolve()["status"], "no_plugins")
        self.assertEqual(self.resolve("incomplete")["status"], "invalid_target")

    def test_wrong_or_empty_service_descriptor_is_rejected(self) -> None:
        plugin = self.plugin()
        service = next((plugin / "java-plugin/src/main/resources/META-INF/services").iterdir())
        service.write_text("# no provider\n", encoding="utf-8")
        self.assertEqual(self.resolve("example")["status"], "invalid_target")
        service.rename(service.with_name("com.shelldot.tuoni.plugin.sdk.listener.ListenerPlugin"))
        self.assertEqual(self.resolve("example")["status"], "invalid_target")

    def test_missing_local_skill_cannot_use_root_or_template_skills(self) -> None:
        self.plugin(clients=())
        for folder in (self.root, self.root / "templates/command"):
            skill = folder / ".agents/skills/command-logic/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("Must not be selected", encoding="utf-8")
        result = self.resolve("example")
        self.assertEqual(result["reason"], "invalid_local_skill")
        self.assertEqual(result["candidates"], [])

    def test_client_preference_and_missing_tree_fallback(self) -> None:
        self.plugin("both")
        self.plugin("claude-only", clients=("claude",))
        self.plugin("agents-only", clients=("agents",))
        self.assertEqual(self.resolve("both", client="claude")["client"], "claude")
        self.assertEqual(self.resolve("claude-only")["client"], "claude")
        self.assertEqual(self.resolve("agents-only", client="claude")["client"], "agents")

    def test_external_nested_and_traversal_paths_are_rejected(self) -> None:
        plugin = self.plugin()
        outside = self.scratch / "outside"
        outside.mkdir()
        for target in (str(outside), str(plugin / "exec-code"), "../commands/example", "workspace/commands/../commands/example", "..", "."):
            with self.subTest(target=target):
                self.assertEqual(self.resolve(target)["status"], "invalid_target")

    def symlink(self, link: Path, target: Path, directory: bool = False) -> None:
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"Symlink creation unavailable: {error}")

    def test_plugin_symlink_cannot_escape_workspace(self) -> None:
        self.plugin()
        outside = self.scratch / "outside"
        outside.mkdir()
        alias = self.root / "workspace/commands/alias"
        self.symlink(alias, outside, directory=True)
        self.assertEqual(self.resolve("alias")["status"], "invalid_target")
        self.assertEqual([item["name"] for item in self.resolve()["candidates"]], ["example"])

    def test_local_skill_symlink_cannot_escape_to_root(self) -> None:
        plugin = self.plugin(clients=("claude",))
        root_skill = self.root / ".agents/skills/command-logic/SKILL.md"
        root_skill.parent.mkdir(parents=True)
        root_skill.write_text("Root router", encoding="utf-8")
        local = plugin / ".agents/skills/command-logic/SKILL.md"
        local.parent.mkdir(parents=True)
        self.symlink(local, root_skill)
        result = self.resolve("example")
        self.assertEqual(result["reason"], "invalid_local_skill")
        self.assertNotIn("skill_path", result)

    def test_workspace_symlink_is_rejected(self) -> None:
        outside = self.scratch / "outside"
        (outside / "commands").mkdir(parents=True)
        self.symlink(self.root / "workspace", outside, directory=True)
        self.assertEqual(self.resolve()["status"], "invalid_workspace")

    def test_cli_json_exit_codes_and_read_only_operation(self) -> None:
        self.plugin()
        tool_dir = self.root / "tools"
        tool_dir.mkdir()
        for name in ("resolve_workspace_plugin.py", "scaffold_plugin.py"):
            shutil.copyfile(REPO_ROOT / "tools" / name, tool_dir / name)
        before = self.snapshot()
        for arguments, status, code in (([], "needs_target", 2), (["--target", "example"], "ready", 0), (["--target", "missing"], "invalid_target", 2)):
            with self.subTest(arguments=arguments):
                completed = subprocess.run([sys.executable, str(tool_dir / "resolve_workspace_plugin.py"), "command", "logic", *arguments], cwd=self.scratch, capture_output=True, text=True, check=False)
                self.assertEqual(completed.returncode, code, completed.stderr)
                self.assertEqual(json.loads(completed.stdout)["status"], status)
                self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
