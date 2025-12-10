WebSocket URL:
    ws://HOST_IP:20200

// TODO: Uniformity the client -> server messages and the error format. Add the payload.

Client → Server messages:

1) Identify
{
  "action": "identify",
  "payload": { "username": string }
}

2) Create room
{
  "action": "createRoom",
  "room": "<string>" // Optional, change this so it's inside the payload. Makes it more uniform.
}

3) Join room
{
  "action": "joinRoom",
  "room": "<string>"
}

4) Leave room
{
  "action": "leaveRoom",
}

5) Send message
{
  "action": "sendMessage",
  "message": "<string>"
}

6) Rename
{
  "action": "rename",
  "newUsername": "<string>" 
}

---

Server → Client messages:

1) Rooms list
{
  "action": "roomsList",
  "rooms": [string]
}

2) Joined room
{
  "action": "joined",
  "payload": { "room": string }
}

3) Chat message
{
  "action": "message",
  "payload": {
    "from": string,
    "room": string,
    "message": string
  }
}

Error format:

1) Error
{
  "action": "error",
  "message": "<string>"
}
