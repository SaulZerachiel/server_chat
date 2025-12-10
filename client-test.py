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
    global connected
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
        
        # Centrer la fenêtre sur l'écran
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 360
        window_height = 160
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"+{x}+{y}")

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
        
        # Centrer la fenêtre sur l'écran
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 360
        window_height = 150
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"+{x}+{y}")

        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        color = "#ff6b6b" if error else "white"
        ctk.CTkLabel(frame, text=message, text_color=color, wraplength=320, font=("Segoe UI", 12)).pack(pady=(10, 8))

        ctk.CTkButton(frame, text="OK", command=self.destroy, corner_radius=12, font=("Segoe UI", 12)).pack(pady=(4, 6))

        self.grab_set()
        self.wait_window()

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, title="Settings", on_username_change=None):
        super().__init__()
        self.title(title)
        self.geometry("400x160")
        self.resizable(False, False)
        self.on_username_change = on_username_change
        
        # Centrer la fenêtre sur l'écran
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 400
        window_height = 160
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"+{x}+{y}")

        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Username section
        ctk.CTkLabel(frame, text="Change Username", font=("Segoe UI", 14, "bold")).pack(pady=(10, 8), anchor="w", padx=15)
        
        username_frame = ctk.CTkFrame(frame, fg_color="transparent")
        username_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.username_entry = ctk.CTkEntry(username_frame, placeholder_text="New username", corner_radius=10, font=("Segoe UI", 11))
        self.username_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        ctk.CTkButton(username_frame, text="Save", command=self.save_username, corner_radius=10, font=("Segoe UI", 11), width=60).pack(side="left")

        # Close button
        ctk.CTkButton(frame, text="Close", command=self.destroy, corner_radius=12, font=("Segoe UI", 12)).pack(pady=(10, 0))

        self.grab_set()

    def save_username(self):
        username = self.username_entry.get().strip()
        if username and self.on_username_change:
            self.on_username_change(username)
            self.username_entry.delete(0, "end")
            show_info("Success", "Username changed!")

def show_error(title, msg):
    CTkMessageBox(title=title, message=msg, error=True)

def show_info(title, msg):
    CTkMessageBox(title=title, message=msg, error=False)

