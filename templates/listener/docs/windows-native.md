# Windows native DLLs

The listener supports Windows x86 and x64 `NATIVE_LIB` alongside its managed and
shellcode formats. Java selects `listener.native32_dll` or `listener.native64_dll`
using the target process architecture and sets `ExecUnit.entrypoint` to `start`.
ARM and unknown architectures remain unsupported. Linux continues to use its
separate `run(readPipe, writePipe)` ABI.

The Windows export is:

```cpp
extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName);
```

The loader supplies the unprefixed local named-pipe name. Native DLL bytes are not
patched. The export definition preserves the undecorated name on both architectures.
The native implementation is [Main.cpp](../exec-code/win-native/listener/Main.cpp);
extend it alongside the C# and Linux implementation when adding behavior.

[The utility sources](../exec-code/win-native/exec-unit-utils/README.md) come from
`listeners_default/listeners/simple_tcp_listener/execunits/windows/TcpListenerNativeDll`:
`CommunicationNamedPipes`, `TLV`, `Conversions`, and `RaiiHelpers`. The provenance
manifest records reference hashes and identifies locally modified files.

The copied transport retains its reference API and reader-thread design. Local
changes add bounded framing/waits, full writes, connection-state checks and cleanup
that cancels/drains I/O and joins the reader before releasing its state. Header
changes support MinGW packing and explicit includes. Check `isConnected()` after
`connect()` so failed startup cannot be confused with empty configuration. The
owner must destroy the pipe outside its callbacks after application calls finish.

[Conversions.h](../exec-code/win-native/exec-unit-utils/Conversions.h) declares
`byte` explicitly as `BYTE`, so lean Windows headers do not remove the utility's
required type. [TLV.cpp](../exec-code/win-native/exec-unit-utils/TLV.cpp) uses
allocation-free, nonthrowing `clear()` and destruction, releasing existing nodes
without allocating a temporary cleanup container.

The default validates empty configuration and polls until host disconnect. Its
application traffic channel remains TODO, just as in the managed/Linux defaults.
No worker or pending I/O may survive return from `start`.

Build from this plugin root with `make build`. The standalone
`make build-windows-native` target cross-compiles both DLLs in Docker using MinGW
and writes them to `exec-code/win-native/build/` for Gradle, plus `build/`.
The full build embeds both DLLs in the JAR and exports them with the other formats.
The standalone native build does not build Java or the managed formats.

The [native build script](../exec-code/win-native/build_windows.sh) statically links
compiler runtimes. The [PE verifier](../scripts/verify_windows_native.py) rejects
wrong architectures, managed images, missing/decorated/extra exports, forwarded
exports and dependencies outside the allowed Windows system DLLs. The Java
`execUnitFormatsCheck` also checks native PE roles and architecture-specific resource
selection. These checks do not execute DLLs.

After building, run the [runtime check](../scripts/check_windows_native_runtime.py)
on Windows with Python matching the DLL architecture:

```powershell
python scripts/check_windows_native_runtime.py build/listener.native64_dll --mode listener
```

Use a 32-bit Python interpreter for `listener.native32_dll`. The check uses isolated
child processes and real local named pipes to exercise normal behavior, invalid
configuration, startup/reporting disconnects, repeated invocations and immediate
unload. It checks command completion/output or idle listener lifetime, and observes
handle growth. The harness is a local peer simulation; a real agent's final status
and deployed loader behavior still require integration verification. A watchdog
fails a hung/crashed child. Do not report any of these runtime checks as passed
unless they actually ran against fresh DLLs.
