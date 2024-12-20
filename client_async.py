#!/usr/bin/env python3
"""Pymodbus asynchronous client example.

usage::

    client_async.py [-h] [-c {tcp,udp,serial,tls}]
                    [-f {ascii,rtu,socket,tls}]
                    [-l {critical,error,warning,info,debug}] [-p PORT]
                    [--baudrate BAUDRATE] [--host HOST]

    -h, --help
        show this help message and exit
    -c, -comm {tcp,udp,serial,tls}
        set communication, default is tcp
    -f, --framer {ascii,rtu,socket,tls}
        set framer, default depends on --comm
    -l, --log {critical,error,warning,info,debug}
        set log level, default is info
    -p, --port PORT
        set port
    --baudrate BAUDRATE
        set serial device baud rate
    --host HOST
        set host, default is 127.0.0.1

The corresponding server must be started before e.g. as:
    python3 server_sync.py
"""
import asyncio
import logging
import sys
import pdb
import os
import json
import time
import csv
import math
from tank_state import *
from detector import *

try:
    import helper
except ImportError:
    print("*** ERROR --> THIS EXAMPLE needs the example directory, please see \n\
          https://pymodbus.readthedocs.io/en/latest/source/examples.html\n\
          for more information.")
    sys.exit(-1)

import pymodbus.client as modbusClient
from pymodbus import ModbusException


global dtDict
global argFile, inputRate, dilutionRate, update
global delta

_logger = logging.getLogger(__file__)
logging.basicConfig(filename='logs/async_client.log', level=logging.DEBUG)
_logger.setLevel("DEBUG")




def setup_async_client(description=None, cmdline=None):
    global dtDict, argFile, delta
    """Run client setup."""
    args = helper.get_commandline(
        server=False, description=description, cmdline=cmdline
    )

    if args.file != None:
        argFile = os.path.join('.', args.file)
        try:
            with open(argFile,'r') as rf:
                dtDict = json.load(rf)
        except:
            print("error opening argument file {}\n".format(argFile))
            exit(1)

    _logger.info("### Create client object")
    client = None

    delta = args.delta

    if args.comm == "tcp":
        client = modbusClient.AsyncModbusTcpClient(
            args.host,
            port=args.port,  # on which port
            # Common optional parameters:
            framer=args.framer,
            timeout=args.timeout,
            retries=3,
            reconnect_delay=1,
            reconnect_delay_max=10,
            #    source_address=("localhost", 0),
        )
    elif args.comm == "udp":
        client = modbusClient.AsyncModbusUdpClient(
            args.host,
            port=args.port,
            # Common optional parameters:
            framer=args.framer,
            timeout=args.timeout,
            #    retries=3,
            # UDP setup parameters
            #    source_address=None,
        )
    elif args.comm == "serial":
        client = modbusClient.AsyncModbusSerialClient(
            args.port,
            # Common optional parameters:
            #    framer=ModbusRtuFramer,
            timeout=args.timeout,
            #    retries=3,
            # Serial setup parameters
            baudrate=args.baudrate,
            #    bytesize=8,
            #    parity="N",
            #    stopbits=1,
            #    handle_local_echo=False,
        )
    elif args.comm == "tls":
        client = modbusClient.AsyncModbusTlsClient(
            args.host,
            port=args.port,
            # Common optional parameters:
            framer=args.framer,
            timeout=args.timeout,
            #    retries=3,
            # TLS setup parameters
            sslctx=modbusClient.AsyncModbusTlsClient.generate_ssl(
                certfile=helper.get_certificate("crt"),
                keyfile=helper.get_certificate("key"),
            #    password="none",
            ),
        )
    else:
        raise RuntimeError(f"Unknown commtype {args.comm}")
    return client


async def run_async_client(client, modbus_calls=None):
    """Run sync client."""
    _logger.info("### Client starting")
    await client.connect()
    assert client.connected
    if modbus_calls:
        await modbus_calls(client)
    client.close()
    _logger.info("### End of Program")


