#!/bin/sh
# Full PCB flow: place -> Specctra DSN -> Freerouting (autoroute) -> import + GND pours + DRC
# Needs: KiCad 7 (pcbnew python), Java 17+, freerouting-1.9.0.jar (FREEROUTING=/path/to/jar), xvfb-run.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-$HERE/pcb}
FR=${FREEROUTING:-$HERE/../tools/freerouting-1.9.0.jar}
export KICAD7_FOOTPRINT_DIR=${KICAD7_FOOTPRINT_DIR:-/usr/share/kicad/footprints}
python3 "$HERE/gen_pcb.py" place "$OUT"
rm -f "$OUT/lsr_ctl.ses"
( cd "$OUT" && xvfb-run -a java -jar "$FR" -de lsr_ctl.dsn -do lsr_ctl.ses -mp 30 -mt 1 -oit 1.0 > freerouting.log 2>&1 )
test -s "$OUT/lsr_ctl.ses" || { echo "freerouting failed, see $OUT/freerouting.log"; exit 1; }
python3 "$HERE/gen_pcb.py" finish "$OUT"
grep -E "^\*\* Found" "$OUT/lsr_ctl_drc.rpt"
