#!/usr/bin/env python3
"""Copy and name a command or listener plugin template.

The repository skills call this script so both agent clients apply the same
project, source, resource, and build-file renames.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import unicodedata
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE_ROOT = REPO_ROOT / "workspace"
IGNORED_DIRECTORIES = {".git", ".gradle", ".vs", "bin", "build", "obj", "__pycache__"}
IGNORED_SUFFIXES = {".class", ".log", ".native64_so", ".pdb", ".pyc", ".shellcode"}
TEXT_SUFFIXES = {".config", ".cpp", ".cs", ".csproj", ".h", ".java", ".kt", ".kts", ".md", ".sh", ".sln"}
TEXT_NAMES = {".dockerignore", ".gitattributes", ".gitignore", "Dockerfile", "Makefile"}
# Keywords and literals cannot be Java package components. Restricted identifiers
# such as `record` remain legal here; generated class names also include a suffix.
JAVA_RESERVED_WORDS = frozenset("""
    abstract assert boolean break byte case catch char class const continue
    default do double else enum extends final finally float for goto if
    implements import instanceof int interface long native new package private
    protected public return short static strictfp super switch synchronized this
    throw throws transient try void volatile while true false null _
""".split())


def ignored(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in IGNORED_DIRECTORIES or Path(name).suffix.lower() in IGNORED_SUFFIXES
    }


def name_parts(value: str) -> list[str]:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    ascii_name = unicodedata.normalize("NFKD", separated).encode("ascii", "ignore").decode()
    parts = re.findall(r"[A-Za-z0-9]+", ascii_name)
    if not parts:
        raise ValueError("Name must contain at least one ASCII letter or digit")
    return [part.lower() for part in parts]


def java_package_part(slug: str) -> str:
    component = slug.replace("-", "_")
    if component[0].isdigit():
        component = "n_" + component
    if component in JAVA_RESERVED_WORDS:
        component = "plugin_" + component
    return component


def replacements(kind: str, slug: str, words: list[str]) -> dict[str, str]:
    title = kind.capitalize()
    pascal = "".join(word.capitalize() for word in words)
    if pascal[0].isdigit():
        pascal = "N" + pascal
    base_class = pascal if pascal.lower().endswith(kind) else pascal + title
    display = " ".join(word.capitalize() for word in words)
    base_display = display if words[-1] == kind else display + " " + title
    package_part = java_package_part(slug)
    package = f"com.example.tuoni.{kind}.{package_part}"
    artifact = f"{kind}-{slug}"
    project = f"{kind}-plugin-{slug}"
    executable = f"{artifact}-execunit"

    changes = {
        f"com/example/tuoni/{kind}/": f"com/example/tuoni/{kind}/{package_part}/",
        f"com.example.tuoni.{kind}": package,
        f'group = "com.example.tuoni"': f'group = "{package}"',
        f"example.{kind}.template": f"example.{kind}.{package_part}",
        f"{title}ExecUnitTemplate": f"{base_class}ExecUnit",
        f"Template{title}Template": f"{base_class}Template",
        f"Template{title}Plugin": f"{base_class}Plugin",
        "TemplateConfigurationSchema": f"{base_class}ConfigurationSchema",
        f"Template{title}": base_class,
        f"{kind}-execunit-template": executable,
        f"{kind}-execunit": executable,
        f"{kind}-plugin-template": project,
        f"{kind}-linux.native64_so": f"{artifact}-linux.native64_so",
        f"{kind}.shellcode": f"{artifact}.shellcode",
        f"exec-code/linux/{kind}/Main.cpp": f"exec-code/linux/{artifact}/Main.cpp",
        f"${{script_dir}}/{kind}/Main.cpp": f"${{script_dir}}/{artifact}/Main.cpp",
        f"template-{kind}": slug,
        f"{title} Plugin Template": f"{base_display} Plugin",
        f"Unimplemented {kind} plugin skeleton": f"Unimplemented {base_display.lower()} plugin skeleton",
        f"# {title} plugin skeleton": f"# {base_display} plugin skeleton",
        "Start with the [shared setup and build instructions](../README.md). This folder": "This folder",
    }
    return changes


def rewrite_text_files(root: Path, changes: dict[str, str]) -> None:
    # Match the longest original token, then substitute once. Replacement values
    # may themselves contain template tokens (for example MyTemplateCommand).
    pattern = re.compile("|".join(re.escape(key) for key in sorted(changes, key=len, reverse=True)))
    for path in root.rglob("*"):
        if not path.is_file() or (path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES and "META-INF" not in path.parts):
            continue
        data = path.read_bytes()
        text = data.decode("utf-8")
        updated = pattern.sub(lambda match: changes[match.group(0)], text)
        if updated != text:
            path.write_bytes(updated.encode("utf-8"))


def rename_sources(root: Path, kind: str, changes: dict[str, str], slug: str) -> None:
    title = kind.capitalize()
    package_part = java_package_part(slug)
    source_dir = root / "java-plugin" / "src" / "main" / "java" / "com" / "example" / "tuoni" / kind
    package_dir = source_dir / package_part
    package_dir.mkdir()
    for source in list(source_dir.iterdir()):
        if source != package_dir:
            source.rename(package_dir / source.name)
    for old_class in (f"Template{title}Template", f"Template{title}Plugin", "TemplateConfigurationSchema", f"Template{title}"):
        old_file = package_dir / f"{old_class}.java"
        if old_file.exists():
            old_file.rename(package_dir / f"{changes[old_class]}.java")

    win_dir = root / "exec-code" / "win"
    (win_dir / f"{kind}-execunit.sln").rename(win_dir / f"{changes[f'{kind}-execunit']}.sln")
    (win_dir / f"{kind}-execunit.csproj").rename(win_dir / f"{changes[f'{kind}-execunit']}.csproj")
    linux_dir = root / "exec-code" / "linux"
    (linux_dir / kind).rename(linux_dir / f"{kind}-{slug}")


def scaffold(kind: str, name: str | None, folder: str | None) -> tuple[Path, str]:
    if name is None and folder is not None:
        name = Path(folder).name
        name = re.sub(rf"^{kind}[-_]", "", name, flags=re.IGNORECASE)
    if not name:
        name = f"new-{kind}"
    words = name_parts(name)
    slug = "-".join(words)
    source = REPO_ROOT / "templates" / kind
    if not source.is_dir():
        raise FileNotFoundError(f"Missing {kind} template: {source}")

    destination = Path(folder) if folder is not None else DEFAULT_WORKSPACE_ROOT / f"{kind}s" / slug
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    if destination.is_relative_to(source.resolve()):
        raise ValueError("Destination cannot be inside the source template")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f".{destination.name}-", dir=destination.parent) as temporary:
        working_copy = Path(temporary) / destination.name
        shutil.copytree(source, working_copy, ignore=ignored)
        changes = replacements(kind, slug, words)
        project = working_copy / "exec-code" / "win" / f"{kind}-execunit.csproj"
        match = re.search(r"<ProjectGuid>(\{[0-9A-Fa-f-]+\})</ProjectGuid>", project.read_text(encoding="utf-8"))
        if match is None:
            raise ValueError(f"Missing project GUID in {project}")
        changes[match.group(1)] = "{" + str(uuid.uuid4()).upper() + "}"
        rewrite_text_files(working_copy, changes)
        rename_sources(working_copy, kind, changes, slug)
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        working_copy.rename(destination)
    return destination, slug


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("command", "listener"))
    parser.add_argument("--name", help="Plugin name; words are normalized for identifiers")
    parser.add_argument(
        "--folder",
        help=(
            "Exact destination directory; relative paths use the current working directory. "
            "Defaults to this repository's workspace/{commands,listeners}/<normalized-name>. "
            "The destination must not already exist."
        ),
    )
    args = parser.parse_args()
    try:
        destination, slug = scaffold(args.kind, args.name, args.folder)
    except (FileExistsError, FileNotFoundError, OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    print(f"Created {args.kind} '{slug}' at {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
