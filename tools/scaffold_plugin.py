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
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE_ROOT = REPO_ROOT / "workspace"
IGNORED_DIRECTORIES = {".git", ".gradle", ".vs", "bin", "build", "obj", "__pycache__"}
IGNORED_SUFFIXES = {".class", ".log", ".native32_dll", ".native64_dll", ".native64_so", ".pdb", ".pyc", ".shellcode"}
TEXT_SUFFIXES = {".config", ".cpp", ".cs", ".csproj", ".h", ".java", ".kt", ".kts", ".md", ".sh", ".sln", ".targets"}
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
EXECUNITS = ("shellcode-native", "dotnet-dll", "dotnet-exe", "native-lib")
OPERATING_SYSTEMS = ("windows", "linux")
AVAILABLE_FORMATS = {
    "windows": frozenset(EXECUNITS),
    "linux": frozenset(("native-lib",)),
}
JAVA_EXECUNITS = {
    "shellcode-native": "SHELLCODE_NATIVE",
    "dotnet-dll": "DOTNET_DLL",
    "dotnet-exe": "DOTNET_EXE",
    "native-lib": "NATIVE_LIB",
}


def ignored(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in IGNORED_DIRECTORIES or Path(name).suffix.lower() in IGNORED_SUFFIXES
    }


def parse_selection(value: Optional[str], choices: tuple[str, ...], option: str) -> set[str]:
    if value is None:
        return set(choices)
    items = [item.lower().replace("_", "-") for item in re.split(r"[\s,]+", value.strip()) if item]
    if not items:
        raise ValueError(f"{option} cannot be empty; choose from: {', '.join(choices)}")
    unknown = set(items) - set(choices)
    if unknown:
        raise ValueError(f"Unsupported {option}: {', '.join(sorted(unknown))}; choose from: {', '.join(choices)}")
    return set(items)


def support_matrix(execunits: Optional[str], oses: Optional[str]) -> dict[str, set[str]]:
    formats = parse_selection(execunits, EXECUNITS, "execunits")
    systems = parse_selection(oses, OPERATING_SYSTEMS, "os")
    selected = {
        os_name: formats & AVAILABLE_FORMATS[os_name]
        for os_name in OPERATING_SYSTEMS if os_name in systems
    }
    if oses is not None:
        missing = [os_name for os_name, supported in selected.items() if not supported]
        if missing:
            raise ValueError(
                f"No selected execunit is available for {', '.join(missing)}; "
                "Linux supports only native-lib"
            )
    return {os_name: supported for os_name, supported in selected.items() if supported}


def java_set(formats: set[str]) -> str:
    return "Set.of(" + ", ".join(
        f"ExecUnitType.{JAVA_EXECUNITS[name]}" for name in EXECUNITS if name in formats
    ) + ")"


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    if content.count(old) != 1:
        raise ValueError(f"Expected one template section in {path}: {old[:70]!r}")
    path.write_text(content.replace(old, new), encoding="utf-8")


def reset_generated_verification(root: Path) -> None:
    """Start a generated copy with its own verification record."""
    agents = root / "AGENTS.md"
    content = agents.read_text(encoding="utf-8")
    content = content.replace(
        "This is the current source-template snapshot. When editing the source template itself, keep this snapshot accurate for a fresh copy; verification of the template repository is not verification of a newly generated plugin.",
        "This is a generated plugin. Its source map and support declarations describe this copy; verification of the source template does not verify this plugin.",
    )
    content, count = re.subn(
        r"<!-- template-verification:start -->.*?<!-- template-verification:end -->",
        "## Generated-plugin verification\n\n"
        "Build, packaging, artifact, and runtime checks have not been run for this "
        "generated copy. Record its own commands, results, artifacts, and unavailable "
        "checks here before claiming verification. Source-template test results "
        "are not inherited.",
        content,
        flags=re.DOTALL,
    )
    if count != 1:
        raise ValueError("Expected one source-template verification section in AGENTS.md")
    agents.write_text(content, encoding="utf-8")


