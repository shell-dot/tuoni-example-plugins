#!make
.DEFAULT_GOAL := help

PYTHON ?= python3

# Keep names and destination paths as single literal POSIX shell arguments.
shell_quote = '$(subst ','"'"',$(1))'

EXAMPLES := $(patsubst %/Makefile,%,$(wildcard *-plugin/Makefile))
LINUX_EXAMPLES := $(patsubst %/exec-code/linux/build_linux.sh,%,$(wildcard *-plugin/exec-code/linux/build_linux.sh))
WINDOWS_NATIVE_EXAMPLES := $(patsubst %/exec-code/win-native/build_windows.sh,%,$(wildcard *-plugin/exec-code/win-native/build_windows.sh))

.PHONY: help build build-dotnet build-linux build-windows-native install clean new-command new-listener
help:
	@printf '%s\n' \
		'Create a plugin from a template (Python 3.9+ required):' \
		'  make new-command NAME="Daily Check" [FOLDER="path/to/plugin"] [PYTHON=python3]' \
		'  make new-listener NAME="Event Relay" [FOLDER="path/to/plugin"] [PYTHON=python3]' \
		'  Default destinations: workspace/commands/<normalized-name> and workspace/listeners/<normalized-name>.' \
		''
	@set -e; \
	for example in $(EXAMPLES); do \
		$(MAKE) -C "$$example" help; \
	done

new-command new-listener:
	$(if $(strip $(value NAME)),,$(error NAME is required; use make $@ NAME="Plugin Name" [FOLDER="path/to/plugin"]))
	@$(PYTHON) tools/scaffold_plugin.py $(patsubst new-%,%,$@) --name=$(call shell_quote,$(value NAME)) $(if $(strip $(value FOLDER)),--folder=$(call shell_quote,$(value FOLDER)))

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
