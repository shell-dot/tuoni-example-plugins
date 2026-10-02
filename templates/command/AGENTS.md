# Command Plugin Template: project context

Read this file before changing the plugin. After a command, skill, or partial implementation, update the relevant facts here using the [context maintenance guide](docs/project-context.md). Preserve user-authored instructions and replace outdated facts rather than appending a session transcript. The companion CLAUDE.md points here and can hold additional client-specific instructions.

This is the initial scaffold snapshot. When editing the source template itself, keep this snapshot accurate for a fresh copy; verification of the template repository is not verification of a newly generated plugin.

## Purpose and scope

- Command name: `template-command`; plugin ID: `example.command.template`.
- Java package: `com.example.tuoni.command`.
- Purpose: named command scaffold; user-requested command behavior has not been implemented.
- Existing exec-units: Windows shellcode and Linux x64 native library. Both remain in scope unless the user limits the task. Advertised support does not establish runtime readiness.
- The scaffold's Windows capability checks currently filter by OS only. Reconcile process-architecture guards with actual artifacts during implementation; this scaffold does not establish ARM or unknown-architecture support.

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
- Schema currently declares an empty object with no additional properties and no file fields. Java validation still throws a TODO exception, so the factory is not operational even for `{}`.
- No typed plugin configuration class or plugin-specific payload format exists yet. Both generation methods supply an empty configuration buffer. The examples in [configuration.md](docs/configuration.md) are guidance, not this plugin's implemented contract.
- Agent IPC framing and message IDs are described in [execunit-ipc.md](docs/execunit-ipc.md). Record future plugin configuration fields, encoding, defaults, validation, versioning, and update semantics here or link the implemented codec/contract document.
- Windows preserves `QQQWWWEEE` for pipe-name patching. Linux uses agent-supplied FIFO paths and the `run` export.

## Logic and output status

- Inline comments describe the unfinished Java and native hooks, including configuration handoff, result framing, completion, and resource ownership. They are implementation guidance; the TODOs and stub behavior remain in place.
- Windows `Program` and IPC helper implementations are stubs; pipe ownership must span initialization, execution, reporting, and cleanup.
- Linux connects and reports an unimplemented-command failure; command behavior remains TODO.
- `parseResult` is unimplemented. There is no established result payload or presentation contract yet. Command updates explicitly report unsupported.
- Use the [native implementation map](docs/native-runtime.md) and [output guide](docs/output.md) when implementing these areas; keep this section aligned with the actual code afterward.

## Builds and verification

- Required workflow: unless the prompt explicitly overrides it, execute the complete `make build` from this plugin root after substantial coherent implementation steps and after the final code/build-input change, including focused configuration, logic, or output tasks. Wait for its result and verify all in-scope native exports and the packaged Java plugin. Use Docker for every build unless the user explicitly requests another route. If Docker is missing or unusable, inform the user and mark builds blocked without a local fallback; follow the [build checkpoints](docs/building.md#required-build-checkpoints). Record the actual command, working directory, exit status, artifact paths and failures/unavailable phases; partial compile targets do not satisfy this requirement.
- Apply the [Java artifact and initialization gate](docs/java-verification.md): verify SDK APIs, complete plugin-owned dependency packaging, the exact exported JAR, and isolated provider initialization/schema/factory paths. A normal Gradle test classpath or server Jackson must not mask missing private dependencies. Record the artifact hash and actual startup-test result; the fresh scaffold has not passed this check.
- Verify configuration and response agreement using [both levels of byte checks](docs/payload-verification.md): actual encoders/decoders and actual framing/unwrapping. Outgoing SDK configuration buffers must have position zero and an exact payload limit. A build or codec-only test does not verify startup framing.
- Build targets: Java 21, .NET Framework 4.6.2, C++11/Linux x64. SDK dependency: `com.shelldot:tuoni-plugin-sdk:0.15.0` as `compileOnly`; no JSON parser dependency is installed in the fresh template.
- Default build from the plugin root: `make build` in a Linux/WSL shell with Docker available there. Local compiler/Gradle commands in the build guide apply only when the user explicitly requests a non-Docker route. The Makefile uses `scripts/docker/run-docker.sh` to select `sudo` automatically for a local Docker socket permission denial, preserving the selected socket and BuildKit setting; explicit `DOCKER=...` overrides bypass detection.
- Native resource names: `command.shellcode` and `command-linux.native64_so`. Local distributable: `java-plugin/build/libs/command-plugin-template-0.0.1.jar`; Docker export: `build/command-plugin-template-0.0.1.jar`.
- Follow [building.md](docs/building.md) for platform tools, native conversion, dependency packaging, and checks against fresh artifact bytes.
- Verification for this generated instance: not recorded yet. Record commands, outcomes, unavailable checks, and whether native resources/JARs were rebuilt. Compilation alone does not establish runtime behavior.

## Next work and skill routing

- Start with the [implementation recipe](docs/implementation-recipes.md) for the minimum complete path, optional feature selection, and a worked JSON -> native -> Java result trace. Its fields and fixtures are examples, not implemented scaffold behavior.
- [Existing plugin patterns](docs/existing-plugins.md) maps reviewed Java/native counterparts, source ownership, compatibility constraints, and focused verification. These are reference patterns; the fresh scaffold still has the implementation TODOs listed above.

1. Record the user's intended behavior and any platform limits.
2. Use [command-implement](.agents/skills/command-implement/SKILL.md) to implement the entire command from the prompt; it coordinates `command-conf`, `command-logic`, and `command-output` through builds and verification. Use those focused skills directly for configuration, execution, or result content/presentation changes. All four skills are under `.agents/skills/` and `.claude/skills/`.
3. Replace the appropriate TODO paths and record implemented contracts, remaining limitations, and actual verification here before finishing the task.
