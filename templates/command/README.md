# Command plugin skeleton

Start with the [shared setup and build instructions](../README.md). This folder
contains one command template, a C# Windows entry point, and a C++ Linux x64
entry point.

| File under `java-plugin/src/main/java/com/example/tuoni/command/` | Purpose |
| --- | --- |
| `TemplateCommandPlugin.java` | Plugin initialization and command template registration |
| `TemplateCommandTemplate.java` | Name, description, schema, compatibility, validation, and factory |
| `TemplateCommand.java` | SDK command serialization, result, update, and cleanup hooks |
| `TemplateConfigurationSchema.java` | Empty configuration schema to customize |

To implement the entire command from a prompt, use `$command-implement` in Codex
or `/command-implement` in Claude Code. The [implementation skill](.agents/skills/command-implement/SKILL.md)
coordinates configuration, logic, and output through builds, verification, and
project-context updates. It is included in this folder and in generated plugins.

To add configuration fields across Java and the Windows/Linux exec-units, use
`$command-conf` in Codex or `/command-conf` in Claude Code. The skill is included
in this folder and in plugins created from this template.

To implement command behavior with minimal result output, use `$command-logic`
in Codex or `/command-logic` in Claude Code.

To change what users see or receive from a command, use `$command-output` in
Codex or `/command-output` in Claude Code.

The plugin-root [AGENTS.md](AGENTS.md) stores the current implementation context; [CLAUDE.md](CLAUDE.md) directs Claude to that shared context. Each template skill reads and updates it so later tasks retain the plugin's decisions, contracts, checks, and remaining work.

The following guides are copied into generated plugins:

| Task | Guide |
| --- | --- |
| Implement a complete command with only the needed features | [Implementation recipe and worked trace](docs/implementation-recipes.md) |
| Adapt an existing Java/native command pair | [Existing plugin patterns](docs/existing-plugins.md) |
| Maintain context for later commands and skills | [Context maintenance](docs/project-context.md) |
| Add configuration and validate its payload encoding | [Configuration walkthrough](docs/configuration.md) |
| Implement native helpers and own the IPC connection | [Native runtime](docs/native-runtime.md) |
| Check message IDs, framing, updates, and stop handling | [IPC reference](docs/execunit-ipc.md) |
| Parse and format complete or streaming results | [Output examples](docs/output.md) |
| Add dependencies, build, and verify the JAR | [Build guide](docs/building.md) |

`exec-code/win/Program.cs` contains initialization, an empty execution hook, completion,
and cleanup. Initialization and completion throw `NotImplementedException`; the
program currently prints the initialization error and exits with code 1.

`exec-code/linux/command/Main.cpp` exports `run(char*, char*)` for the Linux agent.
It uses the example FIFO transport helpers under `exec-code/linux/common/` to connect and
report an unimplemented command failure. Replace that TODO with command behavior.

`exec-code/win/exec-unit-utils/` contains minimal **API stubs** for the host envelope helper `TLV`,
`CommunicationNamedPipes`, and `CommunicationNamedPipesCommand`. The project
compiles them directly, so they appear in the solution without a shared project.
These are a subset of the example utility APIs, not copies of their implementations.
Encoding, decoding, connection, and reporting methods are unimplemented. The
entry point does not call these transport stubs or report success to an agent.

The Java class implements `ExecUnitCommand` and `ShellcodeCommand` and accepts
Windows and Linux x64 `SHELLCODE_AGENT` agents. It advertises `SHELLCODE_NATIVE`
for Windows and `NATIVE_LIB` for Linux x64. Linux loads
`/command-linux.native64_so` with the `run` export; the agent supplies FIFO paths,
so no byte patch is needed. Windows loads `/command.shellcode` from the JAR,
replaces every UTF-16LE `QQQWWWEEE` pipe-name placeholder with the SDK pipe name,
and returns it with named-pipe IPC and an empty configuration buffer. The new name
must have the same encoded length as the placeholder. Build the C# Release project
first so its post-build step creates
`java-plugin/src/main/resources/command.shellcode`. Build the Linux library before
a direct Java build so Gradle can include it.
Result parsing and command configuration are still TODO hooks.

Open [exec-code/win/command-execunit.sln](exec-code/win/command-execunit.sln) in Visual Studio,
or build the C# skeleton from this folder:

```powershell
msbuild exec-code/win/command-execunit.sln /p:Configuration=Release
```

Output: `exec-code/win/bin/Release/command-execunit-template.exe`.
Java output: `java-plugin/build/libs/command-plugin-template-0.0.1.jar`.

For a direct Linux build, run `bash exec-code/linux/build_linux.sh` on Linux with
`g++`. This writes `exec-code/linux/build/command-linux.native64_so`. To build it
inside Docker and extract it for Gradle, run `make build-linux`.

Use a Linux shell (WSL on Windows), GNU Make, standard Unix file utilities, and
Docker configured for Linux containers. Run `make build` from this folder. The JAR,
EXE, generated shellcode, and Linux library are extracted to `build/`.
Run `make build-dotnet` to compile and extract only the EXE to `build/`.
