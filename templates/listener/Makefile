#!make
.DEFAULT_GOAL := help

DOCKER ?= docker
BUILD_DIR := build
JAR_NAME := listener-plugin-template-0.0.1.jar
EXEC_NAME := listener-execunit-template

.PHONY: help build build-dotnet build-linux clean
help:
	@printf '%s\n' 'make build         Build both listener execunits and the plugin JAR with Docker' 'make build-dotnet  Build only the .NET listener executable with Docker' 'make build-linux   Build only the Linux x64 native execunit with Docker' 'make clean         Remove the extracted build artifacts'

build:
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@printf '%s\n' "Built $(BUILD_DIR)/$(JAR_NAME)" "Built $(BUILD_DIR)/$(EXEC_NAME).exe" "Built $(BUILD_DIR)/$(EXEC_NAME).shellcode" "Built $(BUILD_DIR)/listener-linux.native64_so"

build-dotnet:
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target dotnet-artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@printf '%s\n' "Built $(BUILD_DIR)/$(EXEC_NAME).exe"

build-linux:
	@mkdir -p -- "$(BUILD_DIR)" exec-code/linux/build
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target linux-artifacts \
		--output "type=local,dest=exec-code/linux/build/" \
		.
	cp exec-code/linux/build/listener-linux.native64_so "$(BUILD_DIR)/"

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
