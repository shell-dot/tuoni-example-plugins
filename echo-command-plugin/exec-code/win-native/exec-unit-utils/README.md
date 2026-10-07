# Windows command utilities

These six C++ files come from `commands_default/common/CommonCppExecUnit`.
The echo example adds only a public `isConnected()` query to
`CommunicationNamedPipes.h`; its other utility sources match the command template.

The build compiles `CommunicationNamedPipes.cpp`,
`CommunicationNamedPipesCommand.cpp`, and `TLV.cpp` separately, then links them
into each DLL. Upstream warnings are enabled without treating them as errors;
example entrypoints still use `-Werror`. A
[MinGW include shim](../compat/mingw/Windows.h) resolves the reference's
`<Windows.h>` spelling on case-sensitive build hosts without editing its source.
The build also force-includes [Win32Compatibility.h](../compat/mingw/Win32Compatibility.h)
so sources using either header spelling receive a guarded fallback for
`ERROR_UNHANDLED_EXCEPTION` when MinGW's headers omit it. The fallback uses
Microsoft's [documented value, 574](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--500-999-#error_unhandled_exception),
and preserves the toolchain definition when present.

Each command's `Main.cpp` owns its connection, behavior and checked terminal
report. Only the more-data command needs a bounded update queue; its callbacks
record updates and stop requests, while output stays on the invocation thread.
Callback state is declared before the pipe. Pipe destruction cancels I/O and
joins the reader before that state is destroyed.

Keep the unchanged sources in sync with the reference utilities. Update original
hashes only after reviewing an upstream refresh. Compilation and DLL runtime
checks are separate from source-copy verification.
