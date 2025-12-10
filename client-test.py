import asyncio
import json
import threading
import queue
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import websockets
from datetime import datetime

# ------------------------------------------------------------------
# Queues réseau
# ------------------------------------------------------------------
out_queue = queue.Queue()
in_queue = queue.Queue()

current_room = None
connected = False

# ------------------------------------------------------------------
# Protocol helper
# ------------------------------------------------------------------
def send_action(action, payload=None):
    if payload is None:
        payload = {}
    out_queue.put({**payload, "action": action})

# ------------------------------------------------------------------
# Boucle réseau
# ------------------------------------------------------------------
async def network_loop(uri, username):
    global connected, current_room
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
            connected = True
            await ws.send(json.dumps({"action": "identify", "payload": {"username": username}}))

            async def receiver():
                async for raw in ws:
                    try:
                        obj = json.loads(raw)
                    except:
                        in_queue.put({"action": "error", "payload": {"reason": "invalid_json"}})
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
                in_queue.put({"action": "error", "payload": {"reason": "connection_closed"}})
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

# ----------------------------------------------------------------------
# DIALOGUES CUSTOM (style Discord)
# ----------------------------------------------------------------------
class CTkInputDialog(ctk.CTkToplevel):
    def __init__(self, title="Input", message="Enter value:"):
        super().__init__()
        self.title(title)
        self.geometry("360x160")
        self.resizable(False, False)
        self.result = None

        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        lbl = ctk.CTkLabel(frame, text=message, wraplength=300, font=("Segoe UI", 12))
        lbl.pack(pady=(8, 6), anchor="center")

        self.entry = ctk.CTkEntry(frame, width=300, corner_radius=10, font=("Segoe UI", 12))
        self.entry.pack(pady=6)
        self.entry.focus()

        btn = ctk.CTkButton(frame, text="OK", command=self.ok, corner_radius=12, font=("Segoe UI", 12))
        btn.pack(pady=(8, 4))

        self.bind("<Return>", lambda e: self.ok())
        self.grab_set()
        self.wait_window()

    def ok(self):
        self.result = self.entry.get()
        self.destroy()

def ask_string(title, text):
    dialog = CTkInputDialog(title=title, message=text)
    return dialog.result

class CTkMessageBox(ctk.CTkToplevel):
    def __init__(self, title="Message", message="Information:", error=False):
        super().__init__()
        self.title(title)
        self.geometry("360x150")
        self.resizable(False, False)

        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        color = "#ff6b6b" if error else "white"
        ctk.CTkLabel(frame, text=message, text_color=color, wraplength=320, font=("Segoe UI", 12)).pack(pady=(10, 8))

        ctk.CTkButton(frame, text="OK", command=self.destroy, corner_radius=12, font=("Segoe UI", 12)).pack(pady=(4, 6))

        self.grab_set()
        self.wait_window()

def show_error(title, msg):
    CTkMessageBox(title=title, message=msg, error=True)

def show_info(title, msg):
    CTkMessageBox(title=title, message=msg, error=False)

