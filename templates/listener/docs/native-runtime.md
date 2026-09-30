# Listener native implementation map

Read this when implementing or extending the native runtime. Paths are relative to the plugin root; use the renamed paths in the generated copy. Reuse existing runtime/transport classes instead of introducing duplicate owners. The [IPC reference](execunit-ipc.md) distinguishes the local-agent pipe from the transport to Java.

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

Adapt helper namespaces, method casing, callbacks, and ownership to this template. Existing managed helpers can use `load` / `getFullBuffer`, while template methods are `Load` / `GetFullBuffer`. Compare implementations before transplanting them; newer bounded helpers and older compatibility paths coexist. Keep these helpers responsible for the native host IPC protocol. Decode plugin configuration and application payloads separately using the format chosen for the task.

## Windows files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/win/Program.cs` | `Main` owns runtime/cancellation state; `Initialize` connects and parses configuration; `WaitForStop` keeps the runtime alive while its transport works; `Cleanup` ends sessions and workers. |
| `exec-code/win/exec-unit-utils/CommunicationNamedPipes.cs` | `Connect` opens the agent pipe and reads initial configuration. Add shared full-frame read/write helpers and reader ownership here; implement safe `Close`/`Dispose`. |
| `exec-code/win/exec-unit-utils/TLV.cs` | `Load` and `GetFullBuffer` decode/encode bounded host IPC envelopes. This helper does not choose the plugin configuration or application payload format. |
| `exec-code/win/exec-unit-utils/CommunicationNamedPipesListener.cs` | Retain/register the constructor callback and `SetCallback`; implement `GetMetadata`, `GetDataToSend`, and `NewDataFromC2`, including sequence-correlated responses and timeout/disconnect handling. |
| `exec-code/win/listener-execunit.csproj` | Add new sources as explicit `<Compile Include="RelativePath.cs" />` entries; new files are not automatically compiled. |

The `using (var pipe = ...)` currently inside `Initialize` ends before the listener loop starts. Move ownership to `Main` or the existing runtime object so the connection survives until shutdown. Preserve `QQQWWWEEE` for Java's shellcode patching.

When restructuring `Main`:

1. Create cancellation/runtime state and register the actual callbacks before starting the pipe reader. Call `Connect`, validate the returned configuration, then initialize the requested transport to Java.
2. Keep both connections alive for their required lifetimes. The pipe reader dispatches local-agent messages; the application transport sends metadata/requests and receives commands from Java. Use a single reader per connection and serialize its writes.
3. Connect transport/pipe disconnects and the chosen retry policy to cancellation. `Console.CancelKeyPress` can remain a console convenience; a native host needs a real disconnect/cancellation path. Unsubscribe any registered handler and drain in-flight calls before returning. Replace the placeholder `WaitForStop` with ownership of, or a wait on, those running workers.
4. Replace `catch (NotImplementedException)` with handling for actual configuration, I/O, and transport failures. The listener helper has no command `sendError`/terminal-message API. Use an established application error message when available, then apply the listener's retry/shutdown behavior; do not invent command completion messages.
5. In `finally`, follow the [shutdown sequence](#shutdown-sequence): cancel, prove reads/waiters unblock, unregister/drain callbacks, join/await workers, and dispose remaining resources. Cleanup must work after partial initialization and repeated calls. A reader callback should signal shutdown rather than wait for itself to terminate.

Custom output belongs in the application transport encoder and Java decoder. If no separate native transport class exists, keep that code in `Program.cs` initially or introduce a clearly owned helper and include it in the project. Do not put arbitrary Java telemetry in `NewDataFromC2`, which sends opaque server data to the local agent.

## Linux files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/linux/listener/Main.cpp` | Implement exported `run(char*, char*)`: configure callbacks, call `connect`, parse configuration, run the requested application transport, and retain ownership until shutdown. |
| `exec-code/linux/common/CommunicationNamedPipes.h` and `.cpp` | `connect`, `getData`, and `putData` handle framed I/O; `setCallback`/`listenForMessages` dispatch inbound messages; `getMetadata`, `getDataToSend`, `waitForResponseData`, and `newDataFromC2` implement agent exchanges; `close` unblocks and ends owned work. |
| `exec-code/linux/common/TLV.h` and `.cpp` | Preserve the host IPC envelope codec and repair bounds validation where required; plugin payload decoders stay separate. |
| `exec-code/linux/build_linux.sh` | Include any new transport/parser translation units in this exec-unit's compiler invocation; preserve the `run` export and artifact name. |

Keep `run` alive while callbacks/workers can access its pipe and runtime state. The current `close` closes descriptors and joins the reader, but does not prove a blocked FIFO read wakes; `waitForResponseData` also has an unbounded `sem_wait` without shutdown cancellation. Repair these paths when using the helper, including partial-startup failure and safe synchronization of shared state. Review connection failure, full I/O, bounded lengths, and waiter cancellation in the helper; a valid empty configuration must not be mistaken for connection failure. Catch operation/callback exceptions inside the native runtime. Do not let a C++ exception escape the C export, or wait for the current reader thread from its own callback. Mirror Windows behavior for disconnection, reconnection if supported, and shutdown, and follow the [build guide](building.md) to rebuild resources.
