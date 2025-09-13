#!/usr/bin/env python3
"""
Audio-enabled voice interaction test with real-time audio streaming
"""
import asyncio
import json
import websockets
import sys
import sounddevice as sd
import numpy as np

# audio configuration
SR = 16000 # sample rate: 16 kHz
CH = 1 # channels: mono
DTYPE = "int16" # data type: 16-bit signed integers
BLOCK_SIZE = 480 # small block size for low latency (30ms at 16kHz)
BUFFER_SIZE = 2 # minimal buffer for low latency

async def websocket_client():
    uri = "ws://localhost:8080/ws"
    print("AR Training Voice Test (Audio Enabled)")
    print("=" * 50)
    print("Connecting to server...")

    try:
        async with websockets.connect(uri, ping_interval=None) as ws:
            print("Connected successfully!")
            print("Setting up audio streams...")
            
            # start session
            await ws.send(json.dumps({
                "type": "session.init",
                "scenario_id": "spill-l1",
                "trainee_id": "voice_test_user"
            }))

            # playback: write Vapi audio to an output stream with low latency settings
            out_stream = sd.OutputStream(
                samplerate=SR, 
                channels=CH, 
                dtype=DTYPE,
                blocksize=BLOCK_SIZE,
                latency='low'
            )
            out_stream.start()
            print("Audio output stream started (low latency)")

            # mic capture: stream mic to server as raw PCM with small buffer
            q = asyncio.Queue(maxsize=BUFFER_SIZE)

            def mic_callback(indata, frames, time, status):
                if status:
                    # can uncomment for debugging audio issues
                    # print(status, file=sys.stderr)
                    pass
                try:
                    # put bytes into asyncio queue; drop if full
                    q.put_nowait(bytes(indata))
                except asyncio.QueueFull:
                    # drop frames if queue is full to prevent blocking
                    pass

            in_stream = sd.InputStream(
                samplerate=SR, 
                channels=CH, 
                dtype=DTYPE, 
                callback=mic_callback,
                blocksize=BLOCK_SIZE,
                latency='low'
            )
            in_stream.start()
            print("Microphone input stream started (low latency)")
            print("You should hear the agent speaking. Try talking!")
            print("Ctrl+C to quit")
            print()

            async def send_mic():
                """Send microphone audio chunks to the server"""
                chunk_count = 0
                while True:
                    chunk = await q.get()
                    await ws.send(chunk)
                    chunk_count += 1
                    if chunk_count % 50 == 0:  # log every ~1.5 seconds
                        print(f"Sent {chunk_count} audio chunks")

            async def recv_msgs():
                """Receive and handle messages from the server"""
                audio_chunk_count = 0
                while True:
                    msg = await ws.recv()
                    if isinstance(msg, (bytes, bytearray)):
                        # play TTS chunk from Vapi
                        try:
                            arr = np.frombuffer(msg, dtype=np.int16)
                            if len(arr) > 0:
                                out_stream.write(arr)
                                audio_chunk_count += 1
                                if audio_chunk_count % 10 == 0:
                                    print(f"Played {audio_chunk_count} audio chunks")
                        except Exception as e:
                            print(f"Audio playback error: {e}")
                    else:
                        # handle JSON messages
                        try:
                            data = json.loads(msg)
                            msg_type = data.get("type")
                            
                            if msg_type == "session.accept":
                                print(f"Session accepted (run: {data.get('run_id')})")
                                print(f"Current step: {data.get('instruction')}")
                                print("Start speaking to interact with the agent!")
                                
                            elif msg_type == "next_step":
                                print(f"Next step: {data.get('instruction')}")
                                print(f"Requirements: {data.get('requirements', [])}")
                                
                            elif msg_type == "feedback":
                                print(f"Feedback: {data.get('message')}")
                                
                            elif msg_type == "session.complete":
                                print(f"Training complete! Score: {data.get('score')}")
                                print(f"Summary: {data.get('summary')}")
                                
                            else:
                                print(f"Server message: {json.dumps(data, indent=2)}")
                                
                        except json.JSONDecodeError:
                            print(f"Invalid JSON received: {msg}")

            # run both audio tasks concurrently
            try:
                await asyncio.gather(send_mic(), recv_msgs())
            finally:
                # clean up audio streams
                in_stream.stop()
                out_stream.stop()
                in_stream.close()
                out_stream.close()
                print("Audio streams closed")

    except ConnectionRefusedError:
        print("Connection refused. Is the server running on localhost:8080?")
        print("Run: uvicorn main:app --reload --port 8080")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    try:
        print("Starting audio-enabled voice test...")
        print("Make sure your microphone and speakers are working!")
        print()
        asyncio.run(websocket_client())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Startup error: {e}")
        print("Try installing audio dependencies: pip install sounddevice numpy")
