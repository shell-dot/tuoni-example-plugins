# Tuoni Plugin Examples

Welcome to the Tuoni Plugin Examples repository!

This repository contains example plugins for the [Tuoni](https://github.com/shell-dot/tuoni) Command and Control (C2) framework. \
Each plugin consists of two parts:

1. **Execution codes and agent executables**: Windows C# and, where supported, Windows/Linux C++ (`exec-code/`).
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
make build-dotnet  # Extract .NET EXEs, DLLs, and DLL entrypoint metadata to each project's output directory
make build-linux   # Extract Linux execunits for plugins that provide them
make build-windows-native  # Extract Windows x86/x64 native DLLs
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
plugins or generating command and listener shellcode. Commands and listeners
export `.dotnet_exe`, `.dotnet_dll`, and `.dotnet_dll_method` alongside the legacy
shellcode-input `.exe`; payload projects retain their existing executable output.

The command/listener examples and templates support these execution formats:

| Target | Formats | Loader entry point |
| --- | --- | --- |
| Windows x86/x64 | `SHELLCODE_NATIVE`, `DOTNET_EXE`, `DOTNET_DLL`, `NATIVE_LIB` | Patched shellcode; EXE `Main(args)`; managed DLL method metadata; native DLL `start(pipeName)` |
| Linux x64 | `NATIVE_LIB` | `run(readPipe, writePipe)` |

Managed EXE/DLL variants receive their pipe name in `args[0]`; only shellcode is
patched. All variants preserve the same plugin configuration and behavior.
`make build` embeds and exports every supported format, including Windows
`.native32_dll` and `.native64_dll` artifacts. `make build-windows-native` builds
just those DLLs using MinGW inside Docker, verifies their architecture, sole
`start` export and Windows system DLL dependencies, and exports them to `build/`.
Native sources live in each project's `exec-code/win-native/` directory.
The `exec-unit-utils/` subdirectory carries utilities copied from the reference
command/listener codebases, with provenance and documented local compatibility fixes.
Other OS/architecture combinations are not advertised.
Use `make install PLUGIN_DIR=/path/to/plugins` to choose the server's plugin directory;
command-line overrides are passed to every example.
The `install` target builds the plugin, resolves `tuoni`, copies the JAR, and runs
`tuoni restart`. It prefers the current user's PATH and login shell, then checks
root's login shell through `sudo`, including Tuoni's standard `/srv/tuoni/tuoni`
location. A root installation runs as root; a user installation keeps that user's
context and uses sudo only if the plugin directory requires it. Missing Tuoni
fails before the JAR is copied. Use `TUONI=/path/to/tuoni` to choose a specific
executable; this override also propagates to every example.

New command and listener plugins include the same standalone installer and
`make install` target, including scaffolds with selected OSs or exec-unit formats.

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
The command template starts as a no-op: `{}` validates, all exec-units connect and
return `DONE` and report success, and Java displays it in the `output` text result.
The execution hooks are ready for new behavior.
The listener template starts idle with working Java lifecycle and native pipe startup;
its data traffic channel remains TODO. Both use implemented local-agent IPC utilities;
`{}` is serialized as a zero-length native payload. See the [command defaults](templates/command/README.md#default-behavior)
and [listener defaults](templates/listener/README.md#default-behavior) for the contracts
and extension points. The payload template retains its behavior TODOs.

## Create a Plugin from a Template

From the repository root, use GNU Make and Python 3.9+ to create a command or
listener plugin.

For guided creation, launch the terminal wizard:

```sh
make new
# Or launch directly, from any directory:
python3 /path/to/tuoni-example-plugins/tools/new_plugin.py
```

The wizard walks through plugin type, name, target operating systems, execution
formats, and destination, then shows a review before creating the plugin. Use
arrow keys and Space to select options, Enter to continue, Esc or Shift-Tab to go
back, and Ctrl-C to cancel. Text fields accept spaces without shell quoting;
Left/Right, Home/End, Backspace/Delete, and Ctrl-U (clear) edit the text. In the
destination field, Tab completes existing parent directories. Leave it blank to
use `workspace/commands/<normalized-name>` or `workspace/listeners/<normalized-name>`.
Custom paths support `~` and resolve relative to the directory you launched from.
Existing destinations are rejected. The wizard keeps platform and format choices
compatible, including Linux's `native-lib` requirement.

The TUI uses Python's standard-library `curses` module and needs an interactive
terminal of at least 64 columns by 22 rows. Use Linux, macOS with a Python build
that includes curses, or WSL on Windows. It works independently of Bash/Zsh
completion and requires no extra Python packages. It calls the same generator as
the Make targets, so new plugins include their build and install Makefile targets.
Creation requires no Docker or sudo access; after creation it prints the commands
to build and install the plugin separately.

For the argument-based Make targets, install argument completion once:

```sh
make install-completion
```

The installer automatically detects Bash or Zsh from your login shell
(`$SHELL`). Zsh uses its native completion system, including on Kali, and
installation adds a guarded source block to your `.zshrc` (respecting
`ZDOTDIR`). Bash requires Bash 4.2+ and the `bash-completion` package. If you want
to configure a different shell, optionally add `COMPLETION_SHELL=zsh` or
`COMPLETION_SHELL=bash`.
Open a new shell, or load the installed script in your current shell:

```sh
# Bash
source "${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions/make"
# Zsh
source "${XDG_DATA_HOME:-$HOME/.local/share}/zsh/tuoni-make-completion.zsh"
```

On macOS, the default Zsh uses the same `make install-completion` command;
no Homebrew completion package is needed. Make and Python 3.9+ must be available.
For Bash, use Homebrew's modern Bash and `bash-completion@2`:

```sh
brew install bash bash-completion@2
```

Enable bash-completion in your Bash startup files as described in
[Homebrew's instructions](https://docs.brew.sh/Shell-Completion#bash), then run
`make install-completion` from that Bash setup. Apple's bundled Bash 3.2 is
unsupported. The loader recognizes Intel, Apple Silicon, and custom Homebrew
prefixes. The native Zsh completion has been tested on Linux; it has not yet
been tested on a Mac host.

After `make new-command` or `make new-listener`, Tab completes `NAME=`, `FOLDER=`,
`EXECUNITS=`, `OS=`, and `PYTHON=`. For example, `EX` followed by Tab becomes
`EXECUNITS=`; `EXECUNITS=nat` becomes `EXECUNITS=native-lib`. Add a comma and press
Tab to choose another format without quoting a space-separated list. `OS` works
the same way, and `FOLDER` completes directories and escapes spaces. Already
selected options/values are omitted; `OS=linux` offers only `native-lib`, and
managed-only formats offer only Windows. Normal Make target/flag completion is
retained. `NAME` is free text: use `NAME=DailyCheck`, or quote a name with spaces.
To try completion without installing it, source `tools/make-completion.bash`
in Bash or `tools/make-completion.zsh` in Zsh.

For example:

```sh
make new-command NAME="Daily Check"
make new-listener NAME="Event Relay"
make new-command NAME="Daily Check" FOLDER="./custom plugins/daily-check"
make new-listener NAME="Event Relay" FOLDER="/path/to/event-relay"
make new-command NAME="Linux Check" EXECUNITS="native-lib" OS="linux"
make new-listener NAME="Managed Relay" EXECUNITS="dotnet-dll dotnet-exe" OS="windows"
```

`NAME` is required. Without `FOLDER`, the targets create
`workspace/commands/<normalized-name>` or `workspace/listeners/<normalized-name>`
under this repository; `Daily Check` becomes `daily-check`. `FOLDER` is the exact
plugin destination, with relative paths resolved from Make's working directory
(after any `make -C` option). Missing parent directories are created; an existing
destination is rejected without overwriting it. These targets copy and rename
the templates. Build the generated plugin separately from its directory with
`make build`. Scaffolding requires no Docker access.

`EXECUNITS` accepts one or more of `shellcode-native`, `dotnet-dll`, `dotnet-exe`,
and `native-lib`; `OS` accepts `windows` and `linux`. Separate values with spaces
or commas. Either option can be used alone. Unspecified dimensions keep the
template's existing support: Windows x86/x64 has all four formats; Linux x64 has
`native-lib` only. The generated Java plugin advertises the selected combinations
and rejects the others. A requested OS with no compatible selected execunit fails
before a directory is created. The generated plugin retains the template's source
files for later expansion, while `make build` compiles and packages only the
selected formats.

The targets use `python3` by default. Set `PYTHON=python` if that is your Python 3
command, for example `make new-command NAME="Daily Check" PYTHON=python`.

The repository provides `command-new` and `listener-new` skills for Codex CLI and
Claude Code. In Codex, invoke `$command-new` or `$listener-new`; in Claude Code,
invoke `/command-new` or `/listener-new`. Give a name and optional destination
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
A name-only request or an explicit scaffold-only request keeps the command's no-op
behavior, or the listener's idle startup and channel TODOs, for later implementation.

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
