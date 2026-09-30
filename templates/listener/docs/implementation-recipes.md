# Implement a listener from a prompt

Start here for a new listener or an unfinished scaffold. Choose the transport shape, record the small contract below, then follow the implementation order. Read the detailed guides at the step that needs them. Examples here are design recipes, not implemented template behavior or a replacement for an existing peer protocol.

## Choose the transport shape

| Prompt / peer behavior | Java owns | Native owns | Closest reviewed source pair |
| --- | --- | --- | --- |
| Agent connects to a persistent TCP endpoint | Server socket, sessions, per-agent command delivery | Outbound connection and local-agent IPC | `tcp-reverse-listener` / `simple_tcp_listener` |
| Agent polls an HTTP/HTTPS endpoint | HTTP handlers and responses | HTTP client, polling schedule and local-agent IPC | `http-listener` / `simple_http_listener` |
| Reach another agent through an existing agent | Relay command subscriptions and channel-to-agent mapping | A listener on the downstream agent **and a companion command** on the relay agent | `relay-tcp-bind-listener` / `relay_tcp_bind` (or matching TCP reverse / SMB pair) |
| DNS requests carry pieces of agent traffic | DNS request handling and correlated reconstruction | DNS exchange and matching message assembly | `dns-listener` / `simple_dns_listener` |
| An external controller registers agents and submits results | External protocol, agent registration and command routing | Whatever the specified external controller implements | `ws-external-listener`; not a drop-in native listener pair |

