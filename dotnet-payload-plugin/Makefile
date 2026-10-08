#!make
.DEFAULT_GOAL := help

# The runner uses sudo only when the local Docker socket denies access.
# An explicit DOCKER override bypasses automatic detection.
DOCKER ?= sh scripts/docker/run-docker.sh
BUILD_DIR  := build
JAR_NAME   := tuoni-example-plugin-dotnet-payload-0.0.1.jar

##### GENERAL #####
## help: List all available make targets with descriptions
.PHONY: help
help:
	@printf '%s\n' '[*] usage: make <target>'
	@echo ""
	@awk -F ': ' '/^## / { target=$$1; sub(/^## /, "", target); printf "  %-22s %s\n", target, substr($$0, index($$0, ": ") + 2) }' $(MAKEFILE_LIST)

## build: Build the plugin JAR inside Docker and extract to build/
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
	@echo "[+] Build complete: $(BUILD_DIR)/dotnet-agent.exe"

## build-dotnet: Build and extract only the .NET agent executable with Docker
.PHONY: build-dotnet
build-dotnet:
	@mkdir -p -- "$(BUILD_DIR)"
	DOCKER_BUILDKIT=1 $(DOCKER) build \
		-f scripts/docker/Dockerfile \
		--target dotnet-artifacts \
		--output "type=local,dest=$(BUILD_DIR)/" \
		.
	@echo "[+] Build complete: $(BUILD_DIR)/dotnet-agent.exe"

PLUGIN_DIR ?= /srv/tuoni/plugins/server
TUONI ?= tuoni

## install: Copy plugin JAR to Tuoni server and restart
.PHONY: install
install: build
	sh scripts/install/install-plugin.sh "$(BUILD_DIR)/$(JAR_NAME)" "$(PLUGIN_DIR)" "$(TUONI)"

## clean: Remove build artifacts
.PHONY: clean
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
	@echo "[+] Cleaned"
