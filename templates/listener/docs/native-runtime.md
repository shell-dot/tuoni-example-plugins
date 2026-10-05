# Listener native implementation map

Read this when implementing or extending the native runtime. Paths are relative to the plugin root; use the renamed paths in the generated copy. Reuse existing runtime/transport classes instead of introducing duplicate owners. The [IPC reference](execunit-ipc.md) distinguishes the local-agent pipe from the transport to Java.

The [idle entrypoints](../README.md#default-behavior) already connect, validate zero configuration bytes, wait for their owned reader, and clean up before return. Managed Windows uses `finally`; native Windows and Linux use RAII and whole-entrypoint exception boundaries. Traffic setup/forwarding and cleanup of added channel workers remain TODO. Extend those hooks; verify response-wait timeout/disconnect cancellation before using request helpers.

## Host process and unload requirements

Exec-units run inside an existing host process. The loader may unload their library/code as soon as `Main` / exported `start` / `run` returns. Every success, failure, cancellation, disconnect, and partial-startup path must leave the host alive and **zero invocation-owned work running, queued, or able to call back into the exec-unit**.

- Never terminate or stop the host to finish an invocation: no `Environment.Exit`, `Environment.FailFast`, `ExitProcess`, `TerminateProcess`, `exit` / `_exit` / `_Exit` / `quick_exit`, `abort`, `std::terminate`, or fatal signals directed at the host. Do not set process-wide `Environment.ExitCode` for an invocation failure. Use the protocol's failure path when usable, clean up, and return normally.
- Contain ordinary exceptions at the entrypoint and inside every worker, task, callback, and cleanup path. Observe task failures and signal the owner to shut down. No C++ exception may escape the C export; no joinable `std::thread` may reach destruction. Cleanup/destructors must not throw or skip the remaining cleanup after one failure. Catching exceptions does not repair invalid memory access or undefined behavior: validate lengths before allocation/indexing, retain buffers until users finish, and copy borrowed entrypoint arguments needed by workers.
- Protect pipe/socket writes against host-terminating `SIGPIPE` using the platform's per-operation or per-thread mechanism, including pending-signal handling when required. Do not solve this by changing the host's process-wide signal disposition.
- Prefer synchronous work when sufficient. Otherwise retain and join/await every owned thread/task, including workers started inside reused helpers or libraries. No detached threads, fire-and-forget tasks, or untracked `async void` work. `IsBackground = true` does not make a worker safe to unload.
- Track timers, queued continuations, async I/O, event/cancellation handlers, subscriptions, and native callbacks as work too. Unregister/disable their producers and wait for in-flight executions before return; no callback pointer or delegate may remain callable afterward. Idle shared runtime thread-pool threads can remain, but none of this invocation's queued or running work may remain on them.

### Failure-path cleanup before return

**Implement and verify failure cleanup before adding the requested operation.** A handled command/listener error must finish this invocation safely even when configuration parsing, reporting that error, or cleanup itself encounters another failure. The copied scaffold and reused helpers must be audited; their presence is not proof of safe failure handling.

1. Give each invocation one runtime owner with RAII-managed resources and an idempotent, nonthrowing shutdown path. Initialize descriptor/handle state as unowned, transfer each acquired resource to its owner immediately, and install cleanup before connecting, parsing, or starting work. A partially constructed object's destructor does not clean up the object itself: already acquired resources need their own guards. Avoid starting workers in constructors before their ownership and rollback are established.
2. Cover the **whole exported `start` / `run` body** with a C++ exception boundary, including argument copies, runtime construction, `connect`, configuration parsing, execution, encoding, reporting, and teardown. Guard every worker entry and callback separately; failure there signals the owner to shut down. Add a final `catch (...)` for ordinary C++ exceptions beyond named errors. A `noexcept` declaration alone does not handle exceptions. Destructors/cleanup must contain their own failures so unwinding cannot bypass remaining cleanup or destroy a joinable thread.
3. Route every post-acquisition return and exception through the same shutdown owner. Arrange scope guards and member destruction so cancellation, callback draining, and joining finish **before** thread objects or state used by workers are destroyed. A finished but unjoined `std::thread` is still joinable; destroying it terminates the process. Never fix this with `detach`, an empty catch around cleanup, or abandoning work after a timed wait. See the [C++ thread destructor rule](https://eel.is/c++draft/thread.thread.destr).
4. Treat application output/error reporting as bounded, best-effort work on a usable connection. Its encoding, allocation, and send can fail too. Preserve the original operation failure, stop producers, and always reach cleanup even if the peer disconnects during reporting. Keep one reporting owner for the actual listener transport; do not invent command completion messages, recursively report a reporting failure, or retry forever. Release the reporting connection only when its owned sends have completed or been safely cancelled.
5. Prevent memory faults at their source: check nullable arguments and protocol children before dereferencing; validate input lengths, integer conversions, bounds, and allocations; keep borrowed data valid or copy it under the loader's argument contract. Synchronize shared state and retain buffers until their last user finishes. `catch (...)` does not catch Linux `SIGSEGV`/`SIGPIPE` or repair undefined behavior; do not install process-wide fault handlers to pretend otherwise.
6. Protect **every** Linux write path, including the handshake, local-agent exchanges, application output/error frames, and cleanup diagnostics. Handle `EPIPE` as disconnect. For sockets, use the supported per-send suppression mechanism; `MSG_NOSIGNAL` is a socket `send` flag, not a FIFO `write` flag. FIFO writes need a reviewed per-thread signal strategy that preserves the prior mask and pending host signals and consumes only newly generated `SIGPIPE` when required before restoring the mask. Do not set process-wide `SIG_IGN`, even temporarily. Check short reads/writes and interrupted operations as well. See [POSIX write](https://pubs.opengroup.org/onlinepubs/9699919799/functions/write.html), [Linux send](https://man7.org/linux/man-pages/man2/send.2.html), and [signal masks and pending signals](https://man7.org/linux/man-pages/man7/signal.7.html).

Audit each exit with a small failure matrix before declaring the implementation complete:

| Failure point to exercise | Required cleanup evidence |
| --- | --- |
| Invalid arguments, constructor/allocation failure, or first/second connection open failure | Only acquired resources are released; no cleanup dereferences missing state or reports on an unavailable connection. |
| Invalid/truncated configuration or failure just after a reader starts | Already-started work is cancelled, unblocked, drained, and joined before parser/runtime state is destroyed. |
| Requested operation failure or exception in a worker/callback | Host remains alive; one owner shuts down; no exception escapes the C export or worker/callback boundary. |
| Application/agent frame encoding or send fails; peer closes during any write | Broken-pipe handling does not signal-terminate the host; reporting failure cannot skip cleanup or cause an unbounded retry. |
| Stop/disconnect during blocking I/O, a response wait, or retry delay | Each wait has a proven cancellation/unblock path; no self-join, lock-order deadlock, or worker survives return. |
| Cleanup after partial startup, repeated cleanup, and a second invocation | No double close/free, stale descriptor reuse, stale callback, or prior-invocation state remains. |

### Shutdown sequence

Give one owner responsibility for finishing the invocation. Keep its entrypoint alive until all of these steps finish:

1. Stop accepting/scheduling work and signal cancellation, including after partial initialization.
2. Unblock pending FIFO opens, connects, reads, writes, accepts, response waiters, retry delays, and name resolution when used, with a cancellation mechanism supported by that API. Closing a descriptor from another thread is not by itself proof that a blocked operation wakes up. Coordinate descriptor ownership to avoid a later close affecting a reused descriptor.
3. Disable/unregister callback sources and drain in-flight callbacks. A callback signals shutdown; it must not join itself. Do not hold a lock while waiting for a worker that needs that lock to exit.
4. Join/await every owned worker and finish or cancel owned sends while their buffers and state still exist. Check wait results. A cancellation request, completion message, sleep, or expired join timeout is not proof of completion.
5. Release remaining resources and clear their ownership state, then return only after no work can access the exec-unit's code/data. Cleanup must work after failed startup and on repeated calls without throwing or skipping remaining resources.

Design blocking operations for cooperative, bounded cancellation within the supported stop grace period. Do not use `Thread.Abort`, `TerminateThread`, detach, or return with a live worker to bypass a shutdown problem. If a worker cannot be stopped, keep the entrypoint and required state alive while resolving shutdown; record the defect instead of claiming completion or unload safety. Reused examples and a method named `Close` / `Dispose` are not evidence that these rules hold.

### Required lifecycle verification

Before declaring an affected native path complete:

- Audit construction, connection, configuration parsing, execution, application/agent reporting, cleanup, and every return/throw path against the [failure matrix](#failure-path-cleanup-before-return). Record resource/work owners, stop/unblock mechanisms, and join/drain points in project context.
- Use the actual built exec-unit in a compatible host/loader that remains alive after `run` / `start` / `Main` returns. Start with a deliberately failing operation and a peer that disconnects during an application/agent write, then cover applicable matrix rows and normal completion/stop. Failure tests must exercise the real entrypoint and helpers, not only a mocked operation function.
- Immediately unload after return using the loader for the supported artifact format, and repeat load/invoke/unload in the same surviving host. Include a failed invocation followed by a successful one. Do not assume a generic `dlopen`/`dlclose` harness matches a custom mapped-library or shellcode loader.
- Verify the host continues running, every invocation-owned worker has ended, callbacks are unregistered/drained, no invocation work runs after return/unload, and resources do not accumulate across repetitions. Check ownership directly; total process thread count alone is insufficient.
- A hang, host exit, late callback, surviving worker, invalid access, or resource leak fails verification. Keep Docker compilation/build results separate from runtime evidence: a successful build or standalone executable exit does not prove safe failure handling or unloading. If the compatible host/loader is unavailable or unknown, report the exact unverified paths and required runtime test; do not claim stability passed.

## Reusing existing implementations

The [existing plugin map](existing-plugins.md) identifies reference helpers and their native/Java peers. Trace `.projitems` / `.vcxitems` imports and POSIX forwarding includes before choosing a source to edit. An EXE/DLL/shellcode wrapper may only delegate to shared logic; a platform `Main.cpp` may include the canonical POSIX implementation. Include shared sources exactly once and update explicit build manifests when adding files.

Adapt helper namespaces, method casing, callbacks, and ownership to this template. Existing managed helpers can use `load` / `getFullBuffer`, while template methods are `Load` / `GetFullBuffer`. Compare implementations before transplanting them; newer bounded helpers and older compatibility paths coexist. Keep these helpers responsible for the native host IPC protocol. Decode plugin configuration and application payloads separately using the format chosen for the task.

The additional Windows C++ implementation, `start` ABI, scoped pipe ownership,
build artifacts and runtime checks are described in [Windows native DLLs](windows-native.md).
Extend it whenever changing the corresponding managed or Linux behavior.

## Managed Windows files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/win/Program.cs` | `Main` owns runtime/cancellation state; `Initialize` connects and parses configuration; `WaitForStop` keeps the runtime alive while its transport works; `Cleanup` ends sessions and workers. |
| `exec-code/win/exec-unit-utils/CommunicationNamedPipes.cs` | `Connect` opens the agent pipe and reads initial configuration. Preserve bounded complete-frame reads, owned reader lifetime, and close/unblock/join disposal. |
| `exec-code/win/exec-unit-utils/TLV.cs` | `Load` and `GetFullBuffer` decode/encode bounded host IPC envelopes. This helper does not choose the plugin configuration or application payload format. |
| `exec-code/win/exec-unit-utils/CommunicationNamedPipesListener.cs` | Retain/register the constructor callback and `SetCallback`; use the implemented `GetMetadata`, `GetDataToSend`, and `NewDataFromC2` only when adding the traffic channel, and verify response timeout/disconnect handling before use. |
| `exec-code/win/listener-execunit.csproj` | Add new sources as explicit `<Compile Include="RelativePath.cs" />` entries; new files are not automatically compiled. |

The idle `Main` owns its pipe across `Initialize`, `WaitForStop`, and `Cleanup`. `Initialize` validates empty configuration; `WaitForStop` joins the reader until host disconnect. Traffic-channel setup and forwarding remain TODO. Preserve scoped ownership and `QQQWWWEEE` for Java's shellcode patching.

When extending `Main`:

1. Create cancellation/runtime state and register the actual callbacks before starting the pipe reader. Call `Connect`, validate the returned configuration, then initialize the requested transport to Java.
2. Keep both connections alive for their required lifetimes. The pipe reader dispatches local-agent messages; the application transport sends metadata/requests and receives commands from Java. Use a single reader per connection and serialize its writes.
3. Connect transport/pipe disconnects and the chosen retry policy to cancellation. The default registers no `Console.CancelKeyPress` handler. If adding a console convenience handler, retain the actual host disconnect/cancellation path. Unsubscribe any registered handler and drain in-flight calls before returning. Extend the current pipe-reader wait with ownership of, or a wait on, the new channel workers.
4. Preserve the default handling of actual configuration, I/O, and transport failures. The listener helper has no command `sendError`/terminal-message API. Use an established application error message when available, then apply the listener's retry/shutdown behavior; do not invent command completion messages.
5. In `finally`, follow the [shutdown sequence](#shutdown-sequence): cancel, prove reads/waiters unblock, unregister/drain callbacks, join/await workers, and dispose remaining resources. Cleanup must work after partial initialization and repeated calls. A reader callback should signal shutdown rather than wait for itself to terminate.

Custom output belongs in the application transport encoder and Java decoder. If no separate native transport class exists, keep that code in `Program.cs` initially or introduce a clearly owned helper and include it in the project. Do not put arbitrary Java telemetry in `NewDataFromC2`, which sends opaque server data to the local agent.

## Windows native files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/win-native/listener/Main.cpp` | Exported `start(const char*)` owns `CommunicationNamedPipes`, checks connection state after configuration receipt, validates empty input, and waits for disconnect. Its application channel remains TODO. |
| `exec-code/win-native/exec-unit-utils/CommunicationNamedPipes.*` | Copied reference utility owns connection state, framed I/O, response waiters, cancellation and joined reader shutdown. Callback state must remain alive until `close` finishes. |
| `exec-code/win-native/exec-unit-utils/TLV.*`, `Conversions.*`, and `RaiiHelpers.h` | Keep host-envelope decoding bounded and cleanup nonthrowing; document local changes beside these copied sources. |
| `exec-code/win-native/build_windows.sh` and `exports.def` | Add parser/behavior translation units to both architecture builds; keep the undecorated `start` export and x86/x64 artifact names. |

Retain the scoped pipe until added work and callbacks have ended. A failed `connect()` must not be mistaken for valid empty configuration: check `isConnected()` before decoding. Keep the whole `start` body behind an ordinary C++ exception boundary, including partial startup and cleanup. The argument is a local pipe name, and native DLL bytes are never patched. Check the [Windows DLL artifact and lifecycle requirements](windows-native.md) after rebuilding; safe disconnect and immediate unload need runtime evidence.

## Linux files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/linux/listener/Main.cpp` | Extend `serve` inside exported `run(char*, char*)`: preserve scoped connect/configuration validation/reader waiting and add the requested application transport at its TODO. |
| `exec-code/linux/common/CommunicationNamedPipes.h` and `.cpp` | `connect`, `getData`, and `putData` handle framed I/O; `setCallback`/`listenForMessages` dispatch inbound messages; `getMetadata`, `getDataToSend`, `waitForResponseData`, and `newDataFromC2` implement agent exchanges; `close` unblocks and ends owned work. |
| `exec-code/linux/common/TLV.h` and `.cpp` | Preserve the host IPC envelope codec and repair bounds validation where required; plugin payload decoders stay separate. |
| `exec-code/linux/build_linux.sh` | Include any new transport/parser translation units in this exec-unit's compiler invocation; preserve the `run` export and artifact name. |

Apply the [failure-path cleanup gate](#failure-path-cleanup-before-return) while implementing `run`; keep its pipe/runtime state alive until all callbacks/workers finish. The idle path now uses atomic activity state, nonblocking cancellable reads, joined cleanup, and reset descriptor ownership. The default makes no metadata/data requests; before enabling those exchanges, repair `waitForResponseData`'s unbounded `sem_wait` and verify response-wait shutdown, partial startup, and synchronization. Check `sem_wait` results and response pointers before dereferencing; validate optional message children. Read the complete four-byte length prefix before decoding it, cap frame allocation, and release already-open descriptors if initial-frame validation fails. Audit the handshake and other writes as well as connection failure, full I/O, and waiter cancellation. Distinguish valid empty configuration from connection failure. Mirror managed/native Windows behavior for disconnection, reconnection if supported, and shutdown, and follow the [build guide](building.md) to rebuild resources.
