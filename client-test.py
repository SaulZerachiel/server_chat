"""
WebSocket Chat Client - CustomTkinter GUI
==========================================
A multi-room Discord-style chat application using WebSocket for real-time messaging.

Features:
- Multi-room support (join multiple rooms simultaneously)
- View room chat without joining
- Real-time user count per room
- Emoji picker for messages
- Custom username management
- Async networking with threaded GUI

Architecture:
- Async WebSocket network thread handles all server communication
- Main thread runs CustomTkinter GUI
- Queue-based message passing between threads
- Session-based message storage (in-memory per room)
"""

import asyncio
import json
import threading
import queue
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import websockets
from datetime import datetime

# ==================================================================
# GLOBAL STATE - Inter-thread communication
# ==================================================================
out_queue = queue.Queue()        # Messages FROM GUI TO server
in_queue = queue.Queue()         # Messages FROM server TO GUI
connected = False                # Global connection status

# ==================================================================
# NETWORK PROTOCOL HELPERS
# ==================================================================
def send_action(action, payload=None):
    """
    Send an action to the server through the outgoing queue.
    
    Args:
        action (str): The action name (e.g., "joinRoom", "sendMessage")
        payload (dict): Optional payload data to send with the action
    """
    if payload is None:
        payload = {}
    out_queue.put({**payload, "action": action})

# ==================================================================
# ASYNC NETWORK LOOP
# ==================================================================
async def network_loop(uri, username):
    """
    Main async network loop - handles all WebSocket communication.
    
    This function:
    1. Connects to the WebSocket server
    2. Sends identify message with username
    3. Continuously receives messages from server
    4. Continuously sends queued messages to server
    5. Handles disconnections and errors gracefully
    
    Args:
        uri (str): WebSocket URI (e.g., "ws://localhost:20200")
        username (str): Username to identify with on the server
    """
    global connected
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
            connected = True
            # Identify ourselves to the server
            await ws.send(json.dumps({"action": "identify", "payload": {"username": username}}))

            async def receiver():
                """Continuously receive and parse messages from server."""
                async for raw in ws:
                    try:
                        obj = json.loads(raw)
                    except:
                        in_queue.put({"action": "error", "payload": {"reason": "invalid_json"}})
                        continue
                    in_queue.put(obj)

            recv_task = asyncio.create_task(receiver())

            try:
                # Main send loop - continuously check for outgoing messages
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
    """
    Start the async network loop in a separate daemon thread.
    
    Args:
        host (str): Server host IP address
        port (str): Server port number
        username (str): Username to use for this session
    """
    uri = f"ws://{host}:{port}"
    t = threading.Thread(target=lambda: asyncio.run(network_loop(uri, username)), daemon=True)
    t.start()

# ----------------------------------------------------------------------
# DIALOGUES CUSTOM (style Discord)
# ----------------------------------------------------------------------
# ==================================================================
# CUSTOM DIALOG WINDOWS (Discord-style)
# ==================================================================

class CTkInputDialog(ctk.CTkToplevel):
    """
    Custom input dialog window for collecting text input from user.
    Example: Room names, usernames, etc.
    """
    def __init__(self, title="Input", message="Enter value:"):
        super().__init__()
        self.title(title)
        self.geometry("360x160")
        self.resizable(False, False)
        self.result = None
        
        # Center window on screen
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 360
        window_height = 160
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"+{x}+{y}")

        # Create frame with rounded corners
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Message label
        lbl = ctk.CTkLabel(frame, text=message, wraplength=300, font=("Segoe UI", 12))
        lbl.pack(pady=(8, 6), anchor="center")

        # Text entry field
        self.entry = ctk.CTkEntry(frame, width=300, corner_radius=10, font=("Segoe UI", 12))
        self.entry.pack(pady=6)
        self.entry.focus()

        # OK button
        btn = ctk.CTkButton(frame, text="OK", command=self.ok, corner_radius=12, font=("Segoe UI", 12))
        btn.pack(pady=(8, 4))

        # Allow Enter key to submit
        self.bind("<Return>", lambda e: self.ok())
        self.grab_set()  # Make window modal
        self.wait_window()

    def ok(self):
        """Confirm input and close dialog."""
        self.result = self.entry.get()
        self.destroy()

