import asyncio
import os
import logging
import json
import redis
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

downloads_dir = '/wordCount/downloads/'

file_semaphore = asyncio.Semaphore(20)

# Redis connection setup
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)

server_host = os.environ.get('SERVER_HOST', '0.0.0.0')
server_port = int(os.environ.get('SERVER_PORT', 8091))
balancer_host = os.environ.get('BALANCER_HOST', 'balancer')
balancer_port = int(os.environ.get('BALANCER_PORT', 8089))


async def count_word_in_file(file_name, target):
    async with file_semaphore:
        try:
            # Check Redis cache first
            cache_key = f"{file_name}:{target}"
            cached_result = redis_client.get(cache_key)
            if cached_result:
                logger.info(f"[Server] Cache hit for {cache_key}")
                redis_client.zincrby('word_count', 1, target)
                return json.loads(cached_result)  # Return cached result

            # If no cache, calculate the word count
            result = await asyncio.to_thread(_count, file_name, target)
            # Store the result in Redis cache with an expiry (e.g., 10 minutes)
            redis_client.setex(cache_key, 600, json.dumps(result))
            redis_client.zincrby('word_count', 1, target)

            return result
        except Exception as e:
            logger.error(f"[Server] Error with file {file_name}, {e}")
            return {
                'file': file_name,
                'word': target,
                'count': -1,
                'error': str(e)
            }


def _count(file_name, target):
    file_path = os.path.join(downloads_dir, file_name)
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        words = content.split()
        cnt = sum(1 for word in words if word == target)
        return {
            'file': file_name,
            'word': target,
            'count': cnt
        }


async def heartbeat(balancer_host, balancer_port, server_host, server_port):
    while True:
        weight = await calculate_dynamic_weight()
        # logger.info(f"[Server] Current calculated weight: {weight}")

        try:
            _, writer = await asyncio.open_connection(balancer_host, balancer_port)
            # logger.info(f"[Server] Established heartbeat connection to balancer at {balancer_host}:{balancer_port}")

            message = f"!HEARTBEAT!,{server_host},{server_port},{weight}\n"
            writer.write(message.encode())
            await writer.drain()
            logger.debug(f"[Server] Sent heartbeat: {message.strip()}")
            await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("[Server] Heartbeat task was cancelled")
            break
        except Exception as e:
            logger.error(f"[Server] Error in heartbeat connection: {e}", exc_info=True)
            logger.info("[Server] Attempting to reconnect in 5 seconds...")
            await asyncio.sleep(5)
        finally:
            if 'writer' in locals() and not writer.is_closing():
                writer.close()
                await writer.wait_closed()


async def calculate_dynamic_weight():
    return random.randint(1, 5)  # Example: return a random weight between 1 and 5


async def handle_client(reader, writer):
    client_addr = writer.get_extra_info('peername')
    try:
        while True:
            data = await reader.readuntil(b'\n')
            if not data:
                break
            message = data.decode().strip()
            logger.info(f"[Server] Received from {client_addr}: {message!r}")
            res = ""
            if message == '0':
                res = ','.join(os.listdir(downloads_dir))
            else:
                filename, word = message.split(',')
                res = await count_word_in_file(filename, word)
                res = json.dumps(res)
            writer.write(f"{res}\n".encode())
            await writer.drain()
            logger.info(f"[Server] Sent to {client_addr}: {res!r}")
    except asyncio.IncompleteReadError:
        logger.info(f"[Server] Client {client_addr} disconnected")
    except Exception as e:
        logger.error(f"[Server] Error occurs: {e}")
    logger.info(f"[Server] Connection ended for {client_addr}")




async def main():
    server = await asyncio.start_server(
        handle_client, server_host, server_port
    )
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f"[Server] Run a server on: {addrs}")

    heartbeat_task = asyncio.create_task(heartbeat(balancer_host, balancer_port, server_host, server_port))

    try:
        async with server:
            await server.serve_forever()
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


if __name__ == '__main__':
    asyncio.run(main())
