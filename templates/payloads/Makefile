#!make
.DEFAULT_GOAL := help

# The runner uses sudo only when the local Docker socket denies access.
# An explicit DOCKER override bypasses automatic detection.
DOCKER ?= sh scripts/docker/run-docker.sh
BUILD_DIR := build
JAR_NAME := payload-plugin-template-0.0.1.jar
EXEC_NAME := payload-template

.PHONY: help build build-dotnet clean
help:
	@printf '%s\n' 'make build         Build the payload program and plugin JAR with Docker' 'make build-dotnet  Build only the .NET payload executable with Docker' 'make clean         Remove the extracted build artifacts'

build:
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@printf '%s\n' "Built $(BUILD_DIR)/$(JAR_NAME)" "Built $(BUILD_DIR)/$(EXEC_NAME).exe"

build-dotnet:
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target dotnet-artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@printf '%s\n' "Built $(BUILD_DIR)/$(EXEC_NAME).exe"

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
