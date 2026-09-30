# Command native implementation map

Read this when replacing the native skeleton or extending its IPC helpers. Paths are relative to the plugin root; use the renamed paths in the generated copy. Reuse existing runtime classes when they already implement these responsibilities. The [IPC reference](execunit-ipc.md) defines the wire bytes.

## Host process and unload requirements

Exec-units run inside an existing host process. The loader may unload their library/code as soon as `Main` / exported `run` returns. Every success, failure, cancellation, disconnect, and partial-startup path must leave the host alive and **zero invocation-owned work running, queued, or able to call back into the exec-unit**.

- Never terminate or stop the host to finish an invocation: no `Environment.Exit`, `Environment.FailFast`, `ExitProcess`, `TerminateProcess`, `exit` / `_exit` / `_Exit` / `quick_exit`, `abort`, `std::terminate`, or fatal signals directed at the host. Do not set process-wide `Environment.ExitCode` for an invocation failure. Use the protocol's failure path when usable, clean up, and return normally.
- Contain ordinary exceptions at the entrypoint and inside every worker, task, callback, and cleanup path. Observe task failures and signal the owner to shut down. No C++ exception may escape the C export; no joinable `std::thread` may reach destruction. Cleanup/destructors must not throw or skip the remaining cleanup after one failure. Catching exceptions does not repair invalid memory access or undefined behavior: validate lengths before allocation/indexing, retain buffers until users finish, and copy borrowed entrypoint arguments needed by workers.
- Protect pipe/socket writes against host-terminating `SIGPIPE` using the platform's per-operation or per-thread mechanism, including pending-signal handling when required. Do not solve this by changing the host's process-wide signal disposition.
- Prefer synchronous work when sufficient. Otherwise retain and join/await every owned thread/task, including workers started inside reused helpers or libraries. No detached threads, fire-and-forget tasks, or untracked `async void` work. `IsBackground = true` does not make a worker safe to unload.
- Track timers, queued continuations, async I/O, event/cancellation handlers, subscriptions, and native callbacks as work too. Unregister/disable their producers and wait for in-flight executions before return; no callback pointer or delegate may remain callable afterward. Idle shared runtime thread-pool threads can remain, but none of this invocation's queued or running work may remain on them.

### Shutdown sequence

Give one owner responsibility for finishing the invocation. Keep its entrypoint alive until all of these steps finish:

1. Stop accepting/scheduling work and signal cancellation, including after partial initialization.
2. Unblock all pending operations, including FIFO opens, connects, name resolution when used, reads, writes, accepts, response waiters, and retry delays, using a mechanism supported by that API. Closing a descriptor from another thread is not by itself proof that a blocked operation wakes up.
3. Disable/unregister callback sources and drain in-flight callbacks. A callback signals shutdown; it must not join itself. Do not hold a lock while waiting for a worker that needs that lock to exit.
4. Join/await every owned worker and drain required writes while their buffers and state still exist. Check wait results. A cancellation request, completion message, sleep, or expired join timeout is not proof of completion.
5. Release remaining resources and return only after no work can access the exec-unit's code/data. Make cleanup safe on repeated calls and after failed startup.

Design blocking operations for cooperative, bounded cancellation within the supported stop grace period. Do not use `Thread.Abort`, `TerminateThread`, detach, or return with a live worker to bypass a shutdown problem. If a worker cannot be stopped, keep the entrypoint and required state alive while resolving shutdown; record the defect instead of claiming completion or unload safety. Reused examples and a method named `Close` / `Dispose` are not evidence that these rules hold.

### Required lifecycle verification

Before declaring an affected native path complete:

- Review every thread/task/callback creation and every return/throw path. Record its owner, stop/unblock mechanism, and join/drain point in project context.
- In a compatible test host that remains alive after the invocation returns, exercise normal completion/stop, invalid configuration, partial startup failure, worker/callback failure, peer disconnect, and cancellation during blocked I/O/waiters. Repeat invocation and actual load/run/unload for the supported artifact format.
- Verify the host continues running, every invocation-owned worker has ended, callbacks are unregistered/drained, and no invocation work runs after return. Check ownership directly; total process thread count alone is insufficient.
- A hang, host exit, late callback, or surviving worker fails verification. Compilation and a standalone executable exiting successfully do not establish safe in-process unloading. If the required host/toolchain is unavailable, report that specific runtime gap without claiming it passed.

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
4. Replace the `catch (NotImplementedException)` scaffold with handling for the operation's real validation, I/O, and execution errors. If connection setup or the pipe itself fails, avoid sending on an unavailable pipe. A reporting failure must still reach cleanup; do not set the host process exit code as an invocation result.
5. In `finally`, request cancellation, unblock pending reads, wait for owned workers to end, and dispose resources. Make cleanup safe after partial initialization and repeated calls. Do not wait for a worker from that same worker's callback; callbacks should signal the owner to shut down.

Keep the initial configuration read and subsequent reader loop under one reader owner. Serialize result, error, option, and completion writes so concurrent sends cannot interleave frame bytes. A stop callback signals cancellation; the command's main execution path decides its documented terminal outcome and finishes within the advertised grace period.

## Linux files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/linux/command/Main.cpp` | Replace the TODO failure path in exported `run(char*, char*)`; retain the pipe for the entire operation and parse the configuration returned by `connect()`. |
| `exec-code/linux/common/CommunicationNamedPipes.h` and `.cpp` | `connect`, `getData`, and `putData` handle framed I/O; `sendResult`/`sendError`/terminal methods send command messages; `setCallbackNewData`, `setCallbackStop`, `startListenerIfNeeded`, and `listenForMessages` control callbacks/readers; `close` ends ownership. |
| `exec-code/linux/common/TLV.h` and `.cpp` | The existing codec handles native host envelopes. Keep it inside the transport boundary; command payload parsing is separate. |
| `exec-code/linux/build_linux.sh` | Add new translation units to the compiler invocation for this exec-unit; preserve its exported `run` and output artifact name. |

Register callbacks before `connect()` when needed. The bundled helper must be reviewed for failed-connect versus valid-empty-configuration handling, partial I/O, and worker lifetime as described in the IPC reference. The current `startListenerIfNeeded` detaches a reader capturing the pipe object. Replace this with owned, joinable work when using the reader, and implement cancellation/unblocking and confirmed worker completion before `run` returns. Synchronize state shared between threads; a plain boolean shutdown flag is not sufficient. Catch operation/callback exceptions within the exec-unit so C++ exceptions do not escape the exported C entrypoint or terminate a reader thread unexpectedly.

Use the same success/failure and cancellation semantics as Windows. The scaffold's final sleep is not evidence that a new asynchronous sender drained its queue: follow the actual transport's write/flush semantics before closing. Follow the [build guide](building.md) to rebuild the native resource after changing either platform.
