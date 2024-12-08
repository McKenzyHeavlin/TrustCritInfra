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
        print(f">> Connected to server at {self.server_host}:{self.server_port}")
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break

                # TODO: Manipulate the client data here, if desired

                print(data)

                # Forward to the server
                server_writer.write(data)
                await server_writer.drain()

                # Await the server's response
                response = await server_reader.read(1024)
                if not response:
                    break

                # TODO: Manipulate server data here, if desired

                # Write the response back to the client
                writer.write(response)
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

if __name__ == "__main__":
    proxy = MITMModbusProxy(
        MITM_PROXY_HOST, MITM_PROXY_PORT, ACTUAL_SERVER_HOST, ACTUAL_SERVER_PORT
    )
    asyncio.run(proxy.start())