import asyncio
import websockets
import json
import sys

# Function to run input() in a separate thread so it doesn't block the async loop
async def get_input(prompt):
    return await asyncio.to_thread(input, prompt)

async def main():
    # Use 127.0.0.1 if running client on the same machine as server
    # If running on a different device, ensure 192.168.1.25 is correct
    uri = "ws://192.168.1.25:6789"
    print(f"Attempting to connect to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to server.")

            async def send_loop():
                # FIX: Use asyncio.to_thread for input()
                while True:
                    try:
                        text = await get_input("Enter action (json): ")

                        if not text.strip():
                            continue

                        obj = json.loads(text)
                        
                        # Add a default room/message context if not present for easier testing
                        if obj.get("action") == "sendMessage" and "room" not in obj:
                             # This is not ideal, but helps with quick testing
                             pass 

                        await websocket.send(json.dumps(obj))
                    except json.JSONDecodeError as e:
                        print("Invalid JSON:", e)
                    except EOFError:
                        print("\nExiting send loop.")
                        break # Exit the loop if EOF (Ctrl+D/Ctrl+Z)
                    except Exception as e:
                        print(f"An unexpected error occurred in send_loop: {e}")
                        break

            async def receive_loop():
                while True:
                    try:
                        # Server sends JSON objects now, so parse them
                        raw_msg = await websocket.recv()
                        obj = json.loads(raw_msg) 
                        
                        if obj.get("action") == "message":
                            print(f"\n[{obj['room']}] {obj['sender']}: {obj['message']}")
                        else:
                            print(f"\n[SERVER] {obj}")
                        
                    except websockets.exceptions.ConnectionClosed:
                        print("\nDisconnected from server.")
                        break
                    except json.JSONDecodeError:
                        print("\nReceived non-JSON message:", raw_msg)
                        continue
                    except Exception as e:
                        print(f"An unexpected error occurred in receive_loop: {e}")
                        break
                    finally:
                        # Re-prompt for input after receiving a message
                        sys.stdout.write("Enter action (json): ")
                        sys.stdout.flush()


            # Running both send and receive loops concurrently
            await asyncio.gather(send_loop(), receive_loop())

    except ConnectionRefusedError:
        print(f"Connection refused. Ensure the server is running at {uri}.")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(main())