#!make
.DEFAULT_GOAL := help

TEMPLATES := $(patsubst %/Makefile,%,$(wildcard */Makefile))

.PHONY: help build build-dotnet clean install
help build build-dotnet clean:
	@set -e; \
	for template in $(TEMPLATES); do \
		$(MAKE) -C "$$template" $@; \
	done

# The repository root invokes install on every immediate child Makefile.
install:
	@printf '%s\n' 'Templates are skeletons; no template plugin is installed.'
