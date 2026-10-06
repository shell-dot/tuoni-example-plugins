# Windows native DLLs

The command supports Windows x86 and x64 `NATIVE_LIB` alongside its managed and
shellcode formats. Java selects `command.native32_dll` or `command.native64_dll`
using the target process architecture and sets `ExecUnit.entrypoint` to `start`.
ARM and unknown architectures remain unsupported. Linux continues to use its
separate `run(readPipe, writePipe)` ABI.

The Windows export is:

```cpp
extern "C" __declspec(dllexport) void __cdecl start(const char* pipeName);
```

The loader supplies the unprefixed local named-pipe name. Native DLL bytes are not
patched. The export definition preserves the undecorated name on both architectures.
The native implementation is [Main.cpp](../exec-code/win-native/command/Main.cpp);
extend it alongside the C# and Linux implementation when adding behavior.

[The utility sources](../exec-code/win-native/exec-unit-utils/README.md) are copied
unchanged from `commands_default/common/CommonCppExecUnit`: `CommunicationNamedPipes`,
`CommunicationNamedPipesCommand`, and `TLV`. Their provenance manifest records the
reference file hashes. A MinGW include shim preserves the upstream header spelling.
The build force-includes [Win32Compatibility.h](../exec-code/win-native/compat/mingw/Win32Compatibility.h)
to supply `ERROR_UNHANDLED_EXCEPTION` only when the installed headers omit it.

[CommandRuntime.h](../exec-code/win-native/common/CommandRuntime.h) supplies ownership
and completion using those classes. It selects bounded structured-command options,
checks `TryConnect` separately from empty configuration, and keeps callbacks limited
to recording updates/stop requests. The command itself runs on the invocation thread.
The pipe's cleanup cancels I/O and joins its reader before callback state is destroyed.
Each entrypoint keeps invocation state local. Expected validation, queue-limit,
and pipe-write failures use checked results; the DLL boundary contains only
unexpected library/runtime exceptions.

`CommandInput.next()` drains updates accepted before a stop request in order
before reporting stopped; updates received after stop are ignored. Queue and stop
decisions use the same lock. This is utility behavior for code that consumes input;
the no-op template still leaves live command updates unsupported.

The default validates empty configuration and writes UTF-8 `DONE`. The shared
`runCommand` owns one checked terminal success/failure attempt after the operation;
failed reporting cannot bypass scoped cleanup. Broken channels are closed and
partial terminal writes are not retried.

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
python scripts/check_windows_native_runtime.py build/command.native64_dll --mode command
```

Use a 32-bit Python interpreter for `command.native32_dll`. The check uses isolated
child processes and real local named pipes to exercise normal behavior, invalid
configuration, startup/reporting disconnects, repeated invocations and immediate
unload. It checks command completion/output or idle listener lifetime, and observes
handle growth. The harness is a local peer simulation; a real agent's final status
and deployed loader behavior still require integration verification. A watchdog
fails a hung/crashed child. Do not report any of these runtime checks as passed
unless they actually ran against fresh DLLs.
