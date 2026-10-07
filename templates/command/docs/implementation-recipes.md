# Implement a command from a prompt

Start here when completing a fresh command. Follow the minimum path, then read only the branches required by the requested behavior. The patterns come from matched Java/native implementations of `fs_copy` and `os_procinfo`; [existing-plugins.md](existing-plugins.md) locates them. Their broader platform matrix and server-only base classes are not prerequisites for this template.


A fresh copy already implements the [no-op path](../README.md#default-behavior): `{}` validation, a shared zero-byte configuration encoder, native IPC connection, `DONE` result parsing/presentation, and checked success completion. The steps below extend those hooks for requested behavior; field, worker, and update examples are optional.

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

Read root context first. Resolve generated names from the source map; paths below use the template names. Use these checkpoints in order, completing the linked focused skill at each phase without requiring another user invocation. After substantial configuration, behavior, and output steps, and at the end, apply the Docker [build checkpoints](building.md#required-build-checkpoints). Verify the [actual configuration and response bytes](payload-verification.md) through both codecs and transport before declaring integration complete.

| Step | Concrete edit and handoff | Evidence before advancing |
| --- | --- | --- |
| 1. Contract | Record the requested operation, inputs/defaults, one output example, failure behavior and existing platforms. Choose inner payload representations appropriate to the data. | One valid input and its expected visible output; known optional branches from the table above. |
| 2. Build prerequisites | Inspect `java-plugin/build.gradle.kts`, [JSON dependencies](building.md#java-dependencies-and-compilation). Retain Java 21, .NET Framework 4.6.2, C++11, the existing SDK and resource names. | Actual SDK signatures verified; any JSON parser and its transitive runtime classes declared and bundled under the [Java gate](java-verification.md); standard Java text/binary APIs need no additional codec dependency. Server `ConfigurationHelper`, `PluginUtils` and `SimpleStateless*` are not SDK classes. |
| 3. Configuration | Apply [command-conf](../.agents/skills/command-conf/SKILL.md): schema -> typed parser -> `createCommand` -> retained configuration -> one encoder used by both Java generation methods -> managed Windows, native Windows, and Linux typed decoders. | Factory accepts valid input, rejects invalid input; Java bytes decode to the same values in managed Windows, native Windows, and Linux. The no-op already validates its empty-object schema. |
| 4. Operation | Apply [command-logic](../.agents/skills/command-logic/SKILL.md): Managed Windows `Program` owns the pipe across initialization/execution/completion; Windows native `start` owns a scoped pipe and one terminal report directly; Linux exported `run` owns its FIFO helper. Implement [failure-path cleanup](native-runtime.md#failure-path-cleanup-before-return) before operation logic, including used transport helpers. | Valid configuration reaches behavior; force operation and reporting failures, partial startup and disconnect. Verify one failure completion while transport is usable, including when error-text formatting fails; safe cleanup still finishes before return. |
| 5. Result | Apply [command-output](../.agents/skills/command-output/SKILL.md): native encoder -> `sendResult` -> `TemplateCommand.parseResult` -> named editor result -> `commit()`. | Native fixture renders the expected value; empty final notification does not erase it. Verify exactly one checked success completion after all required result writes, including zero-output success, using [completion tests](command-completion.md#required-completion-tests). |
| 6. Delivery | Add new C# files to `.csproj`, Windows C++ sources to `exec-code/win-native/build_windows.sh` and Linux C++ sources to `build_linux.sh`; reconcile capability methods with actual artifacts/entrypoints. Follow [native rebuild and packaging](building.md#rebuild-native-resources). | Full Docker build succeeds; exported JAR entries match fresh native artifacts. Run the archive checker and isolated provider/template/schema/factory initialization from that exact JAR. Record its hash and unavailable checks separately. |
| 7. Handoff | Replace README examples and update `AGENTS.md` using [context maintenance](project-context.md). | Completed behavior, actual checks, artifact freshness and unresolved runtime/platform gaps agree with the code. |

The no-op shares `TemplateCommand.supportedTypes` between compatibility and direct generation guards. Windows accepts only X86/X64 and Linux only X64. During step 6, preserve or extend those guards only for architectures supported by the actual built artifacts. ARM or unknown architecture must not select that resource implicitly.

Before declaring steps 4-5 complete, apply the [command completion gate](command-completion.md): every connected path reaches its finalizer and the host observes success/failure. Also apply the [host process and unload requirements](native-runtime.md#host-process-and-unload-requirements): the host stays alive, all owned workers/callbacks end before entrypoint return, and the relevant lifecycle checks pass. Audit every early return/throw and error-send path; repair helper lifetime issues on the implemented path. Verify failure followed by immediate unload and another invocation. Copied examples and successful builds do not establish safety.

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

The [configuration handoff](configuration.md#follow-one-typed-value-through-the-plugin) lists the factory, constructor and generation-method edits. Apply the [checked-send and completion contract](command-completion.md) before using native send helpers. All template result/error/terminal APIs return `bool`. Check the complete-frame write outcome and preserve the existing transport-failure handling; a helper call alone proves neither delivery nor completion.

For managed Windows, native Windows, and Linux, follow this sequence:

1. Keep the outcome as failure while validating and executing the operation.
2. Write `messageBytes` as one result using `sendResult`, checking the full-frame write. Only then record operation success; a send failure must not select success.
3. Reach the single completion owner on every path. After operation workers and result writes finish, send exactly one checked `sendReturnSuccess` or `sendReturnFailed` while the reporting connection is usable. For example, if `Program.Complete` owns completion, `Execute` must not send another terminal message.
4. Drain reporting as supported, stop/join remaining transport work and clean up before entrypoint return. A broken channel follows the explicit host-visible failure path in the completion guide; do not blindly append a terminal message to a corrupted partial frame.

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

Only the native helper builds the frame. Java receives the four result bytes and needs no host-envelope parser. Verify all managed/native paths with Unicode and empty values, Java rejection of malformed/oversized result bytes, a later empty final callback, and success/failure cleanup. Use a compatible pipe/FIFO harness; these exec-units are not standalone console applications.
