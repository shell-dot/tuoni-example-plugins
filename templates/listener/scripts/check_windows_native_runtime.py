#!/usr/bin/env python3
"""Exercise real Windows DLL entrypoints against local pipe/TCP peers in child processes.

Run with a Windows Python interpreter matching the DLL architecture. No Tuoni
server is required; these checks do not establish a real agent's final status.
"""
from __future__ import annotations

import argparse
import ctypes
import gc
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid

from verify_windows_native import verify


def envelope(kind, value=b"", parent=False):
    return bytes([kind | (0x80 if parent else 0)]) + struct.pack("<I", len(value)) + value


def configure_win32():
    from ctypes import wintypes as w
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateNamedPipeW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.LPVOID]
    api.CreateNamedPipeW.restype = w.HANDLE
    api.ConnectNamedPipe.argtypes = [w.HANDLE, w.LPVOID]
    api.ConnectNamedPipe.restype = w.BOOL
    api.ReadFile.argtypes = [w.HANDLE, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), w.LPVOID]
    api.ReadFile.restype = w.BOOL
    api.WriteFile.argtypes = [w.HANDLE, w.LPCVOID, w.DWORD, ctypes.POINTER(w.DWORD), w.LPVOID]
    api.WriteFile.restype = w.BOOL
    api.PeekNamedPipe.argtypes = [w.HANDLE, w.LPVOID, w.DWORD, w.LPVOID, ctypes.POINTER(w.DWORD), w.LPVOID]
    api.PeekNamedPipe.restype = w.BOOL
    api.CloseHandle.argtypes = [w.HANDLE]
    api.CloseHandle.restype = w.BOOL
    api.GetCurrentProcess.restype = w.HANDLE
    api.GetProcessHandleCount.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    api.GetProcessHandleCount.restype = w.BOOL
    return api


class PipeServer:
    def __init__(self, api):
        self.api = api
        self.name = f"tuoni-native-test-{os.getpid()}-{uuid.uuid4().hex}"
        self.handle = api.CreateNamedPipeW("\\\\.\\pipe\\" + self.name, 3, 0, 1, 65536, 65536, 0, None)
        if self.handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())

    def connect(self):
        if not self.api.ConnectNamedPipe(self.handle, None) and ctypes.get_last_error() != 535:
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle is not None:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def send(self, kind, value=b"", parent=False):
        message = envelope(kind, value, parent)
        frame = struct.pack("<I", len(message)) + message
        self.write(frame)

    def send_batch(self, messages):
        frames = []
        for kind, value in messages:
            message = envelope(kind, value)
            frames.append(struct.pack("<I", len(message)) + message)
        self.write(b"".join(frames))

    def write(self, frame):
        written = ctypes.c_ulong()
        buffer = ctypes.create_string_buffer(frame)
        if not self.api.WriteFile(self.handle, buffer, len(frame), ctypes.byref(written), None) or written.value != len(frame):
            raise ctypes.WinError(ctypes.get_last_error())

    def exact(self, size, deadline):
        value = bytearray()
        while len(value) < size:
            if time.monotonic() >= deadline:
                raise TimeoutError("Native DLL did not produce the expected pipe frame")
            available = ctypes.c_ulong()
            if not self.api.PeekNamedPipe(self.handle, None, 0, None, ctypes.byref(available), None):
                raise EOFError("Native DLL closed its pipe")
            if not available.value:
                time.sleep(0.005)
                continue
            count = min(available.value, size - len(value))
            buffer = ctypes.create_string_buffer(count)
            read = ctypes.c_ulong()
            if not self.api.ReadFile(self.handle, buffer, count, ctypes.byref(read), None) or not read.value:
                raise EOFError("Native DLL read failed")
            value.extend(buffer.raw[:read.value])
        return bytes(value)

    def receive(self):
        deadline = time.monotonic() + 12
        length = struct.unpack("<I", self.exact(4, deadline))[0]
        if not 5 <= length <= 64 * 1024 * 1024:
            raise AssertionError("Invalid native frame length")
        frame = self.exact(length, deadline)
        if struct.unpack_from("<I", frame, 1)[0] != length - 5:
            raise AssertionError("Invalid native TLV length")
        return frame[0], frame[5:]


