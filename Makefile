#!make
.DEFAULT_GOAL := help

PYTHON ?= python3
DOCKER ?= sh echo-command-plugin/scripts/docker/run-docker.sh
BUILDER_IMAGE ?= tuoni-plugin-builder:0.15.0-gradle9.7.1-v1
BUILDER_ARCHIVE ?= build/tuoni-plugin-builder.tar

# Keep names and destination paths as single literal POSIX shell arguments.
shell_quote = '$(subst ','"'"',$(1))'

# Only the repository examples participate in aggregate targets. Generated
# projects may live at the root, have spaces in their paths, or lack `install`.
EXAMPLES := echo-command-plugin tcp-listener-plugin dotnet-payload-plugin
LINUX_EXAMPLES := echo-command-plugin tcp-listener-plugin
WINDOWS_NATIVE_EXAMPLES := echo-command-plugin tcp-listener-plugin

.PHONY: help build build-dotnet build-linux build-windows-native install install-completion clean new new-command new-listener
help:
	@printf '%s\n' \
		'Reusable offline toolchains for the lab (run from the repository root):' \
		'  make builder-image  Download Java/Maven and native toolchains once into one amd64 image.' \
		'  make builder-save   Export the image to build/tuoni-plugin-builder.tar.' \
		'  make builder-load   Load that archive on each lab Docker host before make build.' \
		'  make builder-check  Verify the imported toolchains and support tools without networking.' \
		'' \
		'Create a plugin from a template (Python 3.9+ required):' \
		'  make new  Open the interactive plugin wizard (no arguments needed).' \
		'  make new-command NAME="Daily Check" [FOLDER="path/to/plugin"] [EXECUNITS="native-lib dotnet-dll"] [OS="windows linux"] [PYTHON=python3]' \
		'  make new-listener NAME="Event Relay" [FOLDER="path/to/plugin"] [EXECUNITS="native-lib dotnet-dll"] [OS="windows linux"] [PYTHON=python3]' \
		'  Execunits: shellcode-native, dotnet-dll, dotnet-exe, native-lib. OS: windows, linux.' \
		'  Default destinations: workspace/commands/<normalized-name> and workspace/listeners/<normalized-name>.' \
		'  make install-completion  Detect Bash/Zsh automatically and enable Tab completion.' \
		'  Comma-separated lists avoid quotes: EXECUNITS=native-lib,dotnet-dll OS=windows,linux.' \
		''
	@set -e; \
	for example in $(EXAMPLES); do \
		$(MAKE) -C "$$example" help; \
	done

new:
	@$(PYTHON) tools/new_plugin.py

.PHONY: builder-image builder-save builder-load builder-check
builder-image:
	DOCKER_BUILDKIT=1 $(DOCKER) build --platform linux/amd64 \
		-f Dockerfile --target builder -t "$(BUILDER_IMAGE)" .

# Deliberately separate from builder-image: exporting never downloads anything.
builder-save:
	@mkdir -p -- "$(dir $(BUILDER_ARCHIVE))"
	$(DOCKER) image save -o "$(BUILDER_ARCHIVE)" "$(BUILDER_IMAGE)"

builder-load:
	$(DOCKER) image load -i "$(BUILDER_ARCHIVE)"
	$(DOCKER) image inspect "$(BUILDER_IMAGE)" >/dev/null

builder-check:
	$(DOCKER) run --rm --pull=never --platform linux/amd64 --network none \
		"$(BUILDER_IMAGE)" check-tuoni-builder

new-command new-listener:
	$(if $(strip $(value NAME)),,$(error NAME is required; use make $@ NAME="Plugin Name" [FOLDER="path/to/plugin"] [EXECUNITS="native-lib"] [OS="linux"]))
	@$(PYTHON) tools/scaffold_plugin.py $(patsubst new-%,%,$@) --name=$(call shell_quote,$(value NAME)) $(if $(strip $(value FOLDER)),--folder=$(call shell_quote,$(value FOLDER))) $(if $(filter command line,$(origin EXECUNITS)),--execunits=$(call shell_quote,$(value EXECUNITS))) $(if $(filter command line,$(origin OS)),--os=$(call shell_quote,$(value OS)))

install-completion:
	@$(PYTHON) tools/install_make_completion.py $(if $(COMPLETION_SHELL),--shell $(COMPLETION_SHELL))

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