# ------------------------------------------------------------------
# UI Modernisée
# ------------------------------------------------------------------
class ChatClientUI:
    # Palette de couleurs pour les utilisateurs (style Discord)
    USER_COLORS = [
        "#5865F2",  # Bleu Discord
        "#57F287",  # Vert
        "#FEE75C",  # Jaune
        "#F26522",  # Orange
        "#EB459E",  # Rose
        "#80E7FF",  # Cyan
        "#B19CD9",  # Violet
        "#AEE8A0",  # Vert clair
        "#FF6B6B",  # Rouge
        "#FFB347",  # Orange clair
    ]
    
    def __init__(self, master):
        self.master = master
        master.title("Chatbox")
        master.geometry("920x600")
        master.minsize(820, 520)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.last_sender = None  # Pour espacement des messages
        self.last_sender_time = None  # Pour ne pas réafficher le pseudo + heure si même utilisateur
        self.user_colors = {}  # Dictionnaire pour stocker les couleurs des utilisateurs
        self.color_index = 0  # Index pour la prochaine couleur
        self.current_room_label = None  # Pour afficher le nom du salon actuel
        # Messages par room et état des rooms jointes/visualisées
        self.room_chats = {}  # Dictionnaire pour stocker les messages de chaque room {room_name: [{sender,message,system}, ...]}
        self.room_last_senders = {}  # Dictionnaire pour tracker le dernier sender par room
        self.joined_rooms = set(["default"])  # Rooms auxquelles l'utilisateur est inscrit
        self.viewed_room = None  # Room actuellement affichée dans l'UI (peut être view-only)
        # Initialiser la room par défaut
        self.room_chats["default"] = []
        self.room_last_senders["default"] = None

        # Configure grid weights for proper resizing
        master.grid_rowconfigure(1, weight=1)  # Make middle expandable
        master.grid_rowconfigure(0, weight=0)  # Top stays fixed
        master.grid_rowconfigure(2, weight=0)  # Bottom stays fixed
        master.grid_columnconfigure(0, weight=1)

        # ------------------------------------------------------------------
        # TOP CONNECTION
        # ------------------------------------------------------------------
        top = ctk.CTkFrame(master, corner_radius=12)
        top.grid(row=0, column=0, padx=10, pady=(10,10), sticky="ew")
        top.grid_columnconfigure(8, weight=1)  # Make column 8 (empty space) expandable to push Settings to the right


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

        # Status frame with indicator light
        status_frame = ctk.CTkFrame(top, fg_color="transparent")
        status_frame.grid(row=0, column=7, padx=2)

        self.status_indicator = ctk.CTkLabel(status_frame, text="●", font=("Segoe UI", 16), text_color="red")
        self.status_indicator.pack(side="left", padx=(0, 4))

        self.status_label = ctk.CTkLabel(status_frame, text="Not connected", text_color="red", font=("Segoe UI", 12))
        self.status_label.pack(side="left")

        ctk.CTkButton(top, text="⚙️", command=self.open_settings, corner_radius=8, font=("Segoe UI", 16), width=40, height=40).grid(row=0, column=9, padx=8, sticky="e")

        # ------------------------------------------------------------------
        # MIDDLE
        # ------------------------------------------------------------------
        middle = ctk.CTkFrame(master, corner_radius=12)
        middle.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        # Configure grid for middle frame
        middle.grid_rowconfigure(0, weight=1)  # Rooms expand vertically
        middle.grid_rowconfigure(1, weight=0)  # Buttons stay fixed height
        middle.grid_columnconfigure(0, weight=0)  # Left column (rooms + buttons) stays fixed width
        middle.grid_columnconfigure(1, weight=1)  # Right column (chat) expands

        # LEFT CONTAINER – Rooms + Buttons
        left_container = ctk.CTkFrame(middle, fg_color="transparent")
        left_container.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsew")
        left_container.grid_rowconfigure(0, weight=1)  # Rooms expand
        left_container.grid_rowconfigure(1, weight=0)  # Buttons stay fixed

        # Rooms frame
        rooms_frame = ctk.CTkFrame(left_container, corner_radius=12, fg_color="#2B2D31")
        rooms_frame.grid(row=0, column=0, sticky="nsew")

        lbl_rooms = ctk.CTkLabel(rooms_frame, text="ROOMS", font=("Segoe UI", 16, "bold"))
        lbl_rooms.pack(pady=(10, 6), fill="x")

        rooms_main = ctk.CTkFrame(rooms_frame, fg_color="transparent")
        rooms_main.pack(fill="both", expand=True)

        # Listbox container
        listbox_container = tk.Frame(rooms_main, bg="#2B2D31")
        listbox_container.pack(padx=10, pady=5, fill="both", expand=True)

        # STYLE SCROLLBAR (Dark Discord style)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("DarkScrollbar.Vertical.TScrollbar",
                        gripcount=0,
                        background="#2B2D31",
                        darkcolor="#2B2D31",
                        lightcolor="#2B2D31",
                        troughcolor="#2B2D31",
                        bordercolor="#2B2D31",
                        arrowcolor="#72767D",
                        width=12)
        style.map("DarkScrollbar.Vertical.TScrollbar",
                  background=[("active", "#4E505B"), ("!active", "#72767D")])

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

        scrollbar = ttk.Scrollbar(listbox_container, orient="vertical", command=self.rooms_listbox.yview, style="DarkScrollbar.Vertical.TScrollbar")
        scrollbar.pack(side="right", fill="y")
        self.rooms_listbox.config(yscrollcommand=scrollbar.set)

        for seq in ("<Key>", "<Control-v>", "<Button-2>", "<Button-3>"):
            self.rooms_listbox.bind(seq, lambda e: "break")
        
        # Ajouter binding pour voir les messages d'une room quand on la sélectionne (single click)
        # Utiliser l'événement virtuel <<ListboxSelect>> qui se déclenche après la sélection
        self.rooms_listbox.bind("<<ListboxSelect>>", self.on_room_click)

        # RIGHT – Chat frame
        chat_frame = ctk.CTkFrame(middle, corner_radius=12, fg_color="#2B2D31")
        chat_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        lbl_chat = ctk.CTkLabel(chat_frame, text="CHAT", font=("Segoe UI", 16, "bold"))
        lbl_chat.pack(pady=(10, 6), fill="x")

        # Current room info
        self.current_room_label = ctk.CTkLabel(chat_frame, text="No room selected", text_color="#72767D", font=("Segoe UI", 11))
        self.current_room_label.pack(pady=(0, 6), padx=10, fill="x")

        # Chat Text + Scrollbar
        self.chat_container = tk.Frame(chat_frame, bg="#2B2D31")
        self.chat_container.pack(fill="both", expand=True, padx=10, pady=(0,10))

        self.chat_scrollbar = ttk.Scrollbar(self.chat_container, orient="vertical", style="DarkScrollbar.Vertical.TScrollbar")
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
        
        # Configure user color tags
        for i, color in enumerate(self.USER_COLORS):
            self.chat_box.tag_configure(f"user_color_{i}", foreground=color, font=("Segoe UI", 12, "bold"))

        # BOTTOM
        bottom = ctk.CTkFrame(master, corner_radius=12)
        bottom.grid(row=2, column=0, padx=10, pady=10, sticky="ew")

        self.msg_entry = ctk.CTkEntry(bottom, corner_radius=12, font=("Segoe UI", 12))
        self.msg_entry.pack(side="left", padx=10, fill="x", expand=True)
        self.msg_entry.bind("<Return>", lambda e: self.send_message())

        ctk.CTkButton(bottom, text="Send", command=self.send_message, corner_radius=12, font=("Segoe UI", 12)).pack(side="left", padx=(0,10))

        # ------------------------------------------------------------------
        # BUTTONS FRAME (in left container, below rooms)
        # ------------------------------------------------------------------
        buttons_frame = ctk.CTkFrame(left_container, corner_radius=12)
        buttons_frame.grid(row=1, column=0, sticky="ew", pady=10)

        btn_font = ("Segoe UI", 12)
        ctk.CTkButton(buttons_frame, text="Create room", command=self.create_room_prompt, corner_radius=12, font=btn_font).pack(fill="x", pady=(0,4), padx=10)
        ctk.CTkButton(buttons_frame, text="Join selected", command=self.join_selected_room, corner_radius=12, font=btn_font).pack(fill="x", pady=4, padx=10)
        ctk.CTkButton(buttons_frame, text="Leave room", command=self.leave_room, corner_radius=12, font=btn_font).pack(fill="x", pady=4, padx=10)
        ctk.CTkButton(buttons_frame, text="Delete room", command=self.delete_room, corner_radius=12, font=btn_font).pack(fill="x", pady=(4,0), padx=10)

        self.master.after(100, self.poll_incoming)

    # ------------------------------------------------------------------
    # CALLBACKS
    # ------------------------------------------------------------------
    def get_room_name(self, room_display):
        """Extract room name from display text (format: 'room_name (count)')"""
        if ' (' in room_display:
            return room_display.rsplit(' (', 1)[0]
        return room_display

    def on_room_click(self, event):
        """Affiche les messages d'une room quand on clique dessus (sans rejoindre)"""
        sel = self.rooms_listbox.curselection()
        if not sel:
            return
        
        room_display = self.rooms_listbox.get(sel[0])
        room = self.get_room_name(room_display)
        
        # Initialiser la room si elle n'existe pas
        if room not in self.room_chats:
            self.room_chats[room] = []
            self.room_last_senders[room] = None
        
        # Afficher les messages de cette room (sans la rejoindre)
        self.viewed_room = room
        self.display_room_chat(room)
        # Mettre à jour le label en fonction si l'on a déjà rejoint la room
        self.update_room_info(room)

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
        self.status_indicator.configure(text_color="orange")
        self.status_label.configure(text="Connecting...", text_color="orange")
        self.master.after(500, self.check_connected_status)

    def check_connected_status(self):
        if connected:
            self.status_indicator.configure(text_color="green")
            self.status_label.configure(text="Connected", text_color="green")
            send_action("roomsList")
        else:
            self.status_indicator.configure(text_color="red")
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

        room_display = self.rooms_listbox.get(sel[0])
        room = self.get_room_name(room_display)
        
        # Envoyer l'action de join au serveur
        send_action("joinRoom", {"room": room})

    def leave_room(self):
        if not connected:
            show_error("Error", "Connect first.")
            return
        # Leave the currently viewed room (if joined)
        if not self.viewed_room:
            show_info("Info", "No room selected to leave.")
            return

        if self.viewed_room not in self.joined_rooms:
            show_info("Info", "You are not a member of this room.")
            return

        send_action("leaveRoom", {"room": self.viewed_room})

    def open_settings(self):
        SettingsWindow(
            title="Settings",
            on_username_change=self.handle_username_change
        )

    def handle_username_change(self, username):
        send_action("rename", {"newUsername": username})

    def change_username(self):
        newUsername = ask_string("Change Username", "New username:")
        if newUsername:
            send_action("rename", {"newUsername": newUsername})

    def delete_room(self):
        if not connected:
            show_error("Error", "Connect first.")
            return

        sel = self.rooms_listbox.curselection()
        if not sel:
            show_info("Info", "Select a room first.")
            return

        room_display = self.rooms_listbox.get(sel[0])
        room = self.get_room_name(room_display)
        send_action("deleteRoom", {"room": room})

    def send_message(self):
        # Envoi d'un message vers la room actuellement visualisée
        if not connected:
            show_error("Error", "Connect first.")
            return

        if not self.viewed_room:
            show_error("Error", "Select a room to send messages.")
            return

        if self.viewed_room not in self.joined_rooms:
            show_error("Error", "You must join the room before sending messages.")
            return

        text = self.msg_entry.get().strip()
        if not text:
            return
        # Envoyer le message en précisant la room cible
        send_action("sendMessage", {"message": text, "room": self.viewed_room})
        self.msg_entry.delete(0, "end")

    # ------------------------------------------------------------------
    # Append chat avec pseudo + heure
    # ------------------------------------------------------------------
    def append_chat(self, sender, message, room=None, system=False):
        """Ajoute un message dans l'historique de la room donnée.
        Si la room correspond à la room affichée, rafraîchit l'affichage."""
        # Déterminer la room cible pour le stockage
        target_room = room or self.viewed_room or "default"

        # Initialiser la room si nécessaire
        if target_room not in self.room_chats:
            self.room_chats[target_room] = []
            self.room_last_senders[target_room] = None

        # Sauvegarder le message dans la room
        self.room_chats[target_room].append({
            "sender": sender,
            "message": message,
            "system": system
        })

        # Si on affiche cette room, rafraîchir l'affichage
        if self.viewed_room == target_room:
            self.refresh_chat_display()

    def refresh_chat_display(self):
        """Rafraîchit l'affichage du chat avec tous les messages de la room actuellement visualisée"""
        if not self.viewed_room:
            return

        target_room = self.viewed_room

        # Vider le chat
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", "end")

        # Réinitialiser le dernier sender pour cette session d'affichage
        last_sender = None

        # Afficher tous les messages de la room
        if target_room in self.room_chats:
            for msg_data in self.room_chats[target_room]:
                sender = msg_data["sender"]
                message = msg_data["message"]
                system = msg_data["system"]

                now = datetime.now().strftime("%H:%M")

                # Si le message vient du même utilisateur que le précédent, on n'affiche pas pseudo+heure
                show_header = not (sender == last_sender)

                # Ajouter un espace si c'est un nouvel utilisateur (et pas le premier message)
                if show_header and last_sender is not None:
                    self.chat_box.insert("end", "\n")

                if system:
                    self.chat_box.insert("end", f"{message}\n", "system")
                else:
                    if show_header:
                        # Obtenir la couleur de l'utilisateur
                        if sender not in self.user_colors:
                            self.user_colors[sender] = self.color_index % len(self.USER_COLORS)
                            self.color_index += 1

                        color_tag = f"user_color_{self.user_colors[sender]}"
                        self.chat_box.insert("end", f"{sender} [{now}]\n", color_tag)
                    self.chat_box.insert("end", f"{message}\n")

                last_sender = sender

        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")
        self.last_sender = last_sender

    def display_room_chat(self, room):
        """Affiche le chat d'une room spécifique et marque cette room en tant que visualisée."""
        self.viewed_room = room

        # Initialiser la room si elle n'existe pas
        if room not in self.room_chats:
            self.room_chats[room] = []
            self.room_last_senders[room] = None

        # Afficher en utilisant refresh (qui prend en compte self.viewed_room)
        self.refresh_chat_display()

    def update_room_info(self, room):
        """Update the room info label and highlight the active room"""
        if not room:
            self.current_room_label.configure(text="No room selected", text_color="#72767D")
            return

        # Si on visualise cette room
        if room == self.viewed_room:
            if room in self.joined_rooms:
                self.current_room_label.configure(text=f"📍 Current room: {room}", text_color="white")
            else:
                self.current_room_label.configure(text=f"Viewing: {room}", text_color="#72767D")
        else:
            # Si pas visualisée mais jointe
            if room in self.joined_rooms:
                self.current_room_label.configure(text=f"Joined: {room}", text_color="white")
            else:
                self.current_room_label.configure(text=f"{room}", text_color="#72767D")

    # ------------------------------------------------------------------
    # Poll incoming
    # ------------------------------------------------------------------
    def poll_incoming(self):
        
        while not in_queue.empty():
            obj = in_queue.get()
            action = obj.get("action")
            payload = obj.get("payload", {})

            if action == "roomsList":
                # Préserver la room actuellement visualisée
                prev_viewed = self.viewed_room

                self.rooms_listbox.delete(0, tk.END)
                rooms_data = obj.get("rooms", {})
                
                # Si rooms_data est une liste (ancien format), utiliser le nouveau format dict
                if isinstance(rooms_data, list):
                    for r in rooms_data:
                        self.rooms_listbox.insert(tk.END, r)
                else:
                    # Nouveau format: dict avec room_name: count
                    for room_name, user_count in sorted(rooms_data.items()):
                        self.rooms_listbox.insert(tk.END, f"{room_name} ({user_count})")

                # Restaurer la sélection si possible
                if prev_viewed:
                    for i in range(self.rooms_listbox.size()):
                        item = self.rooms_listbox.get(i)
                        if item.startswith(prev_viewed + " (") or item == prev_viewed:
                            self.rooms_listbox.selection_clear(0, tk.END)
                            self.rooms_listbox.selection_set(i)
                            self.rooms_listbox.see(i)
                            break

            elif action == "joined":
                room = payload.get("room")
                # Marquer la room comme jointe
                self.joined_rooms.add(room)

                # Initialiser la room si elle n'existe pas
                if room not in self.room_chats:
                    self.room_chats[room] = []
                    self.room_last_senders[room] = None

                # Ajouter le message de join dans l'historique de la room
                self.append_chat("SYSTEM", f"You joined {room}", room=room, system=True)

                # Si l'utilisateur visualise cette room, rafraîchir et indiquer qu'elle est jointe
                if self.viewed_room == room:
                    self.refresh_chat_display()
                    self.update_room_info(room)

            elif action == "left":
                room = payload.get("room")
                # Retirer la room des rooms jointes si présente
                if room in self.joined_rooms:
                    self.joined_rooms.remove(room)

                # Enregistrer le message left dans l'historique de la room
                self.append_chat("SYSTEM", f"You left {room}", room=room, system=True)

                # Si on visualise cette room, rafraîchir l'affichage et mettre à jour le label
                if self.viewed_room == room:
                    self.refresh_chat_display()
                    self.update_room_info(room)

            elif action == "message":
                frm = payload.get("from")
                room = payload.get("room", "")
                msg = payload.get("message", "")
                # Sauvegarder le message dans l'historique de la room
                self.append_chat(frm, msg, room=room)

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
