---
name: command-output
description: Change a Tuoni command's result content and presentation from every existing exec-unit through Java result parsing, based on the user's requested output.
---

# Command output

Before editing, read the plugin-root `AGENTS.md` and `CLAUDE.md` when present, including their referenced project context and applicable instructions. Follow the [context maintenance guide](../../../docs/project-context.md) to create missing context and preserve the existing organization. Verify recorded facts against the files you change.

Before finishing this skill, create or update that project context, including after partial work. Record the native payload fields/encoding and sender locations, Java receiver/parser locations, streaming/version behavior, presentation surfaces and result names, platform coverage, checks performed, artifact freshness, and remaining limitations.

Use this skill from a command plugin copied from this template when the user specifies what they want to see or receive from the command. Preserve the implemented command behavior. Turn the requested fields, labels, ordering, text, binary data, files, and error details into an explicit result contract; infer a simple presentation for details the prompt leaves open.

Start with the [behavior selector](../../../docs/implementation-recipes.md#choose-the-needed-behavior): one value, repeated rows in one result, streaming results and files need different paths. The [one-value trace](../../../docs/implementation-recipes.md#one-value-trace) gives both native sender calls, exact Java parser checks and expected transport/payload bytes. Use its simple path when sufficient; load accumulator/merger guidance only for multipart output.

Reuse the current codecs and retain unrequested result fields and configuration/payload contracts. If older exec-units can still return data, preserve decoding compatibility or introduce an explicit version transition. Read the [IPC reference](../../../docs/execunit-ipc.md) for result framing and streaming modes and the [build guide](../../../docs/building.md) for parser dependencies and packaging.

Inventory every implementation under `exec-code/` and the Java support methods in `TemplateCommandTemplate.java` and `TemplateCommand.java`. Update all existing exec-units unless the user limits platforms. Keep their result field meanings and encoding consistent so one Java parser can handle them. Do not reduce advertised platform support to skip output work.

Choose an inner payload format that fits the requested data and can be implemented with the project's actual dependencies: UTF-8 text, JSON, or a documented binary layout are common choices. Java generation methods supply only these payload bytes, and `parseResult` receives only result payload bytes. The SDK/agent and native pipe helpers own the outer framing described in the [IPC reference](../../../docs/execunit-ipc.md#payload-boundary). No Java transport-codec library is required.

Use the [existing result patterns](../../../docs/existing-plugins.md#results-and-state) to choose between one complete value and multipart results. Keep decoding, merging, and presentation separate when results span messages. Scope accumulator state to the command instance or its validated `previousResult`; never store per-command state on a shared template.

## Exec-unit data

If transport helpers or runtime ownership still need implementation, follow the [native implementation map](../../../docs/native-runtime.md), including moving the Windows pipe out of `Initialize`'s short-lived `using` scope.

- In `exec-code/win/Program.cs` and the code it calls, collect the facts required for the requested output and send them through `CommunicationNamedPipesCommand.sendResult`. The files under `exec-code/win/exec-unit-utils/` are stubs in a fresh template; implement the result transport if still needed. Keep the IPC connection open until results and completion have been sent. Add new C# sources to `exec-code/win/command-execunit.csproj`.
- In `exec-code/linux/command/Main.cpp` and the code it calls, send equivalent data through `CommunicationNamedPipes::sendResult`. Add new C++ sources to `exec-code/linux/build_linux.sh`.

Define the payload shared by native senders and Java: field meanings, encoding, size bounds, and handling of multiple chunks and empty values. Use plain UTF-8 for simple text, or JSON/a documented binary layout when structured data warrants it. Send raw facts or requested file bytes that Java can format, rather than hard-coding a platform-specific display in each exec-unit. Keep `sendError` and failure completion separate from successful results; do not use stdout as the result channel.

When output becomes ongoing, configure `sendConf_ongoingResult()` before sending it. When using relay-in-blocks, enable the matching option on each platform and coordinate Java record reassembly. Follow the IPC reference for the option encoding and completion ordering; repeated `sendResult` calls alone do not configure the agent's forwarding mode.

## Java presentation

Read the [output guide](../../../docs/output.md) for exact editor signatures, complete-value versus streaming parsing, strict UTF-8 examples, and bounded reassembly. Reuse existing parser state rather than creating competing accumulators.

In `java-plugin/src/main/java/com/example/tuoni/command/TemplateCommand.java`, update `parseResult` to decode exactly that payload from the supplied `ByteBuffer`. Check lengths and encodings, handle partial/final results when needed, and throw `SerializationException` for malformed data. Use `CommandResultEditor` to produce the user's requested presentation: for example `setTextResult` or `appendTextResult` for text, `setByteArrayResult` for bytes, and `setFile` or `appendToFile` for downloadable files. Use clear field names and `commit()` the result. Apply formatting here when possible so Windows and Linux display the same way. Update `TemplateCommandTemplate.java` or the plugin README if the result description needs to change.

Verify representative output from every exec-unit against the Java parser, including empty/final notifications, large or chunked records, split UTF-8, and malformed data when relevant. Check visible result fields or downloaded bytes. Follow the build guide to compile, rebuild affected native resources, bundle any new parser dependencies, and compare final JAR entries with fresh artifacts. Report unavailable platform/runtime checks.
