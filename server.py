import asyncio 
import websockets as ws
import json

connected_clients = set() # Build unordered object of unique elements
rooms = {"default":set()} # Default room has clients in room, when a client sends a message all other clients in same room receive that message
client_rooms = dict()

# Send json object to client
async def sendjson(websocket, obj):
    await websocket.send(json.dumps(obj))

# This function is called each time a new client connects
async def handle_client(websocket):
    # Register the new client
    print("Client connected.")
    connected_clients.add(websocket)
    
    # Add client to "default" room.
    rooms["default"].add(websocket)
    client_rooms[websocket] = "default"

    # Add local variable to track room
    current_room = "default"

    try:
        # Send initial room list to client
        await sendjson(websocket, {"action": "roomsList", "rooms": list(rooms.keys())})

        async for raw in websocket:
            action = json.loads(raw)

            # Listen to the action
            match action.get("action"):
                case "createRoom":
                    # Create room
                    if action["room"] and action["room"] not in rooms:
                        rooms[action["room"]] = set()
                        print(f"Created room: {action["room"]}")
                
                case "joinRoom":
                    # TODO: If room doesn't exist don't crash server
                    # Join room
                    if action["room"] not in rooms:
                        await sendjson(websocket, {"action": "error", "message": f"Room '{action["room"]}' does not exist."}) 
                        continue

                    rooms[current_room].remove(websocket)

                    rooms[action["room"]].add(websocket)
                    current_room = client_rooms[websocket]


                case "leaveRoom":
                    # Leave current room and join default room
                    if current_room != "default":
                        rooms[current_room].remove(websocket)
                        rooms["default"].add(websocket)
                        client_rooms[websocket] = "default"
                        current_room = "default"
                        print(f"Client left room and joined default.")

                case "sendMessage":
                    msg = action.get("message")
                    if not msg:
                        continue # Ignore empty messages

                    # Broadcast message to everyone in the client's current_room
                    message_obj = {"action": "message", "sender": str(websocket.remote_address), "message": msg, "room": current_room}
                    
                    # Create a list of send tasks, excluding the sender
                    send_tasks = [client.send(json.dumps(message_obj)) 
                                  for client in rooms[current_room] if client != websocket]
                    
                    await asyncio.gather(*send_tasks, return_exceptions=True)

                case "receiveMessage":
                    msg = action["message"] 

                case _:
                    print("Not an action...")
    
    # If client disconnect -> async loop ends and finally block gets executed
    finally:
        # Unregister the client
        print("Client disconnected.")
        connected_clients.remove(websocket)

# Function to start the WebSocket server
async def main():                                      
    async with ws.serve(handle_client,"0.0.0.0",6789) as server:      # Set up WebSocket server that listens on port 6789
        print("Server running.")
        await server.wait_closed() # Run forever                # Every time a client connects, server will handle the connection 
                                                            # using the handle_client function              

if __name__ == "__main__":
    asyncio.run(main())