def refresh_generated_context(root: Path, kind: str, slug: str,
                              matrix: dict[str, set[str]]) -> None:
    """Replace template-wide support claims with facts about this generated copy."""
    artifact = f"{kind}-{slug}"
    windows = matrix.get("windows", set())
    linux = matrix.get("linux", set())
    resources = []
    if "shellcode-native" in windows:
        resources.append(f"{artifact}.shellcode")
    if "dotnet-exe" in windows:
        resources.append(f"{artifact}.dotnet_exe")
    if "dotnet-dll" in windows:
        resources.extend((f"{artifact}.dotnet_dll", f"{artifact}.dotnet_dll_method"))
    if "native-lib" in windows:
        resources.extend((f"{artifact}.native32_dll", f"{artifact}.native64_dll"))
    if "native-lib" in linux:
        resources.append(f"{artifact}-linux.native64_so")
    toolchains = ["Java 21"]
    if windows & {"shellcode-native", "dotnet-exe", "dotnet-dll"}:
        toolchains.append(".NET Framework 4.6.2")
    if "native-lib" in windows:
        toolchains.append("C++11/Windows x86/x64 (MinGW)")
    if "native-lib" in linux:
        toolchains.append("C++11/Linux x64")
    agents = root / "AGENTS.md"
    content = agents.read_text(encoding="utf-8")

    def bullet(prefix: str, replacement: str) -> None:
        nonlocal content
        pattern = rf"(?m)^- {re.escape(prefix)}.*$"
        content, count = re.subn(pattern, replacement, content, count=1)
        if count != 1:
            raise ValueError(f"Missing generated context statement: {prefix}")

    bullet("Existing exec-units:",
           "- Selected exec-units: the targets in the generated support table above. "
           "Other template sources remain copied, but are not advertised or built.")
    if kind == "command":
        bullet("Capability checks share", "- Capability checks and artifact generation "
               "accept only the OS, process architectures, and formats in the generated support table.")
    bullet("Both generation methods", "- Exec-unit generation uses the shared "
           "`serializeConfiguration()` encoder and returns a fresh zero-length buffer "
           "at position/limit zero; unsupported combinations are rejected.")
    if "shellcode-native" not in windows:
        content = content.replace("`generateExecUnit`, `generateShellCode`, `parseResult`",
                                  "`generateExecUnit`, `parseResult`")
    bullet("Build targets:", "- Build targets: " + ", ".join(toolchains) +
           ". SDK dependency: `com.shelldot:tuoni-plugin-sdk:0.15.0` as `compileOnly`.")
    bullet("Execution resource names:", "- Packaged execution resources: " +
           ", ".join(f"`{name}`" for name in resources) +
           f". Local distributable: `java-plugin/build/libs/{kind}-plugin-{slug}-0.0.1.jar`; "
           f"Docker export: `build/{kind}-plugin-{slug}-0.0.1.jar`.")
    agents.write_text(content, encoding="utf-8")

    readme = root / "README.md"
    content = readme.read_text(encoding="utf-8")
    start = content.index("The Java class implements `ExecUnit")
    end = content.index("## Build", start)
    interface = "`ExecUnitCommand`" if kind == "command" else "`ExecUnitListener`"
    if "shellcode-native" in windows:
        interface += " and `ShellcodeCommand`" if kind == "command" else " and `ShellcodeListener`"
    description = (f"The Java class implements {interface}. It advertises only the "
                   "combinations in the generated support table above. `make build` "
                   "packages the selected execunits and plugin JAR. Other source "
                   "families remain available for later expansion.\n\n")
    if kind == "command":
        description += ("Configuration validation, factory creation, empty-result "
                        "handling, and completion are implemented.\n\n")
    else:
        description += ("Startup and valid `{}` replacement serialization use "
                        "the same empty native payload.\n\n")
    content = content[:start] + description + content[end:]
    start = content.index("## Build\n")
    content = (content[:start] + "## Build\n\n"
               "Use a Linux shell (WSL on Windows), GNU Make, standard Unix file "
               "utilities, and Docker configured for Linux containers. Run "
               "`make build` from this folder. It exports the plugin JAR and the "
               "execution artifacts listed in the generated support table to `build/`. "
               "The Java build checks resource bytes for every selected format.\n\n"
               "`make build-dotnet`, `make build-linux`, and `make build-windows-native` "
               "export a family only when that family is selected; other focused "
               "targets report an error. `make clean` removes exported build outputs. "
               "For direct compiler commands and platform requirements, see "
               "[building.md](docs/building.md) and apply only the selected formats.\n\n"
               "`make install` builds the plugin, copies its JAR into `PLUGIN_DIR` "
               "(default: `/srv/tuoni/plugins/server`), and runs `tuoni restart`. "
               "The standalone [installer](scripts/install/install-plugin.sh) "
               "resolves Tuoni in the current user's PATH and login shell, then "
               "root's login shell through sudo, with `/srv/tuoni/tuoni` as the "
               "standard root fallback. Missing Tuoni fails before copying. "
               "Use `PLUGIN_DIR=/path/to/plugins` or `TUONI=/path/to/tuoni` to "
               "override the destination or executable.\n")
    readme.write_text(content, encoding="utf-8")


