#!make
.DEFAULT_GOAL := help

TEMPLATES := $(patsubst %/Makefile,%,$(wildcard */Makefile))

.PHONY: help build build-dotnet build-linux clean install
help build build-dotnet clean:
	@set -e; \
	for template in $(TEMPLATES); do \
		$(MAKE) -C "$$template" $@; \
	done

build-linux:
	@set -e; \
	for template in command listener; do \
		$(MAKE) -C "$$template" $@; \
	done

# Templates are skeletons and are not installed.
install:
	@printf '%s\n' 'Templates are skeletons; no template plugin is installed.'
