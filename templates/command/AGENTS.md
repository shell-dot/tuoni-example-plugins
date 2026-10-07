# Command Plugin Template: project context

Read this file before changing the plugin. After a command, skill, or partial implementation, update the relevant facts here using the [context maintenance guide](docs/project-context.md). Preserve user-authored instructions and replace outdated facts rather than appending a session transcript. The companion CLAUDE.md points here and can hold additional client-specific instructions.

This is the current source-template snapshot. When editing the source template itself, keep this snapshot accurate for a fresh copy; verification of the template repository is not verification of a newly generated plugin.

## Purpose and scope

For explicit OS, architecture, or format limits, use [support scope](docs/support-scope.md).
These limits take precedence over generic all-exec-unit coverage instructions.
Record task/test limits separately from changes to the supported set; the full
template inventory below does not imply every combination remains requested.

- Command name: `template-command`; plugin ID: `example.command.template`.
- Java package: `com.example.tuoni.command`.
- Purpose: working no-op starting point. The default command accepts `{}`, performs no operation, emits `DONE` as UTF-8 result text, and then reports success on a usable connection.
- Existing exec-units: Windows x86/x64 shellcode, .NET DLL, .NET EXE, native DLLs, and Linux x64 native library. All remain in scope unless the user limits the task. Advertised support does not establish runtime readiness.
- Capability checks share the same OS/process-architecture guard: Windows X86/X64 native DLLs, shellcode and AnyCPU .NET DLL/EXE (the bundled converter defaults to dual-architecture shellcode), Linux X64 native library. ARM and unknown metadata are rejected.

## Required exec-unit safety

