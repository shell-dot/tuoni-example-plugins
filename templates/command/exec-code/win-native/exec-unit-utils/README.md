# Windows command utilities

These six C++ files are copied unchanged from
`commands_default/common/CommonCppExecUnit`. [UPSTREAM.json](UPSTREAM.json)
records the source directory and LF-normalized SHA-256 of every imported file. The echo example
and command template carry identical copies.

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

[Main.cpp](../command/Main.cpp) owns a scoped pipe and uses these public methods
for connection, result, error, and terminal reporting. It selects bounded
structured-command options with a 64 MiB frame cap. The no-op command passes
empty callbacks because it does not use updates or stop requests. The utility
still starts a reader; its cleanup cancels I/O and joins the reader before the
DLL returns. Do not destroy the pipe from a reader callback.

Keep these files in sync with the reference utilities when updating them. Update
the hashes only after reviewing a deliberate upstream refresh. Compilation and
DLL runtime checks are separate from source-copy verification.
