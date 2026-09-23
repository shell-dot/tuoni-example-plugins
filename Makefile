#!make
.DEFAULT_GOAL := help

EXAMPLES := $(patsubst %/Makefile,%,$(wildcard */Makefile))

.PHONY: help build install clean
help build install clean:
	@set -e; \
	for example in $(EXAMPLES); do \
		$(MAKE) -C "$$example" $@; \
	done
