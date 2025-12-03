import asyncio 
import websockets as ws
import json

connected_clients = set() # Build unordered object of unique elements
# This function is called each time a new client connects
async def handle_client(websocket, path):
    # Register the new client
    print("Client connected.")
    connected_clients.add(websocket)
    try:
        # Message loop, recieve messages from this client. This loop runs as long as client stays connected
        async for message in websocket:
            # Broadcast the message to all connected clients, build a list of stacks and each stack sends the message to a different connected client
            print("Message recieved")
            await asyncio.gather(*(client.send(message) for client in connected_clients), return_exceptions=True)
    # If client disconnect -> async loop ends and finally block gets executed
    finally:
        # Unregister the client
        print("Client disconnected.")
        connected_clients.remove(websocket)

# Function to start the WebSocket server
async def main():                                      
    async with ws.serve(handle_client,"0.0.0.0",6789):      # Set up WebSocket server that listens on port 6789
        print("Server running.")
        await asyncio.Future() # Run forever                # Every time a client connects, server will handle the connection 
                                                            # using the handle_client function              

if __name__ == "__main__":
    asyncio.run(main())
