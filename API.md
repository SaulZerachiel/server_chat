WebSocket URL:
    ws://192.168.1.25:20200

Every message uses the following structure:
```json
{
  "action": "<string>",
  "payload": { ... }
}

Client → Server messages:

1) Identify
{
  "action": "identify",
  "payload": { "username": string }
}

2) Create room
{
  "action": "createRoom",
  "room": "<string>" # Change this, needs to be in payload
}

3) Join room
{
  "action": "joinRoom",
  "payload": { "room": string }
}

4) Send message
{
  "action": "sendMessage",
  "payload": { "message": string }
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
  "payload": {
    "reason": "<string>",
    "detail": "<optional>"
  }
}