**Windows `native-lib`: no project-authored exceptions.** Follow the [Windows exception policy](docs/native-memory-safety.md#windows-no-authored-exceptions): use checked status/results, prohibit authored throw/rethrow and exception-based error handling, and treat catches only as defensive containment for dependency/runtime failures. This is a required review criterion, not a claim that the existing implementation has been audited for compliance.

For Windows/Linux C++ review, use [native memory safety](docs/native-memory-safety.md). Identify ownership and valid buffer extents before access, and investigate suspected memory faults in an isolated local test process. Record observed diagnostics and unavailable checks; these review instructions are not runtime verification.

Exec-units share the host process, and their code may be unloaded immediately after `Main` / `start` / `run` returns. They must never crash or terminate that process. Before any return, cancel and unblock owned work, unregister/drain callbacks, join/await all workers, and only then release shared state. No invocation-owned background activity may survive. Apply the [host process and unload requirements](docs/native-runtime.md#host-process-and-unload-requirements), including to reused helpers. Implement per-invocation cleanup before behavior and audit every constructor/connect/parse/execute/report/return path using the [failure-path cleanup gate](docs/native-runtime.md#failure-path-cleanup-before-return). Error reporting can itself fail and must never skip cleanup. Force operation, startup and reporting failures; verify host survival and safe immediate unload/repeated invocation separately from compilation. These are implementation requirements; the fresh scaffold has not passed lifecycle or unload verification.

## Required command completion

Every implemented invocation must reach one completion owner. Before closing a usable reporting connection or returning from `Main`, `start`, or `run`, send exactly one checked `sendReturnSuccess()` on success or `sendReturnFailed()` on failure after required output and operation-worker completion. Empty output, early returns, errors and cancellation still need a final outcome. **`sendError(...)` only sends diagnostic text; it does not mark the command failed and never replaces `sendReturnFailed()`.** Logging and a return code are not completion either. Apply the [command completion gate](docs/command-completion.md), verify host final state and explicit startup/transport failure handling, and record unavailable checks. This scaffold has not passed those runtime checks.

## Source map

Read the [exec-unit overview](docs/execunit-overview.md) for terminology, the
three source families versus generated formats, and a plain-language account of
the default lifecycle. It describes current behavior, not additional implemented
features or runtime verification.

| Responsibility | File / method |
| --- | --- |
| Registration | [TemplateCommandPlugin.java](java-plugin/src/main/java/com/example/tuoni/command/TemplateCommandPlugin.java): `getCommandTemplates` |
| Validation and factory | [TemplateCommandTemplate.java](java-plugin/src/main/java/com/example/tuoni/command/TemplateCommandTemplate.java): `validateConfiguration`, `createCommand`, examples, compatibility |
| Schema | [TemplateConfigurationSchema.java](java-plugin/src/main/java/com/example/tuoni/command/TemplateConfigurationSchema.java): `jsonSchema`, `fileSchemas` |
| Serialization and output | [TemplateCommand.java](java-plugin/src/main/java/com/example/tuoni/command/TemplateCommand.java): constructor, `generateExecUnit`, `generateShellCode`, `parseResult`, update/cleanup hooks |
| Windows entry point | [Program.cs](exec-code/win/Program.cs); explicit C# sources in [command-execunit.csproj](exec-code/win/command-execunit.csproj) |
| Windows native entry point | [Main.cpp](exec-code/win-native/command/Main.cpp): exported `start`; source list in [build_windows.sh](exec-code/win-native/build_windows.sh); [ownership and verification](docs/windows-native.md) |
| Linux entry point | [Main.cpp](exec-code/linux/command/Main.cpp): exported `run`; source list in [build_linux.sh](exec-code/linux/build_linux.sh) |

## Configuration and protocol

- Java and native code agree on an inner payload format suited to the requested data, such as UTF-8 text, JSON or an explicit binary layout. The SDK/agent and native helpers own the host pipe envelope; Java handles only payload bytes and requires no extra transport-codec classes. See the [payload boundary](docs/execunit-ipc.md#payload-boundary).
- Schema declares an empty object with no additional properties and no file fields. Java validation accepts `{}` with JSON whitespace, including multipart JSON with no files; other values, fields, malformed JSON, and uploads are rejected. The `default` example uses `{}`.
- Both generation methods call `serializeConfiguration()` and supply fresh zero-length buffers at position/limit zero. All exec-unit entrypoints require exactly zero payload bytes. Managed Windows startup failure returns `null`; Windows native startup is checked with `TryConnect`; Linux startup failure throws, so neither is confused with valid empty input. No private JSON dependency or typed configuration is needed for this no-field contract. Add a typed parser and encoder when fields are introduced; the examples in [configuration.md](docs/configuration.md) are guidance.
- Agent IPC framing and message IDs are described in [execunit-ipc.md](docs/execunit-ipc.md). Record future plugin configuration fields, encoding, defaults, validation, versioning, and update semantics here or link the implemented codec/contract document.
- Windows shellcode preserves `QQQWWWEEE` for pipe-name patching. Managed EXE/DLL builds accept the pipe name in `args[0]` and are never byte-patched. DLL entrypoint metadata is generated from `RootNamespace` as `<namespace>.Program::start`. Windows native DLLs export `start(const char*)` and receive a local pipe name without byte patching. Linux uses agent-supplied FIFO paths and the `run` export. All formats share the existing configuration and behavior.

## Logic and output status

- Windows `Main` owns the pipe through `Initialize`, `Execute`, one checked `Complete`, and `Cleanup` in `finally`. `Execute` sends `DONE` with `sendResult` and throws if the write fails; success is selected only after the result write succeeds. Failure diagnostics cannot skip failure completion. No callbacks are registered, so no reader worker starts. Disposal releases resources even after failed startup/disconnect; optional readers are unblocked and joined before disposal returns.
- Linux `run` owns the pipe through RAII and contains startup/operation/reporting exceptions. `execute` sends `DONE` with `sendResult` and throws if the write fails; success is selected only after the result write succeeds. Invalid payload selects failure. One checked terminal attempt precedes destruction. No callbacks/workers are installed, and there is no artificial completion delay.
- Both transports bound frame allocation, check complete reads/writes, and return `bool` from result/error/terminal sends. A failed write disables further reporting. Linux blocks/consumes generated `SIGPIPE` on the calling thread without changing host-wide handlers, including for the readiness byte.
- Result payload contract: all exec-units send exactly `44 4f 4e 45` (`DONE`, UTF-8, no newline or terminator) before terminal success. `parseResult` decodes complete UTF-8 payloads, appends to the visible `output` text result, and commits. Empty final notifications preserve `DONE` without editor changes; malformed UTF-8 is rejected before editing, and input buffer positions are preserved. Streaming/block splitting needs additional decoding state if enabled. Live updates remain explicitly unsupported. Java initialization/status/stop hooks intentionally own no resources.
- Linux optional callback helpers still detach their listener; the default no-op never invokes them. Before enabling updates/stop/streaming, replace that path with synchronized, cancellable, joined ownership as required above. Blocking transport startup/I/O and actual host disconnect handling still require runtime verification.
- Use the [native implementation map](docs/native-runtime.md) and [output guide](docs/output.md) when implementing these areas; keep this section aligned with the actual code afterward.

- Windows native DLLs use copied `ExecUnitUtils::CommunicationNamedPipesCommand`, base pipe, and `TLV` sources from `commands_default/common/CommonCppExecUnit`. The utility files are unchanged; a MinGW include shim handles header-name casing, and the build force-includes `compat/mingw/Win32Compatibility.h` to supply the documented `ERROR_UNHANDLED_EXCEPTION` value only when the toolchain headers omit it. `exec-code/win-native/command/Main.cpp` directly owns the scoped pipe and one checked terminal report. The no-op registers empty callbacks, validates empty configuration, and sends `DONE` before success; invalid configuration selects failure. The utility still starts a reader, which its destructor cancels and joins before DLL return. Defensive catches contain unexpected library/runtime exceptions. [Utility provenance and local changes](exec-code/win-native/exec-unit-utils/README.md) are recorded beside the sources. The local runtime harness requires freshly built DLLs; this refactor has not passed DLL runtime verification.

## Builds and verification

- Required workflow: unless the prompt explicitly overrides it, execute the complete `make build` from this plugin root after substantial coherent implementation steps and after the final code/build-input change, including focused configuration, logic, or output tasks. Wait for its result and verify all in-scope native exports and the packaged Java plugin. Use Docker for every build unless the user explicitly requests another route. If Docker is missing or unusable, inform the user and mark builds blocked without a local fallback; follow the [build checkpoints](docs/building.md#required-build-checkpoints). Record the actual command, working directory, exit status, artifact paths and failures/unavailable phases; partial compile targets do not satisfy this requirement.
- Apply the [Java artifact and initialization gate](docs/java-verification.md): verify SDK APIs, complete plugin-owned dependency packaging, the exact exported JAR, and isolated provider initialization/schema/factory paths. A normal Gradle test classpath or server Jackson must not mask missing private dependencies. Record the artifact hash and actual startup-test result; the fresh scaffold has not passed this check.
- Verify configuration and response agreement using [both levels of byte checks](docs/payload-verification.md): actual encoders/decoders and actual framing/unwrapping. Outgoing SDK configuration buffers must have position zero and an exact payload limit. A build or codec-only test does not verify startup framing.
- Build targets: Java 21, .NET Framework 4.6.2, C++11/Windows x86/x64 (MinGW) and Linux x64. SDK dependency: `com.shelldot:tuoni-plugin-sdk:0.15.0` as `compileOnly`; no JSON parser dependency is installed in the fresh template.
- Default build from the plugin root: `make build` in a Linux/WSL shell with Docker available there. Local compiler/Gradle commands in the build guide apply only when the user explicitly requests a non-Docker route. The Makefile uses `scripts/docker/run-docker.sh` to select `sudo` automatically for a local Docker socket permission denial, preserving the selected socket and BuildKit setting; explicit `DOCKER=...` overrides bypass detection.
- Execution resource names: `command.shellcode`, `command.dotnet_exe`, `command.dotnet_dll`, `command.dotnet_dll_method`, `command.native32_dll`, `command.native64_dll`, and `command-linux.native64_so`. Local distributable: `java-plugin/build/libs/command-plugin-template-0.0.1.jar`; Docker export: `build/command-plugin-template-0.0.1.jar`.
- Follow [building.md](docs/building.md) for platform tools, native conversion, dependency packaging, and checks against fresh artifact bytes.

<!-- template-verification:start -->
## Source-template verification

These records belong to this source template only. The scaffolder replaces this section with an unverified status in every generated plugin. Keep persistent build instructions and unresolved source limitations outside this section.

- Windows native command template simplification: `exec-code/win-native/command/Main.cpp` directly owns the no-op, scoped pipe and checked terminal report; the unused template `common/CommandRuntime.h` was removed. Three focused scaffolding tests and the command utility provenance test passed. The three edited template skill mirrors match, and `git diff --check` passed. A source search found no authored `throw` in the Windows native template C++ files. The required `make build` from this template root was attempted through Git Bash but stopped before compilation because `make` is unavailable; Docker is also unavailable. No fresh DLL, runtime harness, JAR, or unload check was produced by this change.

- Native memory-safety guidance: the local skills and repository routers link a general C/C++ review covering ownership, bounds, allocator pairing, API failures, races, and isolated diagnostic tests. Source-template validation passed the three existing documentation-copy, context-copy, and skill-mirror tests; all 36 repository/template skill files passed the skill-creator validator. This documentation-only change provides no new native build, sanitizer, or runtime evidence for the template or any generated plugin.

- Documentation-only orientation and support-scope checks: the two existing scaffolding tests for copied skills/references and project context passed from `tools/` with `python -B -m unittest test_scaffold_plugin.ScaffoldPluginTests.test_skills_and_references_survive_scaffolding test_scaffold_plugin.ScaffoldPluginTests.test_plugin_context_survives_scaffolding -v`. The skill-creator validator passed for all 20 edited skill files; edited Codex/Claude mirrors were byte-identical. These checks include both template kinds and establish no new build or runtime evidence. No execution code, build inputs, artifacts, or actual support declarations changed.

- Template-source verification: SDK 0.15.0 execution-unit types and metadata APIs were inspected with `javap`. Scaffolding checks cover managed/native artifact paths, DLL entrypoint metadata, renamed native source directories, utility provenance, and Java format checks. The Docker Java build runs `execUnitFormatsCheck` for platform selection, PE roles/architectures, resource bytes, entrypoints, and buffer independence; it has not run here. Its command metadata fixture uses the SDK 0.15.0 `AgentMetadata.builder(UUID)` because `AgentMetadata` is sealed; only the ordinary `AgentInfo` interface is proxied. After the defensive fixes, guidance updates, MinGW compatibility fix, and SDK metadata fixture correction, the repository tooling suite ran 74 tests: 71 passed and 3 skipped. Scaffolding preserves both compatibility headers byte-for-byte; the six upstream command utility files and recorded hashes remain unchanged. Python/Bash syntax, managed project XML, matching utility copies, focused skill mirrors, and `git diff --check` passed. Runtime harnesses now include bounded local update-before-stop and invalid-parent startup cleanup fixtures; no DLL was loaded for these checks. Final `make build` from this template root via Git Bash returned exit 127 (`make: command not found`). Docker, GNU Make, and WSL are unavailable, so full builds, Java format checks, exported-JAR hash/initialization, actual IPC, and immediate unload/repeated invocation remain unverified. No native binaries or JAR were rebuilt. These source-template checks do not verify a generated instance.

- Creation-skill audit: template verification history is now isolated from generated-plugin context, including default and restricted scaffolds. Documentation checks cover implementation-skill copies and link section targets, including repeated headings and fenced examples. From the repository root, `python -B -m unittest discover -s tools -p test_scaffold_plugin.py -v` ran 23 tests: 22 passed and the Make integration test was skipped because GNU Make is unavailable. These are documentation/scaffolding checks only; no native build, packaging, or runtime checks were performed for this audit.
- Command completion reminder: all root/template command skills and both client mirrors explicitly distinguish diagnostic `sendError(...)` from terminal `sendReturnFailed()`, and require one checked outcome before entrypoint return on a usable connection. The three focused scaffold tests for copied skills/references, skill mirrors, and project context passed; the skill-creator validator passed all 18 command skill files. This documentation-only update adds no native build or runtime evidence.
- Creation skill naming: the repository creation skill is `command-new`; its client mirrors, routing advice, and copied context references use that name. Renamed-skill validation and 20 focused scaffold/routing tests passed; three symlink tests were skipped because the required Windows privilege is unavailable. This metadata/documentation change adds no native build or runtime evidence.
<!-- template-verification:end -->

## Next work and skill routing

- Start with the [implementation recipe](docs/implementation-recipes.md) for the minimum complete path, optional feature selection, and a worked JSON -> native -> Java result trace. Its fields and fixtures are examples, not implemented scaffold behavior.
- [Existing plugin patterns](docs/existing-plugins.md) maps reviewed Java/native counterparts, source ownership, compatibility constraints, and focused verification. These are reference patterns for replacing the working no-op with command behavior.

1. Record the user's intended behavior and any platform limits.
2. Use [command-implement](.agents/skills/command-implement/SKILL.md) to implement the entire command from the prompt; it coordinates `command-conf`, `command-logic`, and `command-output` through builds and verification. Use those focused skills directly for configuration, execution, or result content/presentation changes. All four skills are under `.agents/skills/` and `.claude/skills/`.
3. Extend the appropriate hooks and record implemented contracts, remaining limitations, and actual verification here before finishing the task.
