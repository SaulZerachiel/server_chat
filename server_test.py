"""
WebSocket Chat Server
====================
Multi-room async WebSocket server for real-time chat application.

Features:
- Multi-room support with per-room user tracking
- Real-time room list broadcasting with user counts
- User identification and renaming
- Room creation, joining, leaving, deletion
- Message broadcasting to room members only
- Automatic user count synchronization

Protocol: JSON-based WebSocket messages
Port: 20200
"""

import asyncio 
import websockets as ws
import json
import datetime
import logging

# ==================================================================
# SERVER STATE MANAGEMENT
# ==================================================================
connected_clients = set()       # Set of all connected websocket clients
rooms = {"default": set()}      # Maps room_name -> set of clients in that room
client_rooms = dict()           # Maps websocket -> set of rooms client has joined
users = dict()                  # Maps websocket -> username
typing_users = dict()           # Maps websocket -> room (for typing indicator, future feature)

# ==================================================================
# LOGGING SETUP
# ==================================================================
logging.basicConfig(
    filename="server.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s: %(message)s"
)

# Clear previous logs
with open("server.log", "w+"):
    pass

# ==================================================================
# UTILITY FUNCTIONS
# ==================================================================
def getIPAddress():
    """Get the server's public IP address."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ipaddress = s.getsockname()[0]
    s.close()
    return ipaddress

ipaddress = getIPAddress()
print(f"Server IP: {ipaddress}")

# ==================================================================
# COMMAND LINE INTERFACE
# ==================================================================
async def cli(server):
    """
    Interactive CLI for server administration.
    
    Commands:
    - rooms: List all rooms and their user counts
    - clients: Show connected clients
    - quit/exit: Gracefully shutdown server
    """
    while True:
        cmd = await asyncio.get_event_loop().run_in_executor(None, input, "> ")

        match cmd:
            case "rooms":
                print(f"Rooms: {rooms.keys()}")
            case "clients":
                print(f"Connected clients: {connected_clients}, count: {len(connected_clients)}")
            case "quit" | "exit":
                print(f"Shutting down server...")
                # Close all client connections
                for client in list(connected_clients):
                    await client.close()
                # Shutdown server
                server.close()
                await server.wait_closed()
                break
            case _:
                print("Not a command.")

# ==================================================================
# MESSAGE SENDING & BROADCASTING
# ==================================================================
async def sendjson(websocket, obj):
    """
    Send a JSON object to a specific client.
    
    Args:
        websocket: The target client websocket
        obj: Python dict to serialize as JSON and send
    """
    await websocket.send(json.dumps(obj))

def get_rooms_with_counts():
    """
    Get all rooms with their current user counts.
    
    Returns:
        dict: Maps room_name -> user_count
    """
    rooms_data = {}
    for room_name, room_clients in rooms.items():
        rooms_data[room_name] = len(room_clients)
    return rooms_data

# ==================================================================
# CLIENT CONNECTION HANDLER
# ==================================================================
async def handle_client(websocket):
    """
    Main handler for each connected client.
    
    Manages client lifecycle:
    1. Registration and identification
    2. Message routing and broadcasting
    3. Room management (join/leave/create/delete)
    4. User presence tracking
    5. Cleanup on disconnect
    """
    # Send the IP-address of the server to the client
    # await sendjson(websocket, {"action": "getIP", "IP": ipaddress})

    # Register the new client
    logging.info(f"Client connected: {websocket}")
    connected_clients.add(websocket)
    logging.info(f"Connected clients: {len(connected_clients)}")
    
    # Assign default username (temporary, client can rename via "identify" action)
    users[websocket] = "User_" + str(datetime.datetime.now().timestamp())
    logging.info(f"User: {users[websocket]}")

    # Auto-join client to "default" room on connection
    rooms["default"].add(websocket)
    client_rooms[websocket] = set(["default"])

    try:
        # Send current room list with user counts to the new client
        await sendjson(websocket, {
            "action": "roomsList", 
            "payload": {"rooms": get_rooms_with_counts()}
        })

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
                            await sendjson(client, {"action": "roomsList", "rooms": get_rooms_with_counts()})

                case "joinRoom":
                    # Join room (multi-join supported)
                    room = action.get("room")
                    if room not in rooms:
                        await sendjson(websocket, {"action": "error", "message": f"Room '{room}' does not exist."}) 
                        continue

                    # Add the websocket to the room and track in client_rooms set
                    rooms[room].add(websocket)
                    client_rooms.setdefault(websocket, set()).add(room)

                    # Notify client that it joined
                    await sendjson(websocket, {
                        "action": "joined",
                        "payload": {"room": room}
                    })

                    # Broadcast updated room counts
                    for client in connected_clients:
                        await sendjson(client, {"action": "roomsList", "rooms": get_rooms_with_counts()})

                case "leaveRoom":
                    # Leave a specific room (expecting 'room' parameter)
                    room = action.get("room")
                    if not room:
                        await sendjson(websocket, {"action": "error", "reason": "no_room_specified", "detail": "No room specified to leave."})
                        continue

                    if room == "default":
                        await sendjson(websocket, {"action": "error", "reason": "cannot_leave_default", "detail": "Cannot leave the default room."})
                        continue

                    if room in rooms and websocket in rooms[room]:
                        rooms[room].remove(websocket)
                        # Ensure client still has default
                        client_rooms.get(websocket, set()).discard(room)
                        client_rooms.get(websocket, set()).add("default")
                        logging.info("Client left room.")

                    await sendjson(websocket, {
                        "action": "left",
                        "payload": {"room": room}
                    })

                    # Broadcast updated room counts
                    for client in connected_clients:
                        await sendjson(client, {"action": "roomsList", "rooms": get_rooms_with_counts()})

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
                            # remove the deleted room from client's set and ensure default present
                            client_rooms.get(client, set()).discard(room)
                            client_rooms.get(client, set()).add("default")
                            await sendjson(client, {
                                "action": "left",
                                "payload": {"room": room}
                            })
                        
                        # Delete the room
                        del rooms[room]
                        logging.info(f"Room deleted: {room}")
                        
                        # Broadcast updated room list to all clients
                        for client in connected_clients:
                            await sendjson(client, {"action": "roomsList", "rooms": get_rooms_with_counts()})
                    else:
                        await sendjson(websocket, {"action": "error", "reason": "room_not_found", "detail": f"Room '{room}' does not exist."})

                case "sendMessage":
                    msg = action.get("message")
                    room = action.get("room")
                    if not msg or not room:
                        continue # Ignore empty messages or missing room

                    if room not in rooms:
                        await sendjson(websocket, {"action": "error", "reason": "room_not_found", "detail": f"Room '{room}' does not exist."})
                        continue

                    # Broadcast message to everyone in the specified room
                    message_obj = {
                        "action": "message",
                        "payload": {
                            "from": users.get(websocket, "Unknown"),
                            "room": room,
                            "message": msg
                        }
                    }

                    for client in rooms[room]:
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
                    await sendjson(websocket, {"action": "roomsList", "rooms": get_rooms_with_counts()})

                case _:
                    print("Not an action...")
                    logging.error("Not an action...")

    except Exception as e:
        logging.exception(f"Error handling client: {e}")

    # If client disconnect -> async loop ends and finally block gets executed
    finally:
        # Remove client from all rooms they belonged to
        rooms_set = client_rooms.get(websocket, set())
        for r in list(rooms_set):
            try:
                rooms[r].remove(websocket)
            except Exception:
                pass
        client_rooms.pop(websocket, None)

        # Broadcast updated room counts
        for client in connected_clients:
            try:
                await sendjson(client, {"action": "roomsList", "rooms": get_rooms_with_counts()})
            except Exception:
                pass

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
