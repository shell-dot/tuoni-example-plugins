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
| Implement native helpers and own the IPC connection | [Native runtime](docs/native-runtime.md) |
| Check message IDs, framing, and configuration delivery | [IPC and transport reference](docs/execunit-ipc.md) |
| Implement Java lifecycle, receive data, and present output | [Java listener walkthrough](docs/listener-java.md) |
| Add dependencies, build, and verify the JAR | [Build guide](docs/building.md) |

`exec-code/win/Program.cs` contains initialization, a cancellable idle wait, and
cleanup. The wait blocks without polling; Ctrl+C signals cancellation when running
as a console application. Initialization throws `NotImplementedException`, so the
current program prints that error and exits with code 1 before reaching the wait.

`exec-code/linux/listener/Main.cpp` exports `run(char*, char*)` for the Linux agent.
It supplies a listener scaffold and the native FIFO/host-protocol helpers under
`exec-code/linux/common/`. Connect to the agent, register callbacks, and implement
the listener transport in that TODO hook.

`exec-code/win/exec-unit-utils/` contains minimal **API stubs** for `TLV`,
`CommunicationNamedPipes`, and `CommunicationNamedPipesListener`. The project
compiles them directly, so they appear in the solution without a shared project.
These are a subset of the example utility APIs, not copies of their implementations.
Their wire framing belongs to the native host protocol; plugin configuration and
application payloads use the format chosen for the task.
Encoding, decoding, connection, callback registration, and data exchange are
unimplemented. The entry point does not call these transport stubs.

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
Startup, reconfiguration, and updated configuration serialization remain TODO hooks;
stop and delete only update local status.

Open [exec-code/win/listener-execunit.sln](exec-code/win/listener-execunit.sln) in Visual Studio,
or build the C# skeleton from this folder:

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
