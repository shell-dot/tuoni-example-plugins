#!make
.DEFAULT_GOAL := help

DOCKER ?= docker
IMAGE_NAME := tuoni-example-command-plugin-builder
BUILD_DIR  := public
JAR_NAME   := tuoni-example-plugin-echo-command-0.0.1.jar
COMMANDS   := echo echo-ongoing echo-ongoing-file echo-ongoing-more-data

##### GENERAL #####
## help: List all available make targets with descriptions
.PHONY: help
help:
	@printf '[*] usage: make <target>\n\n'
	@sed -nr 's/^##\s+/\t/p' $(MAKEFILE_LIST) | column -t -s ':'

## build: Build the plugin JAR and commands inside Docker and extract to public/
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
		echo "[+] Build complete: $(BUILD_DIR)/$$command.shellcode"; \
		echo "[+] Build complete: $(BUILD_DIR)/$$command-linux.native64_so"; \
	done

## build-dotnet: Build and extract only the .NET command executables with Docker
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

## clean: Remove build artifacts and Docker images
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
	@$(DOCKER) image rm "$(IMAGE_NAME)" 2>/dev/null || true
	@echo "[+] Cleaned"
