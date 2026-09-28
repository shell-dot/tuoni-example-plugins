# Tuoni Plugin Examples

Welcome to the Tuoni Plugin Examples repository!

This repository contains example plugins for the [Tuoni](https://github.com/shell-dot/tuoni) Command and Control (C2) framework. \
Each plugin consists of two parts:

1. **Execution codes and agent executables**: Written in C# .NET framework (`exec-code/`).
2. **Server Plugin** (`java-plugin/`): Written in Java against the Tuoni plugin SDK, requiring Java 21+ and Gradle for building.

## Table of Contents

- [Getting Started](#getting-started)
    - [Building with Docker](#building-with-docker)
    - [Prerequisites](#prerequisites)
    - [Building the Server Plugin](#building-the-server-plugin)
- [Plugins](#plugins)
- [Skeleton Templates](#skeleton-templates)

## Getting Started

### Building with Docker

Each example and template includes a Makefile that builds its .NET component and Java plugin inside Docker.
Run the Makefiles from a Linux shell with GNU Make, Docker configured for Linux
containers, and standard Unix file utilities (`mkdir`, `rm`, and `cp`). The example
help targets also require GNU `sed` and `column`.
On Windows, use a Linux shell in WSL with Docker accessible from that environment;
these Makefile recipes cannot run directly in PowerShell or CMD.

Run these commands from the repository root for all example plugins, or from an
individual project's directory for just that project:

```sh
make build    # Extract plugin JARs and Windows/Linux execunits to each project's output directory
make build-dotnet  # Extract only .NET executables to each project's output directory
make build-linux   # Extract Linux execunits for plugins that provide them
make install  # Install the example plugins; templates are skipped
make clean    # Remove build artifacts
make help     # List available targets
```

The root Makefile discovers Makefiles in immediate `*-plugin/` directories
automatically and stops if a command fails. Build templates separately with
`make -C templates build` or from an individual template directory.
`make build` builds the echo and TCP Linux execunits inside Docker, exports their
`.native64_so` files alongside the Windows artifacts, and embeds both platforms
in each plugin JAR. `make build-linux` runs only the Linux build targets for
plugins with `exec-code/linux/build_linux.sh`.
The echo and TCP listener examples use Ubuntu 18.04 amd64 for their native Linux
and Windows conversion stages. All examples and templates export artifacts to
their `build/` output directory by default.
`make build-dotnet` compiles the C# projects in Docker without building Java
plugins or generating command and listener shellcode.
Use `make install PLUGIN_DIR=/path/to/plugins` to choose the server's plugin directory;
command-line overrides are passed to every example.
The `install` target requires the `tuoni` command to be available.

All examples and templates use `docker` by default. If your Docker setup requires
sudo, run `make build DOCKER="sudo docker"` (or use the same override with
`build-dotnet` or `build-linux`). The override also reaches every example when invoked
from the repository root.

Use `BUILD_DIR="build/custom output"` to choose a different output subdirectory,
including one with spaces. The default output directories are ignored by Git.
If you choose another output directory, add that directory to
the project's `.gitignore` before building. Reserve the output directory for
generated files: `make clean` removes it completely, including artifacts from
older versions. Cleanup refuses the project directory itself and any path that
resolves outside it.

### Prerequisites

For a Java build outside Docker, install JDK 21+. The included Gradle wrapper
downloads Gradle on its first run, so a separate Gradle installation is unnecessary.
See each project's README for its native C# build prerequisites.

### Building the Server Plugin

Each plugin's server part can be built using Gradle. Navigate to the individual plugin's `java-plugin/` directory and run the following command:
```sh
sh gradlew assemble
```

On Windows PowerShell, run:

```powershell
.\gradlew.bat assemble
```
This command will compile the Java code for Java 21 and build the server plugin.
Build the C# component first where required; see each plugin's README for its build order.

## Plugins

Here is a list of the example plugins included in this repository:

* **[Echo Command Plugin](echo-command-plugin/README.md) (contains 4 commands)**
  - **Server Plugin**: `echo-command-plugin/java-plugin/`
  - **Execution code**: `echo-command-plugin/exec-code/`

* **[TCP Listener Plugin](tcp-listener-plugin/README.md)**
  - **Server Plugin**: `tcp-listener-plugin/java-plugin/`
  - **Execution code**: `tcp-listener-plugin/exec-code/`

* **[.NET Payload Plugin](dotnet-payload-plugin/README.md)**
  - **Server Plugin**: `dotnet-payload-plugin/java-plugin/`
  - **Execution code**: `dotnet-payload-plugin/exec-code/`

## Skeleton Templates

The [templates](templates/README.md) folder contains minimal starting points for
[command](templates/command/README.md), [listener](templates/listener/README.md),
and [payload](templates/payloads/README.md) plugins. Each includes a Java server
plugin skeleton, a C# `exec-code` skeleton, build files, and customization notes.
Behavior is left as TODO hooks so you can start without the examples' business logic.

---

Happy coding!

For more information on the Tuoni C2 framework, visit the [official Tuoni GitHub repository](https://github.com/shell-dot/tuoni).
