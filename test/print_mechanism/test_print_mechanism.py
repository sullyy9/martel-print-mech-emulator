import asyncio
import os
from typing import Final, Optional
from pathlib import Path
from decimal import Decimal

import cocotb
from cocotb.triggers import Timer

import numpy as np
from numpy import uint8, float32
from numpy.typing import NDArray

import cv2 as cv

from .. import config
from ..clock_domain import ClockDomainDriver

from .thermal_head_driver import ThermalHeadDriver
from .print_mech_monitor import PrintMechMonitor

##################################################


# def test_print_mechanism():
#     config.run_test(
#         toplevel="print_mechanism",
#         output_directory=Path(config.OUTPUT_DIRECTORY, "print_mechanism"),
#         test_module="test.print_mechanism.test_print_mechanism",
#     )


##################################################


@cocotb.test()  # type: ignore
async def run_test(dut):
    clock_domain: Final = ClockDomainDriver(dut.clk, dut.reset)

    head_driver: Final = ThermalHeadDriver(
        name="HeadDriver",
        clock=dut.mech_clk,
        data=dut.mech_data,
        latch=dut.mech_latch,
        dst=dut.mech_dst,
    )

    print_monitor: Final = PrintMechMonitor(
        name="PrintMechMonitor",
        print_line_ready=dut.print_line_ready,
        print_line=dut.print_line,
    )

    clock_domain.start(100_000_000)
    await clock_domain.reset(2)

    print_monitor.start()

    log = cocotb.log.getChild("Test")

    with open(Path(os.path.dirname(__file__), "./Arial16.csv")) as file:
        csv_data = np.genfromtxt(
            file,
            delimiter=",",
            skip_header=1,
            max_rows=50_000,
            dtype=[float32, uint8, uint8, uint8, uint8, uint8, uint8],
        )

        last_timestamp: Optional[float] = None
        i = 0
        for timestamp, clock, data, latch, dst, motora, motorb in csv_data:
            if (i % 1000) == 0:
                log.info(f"{i}/{len(csv_data)}")

            i += 1

            if last_timestamp is None:
                last_timestamp = timestamp

            time_delta_ns = (timestamp - last_timestamp) * 1_000_000_000
            time_delta_ns = int(time_delta_ns)
            if time_delta_ns > 1000:
                time_delta_ns = 1000

            if time_delta_ns > 0:
                await Timer(Decimal(time_delta_ns), "ns")

            last_timestamp = timestamp
            head_driver.write(int(clock), int(data), int(latch), int(dst))
            dut.motor_phase_a.value = int(motora)
            dut.motor_phase_b.value = int(motorb)

    lines: list[NDArray[uint8]] = []
    try:
        while True:
            line = print_monitor.lines.get_nowait()
            lines.append(np.array([uint8(b) for b in line]))
    except asyncio.QueueEmpty:
        pass

    img = np.multiply(np.vstack(lines), 255, dtype=uint8)
    cv.imwrite("test.png", img)
