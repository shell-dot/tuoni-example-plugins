# Listener Java implementation map

Read this for Java lifecycle, application transport, and listener presentation changes. Paths below are relative to the plugin root. The existing class is `java-plugin/src/main/java/com/example/tuoni/listener/TemplateListener.java`; reuse its current collaborators if behavior has already been implemented.

The [current default](../README.md#default-behavior) retains ID/context, starts in `CREATED`, and synchronizes start/stop/delete/reconfigure. Repeated start/stop calls and restart after stop are supported; deletion is terminal. `reconfigure({})` returns the same instance and preserves status; valid replacement encoding returns zero payload bytes. `getInfo()` shows `Listener template <id>: <status>`. No endpoint, session, or worker is owned, and `STARTED` does not assert native health. The table below describes extensions for a requested data traffic channel.

## Lifecycle methods

| Place in `TemplateListener.java` | Responsibility |
| --- | --- |
| Constructor | Retain the listener ID, validated configuration, and `ListenerContext`. Declare the transport, active-session collection, and worker ownership fields needed by this listener. Avoid starting background work before `start()`. |
| `start()` | Acquire the transport resources, then start owned workers. Set `STARTED` only after successful initialization. Unwind partially acquired resources on failure and throw `ExecutionException` with the cause. Make repeated calls consistent with the current lifecycle. |
| `stop()` | Signal cancellation, close transport/session resources that unblock reads or accepts, terminate and await owned workers, clear active sessions, then publish `STOPPED`. Handle partial startup and repeated calls safely. |
| `delete()` | Perform shutdown and release remaining listener-owned state, then publish `DELETED`. Preserve a defined policy for attempts to start a deleted listener. |
| `getStatus()` / `getInfo()` | Read a consistent state snapshot. Keep Java resource status distinct from received native observations. Synchronize snapshots or use immutable/atomic state when receive workers update presentation data. |
| `reconfigure()` | Follow the configuration skill for candidate validation, resource replacement, rollback, and native delivery. Reconfiguration must coordinate with start/stop and current workers. |

Store worker/session references before they can need cleanup. Avoid waiting for a worker while holding a lock that worker needs to exit. A failed receiver worker must notify the owning listener/session rather than leave status permanently indicating a healthy resource.

## Locate or introduce the receiver

The fresh template has no Java application receiver. After choosing the transport required by the user, extend existing files or introduce these **suggested new files** in `java-plugin/src/main/java/com/example/tuoni/listener/`:

| Suggested file | Responsibility |
| --- | --- |
| `TemplateListenerConnectionHandler.java` | One application session: decode incoming messages, resolve its agent, submit opaque requests, send queued commands, then close and remove the session from the listener-owned active-session collection. |
| `TemplateListenerFrameCodec.java` | Application field mapping and full-frame reads/writes using the chosen payload format, with bounds and compatibility handling. Match every native sender/receiver. |
| `TemplateListenerTelemetry.java` | Typed custom observations when the requested output needs them; omit this class if there is no telemetry. |

These files do not exist until implemented. Gradle compiles new Java sources under `src/main/java` automatically. Keep their package aligned with `TemplateListener.java`, and wire handler creation into the actual transport startup/accept path. Use Java standard APIs for UTF-8/binary payloads or a declared bundled JSON parser, following [payload boundaries](execunit-ipc.md#plugin-payloads-and-host-ipc). Java handles the application transport and inner configuration bytes, not the local-agent pipe/FIFO envelope.

## SDK receive and command-send recipe

Follow [Java verification](java-verification.md) for dependency ownership, packaged-JAR loading and actual startup order. The reviewed host reads listener examples/schema before `init`; metadata must not require initialized context. Use the current SDK signatures; the following calls are available in SDK 0.15.0. Import `Agent`, `SerializedCommand`, and `SendStatus` from `com.shelldot.tuoni.plugin.sdk.listener`.

1. Decode one complete, bounded application message. Keep its opaque agent metadata and request bytes separate from custom telemetry.
2. Call `listenerContext.readMetadata(ByteBuffer.wrap(metadataBytes))`. It returns `Optional<AgentMetadata>`; an empty value is invalid metadata, not a new agent with default fields.
3. Resolve `listenerContext.findRegisteredAgent(metadata.guid())`; otherwise call `listenerContext.registerAgent(metadata.guid(), metadata)` and handle registration failure. Bind the session to the resolved identity or explicitly implement identity changes/multiplexing; do not accidentally submit a second agent's data through the first `Agent` object.
4. For an opaque agent request, call `agent.submitSerializedRequest(metadata, ByteBuffer.wrap(requestBytes))`; a metadata-only request may pass `null` as its second argument. Check `agent.getStatus().isBlocked()` before processing/delivery. Handle both its synchronous `InvalidRequestException` and failures of its returned `CompletableFuture<Void>`. For example, wait in a dedicated session worker or chain bounded asynchronous work; do not accumulate unobserved futures indefinitely. Route custom telemetry to the plugin's own decoder instead.
5. In the reverse direction, retrieve commands through `agent.getCommandQueue().pollCommand(timeout, TimeUnit.SECONDS)` or the SDK queue subscription API. The type is `AgentCommandQueue`. An empty poll means no command is currently available (including an inactive agent), not evidence of transport disconnect. Read only the `remaining()` bytes of `command.getSerializedBytes()`; using a duplicate avoids changing the SDK buffer's position.
6. Write the command using the application protocol, protecting the entire frame from concurrent writes. After the required local send/flush completes, call `command.setSendStatus(SendStatus.successful(Instant.now()))`. This reports sending, not execution by the agent.
7. On send failure, call `command.setSendStatus(SendStatus.failure(error, Instant.now(), retryAllowed))`. Select `retryAllowed` according to the transport and existing retry/deduplication policy; a partial send can have an uncertain outcome. Handle a command already dequeued when cancellation occurs rather than silently abandoning its status.
8. Close failed sessions, remove them from the listener-owned active-session collection, and unblock the sender/receiver workers. Preserve interruption (`Thread.currentThread().interrupt()`) when handling `InterruptedException`.

An implementation may use an event loop instead of paired workers; retain the same ownership, bounded work, and send-status behavior. Do not add a second consumer of a session's command queue just to send telemetry.

For a small blocking session worker, steps 2-4 can be written as the following helper inside the connection handler. It assumes that handler retains `ListenerContext listenerContext`. `Agent` comes from `sdk.listener`; `AgentRegistrationException` and `InvalidRequestException` come from `sdk.common.exceptions`. The fully qualified future exception avoids confusing it with the SDK lifecycle exception. The caller closes the failed session on an exception and restores the interrupt flag on interruption.

```java
private Agent submitAndWait(byte[] metadataBytes, byte[] requestBytes)
    throws java.io.IOException, AgentRegistrationException, InvalidRequestException,
        InterruptedException, java.util.concurrent.ExecutionException {
  var metadata = listenerContext.readMetadata(ByteBuffer.wrap(metadataBytes))
      .orElseThrow(() -> new java.io.IOException("Invalid agent metadata"));
  var existing = listenerContext.findRegisteredAgent(metadata.guid());
  Agent agent = existing.isPresent()
      ? existing.get()
      : listenerContext.registerAgent(metadata.guid(), metadata);
  if (agent.getStatus().isBlocked()) {
    throw new java.io.IOException("Agent is blocked");
  }
  ByteBuffer request = requestBytes == null ? null : ByteBuffer.wrap(requestBytes);
  agent.submitSerializedRequest(metadata, request).get();
  return agent;
}
```

Bind the returned agent to the session according to its identity policy; do not add another command-queue consumer on every request. Here the decoder supplies independent byte arrays, so they remain valid until `.get()` completes. Do not block an event loop with this helper: an asynchronous HTTP handler uses the processing future's completion to schedule its response, retaining any pooled body until then. See [request/response ordering](implementation-recipes.md#application-payloads-and-framing).

## Connection state and reconfiguration

The [existing listener patterns](existing-plugins.md#transport-and-lifecycle) map Java connection, native transport, and configuration peers. Keep parser phase, incomplete bytes, agent identity, queue subscription, pending writes, and close state owned by the connection. If using `Flow`, bound demand or buffered bytes and cancel subscriptions on close; do not inherit an unlimited queue simply because a reference requests unlimited demand. Correlated request state needs both expiry and a capacity/byte bound.

Retain partial prefix/body writes until complete before marking `SendStatus.successful`. On failure or shutdown, settle pending sends under the established retry policy; a partially written message has an uncertain delivery outcome. Use the buffer's remaining bytes and an independent view whose byte order is explicitly set.

For resource replacement, validate and construct the candidate first. Coordinate the required stop/start sequence, publish the replacement only after success, and restore the prior usable state when required. The presence of a `Reloadable*` wrapper alone does not prove rollback works: test a replacement that cannot bind and inspect the old listener afterward. Native live-update delivery is a separate path that also needs validation.

## Available presentation surfaces

| Requested result | Java location/API |
| --- | --- |
| Listener summary or current observed values | Update typed listener state in the receiver; format a snapshot in `TemplateListener.getInfo()`, which returns a `String`. Include observation time/state when absence or staleness matters. |
| Agent activity | `listenerContext.getActivityLogger().logAgentActivity(UUID, Collection<AgentEvent>, ListenerInteraction)` |
| File activity event | `logFileActivity(String, Collection<FileEvent>, ListenerInteraction)` |
| Payload activity | `logPayloadActivity(long, Collection<PayloadEvent>, ListenerInteraction)` |
| Invalid activity | `logInvalidActivity(Collection<InvalidEvent>, ListenerInteraction)` |
| Downloadable bytes or richer output | Use an existing plugin/UI facility that actually supports them, or establish that facility as part of the requested work. A file activity event records an event; it does not itself store or expose the file bytes. |

The activity APIs require supported SDK event and interaction objects. Inspect their current constructors/factories before creating events; there is no generic `log(String)` or listener `parseResult` API. Preserve requested native facts through the transport and typed model even when presentation is compact. Validate normal agent traffic alongside custom telemetry, failed/partial sends, invalid metadata, lifecycle failure cleanup, and whatever output surface is actually used.
