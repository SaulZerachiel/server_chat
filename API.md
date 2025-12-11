# WebSocket Chat API Documentation

**Server**: `ws://HOST_IP:20200`

---

## Client → Server Messages

### 1) Identify
Sent when connecting to the server.
```json
{
  "action": "identify",
  "payload": {
    "username": "string"
  }
}
```

### 2) Create Room
Create a new chat room.
```json
{
  "action": "createRoom",
  "payload": {
    "room": "string"
  }
}
```

### 3) Join Room
Join an existing room (can be in multiple rooms simultaneously).
```json
{
  "action": "joinRoom",
  "payload": {
    "room": "string"
  }
}
```

### 4) Leave Room
Leave a specific room (stays in other joined rooms).
```json
{
  "action": "leaveRoom",
  "payload": {
    "room": "string"
  }
}
```

### 5) Send Message
Send a message to a specific room.
```json
{
  "action": "sendMessage",
  "payload": {
    "message": "string",
    "room": "string"
  }
}
```

### 6) Delete Room
Delete a room (admin only or creator).
```json
{
  "action": "deleteRoom",
  "payload": {
    "room": "string"
  }
}
```

### 7) Rename User
Change your username.
```json
{
  "action": "rename",
  "payload": {
    "newUsername": "string"
  }
}
```

---

## Server → Client Messages

### 1) Rooms List
Broadcast list of all rooms with user counts.
```json
{
  "action": "roomsList",
  "payload": {
    "rooms": {
      "room_name_1": 3,
      "room_name_2": 1,
      "default": 5
    }
  }
}
```

### 2) Joined
Confirmation that user joined a room.
```json
{
  "action": "joined",
  "payload": {
    "room": "string"
  }
}
```

### 3) Chat Message
A message sent in a room.
```json
{
  "action": "message",
  "payload": {
    "from": "string",
    "room": "string",
    "message": "string"
  }
}
```

### 4) Left
Confirmation that user left a room.
```json
{
  "action": "left",
  "payload": {
    "room": "string"
  }
}
```

### 5) Error
Error response.
```json
{
  "action": "error",
  "payload": {
    "reason": "string",
    "detail": "string"
  }
}
```

---

## Features

- **Multi-room Support**: Users can join and stay in multiple rooms simultaneously
- **View Without Join**: Click a room to view chat history without joining
- **Message Persistence**: Messages are stored per room in client memory (session-based)
- **User Counts**: Real-time tracking of users per room
- **Emoji Picker**: Built-in emoji selector for messages
- **Username Changes**: Change username at any time
- **Room Management**: Create, join, leave, and delete rooms

---

## Architecture

- **Server**: Async WebSocket server (Python asyncio + websockets)
- **Client**: Threaded Tkinter GUI (customtkinter) with async network thread
- **Communication**: JSON-based protocol over WebSocket
- **Port**: 20200 (default)
