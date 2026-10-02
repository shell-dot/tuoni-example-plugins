#!/usr/bin/env python3
"""Inspect a distributable JAR without loading Java or executing plugin code.

These archive checks do not prove initialization, classloader compatibility,
transitive dependency completeness, valid bytecode, or native runtime behavior.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import sys
import unicodedata
from zipfile import BadZipFile, ZipFile


PLUGIN_ATTRIBUTES = (
    "Plugin-Id", "Plugin-Version", "Plugin-Provider", "Plugin-Name",
    "Plugin-Description", "Plugin-Url",
)
JACKSON3_CLASSES = (
    "tools.jackson.databind.json.JsonMapper",
    "tools.jackson.core.JsonParser",
    "tools.jackson.core.JacksonException",
    "com.fasterxml.jackson.annotation.JsonProperty",
)
SDK_PREFIX = "com/shelldot/tuoni/plugin/sdk/"


def _identifier_start(character: str) -> bool:
    return unicodedata.category(character) in {"Lu", "Ll", "Lt", "Lm", "Lo", "Nl", "Sc", "Pc"}


def _identifier_part(character: str) -> bool:
    code = ord(character)
    return (
        _identifier_start(character)
        or unicodedata.category(character) in {"Mn", "Mc", "Nd", "Cf"}
        or code <= 8 or 14 <= code <= 27 or 127 <= code <= 159
    )


def _class_entry(name: str) -> str:
    if name.endswith(".class"):
        name = name[:-6].replace("/", ".")
    parts = name.split(".")
    if not all(part and _identifier_start(part[0]) and all(map(_identifier_part, part[1:])) for part in parts):
        raise ValueError(f"Invalid Java binary class name: {name!r}")
    return name.replace(".", "/") + ".class"


def _manifest_attributes(data: bytes) -> dict[str, str]:
    # Fold bytes before UTF-8 decoding: a manifest line can split a code point.
    logical_lines: list[bytes] = []
    for line in data.splitlines():
        if not line:
            break  # Per-entry sections cannot supply the main plugin identity.
        if line.startswith(b" "):
            if not logical_lines:
                raise ValueError("Manifest starts with an orphan continuation line")
            logical_lines[-1] += line[1:]
        else:
            logical_lines.append(line)
    attributes: dict[str, str] = {}
    for line in logical_lines:
        key, separator, value = line.partition(b": ")
        if not separator or not re.fullmatch(rb"[A-Za-z0-9_-]+", key):
            raise ValueError(f"Invalid main manifest attribute: {line!r}")
        name = key.decode("ascii").lower()
        if name in attributes:
            raise ValueError(f"Duplicate main manifest attribute: {name}")
        attributes[name] = value.decode("utf-8")
    return attributes


def inspect_archive(
    archive_path: str | Path,
    kind: str,
    *,
    jackson3: bool = False,
    required_classes: tuple[str, ...] | list[str] = (),
) -> list[str]:
    """Return actionable errors; an empty list means only archive checks passed."""
    if kind not in {"command", "listener"}:
        return ["Plugin kind must be command or listener"]
    service = f"META-INF/services/com.shelldot.tuoni.plugin.sdk.{kind}.{kind.title()}Plugin"
    errors: list[str] = []
    try:
        with ZipFile(archive_path) as jar:
            names = Counter(jar.namelist())
            for name, count in sorted(names.items()):
                if count > 1 and (name.endswith(".class") or name in {service, "META-INF/MANIFEST.MF"}):
                    errors.append(f"Ambiguous duplicate JAR entry: {name}")
                class_path = re.sub(r"^META-INF/versions/[0-9]+/", "", name)
                if class_path.startswith(SDK_PREFIX) and name.endswith(".class"):
                    errors.append(f"Bundled SDK class: {name}; keep the Tuoni SDK compileOnly")

            def require_class(name: str, source: str) -> None:
                try:
                    entry = _class_entry(name)
                except ValueError as error:
                    errors.append(f"{source}: {error}")
                    return
                if entry not in names:
                    errors.append(
                        f"{source}: missing classpath-root class {entry}; package it in the distributable JAR. "
                        "A class inside a nested dependency JAR does not satisfy this check"
                    )
                elif not jar.read(entry):
                    errors.append(f"{source}: empty class entry {entry}")

            if "META-INF/MANIFEST.MF" not in names:
                errors.append("Missing META-INF/MANIFEST.MF with plugin metadata")
            else:
                try:
                    manifest = _manifest_attributes(jar.read("META-INF/MANIFEST.MF"))
                    for attribute in PLUGIN_ATTRIBUTES:
                        if not manifest.get(attribute.lower(), "").strip():
                            errors.append(f"Missing or empty main manifest attribute {attribute}")
                except (UnicodeError, ValueError) as error:
                    errors.append(f"Invalid META-INF/MANIFEST.MF: {error}")

            if service not in names:
                errors.append(f"Missing SPI descriptor {service}")
            else:
                try:
                    providers = [line.split("#", 1)[0].strip() for line in jar.read(service).decode("utf-8").splitlines()]
                    providers = list(dict.fromkeys(provider for provider in providers if provider))
                    if not providers:
                        errors.append(f"No providers declared in {service}")
                    for provider in providers:
                        # SPI names must be binary names, not archive paths.
                        if "/" in provider or provider.endswith(".class"):
                            errors.append(f"Invalid SPI provider name {provider!r} in {service}")
                        else:
                            require_class(provider, "SPI provider")
                except UnicodeError as error:
                    errors.append(f"SPI descriptor is not valid UTF-8: {service}: {error}")

            dependencies = [*(JACKSON3_CLASSES if jackson3 else ()), *required_classes]
            for dependency in dict.fromkeys(dependencies):
                require_class(dependency, "Runtime dependency")
    except (OSError, BadZipFile, RuntimeError, NotImplementedError) as error:
        errors.append(f"Cannot inspect JAR {archive_path}: {error}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jar", type=Path, help="Exact distributable JAR exported by the completed build")
    parser.add_argument("--kind", choices=("command", "listener"), required=True)
    parser.add_argument("--jackson3", action="store_true", help="Require Jackson 3 databind/core and Jackson annotation classes")
    parser.add_argument("--require-class", action="append", default=[], metavar="CLASS", help="Additional binary class name or .class entry; repeat as needed")
    arguments = parser.parse_args(argv)
    errors = inspect_archive(arguments.jar, arguments.kind, jackson3=arguments.jackson3, required_classes=arguments.require_class)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Archive checks passed: {arguments.jar}")
    print("Initialization, classloader compatibility, transitive completeness and runtime behavior remain separate checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
