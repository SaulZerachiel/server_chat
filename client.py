import asyncio
import json
import threading
import queue
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
import websockets

# ------------------------------------------------------------------
# Queues pour communiquer entre le thread UI (Tkinter) et le réseau
# ------------------------------------------------------------------
out_queue = queue.Queue()   # UI -> réseau (objets JSON Python)
in_queue = queue.Queue()    # réseau -> UI (dictionnaires Python)

# Etat local du client
current_room = None
connected = False

# ------------------------------------------------------------------
# Protocol helper : construire et envoyer des objets (Python dict)
# ------------------------------------------------------------------
def send_action(action, payload=None):
    """Place une action JSON dans out_queue pour être envoyée au serveur."""
    if payload is None:
        payload = {}
    out_queue.put({**payload, "action": action})

# ------------------------------------------------------------------
# Boucle réseau asynchrone (s'exécute dans un thread séparé)
# ------------------------------------------------------------------
async def network_loop(uri, username):
    global connected, current_room
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
            connected = True
            # Identify (obligatoire)
            await ws.send(json.dumps({"action": "identify", "payload": {"username": username}}))

            # task pour recevoir en continu
            async def receiver():
                async for raw in ws:
                    try:
                        obj = json.loads(raw)
                    except Exception:
                        in_queue.put({"action": "error", "payload": {"reason": "invalid_json"}})
                        continue
                    in_queue.put(obj)

            recv_task = asyncio.create_task(receiver())

            # boucle d'envoi (non-bloquante)
            try:
                while True:
                    try:
                        data = out_queue.get_nowait()
                    except queue.Empty:
                        await asyncio.sleep(0.05)
                        continue

                    # Envoi effectif
                    await ws.send(json.dumps(data))
            except websockets.ConnectionClosed:
                in_queue.put({"action": "error", "payload": {"reason": "connection_closed"}})
            finally:
                recv_task.cancel()

    except Exception as e:
        in_queue.put({"action": "error", "payload": {"reason": "unable_to_connect", "detail": str(e)}})
    finally:
        connected = False
        current_room = None

def start_network_thread(host, port, username):
    """Lance la boucle réseau dans un thread séparé."""
    uri = f"ws://{host}:{port}"
    t = threading.Thread(target=lambda: asyncio.run(network_loop(uri, username)), daemon=True)
    t.start()

