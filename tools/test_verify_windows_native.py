"""Regression checks for native PE verification without executing fixture bytes."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "templates/command/scripts/verify_windows_native.py"
spec = importlib.util.spec_from_file_location("verify_windows_native", CHECKER)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def pe_fixture(bits=64, export=b"start", dependency=b"kernel32.dll", managed=False):
    data = bytearray(0x800)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3c, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    optional_size = 0xf0 if bits == 64 else 0xe0
    struct.pack_into("<HH", data, 0x84, 0x8664 if bits == 64 else 0x14c, 1)
    struct.pack_into("<HH", data, 0x94, optional_size, 0x2002)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x20b if bits == 64 else 0x10b)
    directories = optional + (112 if bits == 64 else 96)
    struct.pack_into("<I", data, directories - 4, 16)
    struct.pack_into("<II", data, directories, 0x1000, 0x80)
    struct.pack_into("<II", data, directories + 8, 0x1100, 40)
    if managed:
        struct.pack_into("<II", data, directories + 14 * 8, 0x1200, 72)
    section = optional + optional_size
    data[section:section + 8] = b".rdata\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x600, 0x1000, 0x600, 0x200)
    struct.pack_into("<IIIII", data, 0x200 + 20, 1, 1, 0x1040, 0x1050, 0x1060)
    struct.pack_into("<I", data, 0x240, 0x1200)
    struct.pack_into("<I", data, 0x250, 0x1090)
    struct.pack_into("<H", data, 0x260, 0)
    data[0x290:0x290 + len(export) + 1] = export + b"\0"
    struct.pack_into("<IIIII", data, 0x300, 0, 0, 0, 0x1140, 0)
    data[0x340:0x340 + len(dependency) + 1] = dependency + b"\0"
    return bytes(data)


class NativePeTests(unittest.TestCase):
    def verify_fixture(self, data, bits=64):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            path = Path(temporary) / f"fixture.native{bits}_dll"
            path.write_bytes(data)
            return checker.verify(path)

    def test_both_native_architectures(self):
        for bits in (32, 64):
            with self.subTest(bits=bits):
                result = self.verify_fixture(pe_fixture(bits), bits)
                self.assertEqual(result["exports"], {"start"})
                self.assertEqual(result["imports"], {"kernel32.dll"})

    def test_mismatched_architecture(self):
        with self.assertRaisesRegex(ValueError, "architecture"):
            self.verify_fixture(pe_fixture(32), 64)

    def test_managed_dll_is_not_native(self):
        with self.assertRaisesRegex(ValueError, "non-native"):
            self.verify_fixture(pe_fixture(managed=True))

    def test_wrong_or_decorated_export(self):
        for name in (b"run", b"_start", b"start@4"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "exactly start"):
                self.verify_fixture(pe_fixture(export=name))

    def test_runtime_dll_dependency_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Non-system"):
            self.verify_fixture(pe_fixture(dependency=b"libwinpthread-1.dll"))

    def test_truncated_or_invalid_image_is_rejected(self):
        for data in (b"", b"MZ", pe_fixture()[:0x250]):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                checker.inspect_pe(data)

    def test_all_standalone_copies_match(self):
        for root in ("templates/listener", "echo-command-plugin", "tcp-listener-plugin"):
            self.assertEqual(CHECKER.read_bytes(), (ROOT / root / "scripts/verify_windows_native.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
