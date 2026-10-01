#!/bin/sh
# Render every printable part to stl/ and the documentation images to docs/img/.
# Needs OpenSCAD (2021.01+) and, for images, xvfb-run.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SCAD="$ROOT/cad/lsr.scad"
STL="$ROOT/stl"; IMG="$ROOT/docs/img"
mkdir -p "$STL/actuator" "$STL/structure" "$STL/antenna" "$STL/tripod" "$STL/electronics" "$IMG"
J=${JOBS:-4}
part() {  # dir name PART [extra -D ...]
  d=$1; n=$2; p=$3; shift 3
  echo "  $d/$n.stl"
  openscad -q -D "PART=\"$p\"" "$@" -o "$STL/$d/$n.stl" "$SCAD" 2>/dev/null
}
(
part actuator act_body act_body &
part actuator act_front_AZ_with_hall_tab act_front &
part actuator act_front_EL act_front_nohall &
part actuator act_cover act_cover &
wait
part actuator act_output act_output &
part actuator act_washer act_washer &
part actuator act_disc act_disc &
part actuator act_cam act_cam &
wait
part actuator enc_cap enc_cap &
part structure base base &
part structure head head &
part structure stub_socket stub_socket &
wait
part structure cable_clip cable_clip &
part tripod adapter_3-8in_photo adapter_nut -D 'NUT="3/8"' &
part tripod adapter_5-8in_survey adapter_nut -D 'NUT="5/8"' &
part tripod adapter_spigot_35mm adapter_spigot35 &
wait
for m in 25 32 40; do part tripod adapter_mast_${m}mm adapter_mast -D "MAST_D=$m" & done
part electronics ebox ebox &
wait
part electronics ebox_lid ebox_lid &
part electronics ebox_bracket ebox_bracket &
for b in 15 20 22 25; do part antenna boom_clamp_D${b} boom_clamp -D "BOOM=$b" & done
wait
part antenna boom_clamp_SQ20 boom_clamp -D 'BOOM_SQ=20' &
for b in 15 20 25; do part antenna counterweight_D${b} counterweight_clamp -D "BOOM=$b" & done
wait
for b in 15 20 25; do part antenna sun_sight_D${b} sun_sight -D "BOOM=$b" & done
wait
)
if command -v xvfb-run >/dev/null && [ "${NO_IMG:-0}" != 1 ]; then
  echo "  renders"
  R="xvfb-run -a openscad -q --colorscheme Tomorrow"
  $R -D 'PART="assembly"' -D 'EL_DEG=20' --imgsize 1400,1100 --camera 560,-760,560,60,0,140 -o "$IMG/assembly.png" "$SCAD" 2>/dev/null &
  $R -D 'PART="assembly"' -D 'EL_DEG=90' -D 'AZ_DEG=30' --imgsize 1400,1100 --camera 700,-800,480,60,0,120 -o "$IMG/assembly_el90.png" "$SCAD" 2>/dev/null &
  $R -D 'PART="act_assembly"' -D 'EXPLODE=22' --imgsize 1100,1100 --camera 300,-360,230,0,0,0 -o "$IMG/actuator_exploded.png" "$SCAD" 2>/dev/null &
  wait
  $R -D 'PART="act_section"' --imgsize 1100,900 --camera 0,-230,40,0,0,0 -o "$IMG/actuator_section.png" "$SCAD" 2>/dev/null &
  $R -D 'PART="act_disc"' --imgsize 900,900 --camera 0,0,220,0,0,0 -o "$IMG/cycloid_disc.png" "$SCAD" 2>/dev/null &
  $R -D 'PART="head"' --imgsize 900,800 --camera 160,-200,180,0,0,40 -o "$IMG/head.png" "$SCAD" 2>/dev/null &
  wait
fi
echo "STL files: $(find "$STL" -name '*.stl' | wc -l)"
