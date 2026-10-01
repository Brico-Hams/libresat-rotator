# Tools

`hardware/build_pcb.sh` autoroutes the board with **Freerouting 1.9.0** (GPL-3.0), which is not stored in git:

    curl -L -o tools/freerouting-1.9.0.jar https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar

Only needed to re-route after changing the placement in `hardware/gen_pcb.py`. The routed board is already in `hardware/pcb/`.