# ------------------------------------------------------------------
# UI Modernisée
# ------------------------------------------------------------------
class ChatClientUI:
    def __init__(self, master):
        self.master = master
        master.title("Chatbox")
        master.geometry("920x600")
        master.minsize(820, 520)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.last_sender = None  # Pour espacement des messages
        self.last_sender_time = None  # Pour ne pas réafficher le pseudo + heure si même utilisateur

        # ------------------------------------------------------------------
        # TOP CONNECTION
        # ------------------------------------------------------------------
        top = ctk.CTkFrame(master, corner_radius=12)
        top.pack(padx=10, pady=(10,10), fill="x")

        ctk.CTkLabel(top, text="Host:", font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", padx=4)
        self.host_var = ctk.StringVar(value="")
        ctk.CTkEntry(top, textvariable=self.host_var, width=120, corner_radius=10, font=("Segoe UI", 12)).grid(row=0, column=1, padx=4)

        ctk.CTkLabel(top, text="Port:", font=("Segoe UI", 12)).grid(row=0, column=2, sticky="w", padx=4)
        self.port_var = ctk.StringVar(value="20200")
        ctk.CTkEntry(top, textvariable=self.port_var, width=80, corner_radius=10, font=("Segoe UI", 12)).grid(row=0, column=3, padx=4)

        ctk.CTkLabel(top, text="Username:", font=("Segoe UI", 12)).grid(row=0, column=4, sticky="w", padx=4)
        self.username_var = ctk.StringVar(value="")
        ctk.CTkEntry(top, textvariable=self.username_var, width=120, corner_radius=10, font=("Segoe UI", 12)).grid(row=0, column=5, padx=4)

        ctk.CTkButton(top, text="Connect", command=self.on_connect, corner_radius=12, font=("Segoe UI", 12)).grid(row=0, column=6, padx=8)

        self.status_label = ctk.CTkLabel(top, text="Not connected", text_color="red", font=("Segoe UI", 12))
        self.status_label.grid(row=0, column=7, padx=6)

        # ------------------------------------------------------------------
        # MIDDLE
        # ------------------------------------------------------------------
        middle = ctk.CTkFrame(master, corner_radius=12)
        middle.pack(padx=10, pady=10, fill="both", expand=True)

        # LEFT – Rooms
        rooms_frame = ctk.CTkFrame(middle, corner_radius=12, fg_color="#2B2D31")
        rooms_frame.pack(side="left", padx=10, pady=10, fill="y")

        lbl_rooms = ctk.CTkLabel(rooms_frame, text="ROOMS", font=("Segoe UI", 16, "bold"))
        lbl_rooms.pack(pady=(10, 6), fill="x")

        rooms_main = ctk.CTkFrame(rooms_frame, fg_color="transparent")
        rooms_main.pack(fill="both", expand=True)

        # Listbox container
        listbox_container = tk.Frame(rooms_main, bg="#2B2D31")
        listbox_container.pack(padx=10, pady=5, fill="both", expand=True)

        # STYLE SCROLLBAR (Dark)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Vertical.TScrollbar",
                        gripcount=0,
                        background="#3A3C40",
                        darkcolor="#3A3C40",
                        lightcolor="#3A3C40",
                        troughcolor="#1E1F22",
                        bordercolor="#1E1F22",
                        arrowcolor="gray",
                        width=8)

        self.rooms_listbox = tk.Listbox(
            listbox_container,
            selectmode=tk.SINGLE,
            activestyle="none",
            bg="#2B2D31",
            fg="white",
            font=("Segoe UI", 13),
            highlightthickness=0,
            bd=0,
            width=28,
            height=13,
            exportselection=False,
        )
        self.rooms_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(listbox_container, orient="vertical", command=self.rooms_listbox.yview, style="Vertical.TScrollbar")
        scrollbar.pack(side="right", fill="y")
        self.rooms_listbox.config(yscrollcommand=scrollbar.set)

        for seq in ("<Key>", "<Control-v>", "<Button-2>", "<Button-3>"):
            self.rooms_listbox.bind(seq, lambda e: "break")

        # BUTTONS FRAME
        buttons_frame = ctk.CTkFrame(rooms_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", side="bottom", pady=10, padx=10)

        btn_font = ("Segoe UI", 12)
        ctk.CTkButton(buttons_frame, text="Create room", command=self.create_room_prompt, corner_radius=12, font=btn_font).pack(fill="x", pady=(0,4))
        ctk.CTkButton(buttons_frame, text="Join selected", command=self.join_selected_room, corner_radius=12, font=btn_font).pack(fill="x", pady=4)
        ctk.CTkButton(buttons_frame, text="Leave room", command=self.leave_room, corner_radius=12, font=btn_font).pack(fill="x", pady=4)
        ctk.CTkButton(buttons_frame, text="Rename", command=self.rename, corner_radius=12, font=btn_font).pack(fill="x", pady=4)

        # RIGHT – Chat frame
        chat_frame = ctk.CTkFrame(middle, corner_radius=12, fg_color="#2B2D31")
        chat_frame.pack(side="left", padx=10, pady=10, fill="both", expand=True)

        lbl_chat = ctk.CTkLabel(chat_frame, text="CHAT", font=("Segoe UI", 16, "bold"))
        lbl_chat.pack(pady=(10, 6), fill="x")

        # Chat Text + Scrollbar
        self.chat_container = tk.Frame(chat_frame, bg="#2B2D31")
        self.chat_container.pack(fill="both", expand=True, padx=10, pady=(0,10))

        self.chat_scrollbar = tk.Scrollbar(self.chat_container, bg="#2B2D31", troughcolor="#1E1F22", width=12)
        self.chat_scrollbar.pack(side="right", fill="y")

        self.chat_box = tk.Text(
            self.chat_container,
            bg="#2B2D31",
            fg="white",
            font=("Segoe UI", 12),
            state="disabled",
            wrap="word",
            yscrollcommand=self.chat_scrollbar.set,
            bd=0,
            highlightthickness=0
        )
        self.chat_box.pack(side="left", fill="both", expand=True)
        self.chat_scrollbar.config(command=self.chat_box.yview)

        self.chat_box.tag_configure("pseudo", font=("Segoe UI", 12, "bold"))
        self.chat_box.tag_configure("system", font=("Segoe UI", 12, "italic"), foreground="#ff6b6b")

        # BOTTOM
        bottom = ctk.CTkFrame(master, corner_radius=12)
        bottom.pack(padx=10, pady=10, fill="x")

        self.msg_entry = ctk.CTkEntry(bottom, corner_radius=12, font=("Segoe UI", 12))
        self.msg_entry.pack(side="left", padx=10, fill="x", expand=True)
        self.msg_entry.bind("<Return>", lambda e: self.send_message())

        ctk.CTkButton(bottom, text="Send", command=self.send_message, corner_radius=12, font=("Segoe UI", 12)).pack(side="left", padx=(0,10))

        self.master.after(100, self.poll_incoming)

    # ------------------------------------------------------------------
    # CALLBACKS
    # ------------------------------------------------------------------
    def on_connect(self):
        if connected:
            show_info("Info", "Already connected.")
            return

        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        username = self.username_var.get().strip()

        if not host or not port or not username:
            show_error("Error", "Host, port and username are required.")
            return

        try:
            int(port)
        except ValueError:
            show_error("Error", "Invalid port")
            return

        start_network_thread(host, port, username)
        self.status_label.configure(text="Connecting...", text_color="orange")
        self.master.after(500, self.check_connected_status)

    def check_connected_status(self):
        if connected:
            self.status_label.configure(text="Connected", text_color="green")
            send_action("roomsList")
        else:
            self.status_label.configure(text="Not connected", text_color="red")

    def create_room_prompt(self):
        if not connected:
            show_error("Error", "Connect first.")
            return
        room = ask_string("Create room", "Name of the room:")
        if room:
            send_action("createRoom", {"room": room})

    def join_selected_room(self):
        if not connected:
            show_error("Error", "Connect first.")
            return

        sel = self.rooms_listbox.curselection()
        if not sel:
            show_info("Info", "Select a room first.")
            return

        room = self.rooms_listbox.get(sel[0])
        send_action("joinRoom", {"room": room})

    def leave_room(self):
        if not connected:
            show_error("Error", "Connect first.")
            return
        send_action("leaveRoom", {})

    def rename(self):
        newUsername = ask_string("New Username", "New username:")
        if newUsername:
            send_action("rename", {"newUsername": newUsername})

    def send_message(self):
        if not connected:
            show_error("Error", "Connect first.")
            return

        text = self.msg_entry.get().strip()
        if not text:
            return
        send_action("sendMessage", {"message": text})
        self.msg_entry.delete(0, "end")

    # ------------------------------------------------------------------
    # Append chat avec pseudo + heure
    # ------------------------------------------------------------------
    def append_chat(self, sender, message, system=False):
        self.chat_box.configure(state="normal")

        now = datetime.now().strftime("%H:%M")

        # Si le message vient du même utilisateur que le précédent, on n'affiche pas pseudo+heure
        show_header = not (sender == self.last_sender)

        if system:
            self.chat_box.insert("end", f"{message}\n", "system")
        else:
            if show_header:
                self.chat_box.insert("end", f"{sender} [{now}]\n", "pseudo")
            self.chat_box.insert("end", f"{message}\n")

        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")
        self.last_sender = sender

    # ------------------------------------------------------------------
    # Poll incoming
    # ------------------------------------------------------------------
    def poll_incoming(self):
        global current_room
        while not in_queue.empty():
            obj = in_queue.get()
            action = obj.get("action")
            payload = obj.get("payload", {})

            if action == "roomsList":
                self.rooms_listbox.delete(0, tk.END)
                for r in obj.get("rooms", []):
                    self.rooms_listbox.insert(tk.END, r)

            elif action == "joined":
                room = payload.get("room")
                self.append_chat("SYSTEM", f"You joined {room}", system=True)
                current_room = room

            elif action == "left":
                self.append_chat("SYSTEM", f"You left the room", system=True)
                current_room = None

            elif action == "message":
                frm = payload.get("from")
                room = payload.get("room", "")
                msg = payload.get("message", "")
                self.append_chat(frm, msg)

            elif action == "error":
                reason = payload.get("reason", "")
                detail = payload.get("detail", "")
                show_error("Server error", f"{reason}\n{detail}")
                self.append_chat("SYSTEM", f"{reason} {detail}", system=True)

            else:
                self.append_chat("SYSTEM", f"[DEBUG] {obj}", system=True)

        self.master.after(100, self.poll_incoming)

# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main():
    root = ctk.CTk()
    ChatClientUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
