# Keep these defaults identical in all shipped copies; bump both for a new baseline.
BUILDER_IMAGE ?= ghcr.io/shell-dot/tuoni-java-builder:0.15.0
GRADLE_CACHE_ID ?= tuoni-gradle-9.8.2-v3

DOCKER_BUILD_FLAGS = --platform linux/amd64 \
	--build-arg "BUILDER_IMAGE=$(BUILDER_IMAGE)" \
	--build-arg "GRADLE_CACHE_ID=$(GRADLE_CACHE_ID)"

.PHONY: check-docker-buildx check-java-builder
check-docker-buildx:
	@$(DOCKER) info >/dev/null
	@$(DOCKER) buildx version >/dev/null || { \
		printf '%s\n' \
			'Docker Buildx is required to build these plugins.' \
			'For Docker installed by tuoni.sh, install: sudo apt-get install docker-buildx-plugin' \
			'For Debian/Kali docker.io packages, install: sudo apt-get install docker-buildx' \
			'Buildx must also be available through sudo when Docker socket access requires it.' >&2; \
		exit 1; \
	}

check-java-builder: check-docker-buildx
	@$(DOCKER) image inspect "$(BUILDER_IMAGE)" >/dev/null 2>&1 || { \
		printf '%s\n' 'Pulling Java builder image: $(BUILDER_IMAGE)'; \
		$(DOCKER) pull --platform linux/amd64 "$(BUILDER_IMAGE)" || { \
			printf '%s\n' 'Could not pull the Java builder image. Check the image reference and registry access.' >&2; \
			exit 1; \
		}; \
	}
