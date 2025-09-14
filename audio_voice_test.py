#!/usr/bin/env python3
"""
Simple direct Vapi voice test
"""
import asyncio
import json
import websockets
import ssl
import certifi
import httpx
import os
import sounddevice as sd
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# audio configs
SR = 16000
DTYPE = "int16"
BLOCK_SIZE = 320

async def simple_vapi_test():
    """Test Vapi directly"""
    api_key = os.getenv("VAPI_API_KEY")
    assistant_id = os.getenv("VAPI_ASSISTANT_ID")
    
    if not api_key or not assistant_id:
        print("Missing VAPI_API_KEY or VAPI_ASSISTANT_ID in environment")
        print("Create a .env file with your Vapi credentials")
        return
    
    print("Simple Vapi Voice Test")
    print("=" * 30)
    
    try:
        # Start Vapi call
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.vapi.ai/call",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "assistantId": assistant_id,
                    "transport": {"provider": "vapi.websocket"}
                }
            )
            
            if response.status_code == 201:
                call_data = response.json()
                ws_url = call_data.get("transport", {}).get("websocketCallUrl")
                
                if ws_url:
                    await test_voice_connection(ws_url)
                else:
                    print("No WebSocket URL received")
            else:
                print(f"Vapi call failed: {response.status_code}")
                print(response.text)
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

async def test_voice_connection(ws_url): 
    ssl_context = ssl.create_default_context()
    ssl_context.load_verify_locations(cafile=certifi.where())
    
    try:
        async with websockets.connect(ws_url, ssl=ssl_context) as ws:
            print("connected to Vapi!")
            
            # set up audio
            try:
                # get default device info to determine channels
                default_out = sd.query_devices(kind='output')
                default_in = sd.query_devices(kind='input')
                
                out_channels = min(default_out['max_output_channels'], 2) # use stereo if available, otherwise mono
                in_channels = 1 # always use mono for input
                
                print(f"Using output: {default_out['name']} ({out_channels} channels)")
                print(f"Using input: {default_in['name']} ({in_channels} channels)")
                
                out_stream = sd.OutputStream(
                    samplerate=SR, channels=out_channels, dtype=DTYPE,
                    blocksize=BLOCK_SIZE, latency='low'  # Use low latency for better responsiveness
                )
                out_stream.start()
                print("Audio output ready")
                
                # Improved mic setup with better queue management
                mic_queue = asyncio.Queue(maxsize=20)  # Larger buffer
                dropped_chunks = 0
                
                def mic_callback(indata, frames, time, status):
                    nonlocal dropped_chunks
                    if status:
                        print(f"Mic status: {status}")
                    try:
                        mic_queue.put_nowait(bytes(indata))
                    except asyncio.QueueFull:
                        dropped_chunks += 1
                        # Clear old data when queue is full
                        try:
                            mic_queue.get_nowait()  # Remove oldest
                            mic_queue.put_nowait(bytes(indata))  # Add newest
                        except asyncio.QueueEmpty:
                            pass
                        if dropped_chunks % 10 == 1:
                            print(f"⚠️  Mic buffer full, dropped {dropped_chunks} chunks")
                
                in_stream = sd.InputStream(
                    samplerate=SR, channels=1, dtype=DTYPE,
                    callback=mic_callback, blocksize=BLOCK_SIZE
                )
                in_stream.start()
                print("Microphone ready")
                print("You can now speak! The assistant should respond.")
                
                async def send_mic():
                    while True:
                        try:
                            # add timeout to prevent indefinite blocking
                            chunk = await asyncio.wait_for(mic_queue.get(), timeout=1.0)
                            await ws.send(chunk)
                            # small yield to prevent monopolizing the event loop
                            await asyncio.sleep(0)
                        except asyncio.TimeoutError:
                            # send silence if no mic data (keeps connection alive)
                            silence = np.zeros(BLOCK_SIZE, dtype=np.int16).tobytes()
                            await ws.send(silence)
                        except Exception as e:
                            print(f"Mic send error: {e}")
                            break
                
                async def receive_audio():
                    audio_count = 0
                    buffer_errors = 0
                    # pre-allocate stereo conversion array to reduce memory allocations
                    stereo_buffer = np.zeros((BLOCK_SIZE, 2), dtype=np.int16)
                    
                    async for msg in ws:
                        if isinstance(msg, bytes):
                            try:
                                arr = np.frombuffer(msg, dtype=np.int16)
                                if len(arr) > 0:
                                    # audio write with buffer overflow protection
                                    try:
                                        # use asyncio to prevent blocking on audio write
                                        def write_audio():
                                            if out_channels == 2 and len(arr.shape) == 1:
                                                # efficient stereo conversion using pre-allocated buffer
                                                if len(arr) <= BLOCK_SIZE:
                                                    stereo_buffer[:len(arr), 0] = arr
                                                    stereo_buffer[:len(arr), 1] = arr
                                                    out_stream.write(stereo_buffer[:len(arr)])
                                                else:
                                                    # handle larger chunks by splitting
                                                    mono_arr = arr.reshape(-1, 1)
                                                    stereo_arr = np.column_stack((mono_arr, mono_arr))
                                                    out_stream.write(stereo_arr)
                                            else:
                                                out_stream.write(arr.reshape(-1, 1))
                                        
                                        # execute audio write with timeout to prevent blocking
                                        await asyncio.wait_for(
                                            asyncio.get_event_loop().run_in_executor(None, write_audio),
                                            timeout=0.1  # 100ms timeout
                                        )
                                            
                                        audio_count += 1
                                        if audio_count % 100 == 0: # less frequent logging
                                            print(f"🔊 Audio chunks: {audio_count}")
                                            
                                    except (sd.PortAudioError, asyncio.TimeoutError) as e:
                                        buffer_errors += 1
                                        if buffer_errors % 20 == 1:
                                            if isinstance(e, asyncio.TimeoutError):
                                                print(f"⚠️  Audio write timeout #{buffer_errors} (output buffer full)")
                                            else:
                                                print(f"⚠️  Audio buffer issue #{buffer_errors}: {e}")
                                        # continue processing despite buffer errors
                                        
                            except Exception as e:
                                print(f"Audio processing error: {e}")
                        else:
                            try:
                                data = json.loads(msg)
                                msg_type = data.get('type', 'message')
                                print(f"📨 {msg_type}")
                                # handle call end gracefully
                                if 'ended' in msg_type or msg_type in ['hangup', 'error']:
                                    print("Call ended by server")
                                    break
                            except json.JSONDecodeError:
                                print(f"Raw: {str(msg)[:50]}...")
                        
                        # Yield control periodically to prevent blocking
                        if audio_count % 10 == 0:
                            await asyncio.sleep(0)
                
                # Run both tasks
                await asyncio.gather(send_mic(), receive_audio())
                
            except Exception as e:
                print(f"Audio setup error: {e}")
                print("Try: pip install sounddevice numpy")
            finally:
                try:
                    in_stream.stop()
                    out_stream.stop()
                    in_stream.close()
                    out_stream.close()
                except:
                    pass
                
    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(simple_vapi_test())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Error: {e}")