# ------------------------------------------------------------------
# UI (Tkinter)
# ------------------------------------------------------------------
class ChatClientUI:
    def __init__(self, master):
        self.master = master
        master.title("Chat Client")

        # --- Top frame : connection ---
        top = tk.Frame(master)
        top.pack(padx=8, pady=6, anchor="w")

        tk.Label(top, text="Host:").grid(row=0, column=0, sticky="w")
        self.host_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(top, textvariable=self.host_var, width=15).grid(row=0, column=1, padx=4)

        tk.Label(top, text="Port:").grid(row=0, column=2, sticky="w")
        self.port_var = tk.StringVar(value="20200")
        tk.Entry(top, textvariable=self.port_var, width=6).grid(row=0, column=3, padx=4)

        tk.Label(top, text="Username:").grid(row=0, column=4, sticky="w")
        self.username_var = tk.StringVar(value="Lorian")
        tk.Entry(top, textvariable=self.username_var, width=12).grid(row=0, column=5, padx=4)

        self.connect_btn = tk.Button(top, text="Connect", command=self.on_connect)
        self.connect_btn.grid(row=0, column=6, padx=6)

        self.status_label = tk.Label(top, text="Not connected", fg="red")
        self.status_label.grid(row=0, column=7, padx=6)

        # --- Middle frame : rooms + chat ---
        middle = tk.Frame(master)
        middle.pack(padx=8, pady=6)

        # Rooms list + buttons
        rooms_frame = tk.Frame(middle)
        rooms_frame.pack(side=tk.LEFT, padx=(0,8))

        tk.Label(rooms_frame, text="Rooms").pack(anchor="w")
        self.rooms_listbox = tk.Listbox(rooms_frame, width=20, height=12)
        self.rooms_listbox.pack()
        self.rooms_listbox.bind("<Double-Button-1>", self.join_selected_room)

        tk.Button(rooms_frame, text="Create room", command=self.create_room_prompt).pack(fill="x", pady=(6,2))
        tk.Button(rooms_frame, text="Join selected", command=self.join_selected_room).pack(fill="x", pady=2)
        tk.Button(rooms_frame, text="Leave room", command=self.leave_room).pack(fill="x", pady=2)

        # Chat area
        chat_frame = tk.Frame(middle)
        chat_frame.pack(side=tk.LEFT)

        tk.Label(chat_frame, text="Chat").pack(anchor="w")
        self.chat_box = scrolledtext.ScrolledText(chat_frame, width=60, height=18, state=tk.DISABLED)
        self.chat_box.pack()

        # --- Bottom frame : send message ---
        bottom = tk.Frame(master)
        bottom.pack(padx=8, pady=6, fill="x")

        self.msg_entry = tk.Entry(bottom, width=70)
        self.msg_entry.pack(side=tk.LEFT, padx=(0,8), expand=True, fill="x")
        self.msg_entry.bind("<Return>", lambda e: self.send_message())

        tk.Button(bottom, text="Send", command=self.send_message).pack(side=tk.LEFT)

        # Lancer le poller UI -> vérifier in_queue régulièrement
        self.master.after(100, self.poll_incoming)

    # -------- UI callbacks / helpers ----------
    def on_connect(self):
        if connected:
            messagebox.showinfo("Info", "Déjà connecté.")
            return

        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        username = self.username_var.get().strip()

        if not host or not port or not username:
            messagebox.showerror("Erreur", "Host, port et username sont requis.")
            return

        try:
            int(port)
        except ValueError:
            messagebox.showerror("Erreur", "Port invalide.")
            return

        # démarre le thread réseau
        start_network_thread(host, port, username)
        self.status_label.config(text="Connecting...", fg="orange")
        self.master.after(500, self.check_connected_status)

    def check_connected_status(self):
        if connected:
            self.status_label.config(text="Connected", fg="green")
            send_action("roomsList", {})
        else:
            self.status_label.config(text="Not connected", fg="red")

    def create_room_prompt(self):
        if not connected:
            messagebox.showerror("Erreur", "Connecte-toi d'abord.")
            return
        room = simpledialog.askstring("Create room", "Nom du salon :")
        if room:
            send_action("createRoom", {"room": room})

    def join_selected_room(self, event=None):
        if not connected:
            messagebox.showerror("Erreur", "Connecte-toi d'abord.")
            return
        sel = self.rooms_listbox.curselection()
        if not sel:
            messagebox.showinfo("Info", "Sélectionne d'abord un salon.")
            return
        room = self.rooms_listbox.get(sel[0])
        send_action("joinRoom", {"room": room})

    def leave_room(self):
        if not connected:
            messagebox.showerror("Erreur", "Connecte-toi d'abord.")
            return
        send_action("leaveRoom", {})

    def send_message(self):
        if not connected:
            messagebox.showerror("Erreur", "Connecte-toi d'abord.")
            return
        text = self.msg_entry.get().strip()
        if not text:
            return
        send_action("sendMessage", {"message": text})
        self.msg_entry.delete(0, tk.END)

    def append_chat(self, text):
        self.chat_box.config(state=tk.NORMAL)
        self.chat_box.insert(tk.END, text + "\n")
        self.chat_box.see(tk.END)
        self.chat_box.config(state=tk.DISABLED)

    # -------- Poller : consomme in_queue et met à jour l'UI ----------
    def poll_incoming(self):
        global current_room
        while not in_queue.empty():
            obj = in_queue.get()
            action = obj.get("action")
            payload = obj.get("payload", {})

            if action == "roomsList":
                rooms = obj.get("rooms", [])
                self.rooms_listbox.delete(0, tk.END)
                for r in rooms:
                    self.rooms_listbox.insert(tk.END, r)

            elif action == "joined":
                room = payload.get("room")
                self.append_chat(f"*** You joined {room} ***")
                current_room = room

            elif action == "left":
                room = payload.get("room")
                self.append_chat(f"*** You left {room} ***")
                current_room = None

            elif action == "message":
                p = payload
                frm = p.get("from", "unknown")
                room = p.get("room", "")
                msg = p.get("message", "")
                line = f"[{room}] {frm}: {msg}"
                self.append_chat(line)

            elif action == "error":
                reason = payload.get("reason", "unknown")
                detail = payload.get("detail", "")
                self.append_chat(f"[ERROR] {reason} {detail}")
                if reason in ("username_taken", "unable_to_connect"):
                    messagebox.showerror("Erreur serveur", f"{reason}\n{detail}")

            else:
                self.append_chat(f"[DEBUG] {obj}")

        self.master.after(100, self.poll_incoming)

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    root = tk.Tk()
    app = ChatClientUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
