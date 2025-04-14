# Makefile for Basilisk visualization tools

# Check if .project_config exists
ifeq ($(wildcard ../.project_config),)
  $(error "../.project_config not found")
endif

# Load Basilisk path
BASILISK := $(shell . ../.project_config && echo $$BASILISK)

# Compiler options
QCC = $(BASILISK)/src/qcc
CFLAGS = -Wall -O2
LDFLAGS = -lm

# Source directories
CFLAGS += -I$(BASILISK) -I$(BASILISK)/src

# Include Basilisk definitions
include $(BASILISK)/Makefile.defs

# All targets
all: v_view2D independent_viewer

# The v_view tool is compiled using qcc
v_view2D: v_view.c
	$(QCC) $(CFLAGS) -autolink $< -o $@ -lfb_tiny -lm

v_view3D: v_view.c
	$(QCC) $(CFLAGS) -autolink -grid=octree $< -o $@ -lfb_tiny -lm

# The independent_viewer also needs to be compiled using qcc
independent_viewer: independent_viewer.c
	$(QCC) $(CFLAGS) -autolink $< -o $@ -lfb_tiny -lm

# Clean targets
clean:
	rm -f v_view2D v_view3D independent_viewer

rebuild: clean all

install: all
	cp v_view2D $(BASILISK)/src/
	[ -f v_view3D ] && cp v_view3D $(BASILISK)/src/ || true
	cp independent_viewer $(BASILISK)/src/

.PHONY: all clean rebuild install 