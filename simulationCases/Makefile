# Check if .project_config exists
ifeq ($(wildcard ../.project_config),)
  $(error "../.project_config not found")
endif

BASILISK := $(shell . ../.project_config && echo $$BASILISK)

CFLAGS += -O2 -disable-dimensions
CFLAGS += -I$(PWD)/src-local -I$(PWD)/../src-local

# Fix permissions for runtest script
fix-permissions:
	@chmod +x $(BASILISK)/src/runtest

# Make all test targets depend on fix-permissions
%.tst: fix-permissions

include $(BASILISK)/Makefile.defs