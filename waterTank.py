#!/usr/bin/env python3
"""Pymodbus asynchronous Server with updating task Example.

An example of an asynchronous server and
a task that runs continuously alongside the server and updates values.

usage::

    server_updating.py [-h] [--comm {tcp,udp,serial,tls}]
                       [--framer {ascii,rtu,socket,tls}]
                       [--log {critical,error,warning,info,debug}]
                       [--port PORT] [--store {sequential,sparse,factory,none}]
                       [--slaves SLAVES]

    -h, --help
        show this help message and exit
    -c, --comm {tcp,udp,serial,tls}
        set communication, default is tcp
    -f, --framer {ascii,rtu,socket,tls}
        set framer, default depends on --comm
    -l, --log {critical,error,warning,info,debug}
        set log level, default is info
    -p, --port PORT
        set port
        set serial device baud rate
    --store {sequential,sparse,factory,none}
        set datastore type
    --slaves SLAVES
        set number of slaves to respond to

The corresponding client can be started as:
    python3 client_sync.py
"""
import asyncio
import logging
import sys
import os
import pdb
import random
import json
import pymodbus
from tank_state import *

try:
    import server_async
except ImportError:
    print("*** ERROR --> THIS EXAMPLE needs the example directory, please see \n\
          https://pymodbus.readthedocs.io/en/latest/source/examples.html\n\
          for more information.")
    sys.exit(-1)

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)

_logger = logging.getLogger(__name__)

dtDict = {}
# tankState = {}
argFile = ""
slave_id = 0x00

# global for acess by both setup and update
rd_reg_cnt = 2             # number of input registers used, CHANGED FOR PROJECT
rd_output_coil_cnt = 1      # number of output coils used, CHANGED FOR PROJECT
rd_direct_input_cnt = 1      # number of direct inputs

rd_output_coil_address = 0
rd_direct_input_address = rd_output_coil_address+rd_output_coil_cnt + 1
# rd_direct_input_address = 0
rd_reg_address = rd_direct_input_address+rd_direct_input_cnt+1

# 'input' parameters
update = 1.0            # number of seconds @ tank update
port = 5020             # TCP over which 
pH = 7                  # pH level of the water, added for the project
hcl = 0                 # State of hcl release. 0 = off, 1 = on 
global inputRate, dilutionRate, tankState
inputRate = 0
dilutionRate = 0 
tankState = TankStateClass()

updates = 0
def initDT(dtDict):
    global inputRate, dilutionRate
    global port, update
    global pH
    global tankState

    print(dtDict)

    if 'inputRate' in dtDict:
        inputRate = dtDict['inputRate'] # Rate of HCl entering tank

    assert inputRate > 0.0, "inputRate should be positive"

    if 'dilutionRate' in dtDict:
        dilutionRate = dtDict['dilutionRate'] # Rate of water entering tank

    assert dilutionRate > 0.0, "dilutionRate should be positive"

    print("inputRate {}, dilutionRate {}".format(inputRate, dilutionRate))

    if updates==0 and 'port' in dtDict:
        port = dtDict['port']

    assert port==502 or 5000 < port < 10000, "port should either be 502 or in (5000,10000)"

    if 'update' in dtDict:
        update = dtDict['update']

    assert 0.0 < update < 10.0, "update should be positive and less than 10 seconds"

    # ADDITIONS FOR THE PROJECT
    if 'pH' in dtDict:
        pH = dtDict['pH']
    
    assert 0 <= pH <= 14, "water pH should be in [0, 14]"

    if 'HCl' in dtDict:
        hcl = dtDict['HCl']

    assert hcl == 0 or hcl == 1, "hcl pump can either be 0 or 1"

    tankState.set_h_concentration(dtDict['hConcentration'])
    tankState.set_hcl_concentration(dtDict['hclConcentration'])

    print("TESTING " + str(tankState.get_concentrations()))

    # define arrays to hold the output coils, direct inputs, and input registers 
    '''
        coils[0] is control to INPUT
        coils[1] is control to OUTPUT
        coils[2] is control to HCL
        coils[3] is control to NAHSO3
        inputs[0] is state of BRB
        inputs[1] is state of drain button
        inputs[2] is state of 'high' sensor
        inputs[3] is state of 'low' sensor
        registers[0] is state of water level in tank
        registers[1] is state of water pH in tank
    '''

    print(dtDict)




def update_inputs(context):
    global inputRate, dilutionRate, tankState

    print("Starting update_inputs")
    
    with open(argFile,'r') as rf:
        dtDict = json.load(rf)

    print("Finished json load")

    if 'inputRate' in dtDict:
        inputRate = dtDict['inputRate'] # Rate of HCl entering tank

    assert inputRate > 0.0, "inputRate should be positive"

    if 'dilutionRate' in dtDict:
        dilutionRate = dtDict['dilutionRate'] # Rate of water entering tank

    assert dilutionRate > 0.0, "dilutionRate should be positive"

    if 'HCl' in dtDict:
        hcl = dtDict['HCl'] # Toggle if HCL is entering system

    assert hcl == 0 or hcl == 1, "hcl pump can either be 0 or 1"
    print("Finished hcl")


    tankState.set_hcl_input(1 if hcl else 0)

    print("Finished update_inputs")

