# Always finish a command with an explicit outcome

Apply this gate to every command implementation and every configuration, logic or output change. Before `Main`, `start`, or `run` returns, the exec-unit must send one checked `sendReturnSuccess()` on success or `sendReturnFailed()` on failure while its reporting connection is usable. **`sendError(...)` only sends diagnostic text; it does not mark the command failed and never replaces `sendReturnFailed()`.** Reaching the end of the entrypoint, closing a pipe, sending text, or logging an exception is not completion. Implement this in every supported exec-unit and test the host-visible command state. For startup or disconnect failures that prevent delivery, use the host failure path described below.


The default already checks `sendResult` for exact UTF-8 `DONE` and then one selected terminal send. Success is selected only after the result write succeeds; failures attempt diagnostic text and failure completion on a usable connection. Java displays `DONE` independently of terminal status. Preserve this ordering when extending the operation.

## One owner and checked finalization

Give each invocation one completion owner and initialize its outcome to failure until the requested operation and required result writes actually succeed. Install the finalizer before startup and route every return, exception, cancellation and stop path through it, including construction, connection and partial-initialization failures. When no reporting channel exists, apply the host-visible failure handling below. Prefer structured control flow with RAII/finally cleanup over early returns scattered through helpers. Workers and callbacks notify the owner; they do not independently send terminal frames.

Track **outcome**, **terminal send started**, **complete terminal frame written**, and **transport failure** separately. A flag set before calling a send method, or a send method returning normally, is not evidence that a frame was written. Repeated finalization must not emit another terminal outcome. Serialize writes so concurrent output cannot interleave with completion.

Use the existing [command IPC messages](execunit-ipc.md#command-messages):

| Execution outcome | Required report on a usable connection |
| --- | --- |
| Operation succeeds, including no matches, zero rows, or no output | Finish any result writes, then exactly one `sendReturnSuccess` |
| Invalid configuration after the connection is established, partial initialization failure, operation/worker exception, or required output encoding/write failure | A useful `sendError` when possible, then exactly one `sendReturnFailed` |
| Cancelled, stopped or timed out before requested work is complete | Exactly one failure completion unless the existing documented command contract treats that stop as successful completion; never fall through to success by default |
| Error-text formatting/allocation fails while transport is still usable | Still send the minimal failure completion; diagnostic text is not a prerequisite |

`sendResult`, `sendError`, stderr/stdout, a C# process return value, a Java `parseResult` call, and `isFinalResult` are not substitutes for the command's terminal success/failure message. An empty successful command needs no invented result payload, but it still needs success completion.

Implement finalization in this order, coordinated with [failure-path cleanup](native-runtime.md#failure-path-cleanup-before-return):

1. Stop operation producers and callbacks, cancel/unblock their pending work, and join/drain operation workers. Collect their failures before deciding success. Keep the reporting connection and any transport machinery needed for the final send alive; do not close it in generic cleanup first.
2. Finish required result writes and pre-terminal cleanup that can change the outcome. Failed required work or result encoding must select failure. Do not send success early and then discover a failed worker. No result/error data may follow the terminal frame.
3. If the selected outcome is failure, attempt bounded diagnostic reporting without allowing a formatting exception to skip terminal completion. Prepare a small failure-completion path that does not depend on building a large error string or allocating a new result object.
4. On a usable connection, send exactly one selected terminal frame and check the **complete frame** write/drain result. A terminal write is mandatory, not optional best effort. If a diagnostic send irrecoverably broke the stream, follow the transport-failure path below instead of appending bytes to a damaged frame.
5. Once the terminal frame has been fully written, finish transport shutdown: disable/drain remaining callbacks, unblock and join any retained transport workers, close owned resources, and only then return. A completed terminal send does not permit live work to survive unloading. Do not emit a second or opposite terminal outcome if later teardown reports a defect; record and fix that defect.

The bundled result/error/terminal helpers return `bool`; check it at each required send. Windows flushes synchronous writes; Linux loops over interrupted/partial writes and protects the calling thread against generated `SIGPIPE`. Failed writes disable further reporting. Preserve these contracts when extending the helpers. A mock counting calls to `sendReturnSuccess` cannot establish host receipt or final state.

## Make transport failures observable

Do not mark completion sent if the helper is inactive, a write fails, or only part of the frame was written. Normal short writes need a correct full-write loop. After an irrecoverable partial-frame failure, the stream is unusable: do not blindly retransmit the whole frame, send a contradictory outcome, or retry forever. Finish safe cleanup without terminating the host.

Sending every byte to the transport is not proof the remote host processed it. Honor an existing acknowledgment/drain contract when present, but do not invent an acknowledgment message or use a fixed sleep as evidence. The integration test must inspect what the compatible host actually received and its terminal state.

A command cannot send through a connection that never opened or has permanently disconnected. Cover these cases through the **actual supported host/SDK startup, disconnect or timeout failure path**, and verify the command becomes observably failed instead of staying pending/running forever. Do not assume EOF automatically sets failure. If no such mechanism is present or it cannot be tested, record the reporting defect or verification gap explicitly; do not claim every outcome is reported. Do not invent Java status APIs, reconnect/replay an invocation, or change host protocol IDs merely to hide the gap.

## Required completion tests

Use the actual exec-unit helpers and a compatible host/pipe peer. For each usable-channel case, assert the exact terminal frame count is **one**, that it matches success/failure, that all required output precedes it, and that no output follows it. Also verify the host exits its pending/running state with the expected final outcome.

Cover at least:

- Normal success and success with no result data.
- Invalid configuration after connection, partial startup, operation failure and worker/callback failure.
- Early returns, required output encoding failure, and diagnostic encoding failure with a still-usable channel.
- Cancellation/timeout, repeated finalization, and competing stop/worker completion notifications.
- Broken connection before reporting, during an error send and during a terminal frame; confirm no false delivery flag, duplicate/replayed completion, host crash or endless pending state.

Verify failure followed by a new successful invocation and immediate unload safety as part of the [lifecycle checks](native-runtime.md#required-lifecycle-verification). Check Java output formatting and the host's final command state separately; a visible error string alone does not prove failure completion. Record terminal-observation fixtures, actual host outcomes and unavailable checks in [project context](project-context.md). Keep the full Docker build and [Java initialization checks](java-verification.md) required; neither proves command completion was reported.