def ask_string(title, text):
    """Helper function to show input dialog and return result."""
    dialog = CTkInputDialog(title=title, message=text)
    return dialog.result

class CTkMessageBox(ctk.CTkToplevel):
    """
    Custom message dialog for displaying info/error messages to user.
    """
    def __init__(self, title="Message", message="Information:", error=False):
        super().__init__()
        self.title(title)
        self.geometry("360x150")
        self.resizable(False, False)
        
        # Center window on screen
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 360
        window_height = 150
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"+{x}+{y}")

        # Frame with rounded corners
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Message text - red for errors, white for info
        color = "#ff6b6b" if error else "white"
        ctk.CTkLabel(frame, text=message, text_color=color, wraplength=320, font=("Segoe UI", 12)).pack(pady=(10, 8))

        # OK button to dismiss
        ctk.CTkButton(frame, text="OK", command=self.destroy, corner_radius=12, font=("Segoe UI", 12)).pack(pady=(4, 6))

        self.grab_set()  # Make window modal
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
    """Show error message dialog (red text)."""
    CTkMessageBox(title=title, message=msg, error=True)

def show_info(title, msg):
    """Show info message dialog (white text)."""
    CTkMessageBox(title=title, message=msg, error=False)

# ==================================================================
# MAIN CHAT CLIENT UI
# ==================================================================
class ChatClientUI:
    """
    Main GUI class for the WebSocket chat client.
    
    Features:
    - Multi-room chat interface (Discord-style)
    - Real-time message display with user colors
    - Room management (create, join, leave, delete)
    - User status tracking (Current, Viewing, Joined)
    - Member count display per room
    - Emoji picker for messages
    
    Data Structure:
    - self.room_chats: Dict[room_name] -> list of messages
    - self.room_last_senders: Dict[room_name] -> last sender (to avoid repeating names)
    - self.room_counts: Dict[room_name] -> user count
    - self.joined_rooms: Set of room names the user is member of
    - self.viewed_room: Currently displayed room (can be view-only)
    """
    
    # User color palette (Discord-style colors)
    USER_COLORS = [
        "#5865F2",  # Discord Blue
        "#57F287",  # Green
        "#FEE75C",  # Yellow
        "#F26522",  # Orange
        "#EB459E",  # Pink
        "#80E7FF",  # Cyan
        "#B19CD9",  # Purple
        "#AEE8A0",  # Light Green
        "#FF6B6B",  # Red
        "#FFB347",  # Light Orange
    ]
    
    def __init__(self, master):
        """
        Initialize the chat client UI.
        
        Args:
            master: The root Tkinter window
        """
        self.master = master
        master.title("Chatbox")
        master.geometry("920x600")
        master.minsize(820, 520)

        # Set dark theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Message display state
        self.last_sender = None              # Track last sender to avoid repetition
        self.last_sender_time = None         # Track time to avoid showing time repeatedly
        self.user_colors = {}                # Maps username -> color_index
        self.color_index = 0                 # Next color to assign to new user
        
        # Multi-room message storage
        self.room_chats = {}                 # Maps room_name -> list of message dicts
        self.room_last_senders = {}          # Maps room_name -> last sender (per-room)
        self.room_counts = {}                # Maps room_name -> user count (from server)
        
        # Room membership and viewing
        self.joined_rooms = set(["default"]) # Set of rooms user is member of
        self.viewed_room = None              # Currently displayed room (can be view-only)
        
        # Initialize default room
        self.room_chats["default"] = []
        self.room_last_senders["default"] = None
        self.room_counts["default"] = 0

        # Configure grid weights for proper resizing
        master.grid_rowconfigure(1, weight=1)  # Make middle section expandable
        master.grid_rowconfigure(0, weight=0)  # Top stays fixed
        master.grid_rowconfigure(2, weight=0)  # Bottom stays fixed
        master.grid_columnconfigure(0, weight=1)
        
        # Build the user interface
        self.build_ui()

    def create_hover_button(self, parent, text, command, **kwargs):
        """
        Create a button with standard hover effect (color change).
        
        Args:
            parent: The parent widget
            text: Button text
            command: Function to call on click
            **kwargs: Additional button parameters
            
        Returns:
            The created CTkButton widget
        """
        font = kwargs.pop('font', ("Segoe UI", 12))
        btn = ctk.CTkButton(parent, text=text, command=command, font=font, **kwargs)
        return btn

    # ==================================================================
    # UI BUILDING
    # ==================================================================
    def build_ui(self):
        """
        Build the complete user interface.
        
        Layout:
        - Top: Connection controls (host, port, username, connect button, settings)
        - Middle: Three-column layout
            - Left: Room list, buttons (create, join, leave, delete)
            - Center: Chat display area
            - Right: (future expansion)
        - Bottom: Message input field and send button
        """
        master = self.master
        
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

        self.create_hover_button(top, text="Connect", command=self.on_connect, corner_radius=12, font=("Segoe UI", 12)).grid(row=0, column=6, padx=8)

        # Status frame with indicator light
        status_frame = ctk.CTkFrame(top, fg_color="transparent")
        status_frame.grid(row=0, column=7, padx=2)

        self.status_indicator = ctk.CTkLabel(status_frame, text="●", font=("Segoe UI", 16), text_color="red")
        self.status_indicator.pack(side="left", padx=(0, 4))

        self.status_label = ctk.CTkLabel(status_frame, text="Not connected", text_color="red", font=("Segoe UI", 12))
        self.status_label.pack(side="left")

        self.create_hover_button(top, text="⚙️", command=self.open_settings, corner_radius=8, font=("Segoe UI", 16), width=40, height=40).grid(row=0, column=9, padx=8, sticky="e")

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
        
        # Ajouter binding pour voir les messages d'une room quand on clique dessus (single click)
        # Utiliser <Button-1> avec délai pour attraper les clics sur room déjà sélectionnée
        # <<ListboxSelect>> ne se déclenche que si la sélection change, ce qui cause le bug
        self.rooms_listbox.bind("<Button-1>", lambda e: self.master.after(10, lambda: self.on_room_click(e)))

        # RIGHT – Chat frame
        chat_frame = ctk.CTkFrame(middle, corner_radius=12, fg_color="#2B2D31")
        chat_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        lbl_chat = ctk.CTkLabel(chat_frame, text="CHAT", font=("Segoe UI", 16, "bold"))
        lbl_chat.pack(pady=(10, 6), fill="x")

        # Current room info frame (centered display)
        room_info_frame = ctk.CTkFrame(chat_frame, fg_color="transparent")
        room_info_frame.pack(pady=(0, 6), padx=10, fill="x")

        # Label centralisé pour le nom du salon + count
        self.room_name_label = ctk.CTkLabel(room_info_frame, text="No room selected", text_color="#72767D", font=("Segoe UI", 11), justify="left")
        self.room_name_label.pack(side="left", fill="x", expand=True)

        # Label droit vide (gardé pour compatibilité)
        self.room_count_label = ctk.CTkLabel(room_info_frame, text="", text_color="#72767D", font=("Segoe UI", 11), justify="right")
        self.room_count_label.pack(side="right")

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

        self.create_hover_button(bottom, text="Send", command=self.send_message, corner_radius=12, font=("Segoe UI", 12)).pack(side="right", padx=(5,0))
        
        # Bouton emoji transparent
        ctk.CTkButton(bottom, text="😀", command=self.show_emoji_panel, corner_radius=8, font=("Segoe UI", 16), width=40, height=40, fg_color="transparent", hover_color="#404249", border_width=0).pack(side="left", padx=5)

        # ------------------------------------------------------------------
        # BUTTONS FRAME (in left container, below rooms)
        # ------------------------------------------------------------------
        buttons_frame = ctk.CTkFrame(left_container, corner_radius=12)
        buttons_frame.grid(row=1, column=0, sticky="ew", pady=10)

        btn_font = ("Segoe UI", 12)
        self.create_hover_button(buttons_frame, text="Create room", command=self.create_room_prompt, corner_radius=12, font=btn_font).pack(fill="x", pady=(0,4), padx=10)
        self.create_hover_button(buttons_frame, text="Join selected", command=self.join_selected_room, corner_radius=12, font=btn_font).pack(fill="x", pady=4, padx=10)
        self.create_hover_button(buttons_frame, text="Leave room", command=self.leave_room, corner_radius=12, font=btn_font).pack(fill="x", pady=4, padx=10)
        self.create_hover_button(buttons_frame, text="Delete room", command=self.delete_room, corner_radius=12, font=btn_font).pack(fill="x", pady=(4,0), padx=10)

        self.master.after(100, self.poll_incoming)

    # ==================================================================
    # CALLBACK FUNCTIONS & MESSAGE HANDLERS
    # ==================================================================
    def get_room_name(self, room_display):
        """
        Extract room name from display string.
        Helper function to handle any special formatting.
        
        Args:
            room_display (str): The displayed room name (possibly with extra whitespace)
            
        Returns:
            str: Cleaned room name
        """
        return room_display.strip()

    def on_room_click(self, event):
        """
        Handle room list click - display messages from selected room.
        
        This allows viewing a room's chat without joining it.
        When clicked, the room's messages are displayed and member count is shown.
        
        Args:
            event: Tkinter event from button click
        """
        sel = self.rooms_listbox.curselection()
        if not sel:
            return
        
        room_display = self.rooms_listbox.get(sel[0])
        room = self.get_room_name(room_display)
        
        # Get member count from server data
        count = self.room_counts.get(room)
        
        # Initialiser la room si elle n'existe pas
        if room not in self.room_chats:
            self.room_chats[room] = []
            self.room_last_senders[room] = None
        
        # Afficher les messages de cette room (sans la rejoindre)
        self.viewed_room = room
        self.display_room_chat(room)
        # Mettre à jour le label avec le count du serveur
        self.update_room_info(room, count)

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

    def show_emoji_panel(self):
        """
        Toggle display of emoji picker dropdown.
        
        Shows/hides a grid of common emojis that can be clicked to insert into message.
        Panel appears as overlay near the input bar.
        """
        emojis = [
            "😀", "😂", "😍", "🥰", "😎", "🤔", "😢", "😡",
            "👍", "👎", "❤️", "🔥", "✨", "🎉", "🎊", "💯",
            "🚀", "💪", "🙏", "👏", "😴", "🤐", "🤢", "🤮",
            "😈", "👿", "💀", "☠️", "💩", "🤡", "👻", "🎃",
            "😺", "😸", "😻", "😼", "😽", "😾", "😿", "🙀",
            "🍔", "🍕", "🍣", "🍜", "🍰", "🎂", "☕", "🍷"
        ]
        
        # Toggle: close panel if already open
        if hasattr(self, 'emoji_panel') and self.emoji_panel.winfo_exists():
            self.emoji_panel.destroy()
            return
        
        # Create overlay panel near bottom-right of screen
        self.emoji_panel = ctk.CTkFrame(self.master, fg_color="#2B2D31", corner_radius=12, width=320, height=250)
        self.emoji_panel.place(x=self.master.winfo_width() - 340, y=self.master.winfo_height() - 280)
        
        # Create 8-column grid of emoji buttons
        for idx, emoji in enumerate(emojis):
            row = idx // 8
            col = idx % 8
            btn = ctk.CTkButton(
                self.emoji_panel, 
                text=emoji, 
                font=("Segoe UI", 18),
                width=30, 
                height=30,
                fg_color="transparent",
                hover_color="#404249",
                border_width=0,
                command=lambda e=emoji: self.insert_emoji(e)
            )
            btn.grid(row=row, column=col, padx=3, pady=3)
        
        # Fermer le panel si on clique ailleurs
        self.master.after(100, lambda: self.master.bind("<Button-1>", self.close_emoji_panel_on_click))
    
    def close_emoji_panel_on_click(self, event):
        """Ferme le panel d'emoji si on clique ailleurs"""
        if hasattr(self, 'emoji_panel') and self.emoji_panel.winfo_exists():
            # Vérifier si le clic est sur le panel ou ses enfants
            widget = self.master.winfo_containing(event.x_root, event.y_root)
            if widget and "emoji_panel" not in str(widget):
                self.emoji_panel.destroy()
    
    def insert_emoji(self, emoji):
        """Insère un emoji dans le champ de texte et ferme le panel"""
        self.msg_entry.insert(tk.END, emoji)
        if hasattr(self, 'emoji_panel') and self.emoji_panel.winfo_exists():
            self.emoji_panel.destroy()

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
        # Send message to viewed room
        send_action("sendMessage", {"message": text, "room": self.viewed_room})
        self.msg_entry.delete(0, "end")

    # ==================================================================
    # MESSAGE STORAGE & DISPLAY
    # ==================================================================
    def append_chat(self, sender, message, room=None, system=False):
        """
        Add a message to room history.
        
        Stores message in self.room_chats and refreshes display if currently viewing that room.
        
        Args:
            sender (str): Username of sender (or "SYSTEM" for system messages)
            message (str): The message text
            room (str): Target room (defaults to viewed_room or "default")
            system (bool): Whether this is a system message (styled differently)
        """
        # Determine target room for storage
        target_room = room or self.viewed_room or "default"

        # Initialize room if needed
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

    def update_room_info(self, room, count=None):
        """Update the room info label and highlight the active room"""
        if not room:
            self.room_name_label.configure(text="No room selected", text_color="#72767D")
            self.room_count_label.configure(text="")
            return

        # Construire le texte du count avec séparateur
        members_text = f"  |  Members: {count}" if count is not None else ""

        # Déterminer la couleur et le label du nom selon l'état
        if room == self.viewed_room:
            if room in self.joined_rooms:
                name_text = f"📍 Current room: {room}"
                name_color = "white"
            else:
                name_text = f"👁️ Viewing: {room}"
                name_color = "#72767D"
        else:
            # Si pas visualisée mais jointe
            if room in self.joined_rooms:
                name_text = f"✓ Joined: {room}"
                name_color = "white"
            else:
                name_text = f"{room}"
                name_color = "#72767D"

        # Mettre à jour les labels avec tout sur la gauche
        combined_text = name_text + members_text
        self.room_name_label.configure(text=combined_text, text_color=name_color)
        self.room_count_label.configure(text="")  # Vider le label droit

    # ==================================================================
    # NETWORK MESSAGE POLLING (Main event loop)
    # ==================================================================
    def poll_incoming(self):
        """
        Poll incoming messages from the network thread and process them.
        
        This method is called repeatedly (every 100ms) and handles:
        - Room list updates (with member counts)
        - Join/leave confirmations
        - Chat messages from other users
        - User membership changes
        - Error messages
        - Connection events
        
        This bridges async network thread with sync Tkinter GUI.
        """
        
        while not in_queue.empty():
            obj = in_queue.get()
            action = obj.get("action")
            payload = obj.get("payload", {})

            if action == "roomsList":
                # Update room list while preserving current view
                prev_viewed = self.viewed_room

                self.rooms_listbox.delete(0, tk.END)
                rooms_data = obj.get("rooms", {})
                
                # Handle both old list format and new dict format (with counts)
                if isinstance(rooms_data, list):
                    for r in rooms_data:
                        self.rooms_listbox.insert(tk.END, r)
                else:
                    # New format: dict with room_name -> user_count
                    # Save counts for room info display
                    self.room_counts = rooms_data.copy()
                    # Display room names only (counts shown in room info section)
                    for room_name, user_count in sorted(rooms_data.items()):
                        self.rooms_listbox.insert(tk.END, room_name)

                # Restore selection to previously viewed room
                if prev_viewed:
                    for i in range(self.rooms_listbox.size()):
                        item = self.rooms_listbox.get(i)
                        if item == prev_viewed:
                            self.rooms_listbox.selection_clear(0, tk.END)
                            self.rooms_listbox.selection_set(i)
                            self.rooms_listbox.see(i)
                            # Mettre à jour avec le nouveau count
                            self.update_room_info(prev_viewed, self.room_counts.get(prev_viewed))
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
                    self.update_room_info(room, self.room_counts.get(room))

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

        # Schedule next poll in 100ms
        self.master.after(100, self.poll_incoming)

# ==================================================================
# APPLICATION ENTRY POINT
# ==================================================================
def main():
    """
    Initialize and run the chat client application.
    Creates the main window and starts the UI event loop.
    """
    root = ctk.CTk()
    ChatClientUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
