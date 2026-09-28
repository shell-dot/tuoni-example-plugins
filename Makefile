#!make
.DEFAULT_GOAL := help

EXAMPLES := $(patsubst %/Makefile,%,$(wildcard */Makefile))
LINUX_EXAMPLES := $(patsubst %/exec-code/linux/build_linux.sh,%,$(wildcard */exec-code/linux/build_linux.sh))

.PHONY: help build build-dotnet build-linux install clean
help build build-dotnet install clean:
	@set -e; \
	for example in $(EXAMPLES); do \
		$(MAKE) -C "$$example" $@; \
	done

build-linux:
	@set -e; \
	for example in $(LINUX_EXAMPLES); do \
		$(MAKE) -C "$$example" build-linux; \
	done
