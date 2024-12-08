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

_logger = logging.getLogger(__file__)
logging.basicConfig(filename='async_client.log', level=logging.DEBUG)
_logger.setLevel("DEBUG")




def setup_async_client(description=None, cmdline=None):
    global dtDict, argFile
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
    global dtDict, argFile, inputRate, dilutionRate, update

    statelessDetector = StatelessDetector(threshold = 50)
    statefulDetector = StatefulDetector(threshold = 50)

    statefulDetector.set_delta(1)

    """Test connection works."""
    try:
        guard = False
        prev_level = 0
        inputGuessRate = 0
        outputGuessRate = 0
        avg_flow_out = 0
        count = 3
        set_coil_bool = False


        rr = await client.read_coils(0, 1, slave=1)
        output_coils = rr.bits
        print(output_coils[0])

        rr = await client.read_discrete_inputs(2, 1, slave=1)
        discrete_inputs = rr.bits
        print(discrete_inputs[0])

        rr = await client.read_holding_registers(4, 2, slave=1)
        registers = rr.registers
        print("Registers {}".format(registers))

        tankState = TankStateClass()
        tankState.set_client_cmd_coil(output_coils[0])
        tankState.set_hcl_input(discrete_inputs[0])
        tankState.set_h_concentration(registers[0])
        tankState.set_hcl_concentration(registers[1])

        print(tankState.get_tank_state())
        update_inputs()

        while True:
            await asyncio.sleep(update)

            count -= 1

            rr = await client.read_coils(0, 1, slave=1)
            output_coils = rr.bits
            # print(output_coils[0])

            rr = await client.read_discrete_inputs(2, 1, slave=1)
            discrete_inputs = rr.bits
            # print(discrete_inputs[0])

            rr = await client.read_holding_registers(4, 2, slave=1)
            registers = rr.registers
            print("Tank State      {}".format(registers))

            
            tankState.update_state(inputRate, dilutionRate, update)
            predicted_reg = tankState.get_concentrations()
            print("Predicted State {}".format(predicted_reg))
            print("")

            #Stateless detection
            if statelessDetector.detect(registers[0], predicted_reg[0]):
                print("ALERT: Stateless detector")

            #Stateful detection
            if statefulDetector.detect(registers[0], predicted_reg[0]):
                print("ALERT: Stateful detector")

            # Get current state of the system from the coils and registers

            if count == 0:
                set_input = not discrete_inputs[0]
                count = 3
                await client.write_coil(0, set_input, slave=1)
                tankState.set_client_cmd_coil(set_input)
                # tankState.set_hcl_input(set_input)
            # else:
                # set_input = discrete_inputs[0]




            

    except ModbusException:
        pass


async def main(cmdline=None):
    """Combine setup and run."""
    testclient = setup_async_client(description="Run client.", cmdline=cmdline)
    await run_async_client(testclient, modbus_calls=run_a_few_calls)



if __name__ == "__main__":

    asyncio.run(main(), debug=True)
