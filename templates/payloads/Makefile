#!make
.DEFAULT_GOAL := help

# The runner uses sudo only when the local Docker socket denies access.
# An explicit DOCKER override bypasses automatic detection.
DOCKER ?= sh scripts/docker/run-docker.sh
BUILDER_IMAGE ?= tuoni-plugin-builder:0.15.0-gradle9.7.1-v1
BUILD_DIR := build
JAR_NAME := payload-plugin-template-0.0.1.jar
EXEC_NAME := payload-template
PLUGIN_DIR ?= /srv/tuoni/plugins/server
TUONI ?= tuoni

.PHONY: help build build-dotnet install clean
help:
	@printf '%s\n' 'make build         Build the payload program and plugin JAR with Docker' 'make build-dotnet  Build only the .NET payload executable with Docker' 'make install       Build, copy the plugin JAR to Tuoni and restart' 'make clean         Remove the extracted build artifacts'

build:
	@$(DOCKER) image inspect "$(BUILDER_IMAGE)" >/dev/null || { \
		printf '%s\n' "Missing offline builder: $(BUILDER_IMAGE). Run make builder-image at the repository root, or load the instructor archive with make builder-load." >&2; exit 1; \
	}
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build --platform linux/amd64 --network=none $(DOCKER_BUILD_FLAGS) \
		-f scripts/docker/Dockerfile \
		--build-arg "BUILDER_IMAGE=$(BUILDER_IMAGE)" \
		--target artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@printf '%s\n' "Built $(BUILD_DIR)/$(JAR_NAME)" "Built $(BUILD_DIR)/$(EXEC_NAME).exe"

build-dotnet:
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build --platform linux/amd64 --network=none $(DOCKER_BUILD_FLAGS) \
		-f scripts/docker/Dockerfile \
		--build-arg "BUILDER_IMAGE=$(BUILDER_IMAGE)" \
		--target dotnet-artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@printf '%s\n' "Built $(BUILD_DIR)/$(EXEC_NAME).exe"

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
