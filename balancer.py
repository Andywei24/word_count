import asyncio
import random
import logging
import time
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

balancer_ip = os.environ.get('BALANCER_IP', '0.0.0.0')
balancer_port = int(os.environ.get('BALANCER_PORT', 8090))
balancer_server_port = int(os.environ.get('BALANCER_SERVER_PORT', 8089))

from abc import ABC, abstractmethod

class BalancerAlgorithm(ABC):
    @abstractmethod
    def select_server(self, server_addresses, current_index, current_weight):
        pass


# Weighted Round Robin algorithm
class WeightedRoundRobinBalancer(BalancerAlgorithm):
    def _get_gcd_of_weights(self, weights):
        from math import gcd
        from functools import reduce
        return reduce(gcd, weights)

    def select_server(self, server_addresses, current_index, current_weight):
        if not server_addresses:
            return None, current_index, current_weight

        weights = [info[1] for info in server_addresses.values()]
        max_weight = max(weights)
        gcd_weight = self._get_gcd_of_weights(weights)

        while True:
            current_index = (current_index + 1) % len(server_addresses)
            if current_index == 0:
                current_weight -= gcd_weight
                if current_weight <= 0:
                    current_weight = max_weight
                if current_weight == 0:
                    continue

            server_addr = list(server_addresses.keys())[current_index]
            if server_addresses[server_addr][1] >= current_weight:
                return server_addr, current_index, current_weight

# Hash algorithm
class HashBalancer(BalancerAlgorithm):
    def select_server(self, server_addresses, request):
        if not server_addresses:
            return None

        # Hash based on client IP and port (instead of just client IP)
        client_info = request.get_extra_info('peername')
        client_ip = client_info[0]
        client_port = client_info[1]

        # Combine IP and port to create a more diverse hash key
        hash_key = f"{client_ip}:{client_port}"
        server_list = list(server_addresses.keys())
        index = hash(hash_key) % len(server_list)
        return server_list[index]



class LoadBalancer:
    def __init__(self, algorithm='weighted'):
        self.server_addresses = {}
        self.connections = {}
        self.current_weight = 0
        self.current_index = -1
        self.algorithm = None
        self.algorithm_name = algorithm
        self.set_algorithm(algorithm)

    def set_algorithm(self, algorithm):
        if algorithm == 'weighted':
            self.algorithm = WeightedRoundRobinBalancer()
        elif algorithm == 'hash':
            self.algorithm = HashBalancer()
        else:
            raise ValueError("Unknown load balancing algorithm")
        self.algorithm_name = algorithm

    async def create_connection(self, server_addr):
        host, port = server_addr
        reader, writer = await asyncio.open_connection(host, port)
        return reader, writer

    async def get_connection(self, server_addr):
        if server_addr not in self.connections or self.connections[server_addr][1].is_closing():
            reader, writer = await self.create_connection(server_addr)
            self.connections[server_addr] = (reader, writer)
        return self.connections[server_addr]

    def _select_server(self, request):
        if isinstance(self.algorithm, WeightedRoundRobinBalancer):
            server_addr, self.current_index, self.current_weight = self.algorithm.select_server(
                self.server_addresses, self.current_index, self.current_weight)
            logger.info(
                f"[Balancer] Selected server: {server_addr} with weight: {self.server_addresses[server_addr][1]} using algorithm: {self.algorithm_name}")
            return server_addr
        elif isinstance(self.algorithm, HashBalancer):
            server_addr = self.algorithm.select_server(self.server_addresses, request)
            logger.info(f"[Balancer] Selected server: {server_addr} using algorithm: {self.algorithm_name}")
            return server_addr
        else:
            return None

    async def handle_client(self, reader, writer):
        client_addr = writer.get_extra_info('peername')

        # show selected algorithm
        logger.info(f"[Balancer] Using algorithm: {self.algorithm_name} for client {client_addr}")

        selected_server = self._select_server(writer)

        # only take address part
        if isinstance(selected_server, tuple) and len(selected_server) > 2:
            server_addr = selected_server[0]
        else:
            server_addr = selected_server

        if not server_addr:
            logger.error(f"[Balancer] No available servers to handle client {client_addr}")
            writer.close()
            await writer.wait_closed()
            return

        try:
            server_reader, server_writer = await self.get_connection(server_addr)
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                server_writer.write(data)
                await server_writer.drain()

                response = await server_reader.read(1024)
                if not response:
                    break
                writer.write(response)
                await writer.drain()
                logger.info(f"[Balancer] Forward: Client {client_addr} to Server {server_addr}")
        except Exception as e:
            logger.error(f"[Balancer] Error in Balancer: {e}", exc_info=True)
        finally:
            writer.close()
            await writer.wait_closed()

            if server_addr in self.connections:
                server_writer.close()
                await server_writer.wait_closed()
                del self.connections[server_addr]
            logger.info(f"[Balancer] Disconnected with Client {client_addr} and Server {server_addr}")

    async def handle_heartbeat(self, reader, writer):
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                message = data.decode().strip()
                if message.startswith("!HEARTBEAT!"):
                    _, host, port, weight = message.split(',')
                    server_addr = (host, int(port))

                    # WRR algorithm show weight
                    if self.algorithm_name == 'weighted':
                        self.server_addresses[server_addr] = [time.time(), int(weight)]
                        logger.info(f"[Balancer] Received heartbeat from {server_addr} with weight {weight}")
                    else:
                        # don't show weight when using hash algorithm
                        self.server_addresses[server_addr] = [time.time(), None]
                        logger.info(
                            f"[Balancer] Received heartbeat from {server_addr} ")
        except Exception as e:
            logger.error(f"[Balancer] Error in handle_heartbeat: {e}")
        finally:
            server_addr = writer.get_extra_info('peername')
            writer.close()
            await writer.wait_closed()
            # logger.info(f"[Balancer] Heartbeat closed with {server_addr}")

    async def clean_inactive_servers(self):
        while True:
            if not self.server_addresses:
                logger.info(f"[Balancer] No active servers...")
            current_time = time.time()
            inactive_servers = [addr for addr, last_time in self.server_addresses.items() if
                                current_time - last_time[0] > 3]
            for addr in inactive_servers:
                del self.server_addresses[addr]
                logger.info(f"[Balancer] Removed inactive server: {addr}")
            await asyncio.sleep(2)

    async def run(self):
        client_server = await asyncio.start_server(self.handle_client, balancer_ip, balancer_port)
        heartbeat_server = await asyncio.start_server(self.handle_heartbeat, balancer_ip, balancer_server_port)
        logger.info(f"[Balancer] Load balancer running on {balancer_ip}:{balancer_port}")

        asyncio.create_task(self.clean_inactive_servers())

        async with client_server, heartbeat_server:
            await asyncio.gather(client_server.serve_forever(), heartbeat_server.serve_forever())


if __name__ == "__main__":
    algorithm = os.environ.get('BALANCER_ALGORITHM', 'weighted') # weighted or hash
    load_balancer = LoadBalancer(algorithm=algorithm)
    asyncio.run(load_balancer.run())
