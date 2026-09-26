# Command plugin skeleton

Start with the [shared setup and build instructions](../README.md). This folder
contains one command template and one C# execunit entry point.

| File under `java-plugin/src/main/java/com/example/tuoni/command/` | Purpose |
| --- | --- |
| `TemplateCommandPlugin.java` | Plugin initialization and command template registration |
| `TemplateCommandTemplate.java` | Name, description, schema, compatibility, validation, and factory |
| `TemplateCommand.java` | SDK command serialization, result, update, and cleanup hooks |
| `TemplateConfigurationSchema.java` | Empty configuration schema to customize |

`exec-code/Program.cs` contains initialization, an empty execution hook, completion,
and cleanup. Initialization and completion throw `NotImplementedException`; the
program currently prints the initialization error and exits with code 1.

`exec-code/exec-unit-utils/` contains minimal **API stubs** for `TLV`,
`CommunicationNamedPipes`, and `CommunicationNamedPipesCommand`. The project
compiles them directly, so they appear in the solution without a shared project.
These are a subset of the example utility APIs, not copies of their implementations.
Encoding, decoding, connection, and reporting methods are unimplemented. The
entry point does not call these transport stubs or report success to an agent.

The Java class implements the same `ShellcodeCommand` interface as the command
examples and accepts Windows `SHELLCODE_AGENT` agents. `generateShellCode` loads
`/command.shellcode` from the JAR, replaces
every UTF-16LE `QQQWWWEEE` pipe-name placeholder with the SDK pipe name, and returns
it with named-pipe IPC and an empty configuration buffer. The new name must have
the same encoded length as the placeholder. Build the C# Release project first so
its post-build step creates `java-plugin/src/main/resources/command.shellcode`.
Result parsing and command configuration are still TODO hooks.

Open [exec-code/command-execunit.sln](exec-code/command-execunit.sln) in Visual Studio,
or build the C# skeleton from this folder:

```powershell
msbuild exec-code/command-execunit.sln /p:Configuration=Release
```

Output: `exec-code/bin/Release/command-execunit-template.exe`.
Java output: `java-plugin/build/libs/command-plugin-template-0.0.1.jar`.
