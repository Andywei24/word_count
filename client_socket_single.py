import asyncio
import logging
import random
import sys
import json
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

words_list = ["the", "a", "you", "I", "he", "she"]

balancer_host = os.environ.get('BALANCER_HOST', 'localhost')

class Client:
    def __init__(self, file_arg=None, word_arg=None) -> None:
        self.words_list = words_list
        self.files_list = []
        self.file_arg = file_arg
        self.word_arg = word_arg        
    
    async def get_connection(self):
        reader, writer = await asyncio.open_connection(
            balancer_host, 8090
        )
        return reader, writer

    
    async def files_req(self, reader, writer):
        message = '0'
        writer.write(f"{message}\n".encode())
        await writer.drain()

        data = await reader.readuntil(b'\n')
        self.files_list = data.decode().strip().split(',')


    async def count_req(self, reader, writer):
        message = ""
        if not self.word_arg or not self.file_arg:
            message = random.choice(self.files_list) + ',' \
                    + random.choice(self.words_list)
        else:
            message = self.file_arg + ',' + self.word_arg
        writer.write(f"{message}\n".encode())
        await writer.drain()

        data = await reader.readuntil(b'\n')
        data = json.loads(data.decode().strip())

        logger.info(f"Receive answer: {data}")
    
    async def disconnect(self, writer):
        if not writer.is_closing():
            writer.close()
            await writer.wait_closed()
            logger.info(f"Disconnected")

async def main(file_arg, word_arg):
    client = Client(file_arg, word_arg)
    reader, writer = await client.get_connection()
    await client.files_req(reader, writer)
    await client.count_req(reader, writer)
    await client.disconnect(writer)

if __name__ == "__main__":
    file_arg = None
    word_arg = None
    if len(sys.argv) == 3:
        file_arg = sys.argv[1]
        word_arg = sys.argv[2]
    asyncio.run(main(file_arg, word_arg))
