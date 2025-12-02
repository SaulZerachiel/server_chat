# client.py

import asyncio
import websockets
import tkinter as tk
from tkinter import scrolledtext
import threading
import queue
import json

out_queue = queue.Queue()  # messages de l'UI -> réseau
in_queue = queue.Queue()   # messages du réseau -> UI

async def network_loop(uri, username):
    async with websockets.connect(uri) as ws:

        # identification
        await ws.send(json.dumps({
            "action": "identify",
            "payload": {"username": username}
        }))

        async def receive_loop():
            async for msg in ws:
                data = json.loads(msg)
                in_queue.put(data)

        recv_task = asyncio.create_task(receive_loop())

        try:
            while True:
                try:
                    obj = out_queue.get_nowait()
                    await ws.send(json.dumps(obj))
                except queue.Empty:
                    await asyncio.sleep(0.1)
        except websockets.ConnectionClosed:
            pass
        finally:
            recv_task.cancel()

def start_network(host, port, username):
    uri = f"ws://{host}:{port}"
    threading.Thread(
        target=lambda: asyncio.run(network_loop(uri, username)),
        daemon=True
    ).start()

root = tk.Tk()
root.title("Chat Client")

# zone affichage messages
chat_box = scrolledtext.ScrolledText(root, width=60, height=20)
chat_box.pack()

# champ message
entry = tk.Entry(root, width=50)
entry.pack(side=tk.LEFT, padx=5)

def send_message():
    msg = entry.get()
    if msg.strip():
        out_queue.put({"action":"send_message","payload":{"message":msg}})
        entry.delete(0, tk.END)

tk.Button(root, text="Send", command=send_message).pack(side=tk.LEFT)

def update_ui():
    while not in_queue.empty():
        data = in_queue.get()
        if data["action"] == "message":
            p = data["payload"]
            line = f"[{p['room']}] {p['from']}: {p['message']}\n"
            chat_box.insert(tk.END, line)

    root.after(100, update_ui)

update_ui()

host = "127.0.0.1"
port = 8765
username = input("Username : ")

start_network(host, port, username)

root.mainloop()


