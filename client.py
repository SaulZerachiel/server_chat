import asyncio
import json
import threading
import queue
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
import websockets

# ----------------------------------------
# Queues
# ----------------------------------------

out_queue = queue.Queue()
in_queue = queue.Queue()

connected = False
current_room = None

# ----------------------------------------
# Protocol Helper
# ----------------------------------------

def send_action(action, payload=None):
    if payload is None:
        payload = {}
    out_queue.put({"action": action, **payload})


# ----------------------------------------
# Async Network Loop
# ----------------------------------------

async def network_loop(uri, username):
    global connected, current_room
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
            connected = True

            # identify
            await ws.send(json.dumps({"action": "identify", "payload": {"username": username}}))

            # ask for rooms
            await ws.send(json.dumps({"action": "roomsList"}))

            async def receiver():
                async for raw in ws:
                    try:
                        obj = json.loads(raw)
                    except:
                        continue
                    in_queue.put(obj)

            recv_task = asyncio.create_task(receiver())

            try:
                while True:
                    try:
                        data = out_queue.get_nowait()
                    except queue.Empty:
                        await asyncio.sleep(0.05)
                        continue

                    await ws.send(json.dumps(data))

            except websockets.ConnectionClosed:
                pass

            finally:
                recv_task.cancel()

    except Exception as e:
        in_queue.put({"action": "error", "payload": {"reason": "unable_to_connect", "detail": str(e)}})

    finally:
        connected = False
        current_room = None


def start_network_thread(host, port, username):
    uri = f"ws://{host}:{port}"
    t = threading.Thread(target=lambda: asyncio.run(network_loop(uri, username)), daemon=True)
    t.start()


# ----------------------------------------
# Tkinter UI
# ----------------------------------------

class ChatClientUI:
    def __init__(self, master):
        self.master = master
        master.title("Chat Client")

        # --------------------- Top (connect) ---------------------
        top = tk.Frame(master)
        top.pack(padx=8, pady=6, anchor="w")

        tk.Label(top, text="Host:").grid(row=0, column=0)
        self.host_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(top, textvariable=self.host_var, width=15).grid(row=0, column=1)

        tk.Label(top, text="Port:").grid(row=0, column=2)
        self.port_var = tk.StringVar(value="20200")
        tk.Entry(top, textvariable=self.port_var, width=6).grid(row=0, column=3)

        tk.Label(top, text="Username:").grid(row=0, column=4)
        self.username_var = tk.StringVar(value="User")
        tk.Entry(top, textvariable=self.username_var, width=12).grid(row=0, column=5)

        tk.Button(top, text="Connect", command=self.on_connect).grid(row=0, column=6, padx=6)
        self.status_label = tk.Label(top, text="Not connected", fg="red")
        self.status_label.grid(row=0, column=7)

        # --------------------- Rooms ---------------------
        middle = tk.Frame(master)
        middle.pack(padx=8, pady=6)

        rooms_frame = tk.Frame(middle)
        rooms_frame.pack(side=tk.LEFT)

        tk.Label(rooms_frame, text="Rooms").pack(anchor="w")
        self.rooms_list = tk.Listbox(rooms_frame, width=22, height=12)
        self.rooms_list.pack()
        self.rooms_list.bind("<Double-Button-1>", self.join_selected_room)

        tk.Button(rooms_frame, text="Create room", command=self.create_room_prompt).pack(fill="x", pady=2)
        tk.Button(rooms_frame, text="Join selected", command=self.join_selected_room).pack(fill="x", pady=2)
        tk.Button(rooms_frame, text="Leave room", command=self.leave_room).pack(fill="x", pady=2)

        # --------------------- Chat ---------------------

        chat_frame = tk.Frame(middle)
        chat_frame.pack(side=tk.LEFT, padx=8)

        tk.Label(chat_frame, text="Chat").pack(anchor="w")

        self.chat_box = scrolledtext.ScrolledText(chat_frame, width=60, height=18, state=tk.DISABLED)
        self.chat_box.pack()

        # --------------------- Bottom (send) ---------------------
        bottom = tk.Frame(master)
        bottom.pack(padx=8, pady=6, fill="x")

        self.msg_entry = tk.Entry(bottom, width=70)
        self.msg_entry.pack(side=tk.LEFT, expand=True, fill="x")
        self.msg_entry.bind("<Return>", lambda e: self.send_message())

        tk.Button(bottom, text="Send", command=self.send_message).pack(side=tk.LEFT, padx=6)

        self.master.after(100, self.poll_incoming)


    # ------------------ UI Callbacks ------------------

    def on_connect(self):
        if connected:
            return

        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        username = self.username_var.get().strip()

        if not host or not port or not username:
            return

        start_network_thread(host, port, username)
        self.status_label.config(text="Connecting...", fg="orange")
        self.master.after(500, self.check_connected)


    def check_connected(self):
        if connected:
            self.status_label.config(text="Connected", fg="green")
            send_action("roomsList")
        else:
            self.status_label.config(text="Not connected", fg="red")

    # Rooms
    def create_room_prompt(self):
        if not connected:
            return
        room = simpledialog.askstring("Create room", "Room name:")
        if room:
            send_action("createRoom", {"room": room})

    def join_selected_room(self, event=None):
        if not connected:
            return
        sel = self.rooms_list.curselection()
        if not sel:
            return
        room = self.rooms_list.get(sel[0])
        send_action("joinRoom", {"room": room})

    def leave_room(self):
        if connected:
            send_action("leaveRoom")

    # Messages
    def send_message(self):
        if not connected:
            return
        text = self.msg_entry.get().strip()
        if text:
            send_action("sendMessage", {"message": text})
            self.msg_entry.delete(0, tk.END)

    # Chat append
    def append_chat(self, msg):
        self.chat_box.config(state=tk.NORMAL)
        self.chat_box.insert(tk.END, msg + "\n")
        self.chat_box.see(tk.END)
        self.chat_box.config(state=tk.DISABLED)

    # Incoming messages
    def poll_incoming(self):
        while not in_queue.empty():
            obj = in_queue.get()
            action = obj.get("action")

            if action == "roomsList":
                rooms = obj.get("rooms", [])
                self.rooms_list.delete(0, tk.END)
                for r in rooms:
                    self.rooms_list.insert(tk.END, r)

            elif action == "joined":
                room = obj["payload"]["room"]
                self.append_chat(f"*** You joined {room} ***")

            elif action == "left":
                room = obj["payload"]["room"]
                self.append_chat(f"*** You left {room} ***")

            elif action == "message":
                p = obj["payload"]
                self.append_chat(f"[{p['room']}] {p['from']}: {p['message']}")

            elif action == "error":
                self.append_chat(f"[ERROR] {obj}")

            else:
                self.append_chat(f"[DEBUG] {obj}")

        self.master.after(100, self.poll_incoming)


# -----------------------------
# RUN UI
# -----------------------------

def main():
    root = tk.Tk()
    ChatClientUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
