import asyncio 
import websockets as ws

#  
connected_clients = set()
async def handle_client(websocket, path):
    # Register the new client
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            # Broadcast the message to all connected clients
            await asyncio.wait([client.send(message)] for client in connected_clients)
    finally:
        # Unregister the client
        connected_clients.remove(websocket)

# Function to start the WebSocket server
async def main():
    server = await ws.serve(handle_client,"localhost",6789) # Set up WebSocket server that listens on port 6789
                                                            # When a client connects, server will handle the connection using handle_client function
                                                            # TODO: create static IP ?
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