def tcp_peer(server, completed, errors):
    def exact(connection, count):
        value = b""
        while len(value) < count:
            part = connection.recv(count - len(value))
            if not part:
                raise EOFError("Native TCP connection closed early")
            value += part
        return value

    def field(connection):
        count = struct.unpack("<I", exact(connection, 4))[0]
        if count > 1024:
            raise AssertionError("Unexpected TCP fixture field length")
        return exact(connection, count)

    try:
        with server.accept()[0] as connection:
            connection.settimeout(12)
            assert field(connection) == b"META"
            assert field(connection) == b""  # Registration includes the zero data length.
            connection.sendall(struct.pack("<I", 7) + b"COMMAND")
            assert field(connection) == b"META"
            assert field(connection) == b"REQUEST"
        completed.set()
    except BaseException as error:
        errors.append(error)
        completed.set()


def run_case(api, dll, mode, scenario):
    from _ctypes import FreeLibrary
    peer = None
    peer_thread = None
    peer_errors = []
    peer_completed = threading.Event()
    pipe = PipeServer(api)
    library = ctypes.CDLL(str(dll))
    entry = library.start
    entry.argtypes = [ctypes.c_char_p]
    entry.restype = None
    # Validating absent arguments must return without touching an agent channel.
    entry(None)
    worker = threading.Thread(target=entry, args=(pipe.name.encode("ascii"),))
    try:
        configuration = b"hello"
        if mode in {"command", "listener"}:
            configuration = b""
        elif mode == "echo-ongoing-file":
            configuration = struct.pack("<I", 1 if scenario == "stop" else 50) + b"a\nb"
        elif mode == "tcp-listener":
            if scenario == "invalid-parent":
                configuration = b""  # Startup rejection needs no TCP fixture.
            else:
                peer = socket.socket()
                peer.bind(("127.0.0.1", 0))
                peer.listen(1)
                peer.settimeout(12)
                configuration = f"127.0.0.1:{peer.getsockname()[1]}".encode()
        if scenario == "invalid":
            configuration = b"ERR:forced failure" if mode == "echo" else b"x"
        if mode == "tcp-listener" and scenario == "success":
            peer_thread = threading.Thread(target=tcp_peer, args=(peer, peer_completed, peer_errors))
            peer_thread.start()

        worker.start()
        pipe.connect()
        if scenario == "invalid-parent":
            # Reject a parent startup value after parsing many children. Repeated
            # load/unload exercises the listener TLV's sibling cleanup path.
            pipe.send(1, envelope(4) * 1024, parent=True)
        elif scenario != "startup-disconnect":
            pipe.send(1, configuration)
        if scenario in {"disconnect", "startup-disconnect"}:
            pipe.close()
        elif mode == "listener":
            if scenario == "success":
                time.sleep(0.1)
                assert worker.is_alive(), "Idle listener returned before pipe disconnect"
                pipe.close()
        elif mode == "tcp-listener":
            if scenario == "success":
                sent_request = False
                forwarded = False
                while not (forwarded and peer_completed.is_set()):
                    kind, value = pipe.receive()
                    if kind == 0x23:
                        assert value == b"COMMAND"
                        forwarded = True
                    elif kind in (0xa1, 0xa2):
                        offset = 0
                        sequence = None
                        while offset < len(value):
                            tag, length = value[offset], struct.unpack_from("<I", value, offset + 1)[0]
                            child = value[offset + 5:offset + 5 + length]
                            if tag == 2:
                                assert len(child) == 4
                                sequence = child
                            offset += 5 + length
                        assert sequence is not None
                        response = b"META" if kind == 0xa1 else (b"" if sent_request else b"REQUEST")
                        if kind == 0xa2:
                            sent_request = True
                        pipe.send(kind & 0x7f, envelope(2, sequence) + envelope(4, response), True)
                    else:
                        raise AssertionError(f"Unexpected listener message: {kind:#x}")
                pipe.close()
        else:
            output = b""
            terminal = []
            update_sent = False
            while not terminal:
                kind, value = pipe.receive()
                if kind == 0x30:
                    output += value
                    if mode == "echo-ongoing-more-data":
                        if scenario == "update-stop-order":
                            if not update_sent:
                                # Queue all earlier updates and stop together; waiting
                                # for each output would conceal the reader/stop race.
                                pipe.send_batch([(0x39, b"first"), (0x39, b"second"),
                                                 (0x39, b"third"), (0x3f, b"")])
                                update_sent = True
                        else:
                            pipe.send(0x3f if update_sent else 0x39, b"" if update_sent else b"updated")
                            update_sent = True
                    elif scenario == "stop" and not update_sent:
                        pipe.send(0x3f)
                        update_sent = True
                elif kind in (0x33, 0x34):
                    assert not value
                    terminal.append(kind)
                elif kind not in (0x32, 0xb1):
                    raise AssertionError(f"Unexpected command message: {kind:#x}")
            assert terminal == ([0x34] if scenario == "invalid" else [0x33])
            if scenario == "success":
                expected = {"command": b"DONE", "echo": b"hello",
                            "echo-ongoing": b"0: hello\n1: hello\n2: hello\n3: hello\nStopping now\n",
                            "echo-ongoing-file": b"a\nb\nStopping now\n",
                            "echo-ongoing-more-data": b"Initial data: hello\nNew data: updated\n"}
                assert output == expected[mode], output
            if scenario == "stop":
                assert b"USER FORCED STOP" in output
            if scenario == "update-stop-order":
                assert output == (b"Initial data: hello\nNew data: first\n"
                                  b"New data: second\nNew data: third\n"), output
            # No frames, including duplicate completion, may follow the terminal.
            try:
                pipe.receive()
            except EOFError:
                pass
            else:
                raise AssertionError("Frame received after terminal completion")

        worker.join(12)
        assert not worker.is_alive(), "Invocation survived pipe disconnect/failure"
        if peer_thread:
            peer_thread.join(12)
            assert not peer_thread.is_alive(), "TCP fixture did not finish"
        if peer_errors:
            raise peer_errors[0]
    finally:
        pipe.close()
        if peer:
            peer.close()
        if worker.ident is not None:
            worker.join(12)
        if not worker.is_alive():
            # Unload immediately after return; repeat in this same host process below.
            del entry
            FreeLibrary(library._handle)
        if peer_thread:
            peer_thread.join(12)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dll", type=Path)
    parser.add_argument("--mode", required=True, choices=("command", "listener", "echo", "echo-ongoing",
                        "echo-ongoing-file", "echo-ongoing-more-data", "tcp-listener"))
    parser.add_argument("--child", choices=("success", "invalid", "invalid-parent", "disconnect",
                                           "startup-disconnect", "stop", "update-stop-order"))
    args = parser.parse_args()
    if os.name != "nt":
        parser.exit(2, "Runtime checks require Windows.\n")
    result = verify(args.dll)
    if (ctypes.sizeof(ctypes.c_void_p) == 8) != (result["machine"] == 0x8664):
        parser.exit(2, "Use a Python interpreter matching the DLL's x86/x64 architecture.\n")
    if args.child:
        api = configure_win32()
        counts = []
        for _ in range(3):
            run_case(api, args.dll.resolve(), args.mode, args.child)
            gc.collect()
            count = ctypes.c_ulong()
            assert api.GetProcessHandleCount(api.GetCurrentProcess(), ctypes.byref(count))
            counts.append(count.value)
        assert counts[-1] <= counts[0] + 1, f"Handle growth across repeated load/unload: {counts}"
        return 0
    scenarios = ["success", "disconnect", "startup-disconnect"]
    if args.mode in {"command", "listener", "echo", "echo-ongoing-file", "tcp-listener"}:
        scenarios.append("invalid")
    if args.mode == "echo-ongoing-file":
        scenarios.append("stop")
    if args.mode == "echo-ongoing-more-data":
        scenarios.append("update-stop-order")
    if args.mode in {"listener", "tcp-listener"}:
        scenarios.append("invalid-parent")
    for scenario in scenarios:
        subprocess.run([sys.executable, str(Path(__file__).resolve()), str(args.dll.resolve()),
                        "--mode", args.mode, "--child", scenario], check=True, timeout=60)
        print(f"Verified {args.mode}: {scenario}, repeated invocation and immediate unload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
