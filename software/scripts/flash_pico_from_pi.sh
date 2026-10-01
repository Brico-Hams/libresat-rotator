#!/bin/bash
# Update the controller firmware from the Pi Zero over SWD (J14 wired to the Pico SWD pads:
# J14.1 SWCLK <- Pi GPIO25, J14.2 GND, J14.3 SWDIO <- Pi GPIO24). Needs openocd with bcm2835gpio.
#   ./flash_pico_from_pi.sh lsr1.elf
set -euo pipefail
ELF=${1:-lsr1.elf}
openocd -c "adapter driver bcm2835gpio; bcm2835gpio peripheral_base 0x3F000000; adapter speed 1000; \
  adapter gpio swclk 25; adapter gpio swdio 24; transport select swd" \
  -f target/rp2040.cfg -c "program $ELF verify reset exit"
