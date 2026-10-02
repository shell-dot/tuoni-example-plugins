# Listener Plugin Template: project context

Read this file before changing the plugin. After a command, skill, or partial implementation, update the relevant facts here using the [context maintenance guide](docs/project-context.md). Preserve user-authored instructions and replace outdated facts rather than appending a session transcript. The companion CLAUDE.md points here and can hold additional client-specific instructions.

This is the initial scaffold snapshot. When editing the source template itself, keep this snapshot accurate for a fresh copy; verification of the template repository is not verification of a newly generated plugin.

## Purpose and scope

- Plugin ID: `example.listener.template`; Java package: `com.example.tuoni.listener`.
- Purpose: named listener scaffold; user-requested listener behavior has not been implemented.
- Existing exec-units: Windows x86/x64 shellcode and Linux x64 native library. Both OS implementations remain in scope unless the user limits the task. Advertised support does not establish runtime readiness.

## Required exec-unit safety

Exec-units share the host process, and their code may be unloaded immediately after `Main` / `run` returns. They must never crash or terminate that process. Before any return, cancel and unblock owned work, unregister/drain callbacks, join/await all workers, and only then release shared state. No invocation-owned background activity may survive. Apply the [host process and unload requirements](docs/native-runtime.md#host-process-and-unload-requirements), including to reused helpers. Implement per-invocation cleanup before behavior and audit every constructor/connect/parse/execute/report/return path using the [failure-path cleanup gate](docs/native-runtime.md#failure-path-cleanup-before-return). Error reporting can itself fail and must never skip cleanup. Force operation, startup and reporting failures; verify host survival and safe immediate unload/repeated invocation separately from compilation. These are implementation requirements; the fresh scaffold has not passed lifecycle or unload verification.

## Source map

| Responsibility | File / method |
| --- | --- |
| Validation and factory | [TemplateListenerPlugin.java](java-plugin/src/main/java/com/example/tuoni/listener/TemplateListenerPlugin.java): `validateConfiguration`, `create` |
| Schema | [TemplateConfigurationSchema.java](java-plugin/src/main/java/com/example/tuoni/listener/TemplateConfigurationSchema.java): `jsonSchema`, `fileSchemas` |
| Lifecycle and serialization | [TemplateListener.java](java-plugin/src/main/java/com/example/tuoni/listener/TemplateListener.java): constructor, start/stop/delete, reconfiguration, generation, `getInfo` |
| Windows entry point | [Program.cs](exec-code/win/Program.cs); explicit C# sources in [listener-execunit.csproj](exec-code/win/listener-execunit.csproj) |
| Linux entry point | [Main.cpp](exec-code/linux/listener/Main.cpp): exported `run`; source list in [build_linux.sh](exec-code/linux/build_linux.sh) |

## Configuration and protocol

- Plugin-owned configuration, application messages, and telemetry use a straightforward format chosen for the task: UTF-8 text/JSON or explicit binary fields. Java uses standard text/binary APIs and a declared bundled JSON parser if needed. The native helper retains the host IPC protocol; see [payload boundaries](docs/execunit-ipc.md#plugin-payloads-and-host-ipc).
- Schema currently declares an empty object with no additional properties and no file fields. Java validation still throws a TODO exception, so the factory is not operational even for `{}`.
- No typed plugin configuration class or plugin-specific payload contract exists yet. Both generation methods supply an empty configuration buffer. The examples in [configuration.md](docs/configuration.md) are guidance, not this plugin's implemented contract.
- Record future field defaults, validation, wire fields/encoding/versioning, and update/rollback behavior here or link the implemented codec/contract document. Live configuration delivery has not been implemented.
- [execunit-ipc.md](docs/execunit-ipc.md) separates the local-agent pipe from the native-to-Java application transport. No application transport is implemented in this scaffold.
- Windows preserves `QQQWWWEEE` for pipe-name patching. Linux uses agent-supplied FIFO paths and the `run` export.

## Logic, lifecycle, and output status

- Windows `Program` and IPC helpers are stubs. Linux has an exported entry point but no listener transport loop.
- Java startup, reconfiguration, and configuration-update serialization remain TODO. Stop/delete currently change status without an implemented resource lifecycle; `getInfo()` is placeholder text.
- No Java connection handler, custom telemetry model, or output contract exists yet. The suggested files in [listener-java.md](docs/listener-java.md) are not existing implementations.
- Use the [native implementation map](docs/native-runtime.md) and [Java listener walkthrough](docs/listener-java.md) when implementing these areas. Record the actual sender, receiver, presentation surface, and resource ownership afterward.

## Builds and verification

- Required workflow: unless the prompt explicitly overrides it, execute the complete `make build` from this plugin root after substantial coherent implementation steps and after the final code/build-input change, including focused configuration, logic, or output tasks. Wait for its result and verify all in-scope native exports and the packaged Java plugin. Use Docker for every build unless the user explicitly requests another route. If Docker is missing or unusable, inform the user and mark builds blocked without a local fallback; follow the [build checkpoints](docs/building.md#required-build-checkpoints). Record the actual command, working directory, exit status, artifact paths and failures/unavailable phases; partial compile targets do not satisfy this requirement.
- Apply the [Java artifact and initialization gate](docs/java-verification.md): verify SDK APIs, complete plugin-owned dependency packaging, the exact exported JAR, and isolated provider initialization/schema/factory paths. A normal Gradle test classpath or server Jackson must not mask missing private dependencies. Record the artifact hash and actual startup-test result; the fresh scaffold has not passed this check.
- Verify configuration and response agreement using [both levels of byte checks](docs/payload-verification.md): actual encoders/decoders and actual framing/unwrapping. Outgoing SDK configuration buffers must have position zero and an exact payload limit. A build or codec-only test does not verify startup framing.
- Build targets: Java 21, .NET Framework 4.6.2, C++11/Linux x64. SDK dependency: `com.shelldot:tuoni-plugin-sdk:0.15.0` as `compileOnly`; no JSON parser dependency is installed in the fresh template.
- Default build from the plugin root: `make build` in a Linux/WSL shell with Docker available there. Local compiler/Gradle commands in the build guide apply only when the user explicitly requests a non-Docker route. The Makefile uses `scripts/docker/run-docker.sh` to select `sudo` automatically for a local Docker socket permission denial, preserving the selected socket and BuildKit setting; explicit `DOCKER=...` overrides bypass detection.
- Native resource names: `listener.shellcode` and `listener-linux.native64_so`. Local distributable: `java-plugin/build/libs/listener-plugin-template-0.0.1.jar`; Docker export: `build/listener-plugin-template-0.0.1.jar`.
- Follow [building.md](docs/building.md) for platform tools, native conversion, dependency packaging, and checks against fresh artifact bytes.
- Verification for this generated instance: not recorded yet. Record commands, outcomes, unavailable checks, and whether native resources/JARs were rebuilt. Compilation alone does not establish runtime behavior.

## Next work and skill routing

- Start with [implementation recipes](docs/implementation-recipes.md) to select transport ownership, record the configuration/protocol contract, and implement the minimum complete metadata/request/command path. Its transport and payload choices are examples, not an implemented peer protocol.
- [Existing plugin patterns](docs/existing-plugins.md) maps reviewed Java/native counterparts, source ownership, compatibility constraints, and focused verification. These are reference patterns; the fresh scaffold still has the implementation TODOs listed above.

1. Record the user's intended listener transport, output, and any platform limits.
2. Use [listener-implement](.agents/skills/listener-implement/SKILL.md) to implement the entire listener from the prompt; it coordinates `listener-conf`, `listener-logic`, and `listener-output` through builds and verification. Use those focused skills directly for configuration, behavior/lifecycle, or returned data/presentation changes. All four skills are under `.agents/skills/` and `.claude/skills/`.
3. Replace the appropriate TODO paths and record implemented contracts, remaining limitations, and actual verification here before finishing the task.