def configure_support(root: Path, kind: str, slug: str, matrix: dict[str, set[str]]) -> None:
    """Narrow the generated Java declarations and their artifact selection check."""
    package_part = java_package_part(slug)
    java_root = root / "java-plugin" / "src"
    main_dir = java_root / "main" / "java" / "com" / "example" / "tuoni" / kind / package_part
    # The actual class name can differ from the slug when the name already ends in
    # the plugin kind or starts with a digit. Locate it by its support method.
    matches = [path for path in main_dir.glob("*.java") if "getSupportedExecUnitTypes(" in path.read_text(encoding="utf-8") and not path.stem.endswith("Template")]
    if len(matches) != 1:
        raise ValueError(f"Expected one generated {kind} implementation in {main_dir}")
    main = matches[0]
    windows = matrix.get("windows", set())
    linux = matrix.get("linux", set())
    if kind == "command":
        old = """    return switch (metadata.os()) {
      case WINDOWS -> metadata.processArch() == Architecture.X86
              || metadata.processArch() == Architecture.X64
          ? Set.of(ExecUnitType.SHELLCODE_NATIVE, ExecUnitType.DOTNET_DLL,
            ExecUnitType.DOTNET_EXE, ExecUnitType.NATIVE_LIB)
          : Set.of();
      case LINUX -> metadata.processArch() == Architecture.X64
          ? Set.of(ExecUnitType.NATIVE_LIB) : Set.of();
      default -> Set.of();
    };"""
        new = f"""    return switch (metadata.os()) {{
      case WINDOWS -> metadata.processArch() == Architecture.X86
              || metadata.processArch() == Architecture.X64
          ? {java_set(windows)} : Set.of();
      case LINUX -> metadata.processArch() == Architecture.X64
          ? {java_set(linux)} : Set.of();
      default -> Set.of();
    }};"""
        replace_once(main, old, new)
        templates = [path for path in main_dir.glob("*Template.java") if "getSupportedExecUnitTypes(" in path.read_text(encoding="utf-8")]
        if len(templates) != 1:
            raise ValueError(f"Expected one generated command template in {main_dir}")
        replace_once(
            templates[0],
            """    return Set.of(ExecUnitType.SHELLCODE_NATIVE, ExecUnitType.DOTNET_DLL,
        ExecUnitType.DOTNET_EXE, ExecUnitType.NATIVE_LIB);""",
            "    return " + java_set(windows | linux) + ";",
        )
    else:
        old = """    return Set.of(
        PayloadType.of(OperatingSystem.WINDOWS, Architecture.X64),
        PayloadType.of(OperatingSystem.WINDOWS, Architecture.X86),
        LINUX_X64);"""
        payloads = []
        if windows:
            payloads.extend((
                "PayloadType.of(OperatingSystem.WINDOWS, Architecture.X64)",
                "PayloadType.of(OperatingSystem.WINDOWS, Architecture.X86)",
            ))
        if linux:
            payloads.append("LINUX_X64")
        replace_once(main, old, "    return Set.of(\n        " + ",\n        ".join(payloads) + ");")
        replace_once(main, """    if (LINUX_X64.equals(payloadType)) {
      return Set.of(ExecUnitType.NATIVE_LIB);
    }
    return getSupportedPayloadTypes().contains(payloadType)
        ? Set.of(ExecUnitType.SHELLCODE_NATIVE, ExecUnitType.DOTNET_DLL,
            ExecUnitType.DOTNET_EXE, ExecUnitType.NATIVE_LIB)
        : Set.of();""", f"""    if (LINUX_X64.equals(payloadType)) {{
      return {java_set(linux)};
    }}
    return getSupportedPayloadTypes().contains(payloadType)
        ? {java_set(windows)} : Set.of();""")

    if "shellcode-native" not in windows:
        content = main.read_text(encoding="utf-8")
        interface = "ShellcodeCommand" if kind == "command" else "ShellcodeListener"
        content = content.replace(", " + interface + " {", " {")
        content = content.replace(f"import com.shelldot.tuoni.plugin.sdk.{kind}.{interface};\n", "")
        content = content.replace("import com.shelldot.tuoni.plugin.sdk.common.ShellCodeWithConf;\n", "")
        start = content.index("  @Override\n  public ShellCodeWithConf generateShellCode(")
        end_marker = "  private ByteBuffer serializeConfiguration()" if kind == "command" else "  @Override\n  public ByteBuffer serializeUpdatedConfiguration("
        end = content.index(end_marker, start)
        main.write_text(content[:start] + content[end:], encoding="utf-8")

    check = next((java_root / "test" / "java" / "com" / "example" / "tuoni" / kind / package_part).glob("ExecUnitFormatsCheck.java"))
    content = check.read_text(encoding="utf-8")
    start = content.index("          Set<ExecUnitType> expected =")
    end = content.index("          require(supported(os, arch)", start)
    expected = f"""          Set<ExecUnitType> expected = os == OperatingSystem.WINDOWS
                  && (arch == Architecture.X86 || arch == Architecture.X64)
              ? {java_set(windows)}
              : os == OperatingSystem.LINUX && arch == Architecture.X64
                  ? {java_set(linux)} : Set.of();
"""
    check.write_text(content[:start] + expected + content[end:], encoding="utf-8")

    rows = "\n".join(
        f"| {os_name.capitalize()} | {'x86, x64' if os_name == 'windows' else 'x64'} | "
        + ", ".join(f"`{JAVA_EXECUNITS[name]}`" for name in EXECUNITS if name in matrix[os_name]) + " |"
        for os_name in OPERATING_SYSTEMS if os_name in matrix
    )
    note = ("## Generated support\n\n"
            "This plugin advertises and generates execution units for these targets:\n\n"
            "| OS | Process architectures | Execunit formats |\n"
            "| --- | --- | --- |\n" + rows + "\n\n"
            "The template's other source files remain available for later expansion. "
            "`make build` compiles and packages only the selected formats; the Java "
            "support declarations reject unselected targets.\n\n")
    for relative in ("AGENTS.md", "README.md", "docs/support-scope.md"):
        path = root / relative
        content = path.read_text(encoding="utf-8")
        first_line, remainder = content.split("\n", 1)
        path.write_text(first_line + "\n\n" + note + remainder.lstrip("\n"), encoding="utf-8")

    refresh_generated_context(root, kind, slug, matrix)
    from scaffold_build import configure_selected_build
    configure_selected_build(root, kind, slug, package_part, matrix)


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


