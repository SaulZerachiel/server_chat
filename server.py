import asyncio 
import websockets as ws
import json
import datetime

# Notes:
# ° variable "websocket" is a websocket connection object that represents one connected client (like an ID)
# ° List of actions: "createRoom, joinRoom, leaveRoom, sendMessage, receiveMessage, identify, rename"


connected_clients = set()   # Build unordered object of unique elements
rooms = {"default":set()}   # Default room has clients in room,
                            # when a client sends a message all other clients in same room receive that message
client_rooms = dict()
users = dict()

# CLI
async def cli():
    while True:
        cmd = await asyncio.get_event_loop().run_in_executor(None, input, "> ")

        match cmd:
            case "rooms":
                print(f"Rooms: {rooms.keys()}")
            case "clients":
                print(f"Connected clients: {connected_clients}")
            case "quit" | "exit":
                print(f"Shutting down server...")
                for ws in list(connected_clients):
                    await ws.close()
                break
            case _:
                print("Not a command.")

# Converts python object to json text
# And send json object to specific client
async def sendjson(websocket, obj):
    await websocket.send(json.dumps(obj))

# This function is called each time a new client connects
async def handle_client(websocket):
    # Register the new client
    print(f"Client connected: {websocket}")
    connected_clients.add(websocket)
    print(f"Connected clients: {connected_clients}")

    # Give random username to client
    users[websocket] = datetime.datetime.now() # TODO: change this
    print(f"User: {users[websocket]}")

    # Add client to "default" room.
    rooms["default"].add(websocket)
    client_rooms[websocket] = "default"

    # Add local variable to current room
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
                    # Join room
                    if action["room"] not in rooms:
                        await sendjson(websocket, {"action": "error", "message": f"Room '{action["room"]}' does not exist."}) 
                        continue

                    rooms[current_room].remove(websocket)
                    rooms[action["room"]].add(websocket)

                    client_rooms[websocket] = action["room"]
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

                case "identify":
                    ...
                
                case "rename":
                    ...

                case _:
                    print("Not an action...")
    
    # If client disconnect -> async loop ends and finally block gets executed
    finally:
        # Remove client from rooms
        room = client_rooms.get(websocket)
        if room:
            rooms[room].remove(websocket)
        client_rooms.pop(websocket, None)

        # Unregister the client
        print("Client disconnected.")
        connected_clients.remove(websocket)

# Function to start the WebSocket server
async def main():                                      
    # Set up WebSocket server that listens on port 6789
    # Every time a client connects, server will handle the
    # connection using the handle_client function  
    server = await ws.serve(handle_client, "0.0.0.0", 20200)
    print("Server running")

    await asyncio.gather(
        cli(), # CLI
        server.wait_closed() # Websocket task
    )

if __name__ == "__main__":
    asyncio.run(main())