def update_inputs():
    global dtDict, argFile, inputRate, dilutionRate, update

    with open(argFile,'r') as rf:
        dtDict = json.load(rf)


    if 'inputRate' in dtDict:
        inputRate = dtDict['inputRate'] # Rate of HCl entering tank

    assert inputRate > 0.0, "inputRate should be positive"

    if 'dilutionRate' in dtDict:
        dilutionRate = dtDict['dilutionRate'] # Rate of water entering tank

    assert dilutionRate > 0.0, "dilutionRate should be positive"

    if 'update' in dtDict:
        update = dtDict['update']

    assert 0.0 < update < 10.0, "update should be positive and less than 10 seconds"


async def run_a_few_calls(client):
    global dtDict, argFile, inputRate, dilutionRate, update, delta

    statelessDetector = StatelessDetector(threshold = 2000)
    statefulDetector = StatefulDetector(threshold = 2000)

    statefulDetector.set_delta(delta)

    """Test connection works."""
    try:
        guard = False
        prev_level = 0
        inputGuessRate = 0
        outputGuessRate = 0
        avg_flow_out = 0
        count = 3
        set_coil_bool = False

        hConcentrationThresholdHigh = 11220.2 # this should be roughly a pH of 6.95
        hConcentrationThresholdLow = 8912.5 # pH of 7.05
        curCoilState = True


        rr = await client.read_coils(0, 1, slave=1)
        output_coils = rr.bits
        print(output_coils[0])

        rr = await client.read_discrete_inputs(2, 1, slave=1)
        discrete_inputs = rr.bits
        print(discrete_inputs[0])

        rr = await client.read_holding_registers(4, 2, slave=1)
        registers = rr.registers
        prev_registers = registers
        print("Registers {}".format(registers))

        tankState = TankStateClass()
        tankState.set_client_cmd_coil(output_coils[0])
        tankState.set_hcl_input(discrete_inputs[0])
        tankState.set_h_concentration(registers[0])
        tankState.set_hcl_concentration(registers[1])

        print(tankState.get_tank_state())
        update_inputs()

        while True:
            await asyncio.sleep(update * 10)

            rr = await client.read_holding_registers(4, 2, slave=1)
            registers = rr.registers
            # if registers == prev_registers:
            #     continue

            rr = await client.read_coils(0, 1, slave=1)
            output_coil = rr.bits[0]
            # print(output_coils[0])

            tankState.set_client_cmd_coil(output_coil)
            # curCoilState = output_coil

            rr = await client.read_discrete_inputs(2, 1, slave=1)
            discrete_inputs = rr.bits
            # print(discrete_inputs[0])


            print("Tank State      {}".format(registers))

            
            current_time = time.time()
            conc = (registers[0] / (10**11))
            pH_value = -math.log10(conc)

            tankState.update_state(inputRate, dilutionRate, update)
            predicted_reg = tankState.get_concentrations()
            print("Predicted State {}".format(predicted_reg))
            print("")

            #Stateless detection
            if statelessDetector.detect(registers[0], predicted_reg[0]):
                print("ALERT: Stateless detector")

            #Stateful detection
            if statefulDetector.detect(registers[0], predicted_reg[0]):
                print("ALERT: Stateful detector: {}".format(statefulDetector.get_deviation()))
                with open("data.txt", "a") as file:
                    file.write("Delta: {}, Deviation: {}\n".format(statefulDetector.get_delta(), statefulDetector.get_deviation()))
                sys.exit()


            # Get current state of the system from the coils and registers

            if registers[0] > hConcentrationThresholdHigh:
                # curCoilState = False
                await client.write_coil(0, False, slave=1)
                print("Turning coil off")
                # tankState.set_client_cmd_coil(curCoilState)
            elif registers[0] < hConcentrationThresholdLow:
                # curCoilState = True
                await client.write_coil(0, True, slave=1)
                print("Turning coil on")
                # tankState.set_client_cmd_coil(curCoilState)
            
            pump_state = tankState.get_tank_state()['inputs'][0]
            with open("data/ph_data.csv", mode='a', newline='') as f:
                ph_writer = csv.writer(f)
                ph_writer.writerow([current_time, pH_value,pump_state])
            prev_registers = registers

    except ModbusException:
        pass


async def main(cmdline=None):
    """Combine setup and run."""
    testclient = setup_async_client(description="Run client.", cmdline=cmdline)
    await run_async_client(testclient, modbus_calls=run_a_few_calls)



if __name__ == "__main__":
    with open("data/ph_data.csv", mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Time (s)", "actual_pH", "HCl_pump_state"]) #csv header
    asyncio.run(main(), debug=True)
