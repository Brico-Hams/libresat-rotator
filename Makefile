# LibreSat Rotator LSR-1 — top-level build
#   make            everything that does not need Java/Freerouting (STL, renders, fab outputs, firmware, tests, docs)
#   make lsr2       (also: make render  photoreal Cycles renders with Blender 5.x: BLENDER=blender RENDER_OUT=docs/img RENDER_ARGS="--samples 64";
#                    on Windows with Controlled Folder Access set RENDER_OUT outside Documents, like LSR2_OUT)
#   make pcb        re-place + autoroute the PCB (needs Java 17 and tools/freerouting-1.9.0.jar, see tools/README.md)
#   make test       firmware host tests + software tests
#   make verify     tests + STL watertight check + PCB DRC summary + cycloid check
PY ?= python3
BLENDER ?= blender
RENDER_OUT ?= docs/img
RENDER_ARGS ?=
FREECADCMD ?= freecadcmd
export KICAD7_FOOTPRINT_DIR ?= /usr/share/kicad/footprints

all: stl fab firmware calc bom test

stl:
	sh scripts/build_cad.sh
fab:
	$(PY) hardware/export_fab.py
pcb:
	sh hardware/build_pcb.sh hardware/pcb
firmware:
	$(MAKE) -C firmware
calc:
	$(PY) calc/cycloid_check.py
	$(PY) calc/sizing.py > /dev/null
	$(PY) calc/lsr2_sizing.py
	$(PY) calc/lsr2_materials.py
lsr2:
	$(PY) cad/lsr2/plates.py
	$(PY) cad/lsr2/cast_parts.py
	cd $(CURDIR) && REPO=$(CURDIR) $(FREECADCMD) -c "exec(open(r'$(CURDIR)/cad/lsr2/build.py').read())"
	$(PY) scripts/render_lsr2.py $(CURDIR) $(or $(LSR2_OUT),$(CURDIR))/stl/lsr2 docs/img
render:
	$(BLENDER) -b --factory-startup -P scripts/render_blender.py -- $(CURDIR) $(or $(LSR2_OUT),$(CURDIR))/stl/lsr2 $(RENDER_OUT) $(RENDER_ARGS)
bom:
	$(PY) scripts/bom.py
test:
	$(MAKE) -C firmware test
	cd software && $(PY) -m pytest -q
verify: test
	$(PY) calc/cycloid_check.py
	$(PY) calc/lsr2_sizing.py --check
	$(PY) calc/lsr2_materials.py --check
	$(PY) scripts/verify_stl.py
	@grep -E "^\*\* Found" hardware/pcb/lsr_ctl_drc.rpt
sim:
	cd software && $(PY) -m lsr run --sim

.PHONY: all stl fab pcb firmware calc lsr2 render bom test verify sim
