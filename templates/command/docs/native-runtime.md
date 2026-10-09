# Command native implementation map

**Windows C++ policy:** Apply the hard [no authored exceptions requirement](native-memory-safety.md#windows-no-authored-exceptions). The exception boundaries described below provide defensive containment for dependency/runtime failures; they do not authorize project-authored throws or exception-based error handling.

Before changing C++ functions, use the [native memory-safety review](native-memory-safety.md) for buffer lifetimes, checked lengths, allocation/release pairs, API failure handling, and races. It also distinguishes isolated diagnostic evidence from compilation.

Read this when extending the native no-op entrypoints or their IPC helpers. Paths are relative to the plugin root; use the renamed paths in the generated copy. Reuse existing runtime classes when they already implement these responsibilities. The [IPC reference](execunit-ipc.md) defines the wire bytes.

The [current no-op](../README.md#default-behavior) already connects and validates zero configuration bytes, checks its `DONE` result send, selects one terminal outcome, and releases the pipe. Managed Windows uses `finally`; Windows native owns the scoped pipe and final report directly in `start`; Linux uses scoped destruction and a whole-entrypoint exception boundary. Extend `Execute`, Windows native `start`, and Linux `execute` while keeping their completion owners. The optional Linux callback reader is still detached and must be repaired before enabling callbacks.

## Host process and unload requirements

Exec-units run inside an existing host process. The loader may unload their library/code as soon as `Main` / exported `start` / `run` returns. Every success, failure, cancellation, disconnect, and partial-startup path must leave the host alive and **zero invocation-owned work running, queued, or able to call back into the exec-unit**.

- Never terminate or stop the host to finish an invocation: no `Environment.Exit`, `Environment.FailFast`, `ExitProcess`, `TerminateProcess`, `exit` / `_exit` / `_Exit` / `quick_exit`, `abort`, `std::terminate`, or fatal signals directed at the host. Do not set process-wide `Environment.ExitCode` for an invocation failure. Use the protocol's failure path when usable, clean up, and return normally.
- Contain ordinary exceptions at the entrypoint and inside every worker, task, callback, and cleanup path. Observe task failures and signal the owner to shut down. No C++ exception may escape the C export; no joinable `std::thread` may reach destruction. Cleanup/destructors must not throw or skip the remaining cleanup after one failure. Catching exceptions does not repair invalid memory access or undefined behavior: validate lengths before allocation/indexing, retain buffers until users finish, and copy borrowed entrypoint arguments needed by workers.
- Protect pipe/socket writes against host-terminating `SIGPIPE` using the platform's per-operation or per-thread mechanism, including pending-signal handling when required. Do not solve this by changing the host's process-wide signal disposition.
- Prefer synchronous work when sufficient. Otherwise retain and join/await every owned thread/task, including workers started inside reused helpers or libraries. No detached threads, fire-and-forget tasks, or untracked `async void` work. `IsBackground = true` does not make a worker safe to unload.
- Track timers, queued continuations, async I/O, event/cancellation handlers, subscriptions, and native callbacks as work too. Unregister/disable their producers and wait for in-flight executions before return; no callback pointer or delegate may remain callable afterward. Idle shared runtime thread-pool threads can remain, but none of this invocation's queued or running work may remain on them.

### Failure-path cleanup before return

**Implement and verify failure cleanup and terminal reporting before adding the requested operation.** A handled command error must finish this invocation safely even when configuration parsing, reporting that error, or cleanup itself encounters another failure. Use [one completion owner and checked finalization](command-completion.md#one-owner-and-checked-finalization) for every return/exception path. The copied scaffold and reused helpers must be audited; their presence is not proof of safe failure handling or actual completion delivery.

1. Give each invocation one runtime owner with RAII-managed resources and an idempotent, nonthrowing shutdown path. Initialize descriptor/handle state as unowned, transfer each acquired resource to its owner immediately, and install cleanup before connecting, parsing, or starting work. A partially constructed object's destructor does not clean up the object itself: already acquired resources need their own guards. Avoid starting workers in constructors before their ownership and rollback are established.
2. Cover the **whole exported `start` / `run` body** with a C++ exception boundary, including argument copies, runtime construction, `connect`, configuration parsing, execution, encoding, reporting, and teardown. Guard every worker entry and callback separately; failure there signals the owner to shut down. Add a final `catch (...)` for ordinary C++ exceptions beyond named errors. A `noexcept` declaration alone does not handle exceptions. Destructors/cleanup must contain their own failures so unwinding cannot bypass remaining cleanup or destroy a joinable thread.
3. Route every post-acquisition return and exception through the same shutdown owner. Arrange scope guards and member destruction so cancellation, callback draining, and joining finish **before** thread objects or state used by workers are destroyed. A finished but unjoined `std::thread` is still joinable; destroying it terminates the process. Never fix this with `detach`, an empty catch around cleanup, or abandoning work after a timed wait. See the [C++ thread destructor rule](https://eel.is/c++draft/thread.thread.destr).
4. Require exactly one checked success or failure completion on every path with a usable connection, including success with no result payload. Error text is optional and bounded; an error-text encoding/allocation failure must not suppress failure completion while the transport remains usable. Preserve the original operation failure and give finalization one owner. Observe actual full-frame write/flush outcomes; calling a send helper does not prove a frame was written, and a complete local write is not a host acknowledgement. Do not recursively report a reporting failure or retry a terminal frame after an incomplete/uncertain write has made the stream unusable. Always reach cleanup; keep the reporting connection and any required transport work alive until sends have completed or safely failed.
5. Prevent memory faults at their source: check nullable arguments and protocol children before dereferencing; validate input lengths, integer conversions, bounds, and allocations; keep borrowed data valid or copy it under the loader's argument contract. Synchronize shared state and retain buffers until their last user finishes. `catch (...)` does not catch Linux `SIGSEGV`/`SIGPIPE` or repair undefined behavior; do not install process-wide fault handlers to pretend otherwise.
6. Protect **every** Linux write path, including the handshake, result/error/completion frames, and cleanup diagnostics. Handle `EPIPE` as disconnect. For sockets, use the supported per-send suppression mechanism; `MSG_NOSIGNAL` is a socket `send` flag, not a FIFO `write` flag. FIFO writes need a reviewed per-thread signal strategy that preserves the prior mask and pending host signals and consumes only newly generated `SIGPIPE` when required before restoring the mask. Do not set process-wide `SIG_IGN`, even temporarily. Check short reads/writes and interrupted operations as well. See [POSIX write](https://pubs.opengroup.org/onlinepubs/9699919799/functions/write.html), [Linux send](https://man7.org/linux/man-pages/man2/send.2.html), and [signal masks and pending signals](https://man7.org/linux/man-pages/man7/signal.7.html).

Audit each exit with a small failure matrix before declaring the implementation complete:

| Failure point to exercise | Required cleanup evidence |
| --- | --- |
| Invalid arguments, constructor/allocation failure, or first/second connection open failure | Only acquired resources are released; no cleanup dereferences missing state or reports on an unavailable connection. Verify the compatible host makes an invocation that cannot establish its result channel visibly fail. |
| Invalid/truncated configuration or failure just after a reader starts | One failed completion is written if the reporting channel remains usable; already-started work is cancelled, unblocked, drained, and joined before parser/runtime state is destroyed. |
| Requested operation failure or exception in a worker/callback | Host remains alive; one owner records failure and finalizes it; no exception escapes the C export or worker/callback boundary. |
| Result encoding, error send, or terminal send fails; peer closes during any write | An encoding failure with a healthy channel still reaches failure completion. A broken or partially written stream is not retried as a new terminal frame; verify host-visible transport failure. Broken-pipe handling does not terminate the host; reporting failure cannot skip cleanup or cause unbounded retries. |
| Stop/disconnect during blocking I/O, a response wait, or retry delay | Each wait has a proven cancellation/unblock path; no self-join, lock-order deadlock, or worker survives return. |
| Cleanup after partial startup, repeated cleanup, and a second invocation | No double close/free, stale descriptor reuse, stale callback, or prior-invocation state remains. |

### Shutdown sequence

Give one owner responsibility for finishing the invocation, and preserve the reporting channel through terminal finalization. Separate operation workers from transport work needed to finish reporting; joining a writer that still awaits finalization before requesting its final send can deadlock. Keep the entrypoint alive until all of these steps finish:

1. Stop accepting/scheduling work and signal cancellation, including after partial initialization.
2. Unblock operation I/O, response waiters, retry delays, and name resolution when used, with a cancellation mechanism supported by that API. Preserve the writable reporting path when still usable; cancel its I/O when required by a transport failure. Closing a descriptor from another thread is not by itself proof that a blocked operation wakes up. Coordinate descriptor ownership to avoid a later close affecting a reused descriptor.
3. Disable/unregister operation callback sources, drain in-flight callbacks, join/await operation workers, and collect their failures before choosing success. A callback signals shutdown; it must not join itself. Do not hold a lock while waiting for a worker that needs that lock to exit. Retain only transport work required to complete the remaining reporting.
4. Finish required result sends, check their outcomes, then finalize exactly one terminal success/failure through the [completion owner](command-completion.md#one-owner-and-checked-finalization). No results may follow it. A command with no output still sends completion. Keep buffers, reporting state, and required reader/writer work alive until terminal write/flush has completed or failed. If the connection was never established or is broken, verify the compatible host's failure handling instead of pretending a native completion was delivered.
5. Cancel/unblock remaining transport I/O, unregister/drain its callbacks, and join/await every remaining owned worker. Check wait results; a cancellation request, completion message, sleep, or expired join timeout is not proof of completion. A cleanup error after a terminal frame was sent must not produce a second/opposite terminal frame.
6. Release remaining resources and clear their ownership state, then return only after no work can access the exec-unit's code/data. Cleanup must work after failed startup and on repeated calls without throwing or skipping remaining resources.

Design blocking operations for cooperative, bounded cancellation within the supported stop grace period. Do not use `Thread.Abort`, `TerminateThread`, detach, or return with a live worker to bypass a shutdown problem. If a worker cannot be stopped, keep the entrypoint and required state alive while resolving shutdown; record the defect instead of claiming completion or unload safety. Reused examples and a method named `Close` / `Dispose` are not evidence that these rules hold.

### Required lifecycle verification

Before declaring an affected native path complete:

- Audit construction, connection, configuration parsing, execution, result/error/terminal reporting, cleanup, and every return/throw path against the [failure matrix](#failure-path-cleanup-before-return). Record resource/work owners, stop/unblock mechanisms, and join/drain points in project context.
- Run the [completion regression checks](command-completion.md#required-completion-tests), asserting actual terminal wire frames and the host's final command state. Healthy-channel completion must occur once on success, empty success, configuration/operation/worker failure, cancellation, and failure after partial startup. Logs, return codes, helper calls, parser completion, and successful cleanup alone do not prove command completion. If no reporting channel exists or it fails, verify host-visible failure rather than a command left running; report unavailable host checks explicitly without inventing an acknowledgement or fallback API.
- Use the actual built exec-unit in a compatible host/loader that remains alive after `run` / `start` / `Main` returns. Start with a deliberately failing operation and a peer that disconnects during error reporting, then cover applicable matrix rows and normal completion/stop. Failure tests must exercise the real entrypoint and helpers, not only a mocked operation function.
- Immediately unload after return using the loader for the supported artifact format, and repeat load/invoke/unload in the same surviving host. Include a failed invocation followed by a successful one. Do not assume a generic `dlopen`/`dlclose` harness matches a custom mapped-library or shellcode loader.
- Verify the host continues running, every invocation-owned worker has ended, callbacks are unregistered/drained, no invocation work runs after return/unload, and resources do not accumulate across repetitions. Check ownership directly; total process thread count alone is insufficient.
- A hang, host exit, late callback, surviving worker, invalid access, or resource leak fails verification. Keep Docker compilation/build results separate from runtime evidence: a successful build or standalone executable exit does not prove safe failure handling or unloading. If the compatible host/loader is unavailable or unknown, report the exact unverified paths and required runtime test; do not claim stability passed.

## Reusing existing implementations

The [existing plugin map](existing-plugins.md) identifies reference helpers and their native/Java peers. Trace `.projitems` / `.vcxitems` imports and POSIX forwarding includes before choosing a source to edit. An EXE/DLL/shellcode wrapper may only delegate to shared logic; a platform `Main.cpp` may include the canonical POSIX implementation. Include shared sources exactly once and update explicit build manifests when adding files.

Adapt helper namespaces, method casing, callbacks, and ownership to this template. Existing managed helpers can use `load` / `getFullBuffer`, while template methods are `Load` / `GetFullBuffer`. Compare implementations before transplanting them; newer bounded helpers and older compatibility paths coexist. The native helpers own host envelope handling; command configuration and result payloads use the representation agreed with Java.

The additional Windows C++ implementation, `start` ABI, scoped pipe ownership,
build artifacts and runtime checks are described in [Windows native DLLs](windows-native.md).
Extend it whenever changing the corresponding managed or Linux behavior.

## Managed Windows files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/win/Program.cs` | `Main` owns the runtime; `Initialize` connects and parses configuration; `Execute` performs the command; one finalization owner uses `Complete` or equivalent for either terminal outcome; `Cleanup` disposes owned resources. |
| `exec-code/win/exec-unit-utils/CommunicationNamedPipes.cs` | `Connect` opens the pipe and reads the initial frame; extend its shared frame I/O and connection state here. `Close`/`Dispose` cancel and release the connection safely. |
| `exec-code/win/exec-unit-utils/TLV.cs` | `Load` and `GetFullBuffer` support the host IPC envelope inside the native helper. Preserve its type/parent-bit and length rules; these helpers do not prescribe the command payload format. |
| `exec-code/win/exec-unit-utils/CommunicationNamedPipesCommand.cs` | Use the checked `sendResult`, `sendError`, `sendReturnSuccess`, and `sendReturnFailed` helpers. Retain the constructor's update/stop callbacks and dispatch received messages to them. Add the handling-option methods here when the command needs streaming or stop support. |
| `exec-code/win/command-execunit.csproj` | Add each new source as `<Compile Include="RelativePath.cs" />` alongside `Program.cs`. This project does not automatically include new C# files. |

The no-op `Main` owns its pipe across `Initialize`, `Execute`, `Complete`, and `Cleanup`. `Initialize` validates zero payload bytes; `Execute` is the extension point. `Complete` checks one selected terminal send, and `finally` disposes resources even after startup/reporting failures. No callbacks are registered, so no reader worker starts. Keep the `QQQWWWEEE` string available for Java's shellcode patching.

Preserve this ordering when extending `Main`:

1. Install cleanup and the completion owner before startup. Create the cancellation/runtime state and pipe, register update/stop callbacks if used, call `Connect`, then parse the returned configuration bytes. Track connection state separately from empty configuration.
2. Send the necessary handling options before execution produces results. Run the operation while keeping the pipe and any reader worker alive.
3. On every exit path, stop operation producers, unblock and drain their callbacks, join their workers, and collect errors. Finish queued result writes and check their outcomes before terminal success. Keep the reporting pipe and transport reader/writer work needed for finalization alive.
4. The single owner sends one success completion, including for zero output, or one failure completion for an unsuccessful invocation. Attempt concise error text before failure completion, but contain text-encoding failure separately so it cannot suppress the terminal frame on a usable pipe. `Execute` and `Complete` must not both finalize. Check complete-frame writes and required drain; if a write partially fails, do not append or retry a terminal frame on the damaged stream.
5. Route real validation, I/O, and execution errors through that finalizer, as the default exception handler does. If startup or reporting transport fails, native delivery is unavailable: verify the actual host's visible failure handling and report any gap. Do not use a host process exit code, stderr, or an invented acknowledgement as command completion.
6. After reporting completes or becomes impossible, cancel/unblock remaining transport work, unregister/drain its callbacks, join/await all remaining workers, and dispose resources in `finally`. Make cleanup safe after partial initialization and repeated calls. Do not wait for a worker from that same worker's callback; callbacks should signal the owner to shut down.

Keep the initial configuration read and subsequent reader loop under one reader owner. Serialize result, error, option, and completion writes so concurrent sends cannot interleave frame bytes. A stop callback signals cancellation; the command's main execution path decides its documented terminal outcome and finishes within the advertised grace period.

## Windows native files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/win-native/command/Main.cpp` | Exported `start(const char*)` owns the scoped pipe, checks startup and empty configuration, sends `DONE`, and selects one terminal outcome. The no-op registers no callbacks. |
| `exec-code/win-native/exec-unit-utils/CommunicationNamedPipesCommand.*`, `CommunicationNamedPipes.*`, and `TLV.*` | Copied reference utilities own the local-agent framing, callbacks, bounded I/O, cancellation and joined reader cleanup. Record local changes beside the copied sources. |
| `exec-code/win-native/build_windows.sh` and `exports.def` | Add parser/behavior translation units to both architecture builds; keep the undecorated `start` export and x86/x64 artifact names. |

Keep the pipe alive through final reporting; its destructor cancels and joins the reader before `start` returns. Preserve the completion owner even when parsing or result/error reporting fails; a failed partial write disables further reporting. The `start` argument is the local pipe name, and native DLL bytes are never patched. Check the [Windows DLL artifact and lifecycle requirements](windows-native.md) after rebuilding; reader shutdown and safe unload need runtime evidence.

## Linux files and methods

| File | Place to implement or extend |
| --- | --- |
| `exec-code/linux/command/Main.cpp` | Extend `execute` inside exported `run(char*, char*)`; retain its scoped pipe, configuration validation, exception boundary, and single terminal owner. |
| `exec-code/linux/common/CommunicationNamedPipes.h` and `.cpp` | `connect`, `getData`, and `putData` handle framed I/O; `sendResult`/`sendError`/terminal methods send command messages; `setCallbackNewData`, `setCallbackStop`, `startListenerIfNeeded`, and `listenForMessages` control callbacks/readers; `close` ends ownership. |
| `exec-code/linux/common/TLV.h` and `.cpp` | The existing codec handles native host envelopes. Keep it inside the transport boundary; command payload parsing is separate. |
| `exec-code/linux/build_linux.sh` | Add new translation units to the compiler invocation for this exec-unit; preserve its exported `run` and output artifact name. |

Apply the [failure-path cleanup gate](#failure-path-cleanup-before-return) while extending `run`: the default already uses an exception boundary and scoped pipe destruction. Register callbacks before `connect()` when needed. Review failed-connect versus valid-empty-configuration handling, partial I/O, and all write paths including the handshake. Read the complete four-byte length prefix before decoding it, cap frame allocation, and release already-open descriptors if initial-frame validation fails. The no-op registers no callbacks. Before enabling callbacks, replace the optional `startListenerIfNeeded` detached reader with owned work whose cancellation/unblocking and join finish before `run` returns. Synchronize shared state; a plain boolean shutdown flag is not sufficient. Audit helpers called from error reporting and cleanup as carefully as the operation itself.

The bundled Linux `sendResult`, `sendError`, `sendReturnSuccess`, and `sendReturnFailed` return checked `bool` outcomes. `putData` completes interrupted/partial writes or disables the failed stream; all FIFO writes protect the calling thread against generated `SIGPIPE`. Preserve checked outcomes when extending these paths. Complete local writes are not host acknowledgements; verify the host-observed terminal state separately. Keep valid empty configuration/output distinct from missing connection/completion.

Use the same success/failure and cancellation semantics as Windows. The no-op has no completion sleep. If adding an asynchronous sender, drain its owned queue and join it using actual transport write semantics before closing. Follow the [build guide](building.md) to rebuild the native resource after changing any implementation.
