import asyncio 
import websockets as ws
import json
import datetime
import logging

# TODO: change logging system, maybe override old logging file so we don't get an infinite long .log file

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
                for client in list(connected_clients):
                    await client.close()
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
                        "payload": {"room": current_room} # TODO: change current_room to previous room
                    })

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

                case "receiveMessage":
                    msg = action["message"] 

                case "identify":
                    # Identify user
                    username = action.get("payload", {}).get("username", "")
                    if username:
                        users[websocket] = username
                
                case "rename":
                    ...

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
    # Set up WebSocket server that listens on port 6789
    # Every time a client connects, server will handle the
    # connection using the handle_client function  
    server = await ws.serve(handle_client, "0.0.0.0", 20200)
    logging.info("Server running.")
    print("Server running.")

    await asyncio.gather(
        cli(), # CLI
        server.wait_closed() # Websocket task
    )

if __name__ == "__main__":
    asyncio.run(main())
