#!make
.DEFAULT_GOAL := help

PYTHON ?= python3

# Keep names and destination paths as single literal POSIX shell arguments.
shell_quote = '$(subst ','"'"',$(1))'

# Only the repository examples participate in aggregate targets. Generated
# projects may live at the root, have spaces in their paths, or lack `install`.
EXAMPLES := echo-command-plugin tcp-listener-plugin dotnet-payload-plugin
LINUX_EXAMPLES := echo-command-plugin tcp-listener-plugin
WINDOWS_NATIVE_EXAMPLES := echo-command-plugin tcp-listener-plugin

.PHONY: help build build-dotnet build-linux build-windows-native install clean new-command new-listener
help:
	@printf '%s\n' \
		'Create a plugin from a template (Python 3.9+ required):' \
		'  make new-command NAME="Daily Check" [FOLDER="path/to/plugin"] [EXECUNITS="native-lib dotnet-dll"] [OS="windows linux"] [PYTHON=python3]' \
		'  make new-listener NAME="Event Relay" [FOLDER="path/to/plugin"] [EXECUNITS="native-lib dotnet-dll"] [OS="windows linux"] [PYTHON=python3]' \
		'  Execunits: shellcode-native, dotnet-dll, dotnet-exe, native-lib. OS: windows, linux.' \
		'  Default destinations: workspace/commands/<normalized-name> and workspace/listeners/<normalized-name>.' \
		''
	@set -e; \
	for example in $(EXAMPLES); do \
		$(MAKE) -C "$$example" help; \
	done

new-command new-listener:
	$(if $(strip $(value NAME)),,$(error NAME is required; use make $@ NAME="Plugin Name" [FOLDER="path/to/plugin"] [EXECUNITS="native-lib"] [OS="linux"]))
	@$(PYTHON) tools/scaffold_plugin.py $(patsubst new-%,%,$@) --name=$(call shell_quote,$(value NAME)) $(if $(strip $(value FOLDER)),--folder=$(call shell_quote,$(value FOLDER))) $(if $(filter command line,$(origin EXECUNITS)),--execunits=$(call shell_quote,$(value EXECUNITS))) $(if $(filter command line,$(origin OS)),--os=$(call shell_quote,$(value OS)))

build build-dotnet install clean:
	@set -e; \
	for example in $(EXAMPLES); do \
		$(MAKE) -C "$$example" $@; \
	done

build-linux:
	@set -e; \
	for example in $(LINUX_EXAMPLES); do \
		$(MAKE) -C "$$example" build-linux; \
	done

build-windows-native:
	@set -e; \
	for example in $(WINDOWS_NATIVE_EXAMPLES); do \
		$(MAKE) -C "$$example" build-windows-native; \
	done