Java module names are under `tuoni-server/plugin/`; native listener names are under `listeners_default/listeners/`. See [source lookup](existing-plugins.md#locate-a-matching-pair) for classes and source ownership. These sibling checkouts are optional references, not dependencies of the generated plugin.

For a direct listener the path is `Java receiver <-> network transport <-> native listener <-> pipe/FIFO <-> local agent`. For a relay it includes the upstream agent and a relay command; do not implement it as if Java directly accepted the downstream socket. Keep existing Windows and Linux implementations in scope unless the user limits them. A different topology may require additional collaborators, but never silently remove existing support.

## Record the small contract

Write the decisions in project context or a linked protocol document before implementing both ends. Fill in only fields required by the prompt; examples below are optional choices.

| Decision | Example for a new direct stream listener |
| --- | --- |
| Peers and direction | Native connects; Java accepts; one agent per connection |
| Java-only settings | `bindAddress`, `bindPort` |
| Native settings | `hosts`, `port`; advertised destination can differ from Java's bind endpoint |
| Required startup behavior | Connect local-agent IPC, parse configuration, connect transport, send metadata even when there is no queued data |
| Agent traffic | Metadata and requests are opaque SDK bytes; Java commands return intact to `NewDataFromC2` / `newDataFromC2` |
| Framing | Existing peer format, or documented text/JSON/binary messages with transport-appropriate boundaries |
| Output | Bound endpoint and active session count in `getInfo()` unless the prompt requests more |
| Updates | State which fields apply live, need reconnect/restart, or are unsupported; separate Java reconfiguration from delivery to running native code |

Do not add host rotation, custom telemetry, a listener job, uploads, or relay commands merely because a reference has them. Include them when required by the requested behavior or existing compatibility.

## Minimum complete implementation

1. **Make configuration and factory usable.** Follow [the typed Java handoff](configuration.md#follow-one-typed-value-through-the-plugin). One parser supplies validation and factory creation; one encoder supplies both `generateExecUnit` and `generateShellCode`. Classify each field as Java-only/native/both, document its encoding/type/units, and decode equivalent values on Windows and Linux. Valid `{}` must create the listener when no fields are required.
2. **Complete local-agent IPC.** Use [native-runtime.md](native-runtime.md) and [execunit-ipc.md](execunit-ipc.md#listener-messages). Windows helpers are stubs. Connect once, decode the returned inner configuration, retain the pipe/FIFOs, and expose metadata, outgoing agent data, and delivery of incoming commands. This connection does not reach Java.
3. **Implement the selected network transport at both ends.** Java `start()` binds/acquires its resources; native code connects or serves according to the topology. Give one owner each session's decoder, writer, agent association, and cancellation. For streams, read full bounded prefixes/bodies and serialize full-frame writes. Treat end-of-stream as disconnect; close resources to unblock workers on stop.
4. **Prove one complete agent exchange.** Native retrieves metadata and sends it through the selected transport. Java calls `readMetadata`, finds/registers the agent, and submits opaque requests. Java retrieves serialized commands, writes them, and reports `SendStatus`; native forwards only the command bytes to the local agent. Follow [the SDK recipe](listener-java.md#sdk-receive-and-command-send-recipe). A connection alone is not a completed listener.
5. **Finish lifecycle and requested output.** Wire the factory, start, stop, delete, `getInfo()`, and requested reconfiguration. Closing a session ends its workers/subscriptions and settles any dequeued commands. Use [the output selection](#choose-the-output-path) before adding telemetry. Keep unsupported update behavior explicit instead of returning a success or empty update buffer.
6. **Build and verify the assembled plugin.** Follow [building.md](building.md). Add new C# files to the `.csproj` and C++ files to `build_linux.sh`; preserve the Windows pipe placeholder and Linux `run` export. Compile each affected platform, regenerate native resources, and inspect the JAR. Record unavailable runtime/toolchain checks separately from completed work.

Use `listener-conf`, `listener-logic`, and `listener-output` for the corresponding steps. For a complete implementation, carry a focused skill's remaining work into the next phase when the requested path depends on it.

## Application payloads and framing

Choose the simplest format that fits the requested transport and peers. A single text observation can be UTF-8; structured configuration or telemetry can use JSON when each consumer has a suitable parser; opaque metadata/request/command bytes can use explicit length-delimited binary fields. Use Java standard stream/`ByteBuffer` APIs for text/binary, and declare and bundle any JSON parser.

For a stream, reads do not preserve message boundaries. Specify a bounded length prefix or another unambiguous framing rule and consume exactly each complete message. Define field order, integer width/byte order, maximum lengths, and the difference between absent and empty data. The existing reverse TCP example sends an optional handshake, a metadata-only registration message, then metadata/request pairs; commands return as length-prefixed opaque bytes. Its [concrete framing](execunit-ipc.md#java-receive-path-and-output) is one usable reference when it fits the task.

Preserve these handoffs regardless of the chosen encoding:

```text
Native -> Java, on connect:      metadata, even without a request
Native -> Java, agent has data:  metadata + opaque request
Java -> native, queued command: opaque serialized command
Native -> local agent:          NewDataFromC2(command) / newDataFromC2(command)
```

Startup configuration is a separate inner payload supplied by Java generation methods. The native pipe helper strips the host envelope before handing it to the configuration decoder. Do not add application frame prefixes or host IPC wrappers to those configuration bytes.

For a request/response transport such as HTTP, retain the requested HTTP protocol and map its metadata/body/response to the same SDK handoff. Wait for request processing to complete before acknowledging that request or collecting its response commands. Report commands sent only after the response write completes. If using pooled request buffers, retain their storage until the processing future completes, including when the client disconnects. `AgentRequestHandler.submitRequest`, `sendCommands`, and `PendingRequest` in the HTTP reference show these boundaries; a stream listener does not need to copy its Jetty infrastructure.

## Choose the output path

| User asks to see | Smallest implementation |
| --- | --- |
| Listening endpoint, session count | Java-owned state -> `getInfo()`; no native protocol change |
| Received agent activity | Existing SDK activity event + supported `ListenerInteraction` |
| Native-specific observation | Native encoder -> distinct application message -> actual Java receiver -> typed observed state -> requested surface |
| Command execution output | Preserve opaque requests through `submitSerializedRequest`; the command plugin owns its result parsing |
| File bytes or a download | Use a supported storage/output facility; a file activity event alone does not expose bytes |

Use [the Java presentation API table](listener-java.md#available-presentation-surfaces) for exact methods. `ExecUnitListener` has no `parseResult`. Java startup status is local resource status; remote health requires a received observation. Add custom telemetry only when the prompt needs it.

## Focused proof before finishing

- **Configuration:** one valid input reaches both native decoders with the same field values; invalid input fails before resources start. Check both generation paths.
- **Traffic:** metadata-only registration, an agent request, and a queued command traverse the actual receive/send path. For streams, split a prefix/body across reads and combine two frames in one read.
- **Lifecycle:** stop an idle session blocked in I/O, disconnect during a send, and fail startup partway through; workers/resources and send statuses finish consistently.
- **Conditional behavior:** verify requested updates while running, requested telemetry alongside ordinary traffic, or relay channel isolation when those features apply.
- **Artifact:** packaged native bytes match this build, resource names match generation methods, and context records actual checks and remaining limitations.

Source basis: TCP `TcpReverseConfiguration`, `AgentSocketServer`, `TcpReverseConnection`, `OutboundCommand`, and managed/native `Program`/`Main`; HTTP `AgentRequestHandler`, `ReloadableHttpListener`, and `ConnectionConf`; relay `RelayCommandManager` and native bind `Main`; SDK `ListenerContext`, `Agent`, `AgentCommandQueue`, `SerializedCommand`, and `SendStatus`. See [the source map](existing-plugins.md) to locate them. Review older implementations for the focused boundary you copy; their presence is not a runtime verification of this new listener.
