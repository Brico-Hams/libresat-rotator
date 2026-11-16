# make            -> build/lsr1.uf2 (needs PICO_SDK_PATH and arm-none-eabi-gcc)
# make lsr2       -> build-lsr2/lsr2.uf2 (LSR_MODEL=2, external STEP/DIR drivers)
# make test       -> host unit tests of the hardware-independent logic
PICO_BOARD ?= pico
all:
	cmake -B build -DPICO_BOARD=$(PICO_BOARD) -DCMAKE_BUILD_TYPE=Release
	cmake --build build -j
lsr2:
	cmake -B build-lsr2 -DPICO_BOARD=$(PICO_BOARD) -DCMAKE_BUILD_TYPE=Release -DLSR_MODEL=2
	cmake --build build-lsr2 -j
test:
	mkdir -p build-test
	$(CXX) -std=c++17 -O1 -Wall -o build-test/test_core test/test_core.cpp src/core.cpp
	./build-test/test_core
clean:
	rm -rf build build-lsr2 build-test
.PHONY: all lsr2 test clean
