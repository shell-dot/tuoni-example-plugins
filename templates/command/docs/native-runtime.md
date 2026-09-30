# Command native implementation map

Read this when replacing the native skeleton or extending its IPC helpers. Paths are relative to the plugin root; use the renamed paths in the generated copy. Reuse existing runtime classes when they already implement these responsibilities. The [IPC reference](execunit-ipc.md) defines the wire bytes.

## Reusing existing implementations

The [existing plugin map](existing-plugins.md) identifies reference helpers and their native/Java peers. Trace `.projitems` / `.vcxitems` imports and POSIX forwarding includes before choosing a source to edit. An EXE/DLL/shellcode wrapper may only delegate to shared logic; a platform `Main.cpp` may include the canonical POSIX implementation. Include shared sources exactly once and update explicit build manifests when adding files.

Adapt helper namespaces, method casing, callbacks, and ownership to this template. Existing managed helpers can use `load` / `getFullBuffer`, while template methods are `Load` / `GetFullBuffer`. Compare implementations before transplanting them; newer bounded helpers and older compatibility paths coexist. The native helpers own host envelope handling; command configuration and result payloads use the representation agreed with Java.

## Windows files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/win/Program.cs` | `Main` owns the runtime; `Initialize` connects and parses configuration; `Execute` performs the command; `Complete` sends the successful terminal outcome; `Cleanup` disposes owned resources. |
| `exec-code/win/exec-unit-utils/CommunicationNamedPipes.cs` | `Connect` opens the pipe and reads the initial frame; implement shared full-frame read/write helpers and connection state here. `Close`/`Dispose` cancel and release the connection safely. |
| `exec-code/win/exec-unit-utils/TLV.cs` | `Load` and `GetFullBuffer` support the host IPC envelope inside the native helper. Preserve its type/parent-bit and length rules; these helpers do not prescribe the command payload format. |
| `exec-code/win/exec-unit-utils/CommunicationNamedPipesCommand.cs` | Implement `sendResult`, `sendError`, `sendReturnSuccess`, and `sendReturnFailed`. Retain the constructor's update/stop callbacks and dispatch received messages to them. Add the handling-option methods here when the command needs streaming or stop support. |
| `exec-code/win/command-execunit.csproj` | Add each new source as `<Compile Include="RelativePath.cs" />` alongside `Program.cs`. This project does not automatically include new C# files. |

The skeleton's `Initialize` has a local `using (var pipe = ...)`. That scope disposes the pipe before `Execute` and `Complete`. Move ownership to `Main` or an existing runtime object whose lifetime spans all those methods. Keep the `QQQWWWEEE` string available for Java's shellcode patching.

Use this ordering when restructuring `Main`:

1. Create the cancellation/runtime state and pipe, register update/stop callbacks if used, call `Connect`, then parse the returned configuration bytes.
2. Send the necessary handling options before execution produces results. Run the operation while keeping the pipe and any reader worker alive.
3. Send results, then one successful completion. An operation failure sends `sendError` followed by one failure completion while the connection is usable. Choose one owner for terminal reporting so both `Execute` and `Complete` cannot finish the same command.
4. Replace the `catch (NotImplementedException)` scaffold with handling for the operation's real validation, I/O, and execution errors. If connection setup or the pipe itself fails, avoid sending on an unavailable pipe. A reporting failure must still reach cleanup; a local exit code does not replace a delivered completion message.
5. In `finally`, request cancellation, unblock pending reads, wait for owned workers to end, and dispose resources. Make cleanup safe after partial initialization and repeated calls. Do not wait for a worker from that same worker's callback; callbacks should signal the owner to shut down.

Keep the initial configuration read and subsequent reader loop under one reader owner. Serialize result, error, option, and completion writes so concurrent sends cannot interleave frame bytes. A stop callback signals cancellation; the command's main execution path decides its documented terminal outcome and finishes within the advertised grace period.

## Linux files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/linux/command/Main.cpp` | Replace the TODO failure path in exported `run(char*, char*)`; retain the pipe for the entire operation and parse the configuration returned by `connect()`. |
| `exec-code/linux/common/CommunicationNamedPipes.h` and `.cpp` | `connect`, `getData`, and `putData` handle framed I/O; `sendResult`/`sendError`/terminal methods send command messages; `setCallbackNewData`, `setCallbackStop`, `startListenerIfNeeded`, and `listenForMessages` control callbacks/readers; `close` ends ownership. |
| `exec-code/linux/common/TLV.h` and `.cpp` | The existing codec handles native host envelopes. Keep it inside the transport boundary; command payload parsing is separate. |
| `exec-code/linux/build_linux.sh` | Add new translation units to the compiler invocation for this exec-unit; preserve its exported `run` and output artifact name. |

Register callbacks before `connect()` when needed. The bundled helper must be reviewed for failed-connect versus valid-empty-configuration handling, partial I/O, and worker lifetime as described in the IPC reference. In particular, a detached reader that captures the pipe object must not outlive it; arrange cancellation/unblocking and worker completion before `run` returns. Catch operation/callback exceptions within the exec-unit so C++ exceptions do not escape the exported C entrypoint or terminate a reader thread unexpectedly.

Use the same success/failure and cancellation semantics as Windows. The scaffold's final sleep is not evidence that a new asynchronous sender drained its queue: follow the actual transport's write/flush semantics before closing. Follow the [build guide](building.md) to rebuild the native resource after changing either platform.
