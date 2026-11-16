# LibreSat Rotator LSR-1 — top-level build
#   make            everything that does not need Java/Freerouting (STL, renders, fab outputs, firmware, tests, docs)
#   make pcb        re-place + autoroute the PCB (needs Java 17 and tools/freerouting-1.9.0.jar, see tools/README.md)
#   make test       firmware host tests + software tests
#   make verify     tests + STL watertight check + PCB DRC summary + cycloid check
PY ?= python3
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
bom:
	$(PY) scripts/bom.py
test:
	$(MAKE) -C firmware test
	cd software && $(PY) -m pytest -q
verify: test
	$(PY) calc/cycloid_check.py
	$(PY) calc/lsr2_sizing.py --check
	$(PY) scripts/verify_stl.py
	@grep -E "^\*\* Found" hardware/pcb/lsr_ctl_drc.rpt
sim:
	cd software && $(PY) -m lsr run --sim

.PHONY: all stl fab pcb firmware calc bom test verify sim
