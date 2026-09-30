# Implement a command from a prompt

Start here when completing a fresh command. Follow the minimum path, then read only the branches required by the requested behavior. The patterns come from matched Java/native implementations of `fs_copy` and `os_procinfo`; [existing-plugins.md](existing-plugins.md) locates them. Their broader platform matrix and server-only base classes are not prerequisites for this template.

## Choose the needed behavior

| Prompt requires | Implement | Read when needed |
| --- | --- | --- |
| One bounded operation and one answer | Typed configuration, one execution, one complete result, one terminal outcome | [Minimum path](#minimum-path), then [one-value trace](#one-value-trace) |
| No user inputs | Validate an empty JSON object; use an empty typed configuration and empty native payload | [Configuration handoff](configuration.md#follow-one-typed-value-through-the-plugin); omit the walkthrough's example fields |
| Several rows returned together | A documented list representation such as JSON or binary records; format in Java | `os_procinfo` in [results and state](existing-plugins.md#results-and-state) |
| Output while still running | Ongoing-result option before the first result; per-command accumulation and final handling | [IPC options](execunit-ipc.md#command-messages), [streaming output](output.md#streaming-text-with-incomplete-utf-8) |
| Uploaded/downloadable files | Multipart configuration/file bytes or SDK file result APIs | [Uploads](configuration.md#file-uploads-when-requested), [result editor calls](output.md#result-editor-calls) |
| Long-running work, stop, or live updates | Cooperative cancellation or candidate configuration updates, plus owned workers/resources | [Native lifetime](native-runtime.md), [IPC callbacks](execunit-ipc.md#command-messages) |

Combine rows when necessary. A one-answer command needs no job manager, result merger, block relay, background reader for unused callbacks, or update protocol. Leave updates explicitly unsupported when unrequested. Java `markStatus`/`forceStop` can remain intentional no-ops when Java owns no resources; they do not implement native cancellation. Native helper I/O failure and cleanup still need to work.

## Minimum path

Read root context first. Resolve generated names from the source map; paths below use the template names. Use these checkpoints in order, completing the linked focused skill at each phase without requiring another user invocation.

| Step | Concrete edit and handoff | Evidence before advancing |
| --- | --- | --- |
| 1. Contract | Record the requested operation, inputs/defaults, one output example, failure behavior and existing platforms. Choose inner payload representations appropriate to the data. | One valid input and its expected visible output; known optional branches from the table above. |
| 2. Build prerequisites | Inspect `java-plugin/build.gradle.kts`, [JSON dependencies](building.md#java-dependencies-and-compilation). Retain Java 21, .NET Framework 4.6.2, C++11, the existing SDK and resource names. | Any JSON parser actually declared and bundled; standard Java text/binary APIs need no additional codec dependency. Server `ConfigurationHelper`, `PluginUtils` and `SimpleStateless*` are not SDK classes. |
| 3. Configuration | Apply [command-conf](../.agents/skills/command-conf/SKILL.md): schema -> typed parser -> `createCommand` -> retained configuration -> one encoder used by both Java generation methods -> both native typed decoders. | Factory accepts valid input, rejects invalid input; Java bytes decode to the same values in Windows and Linux. An empty schema still needs its validation TODO removed. |
| 4. Operation | Apply [command-logic](../.agents/skills/command-logic/SKILL.md): Windows `Program` owns the pipe across initialization/execution/completion; Linux exported `run` owns its FIFO helper. Complete used transport stubs, then execute the requested operation. | Valid configuration reaches behavior on each platform; failure has an error and one failed completion; cleanup runs after partial initialization too. |
| 5. Result | Apply [command-output](../.agents/skills/command-output/SKILL.md): native encoder -> `sendResult` -> `TemplateCommand.parseResult` -> named editor result -> `commit()`. | Native fixture renders the expected value; empty final notification does not erase it. Send one successful completion after results. |
| 6. Delivery | Add new C# files to `.csproj`, C++ sources to `build_linux.sh`; reconcile capability methods with actual artifacts/entrypoints. Follow [native rebuild and packaging](building.md#rebuild-native-resources). | Affected sources compile; JAR entries match fresh native artifacts, service provider and dependency classes exist. Record unavailable checks separately. |
| 7. Handoff | Replace README examples and update `AGENTS.md` using [context maintenance](project-context.md). | Completed behavior, actual checks, artifact freshness and unresolved runtime/platform gaps agree with the code. |

In the fresh scaffold, the Windows branches of `TemplateCommandTemplate.canSendToAgent` and `TemplateCommand.supportedTypes` check only the OS. During step 6, restrict both to the process architectures supported by the built artifact (X86/X64 for the existing Windows shellcode), and retain the same guard in direct generation calls. ARM or unknown architecture must not select that resource implicitly.

Do not stop at a schema, native function, or compiling Java class: steps 3-5 form one user-visible path. For an existing plugin, keep working portions and apply the checkpoints only to the requested change.


## One-value trace

This is a small example, not behavior to add to every command: "Return the supplied message unchanged." User JSON is `{"message":"A\u20ac"}`. The message is required, may be empty, is at most 64 UTF-8 bytes, and rejects null/unknown fields. Use the [strict JSON validation pattern](configuration.md#strict-json-validation-with-the-sdk), replacing its example fields. JSON is parsed only in Java for this example.

| Boundary | This example's contract |
| --- | --- |
| Java configuration | Validate the message and encode it directly as UTF-8 using [encodeText](configuration.md#utf-8-payloads). Supply those bytes through the existing generation methods. |
| Native input | `Connect()`/`connect()` returns 0..64 payload bytes. Connection success is tracked separately; an empty vector/array alone is not proof of failure. |
| Native operation | Check the size and echo the bytes unchanged; no native JSON parser is needed. |
| Native result | Send the same 0..64 bytes, then one successful completion. |
| Java presentation | Strictly decode the payload and call `setTextResult("message", value)` followed by `commit()`. |

The [configuration handoff](configuration.md#follow-one-typed-value-through-the-plugin) lists the factory, constructor and generation-method edits. Both native platforms use their existing send helper directly:

```csharp
// messageBytes: byte[] from the connected pipe, already size-checked.
pipe.sendResult(messageBytes);
pipe.sendReturnSuccess();
```

```cpp
// messageBytes: std::vector<uint8_t> from the connected pipe, size-checked.
pipe.sendResult(messageBytes);
pipe.sendReturnSuccess();
```

Choose one terminal owner: when `Program.Complete` sends success, `Execute` sends only the result. Complete the Windows transport stubs first. The reference command helpers return `bool` from sends while Windows template stubs return `void`; handle a failed send through a checked return or exception consistently, then clean up.

For the one-answer contract, add a per-command `boolean receivedResult` field. Inside `parseResult`, use the [strict decodeText helper](output.md#strict-utf-8-one-complete-value):

```java
if (isFinalResult && !buffer.hasRemaining() && receivedResult) {
  return; // Terminal notification after the value; preserve the existing entry.
}
if (receivedResult) {
  throw new SerializationException("Unexpected second result payload");
}
if (buffer.remaining() > 64) {
  throw new SerializationException("Result exceeds 64 UTF-8 bytes");
}
String value = decodeText(buffer);
editor.setTextResult("message", value);
editor.commit();
receivedResult = true;
```

The first empty payload, including an empty final callback when no earlier data arrived, represents the valid empty string for this contract. A later empty final callback preserves the entry. A terminal callback does not prove native success; native failure/status reporting remains authoritative. For streaming data use [accumulation](output.md#streaming-text-with-incomplete-utf-8) instead of this one-answer parser.

The exact fixture for `A` followed by the euro sign is:

```text
Configuration returned by Connect/connect: 41 e2 82 ac (4 bytes)
Result passed to sendResult and Java parseResult: 41 e2 82 ac (4 bytes)
Pipe frame written by the native helper:
09 00 00 00 30 04 00 00 00 41 e2 82 ac (13 bytes; frameLength = 9)
```

Only the native helper builds the frame. Java receives the four result bytes and needs no host-envelope parser. Verify both native paths with Unicode and empty values, Java rejection of malformed/oversized result bytes, a later empty final callback, and success/failure cleanup. Use a compatible pipe/FIFO harness; these exec-units are not standalone console applications.
