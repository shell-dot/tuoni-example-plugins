#!make
.DEFAULT_GOAL := help

# The runner uses sudo only when the local Docker socket denies access.
# An explicit DOCKER override bypasses automatic detection.
DOCKER ?= sh scripts/docker/run-docker.sh
BUILD_DIR := build
JAR_NAME := listener-plugin-template-0.0.1.jar
EXEC_NAME := listener-execunit-template
PLUGIN_DIR ?= /srv/tuoni/plugins/server
TUONI ?= tuoni

.PHONY: help build build-dotnet build-linux install clean
help:
	@printf '%s\n' 'make build         Build all listener execunit formats and the plugin JAR with Docker' 'make build-dotnet  Build the .NET EXE, DLL and entrypoint metadata with Docker' 'make build-linux   Build only the Linux x64 native execunit with Docker' 'make build-windows-native  Build Windows x86/x64 native DLLs' 'make install       Build, copy the plugin JAR to Tuoni and restart' 'make clean         Remove the extracted build artifacts'

build:
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@printf '%s\n' "Built $(BUILD_DIR)/$(JAR_NAME)" "Built $(BUILD_DIR)/$(EXEC_NAME).exe" "Built $(BUILD_DIR)/$(EXEC_NAME).dotnet_exe" "Built $(BUILD_DIR)/$(EXEC_NAME).dotnet_dll" "Built $(BUILD_DIR)/$(EXEC_NAME).dotnet_dll_method" "Built $(BUILD_DIR)/$(EXEC_NAME).shellcode" "Built $(BUILD_DIR)/listener-linux.native64_so" "Built $(BUILD_DIR)/listener.native32_dll" "Built $(BUILD_DIR)/listener.native64_dll"

build-dotnet:
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target dotnet-artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@printf '%s\n' "Built $(BUILD_DIR)/$(EXEC_NAME).exe" "Built $(BUILD_DIR)/$(EXEC_NAME).dotnet_exe" "Built $(BUILD_DIR)/$(EXEC_NAME).dotnet_dll" "Built $(BUILD_DIR)/$(EXEC_NAME).dotnet_dll_method"

build-linux:
	@mkdir -p -- "$(BUILD_DIR)" exec-code/linux/build
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target linux-artifacts \
		--output "type=local,dest=exec-code/linux/build/" \
		.
	cp exec-code/linux/build/listener-linux.native64_so "$(BUILD_DIR)/"

install: build
	sh scripts/install/install-plugin.sh "$(BUILD_DIR)/$(JAR_NAME)" "$(PLUGIN_DIR)" "$(TUONI)"

clean:
	@set -eu; \
	if [ ! -d "$(BUILD_DIR)" ]; then exit 0; fi; \
	project_dir=$$(pwd -P); \
	artifact_dir=$$(CDPATH= cd -- "$(BUILD_DIR)" && pwd -P); \
	case "$$artifact_dir" in \
		"$$project_dir"/*) ;; \
		*) printf '%s\n' "Refusing to clean outside a project subdirectory: $$artifact_dir" >&2; exit 1 ;; \
	esac; \
	rm -rf -- "$$artifact_dir"

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
