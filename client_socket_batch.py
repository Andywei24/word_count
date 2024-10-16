import asyncio
import logging
import random
import json
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

balancer_host = os.environ.get('BALANCER_HOST', 'localhost')

clients_num = 20 # numbers of clients that send req simultaneously
req_per_client = 2 # numbers of req that each client send synchronously

words_list = ["the", "a", "you", "I", "he", "she"]

class Client:
    def __init__(self, client_id) -> None:
        self.words_list = words_list
        self.files_list = []
        self.client_id = client_id
        self.reader = None
        self.writer = None
    
    async def connect(self):
        self.reader, self.writer = \
            await asyncio.open_connection(balancer_host, 8090)

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()
    
    async def send_request(self, message):
        self.writer.write(f"{message}\n".encode())
        await self.writer.drain()
        data = await self.reader.read(1024)
        return data
    
    async def files_req(self):
        try:
            message = '0'
            data = await self.send_request(message)
            self.files_list = data.decode().split(',')
        except Exception as e:
            logger.error(f"[Client] Error occurs in files_req: {e}")

    async def count_req(self, req_id):
        try:
            self.req_id = req_id
            message = f"{random.choice(self.files_list).strip()},{random.choice(self.words_list).strip()}"
            logger.info(f"[Client] Client {self.client_id} - Req {self.req_id} - Send: {message}")

            data = await self.send_request(message)

            data = json.loads(data.decode())
            logger.info(f"[Client] Client {self.client_id} - Req {self.req_id} - Receive answer: {data}")
        except Exception as e:
            logger.error(f"[Client] error occurs in count_req: {e}")

async def run_client(client_id):
    client = Client(client_id)
    try:
        await client.connect()
        await client.files_req()

        # requests 1 by 1 for each client
        for i in range(req_per_client):
            await client.count_req(i)
    finally:
        await client.close()

async def main():
    tasks = [run_client(i) for i in range(clients_num)]

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
