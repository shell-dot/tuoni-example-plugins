#!/usr/bin/env python3
"""Verify architecture, the native start export, and OS-only dependencies of DLLs."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


SYSTEM_IMPORTS = {"kernel32.dll", "msvcrt.dll", "ws2_32.dll", "advapi32.dll", "user32.dll", "ntdll.dll"}


def inspect_pe(data: bytes) -> dict:
    def unpack(fmt: str, offset: int):
        if offset < 0 or offset + struct.calcsize(fmt) > len(data):
            raise ValueError("Truncated PE structure")
        return struct.unpack_from(fmt, data, offset)

    if data[:2] != b"MZ":
        raise ValueError("Missing DOS header")
    pe = unpack("<I", 0x3c)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Missing PE header")
    machine, count = unpack("<HH", pe + 4)
    optional_size, characteristics = unpack("<HH", pe + 20)
    optional = pe + 24
    magic = unpack("<H", optional)[0]
    if (machine, magic) not in {(0x14c, 0x10b), (0x8664, 0x20b)}:
        raise ValueError("Expected an x86 or x64 PE image")
    directory_offset = 112 if magic == 0x20b else 96
    if optional_size < directory_offset + 16 * 8:
        raise ValueError("Truncated PE directories")
    if unpack("<I", optional + directory_offset - 4)[0] < 16:
        raise ValueError("Missing PE directories")
    directories = optional + directory_offset
    sections = []
    for i in range(count):
        section = optional + optional_size + i * 40
        virtual_size, rva, raw_size, raw = unpack("<IIII", section + 8)
        sections.append((rva, raw_size, raw))

    def offset(rva: int, size: int = 1) -> int:
        for start, raw_size, raw in sections:
            relative = rva - start
            if 0 <= relative and relative + size <= raw_size and raw + relative + size <= len(data):
                return raw + relative
        raise ValueError("PE RVA is outside initialized section data")

    def name(rva: int) -> str:
        start = offset(rva)
        end = data.find(b"\0", start, start + 512)
        if end < 0:
            raise ValueError("Invalid PE name")
        offset(rva, end - start + 1)
        return data[start:end].decode("ascii")

    export_rva, export_size = unpack("<II", directories)
    exports = set()
    if export_rva:
        export = offset(export_rva, 40)
        functions, names, functions_rva, names_rva, ordinals_rva = unpack("<IIIII", export + 20)
        if functions > 65536 or names > functions:
            raise ValueError("Invalid PE export counts")
        function_table = offset(functions_rva, functions * 4)
        name_table = offset(names_rva, names * 4)
        ordinals = offset(ordinals_rva, names * 2)
        for i in range(names):
            ordinal = unpack("<H", ordinals + i * 2)[0]
            if ordinal >= functions:
                raise ValueError("Invalid export ordinal")
            address = unpack("<I", function_table + ordinal * 4)[0]
            if export_rva <= address < export_rva + export_size:
                raise ValueError("Forwarded export is not an implementation")
            offset(address)
            exports.add(name(unpack("<I", name_table + i * 4)[0]))
        if names != functions:
            raise ValueError("Unnamed exports are not allowed")

    import_rva, import_size = unpack("<II", directories + 8)
    imports = set()
    if import_rva:
        for i in range(256):
            descriptor = unpack("<IIIII", offset(import_rva + i * 20, 20))
            if not any(descriptor):
                break
            imports.add(name(descriptor[3]).lower())
        else:
            raise ValueError("Unterminated PE import table")
    clr_rva, clr_size = unpack("<II", directories + 14 * 8)
    return {"machine": machine, "dll": bool(characteristics & 0x2000),
            "managed": bool(clr_rva or clr_size), "exports": exports, "imports": imports}


def verify(path: Path) -> dict:
    expected = {".native32_dll": 0x14c, ".native64_dll": 0x8664}.get(path.suffix)
    if expected is None:
        raise ValueError("Expected .native32_dll or .native64_dll suffix")
    result = inspect_pe(path.read_bytes())
    if result["machine"] != expected or not result["dll"] or result["managed"]:
        raise ValueError("Wrong architecture or non-native DLL")
    if result["exports"] != {"start"}:
        raise ValueError("The DLL must export exactly start")
    unexpected = result["imports"] - SYSTEM_IMPORTS
    if unexpected:
        raise ValueError("Non-system DLL dependencies: " + ", ".join(sorted(unexpected)))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dlls", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.dlls:
        try:
            verify(path)
        except (OSError, ValueError, UnicodeError) as error:
            parser.exit(1, f"{path}: {error}\n")
        print(f"Verified native DLL: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
