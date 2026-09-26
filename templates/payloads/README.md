# Payload plugin skeleton

Start with the [shared setup and build instructions](../README.md). This folder
contains one payload template and a C# payload program entry point. In the repository
layout, a payload's `exec-code/` is the payload program itself; command and listener
folders use it for their execunits.

| File under `java-plugin/src/main/java/com/example/tuoni/payload/` | Purpose |
| --- | --- |
| `TemplatePayloadPlugin.java` | Plugin initialization and payload template registration |
| `TemplatePayloadTemplate.java` | Name, description, schema, target platform, validation, and factory |
| `TemplatePayload.java` | Output filename, type, and serialization hook |
| `TemplateConfigurationSchema.java` | Empty configuration schema to customize |

`exec-code/Program.cs` is the C# entry point. Windows x64 and the `.exe` output
extension are placeholders in the Java template; choose values appropriate to
your implementation. Payload serialization is unimplemented.

Open [exec-code/payload.sln](exec-code/payload.sln) in Visual Studio,
or build the C# skeleton from this folder:

```powershell
msbuild exec-code/payload.sln /p:Configuration=Release
```

Output: `exec-code/bin/Release/payload-template.exe`.
Java output: `java-plugin/build/libs/payload-plugin-template-0.0.1.jar`.
