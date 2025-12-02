import socket

server = socket.socket()
server.bind(('localhost',12345)) # navigate to server using http://localhost:1234
server.listen(5) # Listen to n numbre of connexions at once

print("Server is listening on port 12345...")
conn, addr = server.accept()
print(f"Connection established with {addr}")

while True:
    msg = conn.recv(1024).decode()
    if msg.lower() == 'exit':
        print("Client has exited the chat :P")
        break