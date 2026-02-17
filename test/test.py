# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import signal
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb.triggers import ClockCycles, ValueChange
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(unit="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(unit="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, unit="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

async def get_period(signal, bit=0):
    prev = (signal.value.to_unsigned() >> bit) & 1
    
    t1 = None
    while True:
        await cocotb.triggers.ValueChange(signal)
        cur = (signal.value.to_unsigned() >> bit) & 1
        if prev == 0 and cur == 1:          # rising edge on the bit
            if t1 is None:
                t1 = cocotb.utils.get_sim_time(unit="ns")
            else:
                t2 = cocotb.utils.get_sim_time(unit="ns")
                return t2 - t1
        prev = cur

@cocotb.test()
async def test_pwm_freq(dut):
    dut._log.info("Start PWM Frequency test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, unit="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # Enable outputs and PWM
    await send_spi_transaction(dut, 1, 0x00, 0xFF)   # Enable output for uo_out
    await send_spi_transaction(dut, 1, 0x01, 0xFF)   # Enable output for uio_out
    await send_spi_transaction(dut, 1, 0x02, 0xFF)   # Enable PWM for uo_out
    await send_spi_transaction(dut, 1, 0x03, 0xFF)   # Enable PWM for uio_out
    await send_spi_transaction(dut, 1, 0x04, 0x80)  # Set PWM duty cycle to 50%

    outputs = [dut.uo_out, dut.uio_out]

    # Need to test all outputs for 3kHz with +-1% tolerance 
    for bus_name in ['uo_out', 'uio_out']:
        signal = getattr(dut, bus_name)      # packed 8-bit signal
        for bit in range(8):
            period_ns = await get_period(signal, bit)
            freq_hz = 1e9 / period_ns
            dut._log.info(f"{bus_name}[{bit}] frequency = {freq_hz:.2f} Hz")
            assert 2970 <= freq_hz <= 3030, \
                f"{bus_name}[{bit}]: expected ~3000 Hz, got {freq_hz:.2f} Hz"

    dut._log.info("PWM Frequency test completed successfully")

async def pwm_helper(signal, bit=0):
    # Wait for rising edge
    while True:
        await cocotb.triggers.ValueChange(signal)
        if ((signal.value.to_unsigned() >> bit) & 1) == 1:
            t_rise1 = cocotb.utils.get_sim_time("ns")
            break

    # Wait for falling edge
    while True:
        await cocotb.triggers.ValueChange(signal)
        if ((signal.value.to_unsigned() >> bit) & 1) == 0:
            t_fall = cocotb.utils.get_sim_time("ns")
            break

    # Wait for next rising edge
    while True:
        await cocotb.triggers.ValueChange(signal)
        if ((signal.value.to_unsigned() >> bit) & 1) == 1:
            t_rise2 = cocotb.utils.get_sim_time("ns")
            break

    period = t_rise2 - t_rise1
    high_time = t_fall - t_rise1

    return period, high_time

@cocotb.test()
async def test_pwm_duty(dut):
    dut._log.info("Start PWM Duty Cycles test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, unit="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    #Enable Outputs and PWM
    await send_spi_transaction(dut, 1, 0x00, 0xFF)   # Enable output for uo_out
    await send_spi_transaction(dut, 1, 0x01, 0xFF)   # Enable output for uio_out
    await send_spi_transaction(dut, 1, 0x02, 0xFF)   # Enable PWM for uo_out
    await send_spi_transaction(dut, 1, 0x03, 0xFF)   # Enable PWM for uio_out

    # Test duty cycles of 0%, 50%, and 100%
    duty_cycles = [0x00, 0x80, 0xFF]

    for duty in duty_cycles:
        await send_spi_transaction(dut, 1, 0x04, duty)      # Set PWM duty cycle
        await ClockCycles(dut.clk, 30000)                   # Wait for the signal to stabilize

        for bus_name in ['uo_out', 'uio_out']:
            signal = getattr(dut, bus_name)

            for bit in range(8):
                bit_val = (signal.value.to_unsigned() >> bit) & 1

                if duty == 0x00:
                    assert bit_val == 0, f"{bus_name}[{bit}] expected 0%"
                    continue

                if duty == 0xFF:
                    assert bit_val == 1, f"{bus_name}[{bit}] expected 100%"
                    continue

                period, high_time = await pwm_helper(signal, bit)

                actual_duty = high_time / period * 100
                expected_duty = duty / 255 * 100

                assert abs(actual_duty - expected_duty) <= 1, \
                    f"{bus_name}[{bit}] expected {expected_duty:.2f}%, got {actual_duty:.2f}%"


    dut._log.info("PWM Duty Cycle test completed successfully")
