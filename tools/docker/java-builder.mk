# Keep these defaults identical in all shipped copies; bump both for a new baseline.
BUILDER_IMAGE ?= ghcr.io/shell-dot/tuoni-java-builder:0.15.0
GRADLE_CACHE_ID ?= tuoni-gradle-9.8.2-v1

DOCKER_BUILD_FLAGS = --platform linux/amd64 \
	--build-arg "BUILDER_IMAGE=$(BUILDER_IMAGE)" \
	--build-arg "GRADLE_CACHE_ID=$(GRADLE_CACHE_ID)"

.PHONY: check-java-builder
check-java-builder:
	@$(DOCKER) image inspect "$(BUILDER_IMAGE)" >/dev/null 2>&1 || { \
		printf '%s\n' 'Pulling Java builder image: $(BUILDER_IMAGE)'; \
		$(DOCKER) pull --platform linux/amd64 "$(BUILDER_IMAGE)" || { \
			printf '%s\n' 'Could not pull the Java builder image. Check the image reference and registry access.' >&2; \
			exit 1; \
		}; \
	}
