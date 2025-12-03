import asyncio
import websockets
import datetime

async def chat():
    uri = "ws://192.168.1.25:6789"

    id = datetime.datetime.now()
    print("Connecting to server...")
    async with websockets.connect(uri) as websocket:
        print(f"{id} Connected to server!")

        async def listen():
            while True:
                msg = await websocket.recv()
                print(f"[Server] {msg}")

        async def send():
            while True:
                # run input() in a thread so it doesn't block asyncio
                msg = await asyncio.to_thread(input)
                await websocket.send(msg)

        await asyncio.gather(listen(), send())

asyncio.run(chat())
