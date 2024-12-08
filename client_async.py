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
global argFile, inputRate, dilutionRate

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
    global dtDict, argFile, inputRate, dilutionRate

    with open(argFile,'r') as rf:
        dtDict = json.load(rf)

    print("Finished json load")

    if 'inputRate' in dtDict:
        inputRate = dtDict['inputRate'] # Rate of HCl entering tank

    assert inputRate > 0.0, "inputRate should be positive"

    if 'dilutionRate' in dtDict:
        dilutionRate = dtDict['dilutionRate'] # Rate of water entering tank

    assert dilutionRate > 0.0, "dilutionRate should be positive"


async def run_a_few_calls(client):
    global dtDict, argFile, inputRate, dilutionRate

    """Test connection works."""
    try:
        guard = False
        prev_level = 0
        inputGuessRate = 0
        outputGuessRate = 0
        update = 1.0
        avg_flow_out = 0

        tankState = TankStateClass()
        tankState.set_h_concentration(dtDict['hConcentration'])
        tankState.set_hcl_concentration(dtDict['hclConcentration'])

        while True:
            await asyncio.sleep(update)

            update_inputs()
            tankState.update_state(inputRate, dilutionRate)
            print(tankState.get_concentrations())

            # Get current state of the system from the coils and registers
            rr = await client.read_coils(0, 1, slave=1)
            output_coils = rr.bits
            print(output_coils[0]) 
  
            await client.write_coil(0, not output_coils[0], slave=1)

    except ModbusException:
        pass


async def main(cmdline=None):
    """Combine setup and run."""
    testclient = setup_async_client(description="Run client.", cmdline=cmdline)
    await run_async_client(testclient, modbus_calls=run_a_few_calls)



if __name__ == "__main__":

    asyncio.run(main(), debug=True)
