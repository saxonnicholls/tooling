#
#  tooling.mk
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  The standard make targets of a repository, driven by its tooling.conf (README "make/tooling.mk"). The
#  repository's Makefile is one line, plus any targets of its own:
#
#      include third_party/tooling/make/tooling.mk
#
#      make test            configure, build, run every CTest, after the checks
#      make test-werror     the same with <option_prefix>WERROR=ON, as CI does
#      make asan            AddressSanitizer and UBSan, warnings as errors
#      make docs            the documentation (tooling.conf docs = yes), in build-docs
#      make check           check_version.py, check_mirror.py, check_interfaces.py, single_include.py --check,
#                           check_pins.py
#      make single-include  write single_include/<name>.hpp (git-ignored; CI attaches it to every release)
#      make ubuntu          the Ubuntu gate in Docker (scripts/test_ubuntu.sh; UBUNTU="--quick" for its arguments)
#      make demos           build and run every demo with its output shown (CTest label demo), or make.demos
#      make benchmarks      build the benchmarks in Release (benchmarks = yes) and run them: CTest label benchmark,
#                           or make.benchmarks
#      make clean
#
#      make test CXX=clang++  BUILD=build-x  CONFIG=Debug  CMAKE_FLAGS="-DX=ON"  JOBS=4
#
#  tooling.conf: option_prefix (required); docs and benchmarks; cmake, added to every configure; make.demos and
#  make.benchmarks, a command each that replaces the default run, with BUILD, CONFIG and CXX in its environment.
#

TOOLING_DIR := $(patsubst %/make/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
TOOLING_REPO ?= $(CURDIR)
PYTHON ?= python3
, := ,

# tooling_conf <get|flag> <key> [default]: one setting, read by scripts/tooling_conf.py
tooling_conf = $(shell $(PYTHON) $(TOOLING_DIR)/scripts/tooling_conf.py --root $(TOOLING_REPO) $(1))

TOOLING_PREFIX := $(call tooling_conf,get option_prefix)
ifeq ($(TOOLING_PREFIX),)
$(error tooling.mk: $(TOOLING_REPO)/tooling.conf sets no option_prefix)
endif
TOOLING_DOCS := $(call tooling_conf,flag docs no)
TOOLING_BENCHMARKS := $(call tooling_conf,flag benchmarks no)
TOOLING_CMAKE := $(call tooling_conf,get cmake "")
TOOLING_DEMOS := $(call tooling_conf,get make.demos "")
TOOLING_BENCH_RUN := $(call tooling_conf,get make.benchmarks "")

ifeq ($(origin CXX),default)
CXX := c++
endif
BUILD ?= build
CONFIG ?= Release
CMAKE_FLAGS ?=
# The machine's share, never all of it (scripts/resources.sh jobs), worked out once
ifeq ($(origin JOBS),undefined)
JOBS := $(shell $(TOOLING_DIR)/scripts/resources.sh jobs)
endif
UBUNTU ?=

# tooling_configure <dir> <build type> <cmake arguments>
tooling_configure = cmake -S . -B $(1) -DCMAKE_BUILD_TYPE=$(2) -DCMAKE_CXX_COMPILER=$(CXX) $(TOOLING_CMAKE) $(3) $(CMAKE_FLAGS)

# tooling_build <dir> <build type> <cmake arguments>: configure, build, run every CTest
define tooling_build
$(call tooling_configure,$(1),$(2),$(3))
cmake --build $(1) --parallel $(JOBS)
ctest --test-dir $(1) --output-on-failure
endef

.PHONY: test test-werror asan docs check single-include ubuntu demos benchmarks clean

test: check
	$(call tooling_build,$(BUILD),$(CONFIG),)

test-werror: check
	$(call tooling_build,build-werror,$(CONFIG),-D$(TOOLING_PREFIX)WERROR=ON)

asan: export UBSAN_OPTIONS ?= halt_on_error=1:print_stacktrace=1
asan: check
	$(call tooling_build,build-asan,RelWithDebInfo,-D$(TOOLING_PREFIX)WERROR=ON -D$(TOOLING_PREFIX)SANITIZE=address$(,)undefined)

check:
	$(PYTHON) $(TOOLING_DIR)/scripts/check_version.py --root $(TOOLING_REPO)
	$(PYTHON) $(TOOLING_DIR)/scripts/check_mirror.py --root $(TOOLING_REPO)
	$(PYTHON) $(TOOLING_DIR)/scripts/check_interfaces.py --root $(TOOLING_REPO)
	$(PYTHON) $(TOOLING_DIR)/scripts/single_include.py --root $(TOOLING_REPO) --check
	$(PYTHON) $(TOOLING_DIR)/scripts/check_pins.py --root $(TOOLING_REPO)

single-include:
	$(PYTHON) $(TOOLING_DIR)/scripts/single_include.py --root $(TOOLING_REPO)

docs:
ifeq ($(TOOLING_DOCS),yes)
	cmake -S . -B build-docs -D$(TOOLING_PREFIX)BUILD_DOCS=ON -D$(TOOLING_PREFIX)BUILD_TESTS=OFF $(TOOLING_CMAKE) $(CMAKE_FLAGS)
	cmake --build build-docs --target docs
else
	@echo "tooling.mk: no documentation to build (tooling.conf: docs = no)" >&2; exit 1
endif

ubuntu:
	$(TOOLING_DIR)/scripts/test_ubuntu.sh --repo $(TOOLING_REPO) $(UBUNTU)

demos:
ifeq ($(TOOLING_DEMOS),)
	$(call tooling_configure,$(BUILD),$(CONFIG),)
	cmake --build $(BUILD) --parallel $(JOBS)
	ctest --test-dir $(BUILD) -L demo --verbose
else
	BUILD=$(BUILD) CONFIG=$(CONFIG) CXX=$(CXX) $(TOOLING_DEMOS)
endif

benchmarks:
ifeq ($(TOOLING_BENCHMARKS),yes)
	$(call tooling_configure,build-bench,Release,-D$(TOOLING_PREFIX)BUILD_BENCHMARKS=ON)
	cmake --build build-bench --parallel $(JOBS)
ifeq ($(TOOLING_BENCH_RUN),)
	ctest --test-dir build-bench -L benchmark --verbose
else
	BUILD=build-bench CONFIG=Release CXX=$(CXX) $(TOOLING_BENCH_RUN)
endif
else
	@echo "tooling.mk: no benchmarks to build (tooling.conf: benchmarks = no)" >&2; exit 1
endif

clean:
	rm -rf $(BUILD) build-werror build-asan build-docs build-bench
