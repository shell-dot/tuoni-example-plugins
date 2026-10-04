# Patterns from existing listener plugins

Use this reference to locate source evidence for configuration, lifecycle, transport, or output patterns. For the ordered implementation path and topology selection, begin with [implementation recipes](implementation-recipes.md). The reviewed sources include direct TCP and HTTP listener pairs, relay command routing, shared artifact helpers, DNS expiry state, and focused Java tests. Adapt the parts required by the user's transport.

The [idle template](../README.md#default-behavior) already supplies empty-object validation, Java lifecycle, and native local-agent IPC startup/disconnect waiting. The application data traffic channel is intentionally TODO. Use these pairs to implement a requested channel; a local status-formatting or idle-startup task can keep the default.

## Locate a matching pair

Locate sibling `listeners_default` and `tuoni-server` checkouts when available. Server implementations live under `tuoni-server/plugin/` (singular); native implementations are under `listeners_default/listeners/<name>/execunits/`. Generated plugins can live elsewhere and do not require those checkouts to use this guide.

Java classes below live under each named module's `src/main/java/com/shelldot/tuoni/plugin/` package tree.

| Concern | Java reference in `tuoni-server/plugin/` | Native reference in `listeners_default/` |
| --- | --- | --- |
| Repeated configuration and Java/native handoff | `tcp-reverse-listener`: `TcpReverseConfiguration`, `TcpReverseListener` | `listeners/simple_tcp_listener/execunits/windows/TcpListener/ConnectionConf.cs`; `execunits/linux/ConnectionConf.cpp` under the same listener |
| Stream receive/send lifecycle | `tcp-reverse-listener`: `TcpReverseConnection`, `OutboundCommand`, `SimpleCommandSubscriber`, `AgentSocketServer` | `listeners/simple_tcp_listener/execunits/linux/Main.cpp` and its socket/pipe helpers |
| Server/native configuration split and reload | `http-listener`: `HttpListenerConfiguration`, `InternalHttpListener`, `ReloadableHttpListener` | `listeners/simple_http_listener/execunits/windows/HttpListener/ConnectionConf.cs` and the platform-specific peers |
| HTTP request processing and send completion | `http-listener`: `handlers/AgentRequestHandler` (`submitRequest`, `sendCommands`, `PendingRequest`) | `listeners/simple_http_listener/execunits/windows/HttpListener/Program.cs`; `execunits/linux/Main.cpp` under the same listener |
| Relay command results become downstream requests; command updates carry replies | `relay-tcp-bind-listener`: `listener/subscription/RelayCommandManager`, `command/RelayTcpBindCommandTemplate` | `listeners/relay_tcp_bind/execunits/linux/Main.cpp` and the distinct `listeners/relay_tcp_bind/commands/tcp_bind/execunits/` command sources |
| External controller owns agent/result protocol | `ws-external-listener`: `WebSocketConnection`, `MessageRouter`, client/server message records | External controller protocol; no matching native exec-unit supplied by this template |
| Expiring receive state | `dns-listener`: `ExpiringMap` | Inspect the matching native DNS protocol when changing that listener; expiry alone does not define its wire contract |
| Resource and DLL entrypoint loading | `common`: `TemplateLoader`, `DotnetDllEntrypoint`, their tests | Shared project manifests, deploy scripts, and generated `.dotnet_dll_method` artifacts |

Direct listeners, relay listeners with companion commands, and external listeners have different ownership. A new direct listener does not automatically need a relay command or every artifact type found in the catalog. Choose the matching SDK capability and existing source topology before adapting a peer.

## Configuration and updates

Separate user configuration, Java resource configuration, and the native wire model. For example, TCP configuration distinguishes a server bind endpoint from advertised hosts/port; the native configuration carries repeated hosts, a port, handshake bytes, and an optional timestamp. Java-only fields stay outside that wire model. Reuse this separation with the [configuration handoff](configuration.md#follow-one-typed-value-through-the-plugin); server-internal encoding helpers are not SDK dependencies.

Trace each field on both sides. The TCP port is a four-byte integer, repeated hosts form a list, and timestamps use a text format with time-zone semantics. The HTTP decoder also contains four-byte integer flags and conversions from seconds to milliseconds. Preserve existing widths/units; do not replace an established integer flag with a one-byte boolean merely because a new-protocol example uses one.

Distinguish absent, empty, zero, false, and inherited values. Repeated fields must not accumulate duplicates when a replacement configuration is parsed twice. Parse a complete candidate, validate ranges/enums/units, then swap state. Avoid silently accepting an invalid timestamp because an older decoder catches and ignores its parse error.

Treat live-update support as a field-by-field property. In the inspected managed TCP decoder, `loadConfChange` only parses input and returns success. The managed HTTP decoder applies only selected scheduling fields in that method. Neither establishes that all startup settings can change live. For each requested field, identify serializer, actual delivery route, native receiver, applied state, and any restart/reconnect. Test the resulting active value and behavior.

A reloadable Java wrapper and native live-update delivery are separate mechanisms. `ReloadableHttpListener` delegates to an `InternalHttpListener` replacement. Its existence is not proof of recovery after a failed replacement start. Preserve stable listener identity, coordinate resource replacement, and verify the required rollback behavior under failure using the [Java lifecycle guide](listener-java.md).

## Transport and lifecycle

The native pipe/FIFO talks to the local agent. The application transport talks to Java. Preserve opaque agent bytes and the existing SDK flow and choose a suitable format for [plugin-owned payloads](execunit-ipc.md#plugin-payloads-and-host-ipc).

The reviewed reverse TCP connection has explicit phases for handshake, length-prefixed metadata, and requests. Its outbound path retains separate length/body progress and sets `SendStatus` after the bytes are written. These phases are useful design references for stream transports; the handshake and raw framing are that established protocol's compatibility details, not a default for every new listener.

HTTP has different completion boundaries: `AgentRequestHandler.submitRequest` waits for the SDK processing future before response/command collection; `sendCommands` reports send status from the response write callback. Its pooled request body stays owned until processing completes, even after disconnect. Reuse that ordering when adapting a request/response listener, without copying HTTP-specific pooling/Jetty machinery into a simple stream transport.

For relay TCP bind, `RelayCommandManager` subscribes to companion command results, parses downstream metadata/requests, and sends queued downstream commands through `updateCommandWithFastTrack` with a send-status callback. It listens for new relay command IDs and subscribes to already-running ones. The native listener and native relay command are separate sources. The reference's module guide records an unresolved disabled Linux end-to-end scenario; resource existence is not evidence of a working relay on that platform.

Keep phase, incomplete data, associated agent, pending writes, subscription, and close state scoped to a connection. Check lengths before allocation and handle partial prefix/body I/O. Choose bounded queue/demand behavior for the actual transport. `SimpleCommandSubscriber` requests `Long.MAX_VALUE`; copying that call does not provide backpressure. Likewise, DNS `ExpiringMap` removes stale entries after a TTL but supplies no total capacity bound; use both lifetime and memory limits when buffering partial messages.

Cancel subscriptions and settle pending sends on close. A partial send may have reached the peer, so follow the established retry/deduplication policy. Use independent buffer views and `remaining()`; code using `limit()` assumes position zero and needs review before reuse.

Trace shared source ownership: Windows launchers import shared `.projitems`, native builds use explicit source manifests, and platform files can be independent copies. Copying a `Program.cs` file does not necessarily copy its implementation or dependencies. Maintain matching Java/native semantics across the implementations actually in scope.

## Receive state and presentation

Resolve the agent only after complete valid metadata is available. Pass SDK-owned request bytes through `Agent.submitSerializedRequest`; decode custom telemetry in its own application fields. Route observations to the correct listener/agent/session, define what survives reconnect, and discard stale incomplete state according to the protocol.

Choose the presentation owner deliberately:

| Information | Owner / surface |
| --- | --- |
| Bound port and Java listener lifecycle | Listener state and `getInfo()`; an existing listener job when the plugin already uses one |
| Remote native observations | Received telemetry with identity and observation time |
| Agent/file/payload activity | Supported `ListenerContext.getActivityLogger()` event types |
| Command delivery | `SerializedCommand.setSendStatus` after transport completion |
| Command execution output | The command result path; listener send status does not establish execution success |

Reuse existing job and activity integration when present. `ExecUnitListener` has no `parseResult`, activity events do not themselves create downloadable files, and Java startup cannot establish remote health. See [listener-java.md](listener-java.md) for actual SDK calls.

## Artifacts and focused verification

Check the full OS, architecture, exec-unit type, resource, and entrypoint combination before advertising or generating a resource. Existing Windows managed/native variants and Linux/BSD/macOS libraries illustrate separate ABIs; they do not expand this template's scope automatically. A .NET DLL may require the companion method resource produced by its build; consult [building.md](building.md).

Use checks that exercise the changed boundary:

- Compare Java startup/update bytes with every native decoder, including repeated fields, default/inherited values, exact widths, and Unicode/time formats where used.
- Follow `tcp-reverse-listener/src/test/.../TcpReverseListenerTest` for fragmented writes, handshake/metadata rejection, disconnect, and command delivery. Prefer deterministic split positions in new tests so failures reproduce.
- For lifecycle changes, test start/stop/restart, failure during replacement, pending sends at shutdown, and native update behavior separately.
- For custom observations, interleave sessions and normal agent traffic, then verify identity, ordering, incomplete-message cleanup, and the requested visible output.
- Verify resource bytes and DLL entrypoint metadata in the distributable. A bundled-DLL test checks packaging, not transport correctness.
