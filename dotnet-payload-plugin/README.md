# tuoni-dotnet-agent

A custom .NET Framework payload agent for the [Tuoni C2 framework](https://docs.shelldot.com). This project consists of two components: a .NET Framework agent template (the executable that runs on target machines) and a Java/Gradle plugin that packages the agent for deployment through the Tuoni server.

## Repository Structure

```
dotnet-payload-plugin/
├── exec-code/                      # .NET Framework 4.6.2 payload agent template (C#)
│   ├── Program.cs                  # Entry point
│   ├── Encryption.cs               # RSA + AES-GCM encryption
│   ├── GlobalConf.cs               # PE overlay configuration extraction
│   ├── Listener.cs                 # C2 message handler
│   ├── ListenerManager.cs          # Listener lifecycle management
│   ├── Logger.cs                   # Debug logging
│   ├── MessagesManager.cs          # Central command dispatcher
│   ├── Metadata.cs                 # System information collection
│   ├── NamedPipeCommunication.cs   # IPC via named pipes
│   ├── NativeCommand.cs            # Built-in command execution
│   ├── NativeCommandLsHelper.cs    # Directory listing helper
│   ├── NativeCommandPsHelper.cs    # Process listing helper
│   ├── PluginCommand.cs            # Plugin shellcode communication
│   ├── PluginExecution.cs          # Shellcode execution via VirtualAlloc
│   ├── ProcessRunner.cs            # Process spawning with output streaming
│   ├── TLV.cs                      # Type-Length-Value protocol
│   ├── dotnet-agent.csproj         # MSBuild project file
│   ├── dotnet-agent.sln            # Visual Studio solution
│   └── App.config                  # .NET Framework runtime config
│
└── java-plugin/                    # Tuoni plugin (Java/Gradle)
    ├── src/main/java/com/shelldot/tuoni/examples/plugin/dotnetpayload/
    │   ├── DotnetPayloadPlugin.java              # Plugin entry point
    │   ├── DotnetPayloadPluginTemplate.java      # Payload template & serialization
    │   ├── DotnetPayloadPluginConfiguration.java # Configuration schema
    │   ├── configuration/
    │   │   ├── JacksonJsonConfiguration.java     # JSON config adapter
    │   │   └── SimpleConfigurationSchema.java    # Schema wrapper
    │   └── utils/
    │       └── ShellcodeUtil.java                # Binary resource loader
    ├── src/main/resources/META-INF/services/     # SPI service registration
    ├── build/resources/main/templates/           # Embedded dotnet-agent.exe (built from exec-code/)
    ├── build.gradle.kts            # Gradle build (Kotlin DSL)
    ├── settings.gradle.kts         # Gradle settings
    ├── gradle.properties           # Build optimization flags
    └── gradle/libs.versions.toml   # Dependency version catalog
```

## Prerequisites

| Software | Version | Notes |
|----------|---------|-------|
| **Windows** | 10/11 or Server 2016+ | The agent uses Windows-only APIs (P/Invoke to kernel32, ntdll, advapi32, bcrypt) |
| **Visual Studio** | 2022 or later | With ".NET desktop development" workload installed |
| **.NET Framework Targeting Pack** | 4.6.2 | Included with VS .NET desktop workload, or install separately |
| **MSBuild** | 15.0+ | Included with Visual Studio; also available via [Build Tools for Visual Studio](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio) |
| **Java JDK** | 21 | Required for building the Tuoni plugin |
| **Gradle** | 9.7.1 | Or use the included Gradle wrapper (`gradlew` / `gradlew.bat`) |

## Build Instructions

Run each command block below from `dotnet-payload-plugin/`, returning there between blocks.

### Step 1: Build the .NET Agent

**Using Visual Studio:**
1. Open `exec-code/dotnet-agent.sln` in Visual Studio
2. Set the build configuration to **Release**
3. Build the solution (Ctrl+Shift+B)

**Using MSBuild from command line:**
```bash
cd exec-code
msbuild dotnet-agent.csproj /p:Configuration=Release
```

**Using Developer Command Prompt:**
```bash
cd exec-code
msbuild /p:Configuration=Release
```

The compiled executable will be at: `exec-code/bin/Release/dotnet-agent.exe`

### Step 2: Build the Tuoni Plugin JAR

The Gradle build automatically copies `dotnet-agent.exe` from the Release output into the JAR. **You must complete Step 1 first.**

**Using the Gradle wrapper (recommended):**
```bash
cd java-plugin
./gradlew build
```

**On Windows (CMD):**
```cmd
cd java-plugin
gradlew.bat build
```

The plugin JAR will be at: `java-plugin/build/libs/tuoni-example-plugin-dotnet-payload-0.0.1.jar`

### Building with Docker (recommended for quick testing)

The entire project can be built inside Docker using the provided Makefile. This requires only Docker and Make — no Windows, Visual Studio, or Java installation needed.

```bash
# Build the plugin JAR and agent EXE
make build

# Build and install to Tuoni server (copies JAR to /srv/tuoni/plugins/server/ and restarts)
make install

# Remove build artifacts
make clean

# List all available targets
make help
```

Build outputs are extracted to the `build/` directory:
- `build/tuoni-example-plugin-dotnet-payload-0.0.1.jar` — the plugin JAR
- `build/dotnet-agent.exe` — the compiled .NET agent

### Build Output Summary

| Artifact | Path | Description |
|----------|------|-------------|
| Agent EXE | `exec-code/bin/Release/dotnet-agent.exe` | The .NET payload executable |
| Plugin JAR (fat) | `java-plugin/build/libs/tuoni-example-plugin-dotnet-payload-0.0.1.jar` | Shadow JAR with all dependencies, ready for Tuoni server |
| Plugin JAR (shallow) | `java-plugin/build/libs/dotnet-payload-plugin-0.0.1-shallow.jar` | JAR without bundled dependencies (not for deployment) |

## Deploying the Plugin to Tuoni Server

1. Build both the agent and plugin JAR as described above
2. Copy `tuoni-example-plugin-dotnet-payload-0.0.1.jar` to your Tuoni server's plugin directory
3. The plugin registers itself with the following metadata:
   - **Plugin ID:** `shelldot.payloads.examples.dotnetpayload`
   - **Plugin Name:** `.NET Payload Plugin`
   - **Plugin Version:** `0.0.1`
   - **Plugin Provider:** `shelldot`
   - **Payload Template:** `custom-dotnet-payload`
   - **Target Platform:** Windows x64

For more details on deploying plugins, see the [Tuoni documentation](https://docs.shelldot.com).

## Architecture Overview

The agent uses a two-layer architecture that separates network communication from command execution:

```
┌──────────────┐         ┌───────────────────────┐         ┌──────────────────┐
│  Tuoni C2    │◄───────►│  Listener Shellcode   │◄───────►│  .NET Agent      │
│  Server      │ network │  (injected at deploy) │  named  │(dotnet-agent.exe)│
│              │         │                       │  pipe   │                  │
└──────────────┘         └───────────────────────┘  (IPC)  └──────────────────┘
```

- **Tuoni C2 Server** — sends commands and receives results over the network
- **Listener Shellcode** — a shellcode blob provided by the Tuoni framework at deployment time; handles network communication with the C2 server and relays messages to/from the .NET agent via a named pipe
- **.NET Agent** — the core payload; receives commands over the named pipe, executes them, and queues results for the listener to pick up

### Payload Identity Metadata

When Tuoni creates a payload, the Java plugin writes the SDK `payloadId` to the optional agent configuration (listener child `0x02`) as an eight-byte, little-endian signed integer. The .NET agent reports the same eight bytes as metadata child `0x43`; this payload-specific field remains separate from the global public-key configuration appended by the listener serializer. Older payloads without the optional configuration remain supported and omit `payloadId`, while a present value must be exactly eight bytes or listener configuration loading fails.

### Encryption

The agent uses a **hybrid encryption** scheme:

- **RSA** (asymmetric) — used only for the initial metadata exchange. The C2 server's public key is embedded in the agent's configuration. The agent encrypts its metadata (which includes a freshly generated AES key) using this public key.
- **AES-GCM** (symmetric) — used for all subsequent communication. A random 128-bit key is generated at startup. Each message uses a random 12-byte IV/nonce and produces a 16-byte authentication tag. Encryption is performed via Windows CNG (`bcrypt.dll`) P/Invoke calls.

## License

This project is licensed under the MIT License.