def update_tank_state(context):
    global inputRate, dilutionRate, tankState

    update_inputs(context)

    print("Starting update_tank_state")
    print("TESTING " + str(tankState.get_concentrations()))

    print("inputRate {}, dilutionRate {}".format(inputRate, dilutionRate))
    
    tankState.update_state(inputRate, dilutionRate)
    # tankState.update_state()
    print(tankState.get_concentrations())


    # if tankState['inputs'][inputMap['HCL']]:
    #     tankState['registers'][registerMap['HCL-CONCENTRATION']] += inputRate

    # tankState['registers'][registerMap['H-CONCENTRATION']] += dissociationRate * tankState['registers'][registerMap['HCL-CONCENTRATION']]
    # tankState['registers'][registerMap['HCL-CONCENTRATION']]  = (1 - dissociationRate) * tankState['registers'][registerMap['HCL-CONCENTRATION']]

    # tankState['registers'][registerMap['HCL-CONCENTRATION']] = (1 - dilutionRate) * tankState['registers'][registerMap['HCL-CONCENTRATION']]

    print("Finished update_tank_state")


async def updating_task(context):
    global tankState
    """Update values in server.

    This task runs continuously beside the server
    It will increment some values each update

    It should be noted that getValues and setValues are not safe
    against concurrent use.
    """
    rd_reg_as_hex = 0x03 
    rd_output_coil_as_hex = 0x01
    rd_direct_input_as_hex = 0x02

    slave_id = 0x00

    print("Running updating_task")
    print(type(context[slave_id]))

    print("TESTING " + str(tankState.get_concentrations()))



    # set values to initial values. not sure why initial getValues is needed, but server_updating.py has it
    context[slave_id].getValues(rd_reg_as_hex, rd_reg_address, count=len(tankState.get_tank_state()['registers']))
    print("Finished getValues")
    context[slave_id].setValues(rd_reg_as_hex, rd_reg_address, tankState.get_tank_state()['registers'])
    print("Finished setValues")

    context[slave_id].getValues(rd_output_coil_as_hex, rd_output_coil_address, count=len(tankState.get_tank_state()['coils']))
    context[slave_id].setValues(rd_output_coil_as_hex, rd_output_coil_address, tankState.get_tank_state()['coils'])

    context[slave_id].getValues(rd_direct_input_as_hex, rd_direct_input_address, count=len(tankState.get_tank_state()['inputs']))
    context[slave_id].setValues(rd_direct_input_as_hex, rd_direct_input_address, tankState.get_tank_state()['inputs'])


    # incrementing loop
    while True:

        print("Starting sleep")
        await asyncio.sleep(update)
        print("Finished sleep")

        update_tank_state(context)
        print(tankState.get_tank_state()['registers'])

        # fetch the coil and direct inputs from the data store
        coil_values  = context[slave_id].getValues(rd_output_coil_as_hex, rd_output_coil_address, count=len(tankState.get_tank_state()['coils']))
        print("coil values", coil_values)

        input_values = context[slave_id].getValues(rd_direct_input_as_hex, rd_direct_input_address, count=len(tankState.get_tank_state()['inputs']))

        # make the input_values reflect what is in tankState, as these are externally applied
        input_values[inputMap['HCL']] = tankState.get_tank_state()['inputs'][inputMap['HCL']]

        print("Finished setValues in updating_task")


def setup_updating_server(cmdline=None):
    """Run server setup."""
    # The datastores only respond to the addresses that are initialized
    # If you initialize a DataBlock to addresses of 0x00 to 0xFF, a request to
    # 0x100 will respond with an invalid address exception.
    # This is because many devices exhibit this kind of behavior (but not all)

    # Continuing, use a sequential block 
    datablock = ModbusSequentialDataBlock(0x00, [0]*(rd_reg_address+rd_reg_cnt))
    context = ModbusSlaveContext(di=datablock, co=datablock, hr=datablock, ir=datablock)
    context = ModbusServerContext(slaves=context, single=True)
    return server_async.setup_server(
        description="Run asynchronous server.", context=context, cmdline=cmdline
    )


async def run_updating_server(args):
    """Start updating_task concurrently with the current task."""
    print("Starting updating_task")
    task = asyncio.create_task(updating_task(args.context))
    print("Finished updating_task")
    task.set_name("example updating task")
    await server_async.run_async_server(args)  # start the server
    task.cancel()


async def main(cmdline=None):
    print("Starting setup_updating_server")
    run_args = setup_updating_server(cmdline=cmdline)
    print("Finishing setup_updating_server")
    await run_updating_server(run_args)


if __name__ == "__main__":
    # first argument is name of file where digital twin arguments reside 
    if not len(sys.argv) < 2:
        #argFile = os.path.join('/tmp', sys.argv[1])
        argFile = os.path.join('.', sys.argv[1])
        try:
            with open(argFile,'r') as rf:
                dtDict = json.load(rf)
        except:
            print("error opening argument file {}\n".format(argFile))
            exit(1)
        sys.argv.pop(1)

    initDT(dtDict)
    """Combine setup and run."""
    asyncio.run(main(), debug=True)