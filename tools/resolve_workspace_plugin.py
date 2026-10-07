#!/usr/bin/env python3
"""Resolve an existing workspace plugin's local skill without modifying files.

Exit 0 and status=ready select exactly one explicit target. All other outcomes
return JSON and exit 2. Without --target, list usable candidates but never select
one. The calling skill, not this script, resolves conversation context.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Importing the shared naming helper must not create a bytecode cache.
sys.dont_write_bytecode = True
from scaffold_plugin import name_parts


REPO_ROOT = Path(__file__).resolve().parents[1]
KINDS = ("command", "listener")
ACTIONS = ("implement", "conf", "logic", "output")
CLIENTS = ("agents", "claude")


def plugin_problem(path: Path, category: Path, kind: str) -> tuple[Path | None, str | None]:
    """Validate the plugin boundary and minimal generated-plugin markers."""
    resolved = path.resolve()
    if resolved.parent != category:
        return None, "Target must resolve to a direct child of the matching workspace folder."
    if not resolved.is_dir():
        return None, "The selected plugin folder does not exist."
    for name in ("java-plugin", "exec-code"):
        directory = resolved / name
        if not directory.is_dir() or not directory.resolve().is_relative_to(resolved):
            return None, f"The selected folder is missing a local {name} directory."
    service = resolved / "java-plugin/src/main/resources/META-INF/services" / (
        f"com.shelldot.tuoni.plugin.sdk.{kind}.{kind.capitalize()}Plugin"
    )
    if not service.is_file() or not service.resolve().is_relative_to(resolved):
        return None, f"The selected folder is missing its local {kind} service descriptor."
    providers = [line.split("#", 1)[0].strip() for line in service.read_text(encoding="utf-8-sig").splitlines()]
    providers = [line for line in providers if line]
    if not providers or any(not re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+", name) for name in providers):
        return None, "The selected plugin service descriptor has no valid Java provider declaration."
    return resolved, None


def local_skill(plugin: Path, kind: str, action: str, client: str) -> tuple[dict | None, str | None]:
    alternate = "claude" if client == "agents" else "agents"
    for selected in (client, alternate):
        skill = plugin / f".{selected}/skills/{kind}-{action}/SKILL.md"
        # A present but invalid preferred skill must not silently select another.
        if skill.exists() or skill.is_symlink():
            resolved = skill.resolve()
            if not resolved.is_relative_to(plugin) or not resolved.is_file():
                return None, "The local skill must be a file contained within the selected plugin."
            return {"name": plugin.name, "path": str(plugin), "skill_path": str(resolved), "client": selected}, None
    return None, f"The selected plugin has no local {kind}-{action}/SKILL.md in either client tree."


def resolve_workspace_plugin(
    kind: str,
    action: str,
    target: str | None = None,
    client: str = "agents",
    *,
    repo_root: Path = REPO_ROOT,
    cwd: Path | None = None,
) -> dict:
    """Return a JSON-compatible result; root is the repository, path the plugin."""
    if kind not in KINDS or action not in ACTIONS or client not in CLIENTS:
        raise ValueError("Unsupported kind, action, or client")
    root = repo_root.resolve()
    working_directory = (cwd or Path.cwd()).resolve()
    workspace = root / "workspace"
    category = workspace / f"{kind}s"
    result = {"root": str(root), "kind": kind, "action": action, "workspace": str(category), "candidates": []}

    def finish(status: str, reason: str, message: str) -> dict:
        return {**result, "status": status, "reason": reason, "message": message}

    try:
        if workspace.resolve() != workspace or category.resolve() != category:
            return finish("invalid_workspace", "workspace_alias", "The workspace and category folders must not redirect to another location.")
        if category.exists() and not category.is_dir():
            return finish("invalid_workspace", "not_directory", "The matching workspace category is not a directory.")
        if category.is_dir():
            seen = set()
            for entry in sorted(category.iterdir(), key=lambda path: path.name.casefold()):
                try:
                    plugin, problem = plugin_problem(entry, category, kind)
                    if problem or plugin in seen:
                        continue
                    candidate, problem = local_skill(plugin, kind, action, client)
                    if not problem:
                        result["candidates"].append(candidate)
                        seen.add(plugin)
                except (OSError, UnicodeError, RuntimeError):
                    # An unrelated or unreadable child is not a usable candidate.
                    continue
        if target is None:
            if result["candidates"]:
                return finish("needs_target", "target_required", "Specify an existing plugin name or path, or use an unambiguous target from prior context. Inventory alone does not select a target.")
            return finish("no_plugins", "no_usable_plugins", f"No existing {kind} plugins with a usable {kind}-{action} skill were found in this workspace category. Create one with {kind}-new first, or repair the intended plugin's local skill.")
        if not target.strip():
            return finish("invalid_target", "empty_target", "The explicit target is empty; specify an existing plugin name or path.")
        supplied = Path(target)
        if ".." in supplied.parts or target.strip() in (".", ".."):
            return finish("invalid_target", "traversal", "Parent-directory traversal cannot select a workspace plugin; provide its name or direct path.")
        is_path = supplied.is_absolute() or "/" in target or "\\" in target or bool(supplied.drive)
        if not is_path:
            selected = category / target
            if not selected.exists() and not selected.is_symlink():
                try:
                    selected = category / "-".join(name_parts(target))
                except ValueError as error:
                    return finish("invalid_target", "invalid_name", str(error))
        elif supplied.is_absolute():
            selected = supplied
        else:
            selected = working_directory / supplied
            if supplied.parts and supplied.parts[0].casefold() == "workspace":
                repo_relative = root / supplied
                if selected.exists() and repo_relative.exists() and selected.resolve() != repo_relative.resolve():
                    return finish("invalid_target", "ambiguous_path", "The relative path identifies different existing folders from the current directory and repository root. Provide an absolute path.")
                if not selected.exists():
                    selected = repo_relative
        plugin, problem = plugin_problem(selected, category, kind)
        if problem:
            return finish("invalid_target", "invalid_plugin", problem)
        candidate, problem = local_skill(plugin, kind, action, client)
        if problem:
            return finish("invalid_target", "invalid_local_skill", problem)
        return {**result, **candidate, "status": "ready", "reason": "explicit_target", "message": "Read the selected plugin's context and local skill, then apply the user's request there."}
    except (OSError, UnicodeError, RuntimeError) as error:
        return finish("unavailable", "filesystem_error", f"Cannot inspect the requested workspace plugin: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=KINDS)
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("--target", help="Existing workspace plugin folder name, display name, or path")
    parser.add_argument("--client", choices=CLIENTS, default="agents")
    arguments = parser.parse_args()
    result = resolve_workspace_plugin(arguments.kind, arguments.action, arguments.target, arguments.client)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
