#!make
.DEFAULT_GOAL := help

IMAGE_NAME := tuoni-example-listener-plugin-builder
BUILD_DIR  := build
JAR_NAME   := tuoni-example-plugin-tcp-listener-0.0.1.jar

##### GENERAL #####
## help: List all available make targets with descriptions
.PHONY: help
help:
	@printf '[*] usage: make <target>\n\n'
	@sed -nr 's/^##\s+/\t/p' $(MAKEFILE_LIST) | column -t -s ':'

## build: Build the plugin JAR and listener inside Docker and extract to build/
.PHONY: build
build:
	@mkdir -p $(BUILD_DIR)
	DOCKER_BUILDKIT=1 sudo docker build \
		-f scripts/docker/Dockerfile \
		--target artifacts \
		--output type=local,dest=$(BUILD_DIR)/ \
		.
	@echo ""
	@echo "[+] Build complete: $(BUILD_DIR)/$(JAR_NAME)"
	@echo "[+] Build complete: $(BUILD_DIR)/tcp-listener.exe"
	@echo "[+] Build complete: $(BUILD_DIR)/tcp-listener.shellcode"

PLUGIN_DIR ?= /srv/tuoni/plugins/server

## install: Copy plugin JAR to Tuoni server and restart
.PHONY: install
install: build
	sudo cp $(BUILD_DIR)/$(JAR_NAME) $(PLUGIN_DIR)/
	tuoni server restart
	@echo "[+] Installed $(JAR_NAME) to $(PLUGIN_DIR) and restarted tuoni"

## clean: Remove build artifacts and Docker images
.PHONY: clean
clean:
	rm -rf $(BUILD_DIR)
	@docker image rm $(IMAGE_NAME) 2>/dev/null || true
	@echo "[+] Cleaned"
