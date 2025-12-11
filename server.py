import asyncio 
import websockets as ws
import json
import datetime
import logging

# Notes:
# ° variable "websocket" is a websocket connection object that represents one connected client (like an ID)
# ° List of actions: "createRoom, joinRoom, leaveRoom, sendMessage, receiveMessage, identify, rename"

connected_clients = set()   # Build unordered object of unique elements
rooms = {"default":set()}   # Default room has clients in room,
                            # when a client sends a message all other clients in same room receive that message
client_rooms = dict()
users = dict()

# Setup logging
logging.basicConfig(
    filename="server.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s: %(message)s"
)

# Overwrite previous logs
with open("server.log", "w+"):
    pass

# Get IP-address
def getIPAddress():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ipaddress = s.getsockname()[0]
    s.close()
    return ipaddress

ipaddress = getIPAddress()
print(ipaddress)

# CLI
async def cli(server):
    while True:
        cmd = await asyncio.get_event_loop().run_in_executor(None, input, "> ")

        match cmd:
            case "rooms":
                print(f"Rooms: {rooms.keys()}")
            case "clients":
                print(f"Connected clients: {connected_clients}, count: {len(connected_clients)}")
            case "quit" | "exit":
                print(f"Shutting down server...")
                # Close client connections
                for client in list(connected_clients):
                    await client.close()
                # Close server
                server.close()
                await server.wait_closed()
                break
            case _:
                print("Not a command.")

# Converts python object to json text
# And send json object to specific client
async def sendjson(websocket, obj):
    await websocket.send(json.dumps(obj))

# This function is called each time a new client connects
async def handle_client(websocket):
    # Send the IP-address of the server to the client
    # await sendjson(websocket, {"action": "getIP", "IP": ipaddress})

    # Register the new client
    logging.info(f"Client connected: {websocket}")
    connected_clients.add(websocket)
    logging.info(f"Connected clients: {len(connected_clients)}")
    
    # Give random username to client
    users[websocket] = "User_" + str(datetime.datetime.now().timestamp())
    logging.info(f"User: {users[websocket]}")

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
                    room = action.get("room")
                    if room and room not in rooms:
                        rooms[room] = set()
                        logging.info(f"Created room: {action['room']}")
                        # Broadcast 
                        for client in connected_clients:
                            await sendjson(client, {"action": "roomsList", "rooms": list(rooms.keys())})

                case "joinRoom":
                    # Join room
                    room = action.get("room")
                    if room not in rooms:
                        await sendjson(websocket, {"action": "error", "message": f"Room '{room}' does not exist."}) 
                        continue

                    rooms[current_room].remove(websocket)
                    rooms[room].add(websocket)

                    client_rooms[websocket] = room
                    current_room = room

                    await sendjson(websocket, {
                        "action": "joined",
                        "payload": {"room": room}
                    })

                case "leaveRoom":
                    # Leave current room and join default room
                    if current_room != "default":
                        rooms[current_room].remove(websocket)
                        rooms["default"].add(websocket)
                        client_rooms[websocket] = "default"
                        current_room = "default"
                        logging.info("Client left room and joined default.")

                    await sendjson(websocket, {
                        "action": "left",
                        "payload": {"room": current_room} 
                    })

                case "deleteRoom":
                    # Delete room if it exists and client has permission
                    room = action.get("room")
                    if room == "default":
                        await sendjson(websocket, {"action": "error", "reason": "cannot_delete_default", "detail": "Cannot delete the default room."})
                        continue
                    
                    if room and room in rooms:
                        # Move all clients in room to default
                        for client in list(rooms[room]):
                            rooms["default"].add(client)
                            client_rooms[client] = "default"
                            await sendjson(client, {
                                "action": "left",
                                "payload": {"room": room}
                            })
                        
                        # Delete the room
                        del rooms[room]
                        logging.info(f"Room deleted: {room}")
                        
                        # Broadcast updated room list to all clients
                        for client in connected_clients:
                            await sendjson(client, {"action": "roomsList", "rooms": list(rooms.keys())})
                    else:
                        await sendjson(websocket, {"action": "error", "reason": "room_not_found", "detail": f"Room '{room}' does not exist."})

                case "sendMessage":
                    msg = action.get("message")
                    if not msg:
                        continue # Ignore empty messages

                    # Broadcast message to everyone in the client's current_room
                    message_obj = {
                        "action": "message",
                        "payload": {
                            "from": users.get(websocket, "Unknown"),
                            "room": current_room,
                            "message": msg
                        }
                    }
                                        
                    for client in rooms[current_room]:
                        await client.send(json.dumps(message_obj))

                case "identify":
                    # Identify user
                    username = action.get("payload", {}).get("username", "")
                    if username:
                        users[websocket] = username
                
                case "rename":
                    username = action.get("newUsername")
                    if username:
                        users[websocket] = username

                case "roomsList":
                    await sendjson(websocket, {"action": "roomsList", "rooms": list(rooms.keys())})

                case _:
                    print("Not an action...")
                    logging.error("Not an action...")

    except Exception as e:
        logging.exception(f"Error handling client: {e}")

    # If client disconnect -> async loop ends and finally block gets executed
    finally:
        # Remove client from rooms
        room = client_rooms.get(websocket)
        if room:
            rooms[room].remove(websocket)
        client_rooms.pop(websocket, None)

        # Unregister the client
        logging.warning("Client disconnected.")
        connected_clients.remove(websocket)

# Function to start the WebSocket server
async def main():                                      
    # Set up WebSocket server that listens on port 20200
    # Every time a client connects, server will handle the
    # connection using the handle_client function  
    server = await ws.serve(handle_client, "0.0.0.0", 20200)
    logging.info("Server running.")
    print("Server running.")

    await asyncio.gather(
        cli(server), # CLI
        server.wait_closed() # Websocket task
    )

if __name__ == "__main__":
    asyncio.run(main())
