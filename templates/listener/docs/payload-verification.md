# Verify configuration and response bytes

Use this gate when implementing a plugin or changing configuration, payload codecs, IPC helpers, native resources, or response handling. A successful build or a same-language encode/decode round trip does not establish Java/native compatibility. Keep the plugin's chosen UTF-8, JSON, or explicit binary payload; Java uses standard APIs or declared bundled parser dependencies.

The [idle contract](../README.md#default-behavior) has zero configuration payload bytes for startup and valid empty replacement encoding. Both native entrypoints reject nonempty startup payloads. There is no application response sender or Java receiver; mark that boundary as intentionally absent rather than inventing a listener result fixture. Verify startup framing and idle disconnect cleanup, and add response checks when the data traffic channel is implemented.

## Record the byte contract

Record these decisions beside the codecs or in project context before changing either end:

| Boundary | Record |
| --- | --- |
| Java configuration producer | Actual factory, shared encoder, both generation methods, startup/update fields, resolved defaults, and expected payload bytes |
| Native configuration consumer | Actual `Connect()` / `connect()`, returned payload boundary, typed decoder, and expected values on each platform |
| Native response producer | Actual encoder/sender, payload fields, chunk/final/error semantics, and expected bytes |
| Java response consumer | Actual receiver/parser, buffer/chunk handling, expected values and visible result |

Specify field order/names, numeric width/signedness/byte order, string encoding, byte versus character lengths, limits, empty/omitted/null values, versioning if present, and trailing-byte policy. Distinguish the user's JSON input from the chosen native payload representation. Do not silently JSON-encode already serialized JSON, base64-encode bytes, add a BOM/terminator, or prepend another length unless the agreed payload requires it.

Java generation supplies only inner configuration bytes. The native IPC helper removes the host envelope exactly once before passing those bytes to the typed decoder. Keep the host framing in the native transport layer described in [execunit-ipc.md](execunit-ipc.md). Verify the actual initial message layout against the compatible host or captured fixture; do not infer its tag or parent/leaf flag from later messages or from an unrelated server message field.

## First check: actual producers against actual consumers

1. Create a small reproducible fixture using the plugin's real Java factory and encoder. Capture the configuration bytes returned in `ExecUnit.configuration()` and `ShellCodeWithConf.configurationBuffer()` from the supported `generateExecUnit` and `generateShellCode` paths. Use valid platform metadata for each path; legacy shellcode generation does not cover the Linux shared-library path. Assert byte equality where both paths apply, `position() == 0`, `limit() == expectedPayloadLength`, independent buffers, and identical semantics for the same configuration. Include supported update encoders and repeated generation calls separately.
2. Feed those captured bytes to the production configuration decoder on **every in-scope exec-unit**. Assert field values, defaults and units, including no extra/unconsumed bytes unless the contract allows them. Use the actual compiled decoder; a hand-translated test decoder or a Java-only round trip is insufficient.
3. Generate response fixtures using each production native encoder/sender and feed the resulting inner payload to the actual Java receiver/parser. Assert typed values and visible output or file bytes, including any errors encoded in the inner payload. Verify completion/error transport separately in the framed-path check below. A hand-written matching byte array alone does not test the native encoder.
4. Include valid empty configuration where allowed, omitted/default fields, non-ASCII text, a size/numeric boundary, and malformed/truncated data relevant to the selected format. Cover chunk splits and empty final notifications when streaming is used. Changes to only one direction still need a startup/response smoke check of the unchanged direction.

At every outgoing SDK configuration/update handoff, normalize the Java `ByteBuffer` to position zero and limit equal to the exact payload length. The reviewed server serialization path computes a value's length from `limit()` while emitting its remaining bytes; a nonzero position can therefore advertise more bytes than are sent. The SDK records do not normalize the supplied configuration. This is a buffer contract, not a reason to add Java host-codec classes.

After relative writes to an allocated buffer, flip it once into reading mode. `ByteBuffer.wrap(bytes)` and a charset encoder's returned buffer are already readable; do not flip them again. `ByteBuffer.wrap(bytes, offset, length)` needs a slice or an exact-range copy to start at position zero. A duplicate preserves its source position and is not normalization. Repeated generation calls must not share a consumed cursor or mutate previously returned data.

Incoming Java result/transport buffers can be direct, read-only, or sliced with a nonzero position. Read only `remaining()` bytes through a duplicate/slice when preserving caller state; do not read the entire backing array or assume `array()` exists. Set/check byte order on the view performing binary numeric reads or writes. Test these receiver cases independently from the outgoing position-zero requirement.

## Second check: real framing and unwrapping

Run a compatible agent or a focused pipe/FIFO peer against the **actual native connection helper and decoder**. Send the Java-produced fixture through the verified host startup framing, then assert that the payload returned by `Connect()` / `connect()` is byte-for-byte identical to the Java input. Check both length and bytes before interpreting fields. Retain that known-good transport fixture as a regression check; guessing the initial envelope in both the harness and implementation can reproduce the same mistake.

Exercise normal delivery, a split four-byte prefix, a split body, and consecutive frames. The native helper must read exactly the bounded prefix/body, reject premature EOF, and loop until all output bytes are written. One read/write call is not a complete-message guarantee. Verify the platform's actual startup handshake, keep one reader owner across startup and the receive loop, and ensure a background reader cannot consume initial configuration first. Linux readiness traffic and Windows startup must follow their respective contracts.

Treat successful connection with zero payload bytes separately from failed connection. The bundled Linux `connect` throws on startup/framing failure; Windows `Connect` returns `null`. A successful zero-length payload is valid for this idle template. Preserve that distinction when extending the configuration.

Trace the response through its real delivery path too:

- Listener: local-agent IPC and the native-to-Java application transport are separate. Send native application frames through the actual Java transport decoder, verify metadata/request/returned-command exchange and any custom telemetry, and preserve opaque SDK bytes. `ExecUnitListener` has no command-style `parseResult` callback.

A parser-only test can run without an agent, but it does not validate the initial host envelope. If no compatible host/captured fixture or runtime toolchain is available, complete independent checks and record that exact gap. Do not invent protocol constants, request unrelated Java transport libraries, or claim the framing check passed.

## Diagnose invalid configuration frames

First locate the throw/report site and identify the failing layer. The following are checks, not a claim that every reported error has the same cause:

| Observation | Check before changing the decoder |
| --- | --- |
| Initial frame rejected before payload decoding | Verified initial message type/flags, complete little-endian length prefix, bounded body read, startup handshake, and a competing reader |
| Helper returns unexpected payload length/first bytes | Missing or duplicate envelope removal, duplicated length prefix, raw text versus JSON/binary, BOM/terminator, or a consumed Java buffer |
| Payload bytes match but fields differ | Field order, widths, signedness, byte order, string byte counts, defaults, version and trailing-byte policy |
| Empty bytes appear | Explicit connection status, valid no-field payload versus failed read, buffer limit/position, and both Java generation methods |
| Code looks correct but runtime still rejects it | Selected OS/process-architecture resource, rebuilt native bytes embedded in the distributable, and the artifact actually used in the failing run |

Use synthetic non-secret inputs to capture boundary byte lengths and bounded hex excerpts. Report the layer, offset/field and expected versus actual shape; avoid a single unexplained "Invalid configuration frame" message. Keep production diagnostics free of configuration secrets. Never make a failing test pass by removing bounds/type validation, stripping guessed prefixes, or catching a decode failure and accepting empty/default configuration.

After the fix, rerun the failing fixture and a valid startup/response case on each affected platform. Follow the [build checkpoints](building.md#required-build-checkpoints), regenerate native resources, and compare packaged bytes with the outputs from that build. Record codec tests, framed transport tests, runtime checks and artifact verification separately in [project context](project-context.md); preserve reusable fixture/test paths for the next change.
