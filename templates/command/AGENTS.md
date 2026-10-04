# Command Plugin Template: project context

Read this file before changing the plugin. After a command, skill, or partial implementation, update the relevant facts here using the [context maintenance guide](docs/project-context.md). Preserve user-authored instructions and replace outdated facts rather than appending a session transcript. The companion CLAUDE.md points here and can hold additional client-specific instructions.

This is the current source-template snapshot. When editing the source template itself, keep this snapshot accurate for a fresh copy; verification of the template repository is not verification of a newly generated plugin.

## Purpose and scope

- Command name: `template-command`; plugin ID: `example.command.template`.
- Java package: `com.example.tuoni.command`.
- Purpose: working no-op starting point. The default command accepts `{}`, performs no operation, emits `DONE` as UTF-8 result text, and then reports success on a usable connection.
- Existing exec-units: Windows shellcode and Linux x64 native library. Both remain in scope unless the user limits the task. Advertised support does not establish runtime readiness.
- Capability checks share the same OS/process-architecture guard: Windows X86/X64 shellcode (the bundled converter defaults to dual architecture), Linux X64 native library. ARM and unknown metadata are rejected.

## Required exec-unit safety

Exec-units share the host process, and their code may be unloaded immediately after `Main` / `run` returns. They must never crash or terminate that process. Before any return, cancel and unblock owned work, unregister/drain callbacks, join/await all workers, and only then release shared state. No invocation-owned background activity may survive. Apply the [host process and unload requirements](docs/native-runtime.md#host-process-and-unload-requirements), including to reused helpers. Implement per-invocation cleanup before behavior and audit every constructor/connect/parse/execute/report/return path using the [failure-path cleanup gate](docs/native-runtime.md#failure-path-cleanup-before-return). Error reporting can itself fail and must never skip cleanup. Force operation, startup and reporting failures; verify host survival and safe immediate unload/repeated invocation separately from compilation. These are implementation requirements; the fresh scaffold has not passed lifecycle or unload verification.

## Required command completion

Every implemented invocation must reach one completion owner. Before closing a usable reporting connection and returning, send exactly one checked terminal success or failure after required output and operation-worker completion. Empty output, early returns, errors and cancellation still need a final outcome. Error text, logging and a return code are not completion. Apply the [command completion gate](docs/command-completion.md), verify host final state and explicit startup/transport failure handling, and record unavailable checks. This scaffold has not passed those runtime checks.

## Source map

| Responsibility | File / method |
| --- | --- |
| Registration | [TemplateCommandPlugin.java](java-plugin/src/main/java/com/example/tuoni/command/TemplateCommandPlugin.java): `getCommandTemplates` |
| Validation and factory | [TemplateCommandTemplate.java](java-plugin/src/main/java/com/example/tuoni/command/TemplateCommandTemplate.java): `validateConfiguration`, `createCommand`, examples, compatibility |
| Schema | [TemplateConfigurationSchema.java](java-plugin/src/main/java/com/example/tuoni/command/TemplateConfigurationSchema.java): `jsonSchema`, `fileSchemas` |
| Serialization and output | [TemplateCommand.java](java-plugin/src/main/java/com/example/tuoni/command/TemplateCommand.java): constructor, `generateExecUnit`, `generateShellCode`, `parseResult`, update/cleanup hooks |
| Windows entry point | [Program.cs](exec-code/win/Program.cs); explicit C# sources in [command-execunit.csproj](exec-code/win/command-execunit.csproj) |
| Linux entry point | [Main.cpp](exec-code/linux/command/Main.cpp): exported `run`; source list in [build_linux.sh](exec-code/linux/build_linux.sh) |

## Configuration and protocol

- Java and native code agree on an inner payload format suited to the requested data, such as UTF-8 text, JSON or an explicit binary layout. The SDK/agent and native helpers own the host pipe envelope; Java handles only payload bytes and requires no extra transport-codec classes. See the [payload boundary](docs/execunit-ipc.md#payload-boundary).
- Schema declares an empty object with no additional properties and no file fields. Java validation accepts `{}` with JSON whitespace, including multipart JSON with no files; other values, fields, malformed JSON, and uploads are rejected. The `default` example uses `{}`.
- Both generation methods call `serializeConfiguration()` and supply fresh zero-length buffers at position/limit zero. Both native entrypoints require exactly zero payload bytes. Windows startup failure returns `null`; Linux startup failure throws, so neither is confused with valid empty input. No private JSON dependency or typed configuration is needed for this no-field contract. Add a typed parser and encoder when fields are introduced; the examples in [configuration.md](docs/configuration.md) are guidance.
- Agent IPC framing and message IDs are described in [execunit-ipc.md](docs/execunit-ipc.md). Record future plugin configuration fields, encoding, defaults, validation, versioning, and update semantics here or link the implemented codec/contract document.
- Windows preserves `QQQWWWEEE` for pipe-name patching. Linux uses agent-supplied FIFO paths and the `run` export.

## Logic and output status

- Windows `Main` owns the pipe through `Initialize`, `Execute`, one checked `Complete`, and `Cleanup` in `finally`. `Execute` sends `DONE` with `sendResult` and throws if the write fails; success is selected only after the result write succeeds. Failure diagnostics cannot skip failure completion. No callbacks are registered, so no reader worker starts. Disposal releases resources even after failed startup/disconnect; optional readers are unblocked and joined before disposal returns.
- Linux `run` owns the pipe through RAII and contains startup/operation/reporting exceptions. `execute` sends `DONE` with `sendResult` and throws if the write fails; success is selected only after the result write succeeds. Invalid payload selects failure. One checked terminal attempt precedes destruction. No callbacks/workers are installed, and there is no artificial completion delay.
- Both transports bound frame allocation, check complete reads/writes, and return `bool` from result/error/terminal sends. A failed write disables further reporting. Linux blocks/consumes generated `SIGPIPE` on the calling thread without changing host-wide handlers, including for the readiness byte.
- Result payload contract: both exec-units send exactly `44 4f 4e 45` (`DONE`, UTF-8, no newline or terminator) before terminal success. `parseResult` decodes complete UTF-8 payloads, appends to the visible `output` text result, and commits. Empty final notifications preserve `DONE` without editor changes; malformed UTF-8 is rejected before editing, and input buffer positions are preserved. Streaming/block splitting needs additional decoding state if enabled. Live updates remain explicitly unsupported. Java initialization/status/stop hooks intentionally own no resources.
- Linux optional callback helpers still detach their listener; the default no-op never invokes them. Before enabling updates/stop/streaming, replace that path with synchronized, cancellable, joined ownership as required above. Blocking transport startup/I/O and actual host disconnect handling still require runtime verification.
- Use the [native implementation map](docs/native-runtime.md) and [output guide](docs/output.md) when implementing these areas; keep this section aligned with the actual code afterward.

## Builds and verification

- Required workflow: unless the prompt explicitly overrides it, execute the complete `make build` from this plugin root after substantial coherent implementation steps and after the final code/build-input change, including focused configuration, logic, or output tasks. Wait for its result and verify all in-scope native exports and the packaged Java plugin. Use Docker for every build unless the user explicitly requests another route. If Docker is missing or unusable, inform the user and mark builds blocked without a local fallback; follow the [build checkpoints](docs/building.md#required-build-checkpoints). Record the actual command, working directory, exit status, artifact paths and failures/unavailable phases; partial compile targets do not satisfy this requirement.
- Apply the [Java artifact and initialization gate](docs/java-verification.md): verify SDK APIs, complete plugin-owned dependency packaging, the exact exported JAR, and isolated provider initialization/schema/factory paths. A normal Gradle test classpath or server Jackson must not mask missing private dependencies. Record the artifact hash and actual startup-test result; the fresh scaffold has not passed this check.
- Verify configuration and response agreement using [both levels of byte checks](docs/payload-verification.md): actual encoders/decoders and actual framing/unwrapping. Outgoing SDK configuration buffers must have position zero and an exact payload limit. A build or codec-only test does not verify startup framing.
- Build targets: Java 21, .NET Framework 4.6.2, C++11/Linux x64. SDK dependency: `com.shelldot:tuoni-plugin-sdk:0.15.0` as `compileOnly`; no JSON parser dependency is installed in the fresh template.
- Default build from the plugin root: `make build` in a Linux/WSL shell with Docker available there. Local compiler/Gradle commands in the build guide apply only when the user explicitly requests a non-Docker route. The Makefile uses `scripts/docker/run-docker.sh` to select `sudo` automatically for a local Docker socket permission denial, preserving the selected socket and BuildKit setting; explicit `DOCKER=...` overrides bypass detection.
- Native resource names: `command.shellcode` and `command-linux.native64_so`. Local distributable: `java-plugin/build/libs/command-plugin-template-0.0.1.jar`; Docker export: `build/command-plugin-template-0.0.1.jar`.
- Follow [building.md](docs/building.md) for platform tools, native conversion, dependency packaging, and checks against fresh artifact bytes.
- Template-source verification: cached SDK 0.15.0 signatures inspected with `javap`; bundled converter help confirms X86/X64 default; `python -m unittest discover -s tools -p test_scaffold_plugin.py` passed (12 tests), and `git diff --check` passed. Full `make build` blocked: Make/Docker unavailable; `wsl --exec sh -lc 'make build'` from the template root returned exit 1 because WSL is not installed. No native resources or JAR were rebuilt; archive hash, isolated Java initialization, real IPC completion, host failure state, and unload/repeated invocation checks remain unverified. These source-template checks are not verification of a generated instance. Documentation now describes the implemented default and extension points across the README, guides, and mirrored skills; keep those references synchronized when changing the contract. Documentation verification: all 36 repository skill files passed the skill validator; 669 local links/anchors and 18 mirrored skill pairs passed consistency checks; all 12 scaffolding tests passed after the documentation update. No code/build inputs changed in this documentation pass.

## Next work and skill routing

- Start with the [implementation recipe](docs/implementation-recipes.md) for the minimum complete path, optional feature selection, and a worked JSON -> native -> Java result trace. Its fields and fixtures are examples, not implemented scaffold behavior.
- [Existing plugin patterns](docs/existing-plugins.md) maps reviewed Java/native counterparts, source ownership, compatibility constraints, and focused verification. These are reference patterns for replacing the working no-op with command behavior.

1. Record the user's intended behavior and any platform limits.
2. Use [command-implement](.agents/skills/command-implement/SKILL.md) to implement the entire command from the prompt; it coordinates `command-conf`, `command-logic`, and `command-output` through builds and verification. Use those focused skills directly for configuration, execution, or result content/presentation changes. All four skills are under `.agents/skills/` and `.claude/skills/`.
3. Extend the appropriate hooks and record implemented contracts, remaining limitations, and actual verification here before finishing the task.
