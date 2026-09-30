# Command exec-unit IPC

Read this when implementing configuration exchange, results, streaming, updates, or cancellation. Both native platforms use this contract; Java supplies/consumes the inner configuration/result bytes through SDK methods.

## Payload boundary

Java supplies configuration/update payload bytes through the SDK and receives result payload bytes in `parseResult`. Choose the payload representation for the data: raw UTF-8, JSON, or an explicit binary layout can each be appropriate. Java does not add or parse the host envelope and needs no transport-codec dependency.

The native pipe/FIFO helpers wrap outgoing payloads and unwrap incoming envelopes. Their existing `TLV` classes serve this **host protocol** only; their presence does not require a matching format inside the payload. Keep host-defined IDs, error text, completion signals and framing unchanged. Use the native helpers for these operations rather than reproducing host framing in each command.

## Connection and framing

These conventions describe the bundled helpers. Verify any changes against the plugin's current host/SDK version.

- Windows uses one duplex named pipe. Open a `NamedPipeClientStream` for the patched pipe name, then read the initial frame. The Windows examples do not send the Linux readiness byte. Keep the UTF-16LE `QQQWWWEEE` placeholder and its encoded length compatible with `ShellcodeResource`.
- Linux's exported `run(char* pipeNameRead, char* pipeNameWrite)` receives two FIFO paths. Open the read FIFO, then the write FIFO, write one readiness byte `0x00` to the write FIFO, then read the initial frame.
- Each subsequent frame is `uint32_le frameLength` followed by exactly that many TLV bytes; the length excludes its own four bytes. The initial frame wraps the bytes provided by Java's `ExecUnit.configuration` / `ShellCodeWithConf`. `Connect()` / `connect()` unwraps the outer TLV and returns its value. Decode the plugin's chosen payload from that value without adding or parsing another IPC frame.
- A TLV is `uint8 typeAndFlags | uint32_le valueLength | value`. Bit `0x80` denotes a parent whose value is consecutive child TLVs. Logical type IDs are `0x00..0x7f`; mask off the parent bit when dispatching. Lengths count bytes, not characters. These are host envelope fields, not a schema for the plugin's inner payload.
- Read and write all bytes, including length prefixes: stream operations may complete partially. Bound frame size and nesting before allocation, validate each child's length against its parent, reject truncated/invalid data, and distinguish a valid empty configuration from a failed connection. The included Linux helpers need review for these conditions; the Windows helpers in a fresh template are stubs.
- Keep a single reader per connection and serialize writes. On failure/cancellation, unblock pending reads and response waiters, cooperatively stop and join/await workers, and release resources only after no owned work can access them. Apply the [host process and unload requirements](native-runtime.md#host-process-and-unload-requirements) before entrypoint return. Completion and disposal must be safe after partial initialization.

## Command messages

Types in this table are logical IDs, before adding the parent flag.

| Direction | Type | Value / handling |
| --- | --- | --- |
| Exec-unit to agent | `0x30` | Result bytes; `sendResult`. Java receives the result payload in `TemplateCommand.parseResult`. |
| Exec-unit to agent | `0x31` parent | Command handling options, described below. |
| Exec-unit to agent | `0x32` | UTF-8 error bytes; `sendError`. |
| Exec-unit to agent | `0x33` / `0x34` | Empty success / failure completion. Send exactly one terminal outcome. Existing helpers encode these as an empty leaf or empty parent; keep host compatibility. |
| Agent to exec-unit | `0x39` | Update bytes from `serializeCommandUpdate`; dispatch to the registered update callback. |
| Agent to exec-unit | `0x3f` | Stop request; signal cancellation and finish within the advertised grace period. |

For example, the UTF-8 payload `A` is the single byte `41`. Calling `sendResult` with that byte makes the native helper write `06 00 00 00 30 01 00 00 00 41`: a four-byte frame length, the host result envelope, and one payload byte. Java receives only `41`.

The `0x31` parent can contain these options:

| Child tag | Encoding | Meaning / helper |
| --- | --- | --- |
| `0x01` | One byte `1` | Ongoing results: `sendConf_ongoingResult()`. Send before streaming results. |
| `0x02` | One byte `1` | Relay in blocks: Linux `sendConf_relayInBlocks()`; implement the equivalent Windows encoding if this mode is needed. |
| `0x03` | Four-byte little-endian grace time in milliseconds | Cooperative stop: Linux and the reviewed Windows default command helper use `sendConf_stoppable`; add the equivalent to the Windows template stub when needed. |

The Windows command helper takes update and stop callbacks in its constructor. Linux uses `setCallbackNewData` and `setCallbackStop`; installing them before connection avoids missing early messages. Implement the options and callback dispatch in the Windows stubs when the requested behavior uses them. Disabling updates must remain explicit in Java's `serializeCommandUpdate`.

For streaming output, preserve message boundaries or document record reassembly. UTF-8 characters and structured records can span delivered chunks when block relay is used. Coordinate native flags, Java accumulation, `isFinalResult`, and `CommandResultEditor.commit()`; do not silently replace earlier chunks. Finish reporting before closing the connection.
