#!make
.DEFAULT_GOAL := help

# The runner uses sudo only when the local Docker socket denies access.
# An explicit DOCKER override bypasses automatic detection.
DOCKER ?= sh scripts/docker/run-docker.sh
BUILD_DIR  := build
JAR_NAME   := tuoni-example-plugin-echo-command-0.0.1.jar
COMMANDS   := echo echo-ongoing echo-ongoing-file echo-ongoing-more-data

##### GENERAL #####
## help: List all available make targets with descriptions
.PHONY: help
help:
	@printf '[*] usage: make <target>\n\n'
	@sed -nr 's/^##\s+/\t/p' $(MAKEFILE_LIST) | column -t -s ':'

## build: Build the plugin JAR and commands inside Docker and extract to build/
.PHONY: build
build:
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@echo ""
	@echo "[+] Build complete: $(BUILD_DIR)/$(JAR_NAME)"
	@for command in $(COMMANDS); do \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.exe"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.dotnet_exe"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.dotnet_dll"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.dotnet_dll_method"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.shellcode"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command-linux.native64_so"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.native32_dll"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.native64_dll"; \
	done

## build-dotnet: Build and extract the .NET command EXEs, DLLs and entrypoint metadata with Docker
.PHONY: build-dotnet
build-dotnet:
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target dotnet-artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@for command in $(COMMANDS); do \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.exe"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.dotnet_exe"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.dotnet_dll"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command.dotnet_dll_method"; \
	done

## build-linux: Build Linux x64 native execunits inside Docker
.PHONY: build-linux
build-linux:
	@mkdir -p -- "$(BUILD_DIR)" exec-code/linux/build
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target linux-artifacts \
		--output "type=local,dest=exec-code/linux/build/" \
		.
	cp exec-code/linux/build/*-linux.native64_so "$(BUILD_DIR)/"

PLUGIN_DIR ?= /srv/tuoni/plugins/server

## install: Copy plugin JAR to Tuoni server and restart
.PHONY: install
install: build
	sudo cp -- "$(BUILD_DIR)/$(JAR_NAME)" "$(PLUGIN_DIR)/"
	tuoni server restart
	@echo "[+] Installed $(JAR_NAME) to $(PLUGIN_DIR) and restarted tuoni"

## clean: Remove build artifacts
.PHONY: clean
clean:
	@set -eu; \
	project_dir=$$(pwd -P); \
	for candidate in "$(BUILD_DIR)" exec-code/linux/build exec-code/win-native/build; do \
		if [ ! -d "$$candidate" ]; then continue; fi; \
		artifact_dir=$$(CDPATH= cd -- "$$candidate" && pwd -P); \
		if [ "$$artifact_dir" != "$$project_dir/$$candidate" ]; then \
			printf '%s\n' "Refusing to clean redirected build directory: $$candidate" >&2; exit 1; \
		fi; \
		rm -rf -- "$$artifact_dir"; \
	done
	@echo "[+] Cleaned"

## build-windows-native: Build Windows x86/x64 native DLLs inside Docker
.PHONY: build-windows-native
build-windows-native:
	@mkdir -p -- "$(BUILD_DIR)" exec-code/win-native/build
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target windows-native-artifacts \
		--output "type=local,dest=exec-code/win-native/build/" \
		.
	cp exec-code/win-native/build/*.native32_dll exec-code/win-native/build/*.native64_dll "$(BUILD_DIR)/"
