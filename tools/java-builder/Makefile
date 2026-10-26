.DEFAULT_GOAL := help

DOCKER ?= docker
BUILDER_IMAGE ?= ghcr.io/shell-dot/tuoni-java-builder:0.15.0

.PHONY: help build check
help:
	@printf '%s\n' 'make build  Build and tag the image locally' 'make check  Verify dependencies in the built image without network access' 'BUILDER_IMAGE=...  Override the image tag' 'DOCKER=...  Override the Docker command'

build:
	DOCKER_BUILDKIT=1 $(DOCKER) build --platform linux/amd64 -t "$(BUILDER_IMAGE)" .
	@$(DOCKER) image inspect --format 'Local image size: {{.Size}} bytes' "$(BUILDER_IMAGE)"

check:
	$(DOCKER) run --rm --platform linux/amd64 --network none \
		--workdir /opt/dependency-project "$(BUILDER_IMAGE)" \
		sh ./gradlew resolveDependencies --no-daemon --offline
