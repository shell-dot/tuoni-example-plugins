# Tuoni Plugin Examples

Welcome to the Tuoni Plugin Examples repository!

This repository contains example plugins for the [Tuoni](https://github.com/shell-dot/tuoni) Command and Control (C2) framework. \
Each plugin consists of two parts:

1. **Execution codes and agent executables**: Windows C# and, where supported, Linux C++ (`exec-code/`).
2. **Server Plugin** (`java-plugin/`): Written in Java against the Tuoni plugin SDK, requiring Java 21+ and Gradle for building.

## Table of Contents

- [Getting Started](#getting-started)
    - [Building with Docker](#building-with-docker)
    - [Prerequisites](#prerequisites)
    - [Building the Server Plugin](#building-the-server-plugin)
- [Plugins](#plugins)
- [Skeleton Templates](#skeleton-templates)
- [Create a Plugin from a Template](#create-a-plugin-from-a-template)

## Getting Started

### Building with Docker

Each example and template includes a Makefile that builds its execunits and Java plugin inside Docker.
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
The command and listener templates also provide Linux x64 C++ execunits and a
`make build-linux` target. Their Java plugin JARs include both platforms.
The echo and TCP listener examples use Ubuntu 18.04 amd64 for their native Linux
and Windows conversion stages. All examples and templates export artifacts to
their `build/` output directory by default.
`make build-dotnet` compiles the C# projects in Docker without building Java
plugins or generating command and listener shellcode.
Use `make install PLUGIN_DIR=/path/to/plugins` to choose the server's plugin directory;
command-line overrides are passed to every example.
The `install` target requires the `tuoni` command to be available.

All example and template Makefiles check Docker access when a build runs. They use
Docker directly when accessible, including rootless setups. If the local Docker
socket denies permission (for example, your user is not in the Docker group), they
automatically use `sudo`, which may prompt for authentication. The runner preserves
the selected socket and BuildKit setting. Missing Docker, unavailable daemons and
remote connection failures are reported without an automatic sudo retry.

An explicit `DOCKER=...` override bypasses detection and reaches every example
when invoked from the repository root. To force sudo manually, use
`make build DOCKER="sudo env DOCKER_BUILDKIT=1 docker"`; the same override works
for `build-dotnet` and `build-linux`. Help, clean and dry runs do not probe Docker.

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

Command/listener skills always build with Docker unless the user explicitly requests
another route. If Docker is missing or unusable, they inform the user and report
the blocked build instead of falling back to local tools. The direct Gradle
commands below apply to skills only with that explicit override.

Each plugin's server part can be built using Gradle. Navigate to the individual plugin's `java-plugin/` directory and run the following command:
```sh
sh gradlew assemble
```

On Windows PowerShell, run:

```powershell
.\gradlew.bat assemble
```
This command will compile the Java code for Java 21 and build the server plugin.
Build the Windows C# and Linux C++ components first where required; see each
plugin's README for its build order.

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
plugin skeleton, Windows C# execunit code, build files, and customization notes.
The command and listener templates keep Windows code in `exec-code/win/` and Linux
C++ code in `exec-code/linux/`.
Behavior is left as TODO hooks so you can start without the examples' business logic.

## Create a Plugin from a Template

The repository provides `new-command` and `new-listener` skills for Codex CLI and
Claude Code. In Codex, invoke `$new-command` or `$new-listener`; in Claude Code,
invoke `/new-command` or `/new-listener`. Give a name and optional destination
folder. Without a folder, the skill creates `workspace/commands/<name>` or
`workspace/listeners/<name>` under this repository, creating missing parent
directories and normalizing the name (for example, `Daily Check` becomes
`daily-check`). An explicit destination overrides that default; relative paths
are resolved from your original working directory. Existing plugin directories
are preserved and reported as conflicts.

The skills use `tools/scaffold_plugin.py` to copy the appropriate template and
rename its Java, Windows, Linux, and build identifiers. If you describe what the
command or listener should do, they continue with the generated plugin's
`command-implement` or `listener-implement` skill using your complete request.
A name-only request or an explicit scaffold-only request leaves behavior TODOs
for later implementation.

### Work on an existing workspace plugin

The repository root also exposes these skills for plugins already created in
`workspace/commands/` or `workspace/listeners/`:

| Command skill | Listener skill | Work |
| --- | --- | --- |
| `command-implement` | `listener-implement` | Complete or finish the plugin |
| `command-conf` | `listener-conf` | Change configuration and validation |
| `command-logic` | `listener-logic` | Change behavior and lifecycle |
| `command-output` | `listener-output` | Change returned data and presentation |

Use `$<skill>` in Codex or `/<skill>` in Claude Code. Include the existing plugin's
name or path, for example:

```text
$command-output for daily-check: include the elapsed time in the result.
$listener-conf for workspace/listeners/beacon: add a connection timeout setting.
```

An unambiguous target from the conversation also works. Each root skill validates
the target, then follows the matching skill inside that plugin, preserving the
full request and its constraints. If no eligible plugin exists, it explains how
to create one. If the target is unclear, it lists candidates and asks which to
use, even when there is only one. An invalid explicit target never falls back to
another project, and these skills do not create plugins automatically.

The routing skills remain visible even with an empty workspace; their checks
prevent plugin work until a valid target is established.

---

Happy coding!

For more information on the Tuoni C2 framework, visit the [official Tuoni GitHub repository](https://github.com/shell-dot/tuoni).