def imported_java_names(kind: str) -> set[str]:
    source_root = REPO_ROOT / "templates" / kind / "java-plugin/src/main/java"
    return {
        match.group(1)
        for source in source_root.rglob("*.java")
        for match in re.finditer(
            r"^import(?: static)? [\w.]+\.([A-Za-z_$][\w$]*);",
            source.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    }


def replacements(kind: str, slug: str, words: list[str]) -> dict[str, str]:
    title = kind.capitalize()
    pascal = "".join(word.capitalize() for word in words)
    if pascal[0].isdigit():
        pascal = "N" + pascal
    base_class = pascal if pascal.lower().endswith(kind) else pascal + title
    imported = imported_java_names(kind)
    while {base_class, base_class + "Template", base_class + "Plugin",
           base_class + "ConfigurationSchema"} & imported:
        base_class = "Custom" + base_class
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
        f"{kind}.dotnet_exe": f"{artifact}.dotnet_exe",
        f"{kind}.dotnet_dll": f"{artifact}.dotnet_dll",
        f"{kind}.native32_dll": f"{artifact}.native32_dll",
        f"{kind}.native64_dll": f"{artifact}.native64_dll",
        f"units=({kind})": f"units=({artifact})",
        f"exec-code/win-native/{kind}/Main.cpp": f"exec-code/win-native/{artifact}/Main.cpp",
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
    for source_set in ("main", "test"):
        source_dir = root / "java-plugin" / "src" / source_set / "java" / "com" / "example" / "tuoni" / kind
        if not source_dir.is_dir():
            continue
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
    (root / "exec-code" / "win-native" / kind).rename(root / "exec-code" / "win-native" / f"{kind}-{slug}")


def scaffold(kind: str, name: Optional[str], folder: Optional[str],
             execunits: Optional[str] = None, oses: Optional[str] = None) -> tuple[Path, str]:
    matrix = support_matrix(execunits, oses)
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
        reset_generated_verification(working_copy)
        if execunits is not None or oses is not None:
            configure_support(working_copy, kind, slug, matrix)
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        working_copy.rename(destination)
    return destination, slug


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("command", "listener"))
    parser.add_argument("--name", help="Plugin name; words are normalized for identifiers")
    parser.add_argument("--execunits", help="Comma- or space-separated formats: " + ", ".join(EXECUNITS))
    parser.add_argument("--os", help="Comma- or space-separated operating systems: " + ", ".join(OPERATING_SYSTEMS))
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
        destination, slug = scaffold(args.kind, args.name, args.folder, args.execunits, args.os)
    except (FileExistsError, FileNotFoundError, OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    print(f"Created {args.kind} '{slug}' at {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
