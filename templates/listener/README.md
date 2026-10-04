# Listener plugin skeleton

Start with the [shared setup and build instructions](../README.md). This folder
contains one listener plugin, a C# Windows entry point, and a C++ Linux x64
entry point.

| File under `java-plugin/src/main/java/com/example/tuoni/listener/` | Purpose |
| --- | --- |
| `TemplateListenerPlugin.java` | Plugin initialization, configuration validation, and listener factory |
| `TemplateListener.java` | SDK listener lifecycle, reconfiguration, compatibility, and serialization hooks |
| `TemplateConfigurationSchema.java` | Empty configuration schema to customize |

To implement the entire listener from a prompt, use `$listener-implement` in Codex
or `/listener-implement` in Claude Code. The [implementation skill](.agents/skills/listener-implement/SKILL.md)
coordinates configuration, logic, and output through builds, verification, and
project-context updates. It is included in this folder and in generated plugins.

To add configuration fields across Java and the Windows/Linux exec-units, use
`$listener-conf` in Codex or `/listener-conf` in Claude Code. The skill is included
in this folder and in plugins created from this template.

To implement listener behavior with minimal data handling, use `$listener-logic`
in Codex or `/listener-logic` in Claude Code.

To change what users see or receive from listener activity, use
`$listener-output` in Codex or `/listener-output` in Claude Code.

The plugin-root [AGENTS.md](AGENTS.md) stores the current implementation context; [CLAUDE.md](CLAUDE.md) directs Claude to that shared context. Each template skill reads and updates it so later tasks retain the plugin's decisions, contracts, checks, and remaining work.

The following guides are copied into generated plugins:

| Task | Guide |
| --- | --- |
| Choose transport ownership and follow the complete implementation path | [Implementation recipes](docs/implementation-recipes.md) |
| Find a matching Java/native source pair | [Existing listener patterns](docs/existing-plugins.md) |
| Maintain context for later commands and skills | [Context maintenance](docs/project-context.md) |
| Add configuration and validate its payload encoding | [Configuration walkthrough](docs/configuration.md) |
| Extend native behavior and preserve IPC ownership | [Native runtime](docs/native-runtime.md) |
| Check message IDs, framing, and configuration delivery | [IPC and transport reference](docs/execunit-ipc.md) |
| Implement Java lifecycle, receive data, and present output | [Java listener walkthrough](docs/listener-java.md) |
| Add dependencies, build, and verify the JAR | [Build guide](docs/building.md) |
| Check the exported JAR and isolated Java initialization | [Java verification](docs/java-verification.md) |
| Compare real encoders, decoders, and IPC framing | [Payload verification](docs/payload-verification.md) |

## Default behavior

The default listener accepts this configuration:

```json
{}
```

Validation accepts JSON whitespace around the empty object, including multipart
configuration with no uploaded files. Other fields, values, malformed JSON, and
uploads are rejected. The `default` example is `{}`. Java serializes this input as
zero native payload bytes, with each buffer's position and limit both zero;
`{}` is not sent as text to the exec-unit.

Java factory creation, start/stop/delete, valid empty reconfiguration, and updated
configuration serialization work without placeholder exceptions. Repeated starts
and stops are harmless; a stopped listener can restart. Deletion is terminal.
`getInfo()` shows `Listener template <id>: <status>`. `STARTED` describes the Java
object's local state; the idle template owns no endpoint and receives no native
health observations. Start or reconfigure after deletion rejects the invalid lifecycle request.

Both native entrypoints use the implemented pipe/FIFO utilities to connect to the
local agent, receive and validate an empty configuration payload, and remain idle
until the host closes the connection. Windows waits for its owned reader in
`WaitForStop`; Linux's exported `run(char*, char*)` waits in `serve`. Cleanup joins
the reader and releases the connection before returning, including after failed startup.

## Extend the template

The data traffic channel is intentionally TODO. Add Java transport setup and SDK
request/command handling in `TemplateListener.start`, Windows channel behavior in
`Program.Initialize`/`WaitForStop`, and matching Linux behavior in `serve`. The
cleanup hooks also mark where to stop and join any added channel workers. The idle
default opens no application endpoint and exchanges no metadata, requests, or commands.
The local-agent pipe/FIFO is separate from the future data traffic channel to Java.
Before using the request helpers for traffic, add timeout/disconnect cancellation
for pending responses. The listener protocol has no command-style terminal success
report or stop message.

The Java class implements `ExecUnitListener` and `ShellcodeListener`. It advertises
Windows x86 and x64 payload types with `SHELLCODE_NATIVE`, and Linux x64 with
`NATIVE_LIB`. Linux loads `/listener-linux.native64_so` with the `run` export; the
agent supplies FIFO paths, so no byte patch is needed. Windows loads
`/listener.shellcode` from the JAR, replaces every UTF-16LE `QQQWWWEEE` pipe-name
placeholder with the SDK pipe name, and returns it with named-pipe IPC and an empty
configuration buffer. The new name must have the same encoded length as the
placeholder. Build the C# Release project first so its post-build step creates
`java-plugin/src/main/resources/listener.shellcode`. Build the Linux library before
a direct Java build so Gradle can include it.
Startup and valid `{}` replacement serialization use the same empty native payload.
No fields require live application; serialization alone does not prove host delivery.

## Build

Skills build with Docker unless the user explicitly requests another route. If Docker
is missing or unusable, inform the user and report the blocked build; do not fall
back to local tools. The local build examples below apply only to an explicitly
requested non-Docker route.

Open [exec-code/win/listener-execunit.sln](exec-code/win/listener-execunit.sln) in Visual Studio,
or build the C# exec-unit from this folder:

```powershell
msbuild exec-code/win/listener-execunit.sln /p:Configuration=Release
```

Output: `exec-code/win/bin/Release/listener-execunit-template.exe`.
Java output: `java-plugin/build/libs/listener-plugin-template-0.0.1.jar`.

For a direct Linux build, run `bash exec-code/linux/build_linux.sh` on Linux with
`g++`. This writes `exec-code/linux/build/listener-linux.native64_so`. To build it
inside Docker and extract it for Gradle, run `make build-linux`.

Use a Linux shell (WSL on Windows), GNU Make, standard Unix file utilities, and
Docker configured for Linux containers. Run `make build` from this folder. The JAR,
EXE, generated shellcode, and Linux library are extracted to `build/`.
Run `make build-dotnet` to compile and extract only the EXE to `build/`.
