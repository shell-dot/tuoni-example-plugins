# Listener exec-unit IPC and Java transport

Read this when implementing configuration updates, listener behavior, or output. There are two separate connections:

```text
local agent <-- named pipe / FIFO --> native listener exec-unit
native listener exec-unit <-- plugin transport --> Java listener receiver
```

The native helper retrieves opaque agent metadata/data and supplies incoming server data to the local agent. User-visible native telemetry must reach the Java receiver through a transport it actually handles.

## Plugin payloads and host IPC

Choose the plugin's configuration, application data, and telemetry encoding to fit the task: UTF-8 text, JSON, or explicit binary fields. Record field meanings, limits, units, and message boundaries. Use Java standard APIs for text/binary; declare and bundle a JSON library when needed. The SDK provides no Java TLV classes. Do not add a Tuoni TLV dependency, vendor server codecs, or ask for a server checkout to encode plugin payloads.

Java generation/update methods supply **inner configuration bytes**. The SDK/agent wraps them for the native pipe/FIFO; `Connect()` / `connect()` returns the unwrapped bytes. Java never adds or parses that IPC envelope. Listener application transport is a separate connection with its own agreed framing; pass SDK-owned metadata, requests, and commands through unchanged.

The native helpers retain the host-controlled protocol below. Their `TLV.cs` and `TLV.h`/`.cpp` implement that host envelope only; complete or repair those helpers as required for IPC compatibility. Their presence does not prescribe the plugin payload format.

## Connection and framing

These conventions describe the bundled helpers. Verify any changes against the plugin's current host/SDK version.

- Windows uses one duplex named pipe. Open a `NamedPipeClientStream` for the patched pipe name, then read the initial frame. The Windows examples do not send the Linux readiness byte. Keep the UTF-16LE `QQQWWWEEE` placeholder and its encoded length compatible with `ShellcodeResource`.
- Linux's exported `run(char* pipeNameRead, char* pipeNameWrite)` receives two FIFO paths. Open the read FIFO, then the write FIFO, write one readiness byte `0x00` to the write FIFO, then read the initial frame.
- Each subsequent frame is `uint32_le frameLength` followed by exactly that many TLV bytes; the length excludes its own four bytes. The initial frame wraps the bytes provided by Java's `ExecUnit.configuration` / `ShellCodeWithConf`. `Connect()` / `connect()` unwraps the outer TLV and returns its value. Parse the plugin's configuration inside that value without adding another IPC frame.
- A TLV is `uint8 typeAndFlags | uint32_le valueLength | value`. Bit `0x80` denotes a parent whose value is consecutive child TLVs. Logical type IDs are `0x00..0x7f`; mask off the parent bit when dispatching. Lengths count bytes, not characters. These are host IPC message IDs, not fields in plugin configuration.
- Read and write all bytes, including length prefixes: stream operations may complete partially. Bound frame size and nesting before allocation, validate each child's length against its parent, reject truncated/invalid data, and distinguish a valid empty configuration from a failed connection. The included Linux helpers need review for these conditions; the Windows helpers in a fresh template are stubs.
- Keep a single reader per connection and serialize writes. On failure/cancellation, unblock pending reads and response waiters, cooperatively stop and join/await workers, and release resources only after no owned work can access them. Apply the [host process and unload requirements](native-runtime.md#host-process-and-unload-requirements) before entrypoint return. Completion and disposal must be safe after partial initialization.

## Listener messages

Types below are logical IDs. Existing helper names are PascalCase in C# and camelCase in C++.

| Direction | Type | Value / handling |
| --- | --- | --- |
| Exec-unit to agent | `0x21` parent | Request metadata: child `0x01` is one byte `1`; child `0x02` is a four-byte little-endian sequence number. `GetMetadata` / `getMetadata`. |
| Exec-unit to agent | `0x22` parent | Request data to transmit: same request children. `GetDataToSend` / `getDataToSend`. |
| Agent to exec-unit | `0x21` / `0x22` parent | Response: correlate child `0x02` with the pending request; child `0x04` contains returned bytes. Handle absent data and connection failure distinctly. |
| Exec-unit to agent | `0x23` leaf | Opaque data received from the Java/server transport. `NewDataFromC2` / `newDataFromC2`. This direction does not send custom output to Java. |
| Agent to exec-unit | `0x20` parent | Dispatch child `0x04` to `SetCallback` / `setCallback`. The shipped helper exposes a generic callback; verify its payload semantics against the current host before treating it as a configuration update. |

Register callbacks before starting the reader. Validate required children and their lengths before dispatch. Response waiters need timeout/disconnect handling, and shutdown must wake them. The bundled listener helpers do not define a command-style `0x3f` stop event; use the actual host/transport cancellation or disconnect path rather than inventing one.

## Java receive path and output

Inspect the current native transport sender and Java connection handler before changing output. The SDK's `ExecUnitListener` has no command-style `parseResult`, but a Java listener can parse its own transport frames. Choose application framing to match the requested transport and existing peers. The following describes the existing TCP example; it can be implemented with ordinary stream and byte-buffer APIs:

1. On each TCP connection, native code first sends the configured raw handshake bytes (possibly empty), then `uint32_le metadataLength | metadata` with no data frame. Java consumes the handshake and this first metadata-only message to find/register the agent. It must not wait for a data frame before registration.
2. Later native sends are `uint32_le metadataLength | metadata | uint32_le dataLength | data`. Java reads both complete bounded fields, calls `ListenerContext.readMetadata`, and passes the opaque data to the associated `Agent.submitSerializedRequest`. Agent request bytes are for the SDK; custom telemetry needs its own application frame/field rather than being mixed into those bytes.
3. In the reverse direction Java sends queued serialized command bytes as `uint32_le length | bytes`. Native code reads them and calls `NewDataFromC2` / `newDataFromC2`.

Source: native `simple_tcp_listener` managed `Program.start` / `SendToServer` and Linux `Main.cpp`, matched to Java `AgentSocketServer.handleFirstRequest` / `handleDataRequest` and `TcpReverseConnection`. See [source lookup](existing-plugins.md#locate-a-matching-pair). For a new protocol, follow [application payloads and framing](implementation-recipes.md#application-payloads-and-framing) to choose the message boundaries needed by the task.

To add user-requested native telemetry, extend the existing application transport's encoder and Java decoder together, preserving compatibility for existing agent traffic. Define the added text, JSON, or binary fields and their boundaries, adding versioning when needed for existing peers. Preserve SDK-owned bytes inside opaque fields. Decode the actual received facts in Java, then update an appropriate presentation: listener `getInfo()`, supported activity events via `ListenerContext.getActivityLogger()`, or an existing plugin output facility. Check the SDK types and UI capabilities for the requested surface. Do not substitute Java startup status for an observation of remote native health.

## Live configuration

`TemplateListener.reconfigure` applies Java listener state. `serializeUpdatedConfiguration` only encodes bytes for the host to deliver; neither method alone proves running exec-units received an update. Trace the current host delivery path or the plugin's existing control transport and register its receiver on every native implementation. Where the host uses the `0x20` callback, verify that mapping and extract child `0x04` in the native IPC helper, then decode its inner bytes with the same plugin configuration parser used at startup.

Validate a complete candidate before publishing it. Apply updates under suitable synchronization, recreate affected sockets/workers when needed, and retain or restore the last working configuration if applying fails. Define full replacement versus patch semantics; do not treat an omitted field as zero accidentally. Test an update arriving while active and a rejected update. If no supported delivery path exists, expose the limitation explicitly instead of returning empty bytes or reporting a successful native update.
