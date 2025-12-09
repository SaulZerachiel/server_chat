import asyncio
import websockets as ws
import json
import datetime

# Notes:
# ° variable "websocket" is a websocket connection object that represents one connected client (like an ID)
# ° List of actions: "createRoom, joinRoom, leaveRoom, sendMessage, receiveMessage, identify, rename"

connected_clients = set()
rooms = {"default": set()}
client_rooms = dict()
users = dict()

# ---------------------- Utils ----------------------

async def sendjson(websocket, obj):
    await websocket.send(json.dumps(obj))


# ---------------------- CLI ------------------------

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
                for wsock in list(connected_clients):
                    await wsock.close()
                break
            case _:
                print("Not a command.")


# ---------------------- Client Handler ------------------------

async def handle_client(websocket):
    print(f"Client connected: {websocket}")
    connected_clients.add(websocket)

    # Assign username placeholder
    users[websocket] = "User_" + str(datetime.datetime.now().timestamp())

    rooms["default"].add(websocket)
    client_rooms[websocket] = "default"
    current_room = "default"

    try:
        # First thing: send initial rooms list
        await sendjson(websocket, {"action": "roomsList", "rooms": list(rooms.keys())})

        async for raw in websocket:
            try:
                action = json.loads(raw)
            except:
                continue

            match action.get("action"):

                # ----------------------------------------
                case "identify":
                    username = action.get("payload", {}).get("username", "")
                    if username:
                        users[websocket] = username

                # ----------------------------------------
                case "roomsList":
                    await sendjson(websocket, {"action": "roomsList", "rooms": list(rooms.keys())})

                # ----------------------------------------
                case "createRoom":
                    room = action.get("room")
                    if room and room not in rooms:
                        rooms[room] = set()
                        print(f"Created room: {room}")
                        # broadcast
                        for client in connected_clients:
                            await sendjson(client, {"action": "roomsList", "rooms": list(rooms.keys())})

                # ----------------------------------------
                case "joinRoom":
                    room = action.get("room")
                    if room not in rooms:
                        await sendjson(websocket, {
                            "action": "error",
                            "message": f"Room '{room}' does not exist."
                        })
                        continue

                    rooms[current_room].remove(websocket)
                    rooms[room].add(websocket)
                    client_rooms[websocket] = room
                    current_room = room

                    await sendjson(websocket, {
                        "action": "joined",
                        "payload": {"room": room}
                    })

                # ----------------------------------------
                case "leaveRoom":
                    if current_room != "default":
                        rooms[current_room].remove(websocket)
                        rooms["default"].add(websocket)
                        client_rooms[websocket] = "default"
                        current_room = "default"

                        await sendjson(websocket, {
                            "action": "left",
                            "payload": {"room": current_room}
                        })

                # ----------------------------------------
                case "sendMessage":
                    msg = action.get("message", "")
                    if not msg:
                        continue

                    message_obj = {
                        "action": "message",
                        "payload": {
                            "from": users.get(websocket, "Unknown"),
                            "room": current_room,
                            "message": msg
                        }
                    }

                    # Send to everyone, INCLUDING the sender
                    for client in rooms[current_room]:
                        await client.send(json.dumps(message_obj))

                # ----------------------------------------
                case _:
                    print(f"Unknown action: {action}")

    finally:
        # Cleanup on disconnect
        room = client_rooms.get(websocket)

        if room:
            rooms[room].remove(websocket)

        client_rooms.pop(websocket, None)
        connected_clients.remove(websocket)
        users.pop(websocket, None)

        print("Client disconnected.")


# ---------------------- Main ------------------------

async def main():
    server = await ws.serve(handle_client, "0.0.0.0", 20200)
    print("Server running")

    await asyncio.gather(
        cli(),
        server.wait_closed()
    )

if __name__ == "__main__":
    asyncio.run(main())
