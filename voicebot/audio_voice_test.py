
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

# Load environment variables
load_dotenv()

# Audio configuration
SR = 48000  # 48kHz works best
CH = 1
DTYPE = "int16"
BLOCK_SIZE = 1024

async def simple_vapi_test():
    """Test Vapi directly"""
    api_key = os.getenv("VAPI_API_KEY")
    assistant_id = os.getenv("VAPI_ASSISTANT_ID")
    
    if not api_key or not assistant_id:
        print("❌ Missing VAPI_API_KEY or VAPI_ASSISTANT_ID in environment")
        print("Create a .env file with your Vapi credentials")
        return
    
    print("🎤 Simple Vapi Voice Test")
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
                    print("❌ No WebSocket URL received")
            else:
                print(f"❌ Vapi call failed: {response.status_code}")
                print(response.text)
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def test_voice_connection(ws_url):
    """Test the voice connection"""
    print("🌐 Connecting to Vapi...")
    
    ssl_context = ssl.create_default_context()
    ssl_context.load_verify_locations(cafile=certifi.where())
    
    try:
        async with websockets.connect(ws_url, ssl=ssl_context) as ws:
            print("✅ Connected to Vapi!")
            
            # Set up audio
            try:
                out_stream = sd.OutputStream(
                    samplerate=SR, channels=CH, dtype=DTYPE,
                    blocksize=BLOCK_SIZE, device=2  # AirPods Pro
                )
                out_stream.start()
                print("🔊 Audio output ready")
                
                # Simple mic setup
                mic_queue = asyncio.Queue(maxsize=10)
                
                def mic_callback(indata, frames, time, status):
                    try:
                        mic_queue.put_nowait(bytes(indata))
                    except asyncio.QueueFull:
                        pass
                
                in_stream = sd.InputStream(
                    samplerate=SR, channels=CH, dtype=DTYPE,
                    callback=mic_callback, blocksize=BLOCK_SIZE,
                    device=1  # AirPods Pro mic
                )
                in_stream.start()
                print("🎤 Microphone ready")
                print("🗣️ You can now speak! The assistant should respond.")
                print("Press Ctrl+C to stop")
                
                async def send_mic():
                    while True:
                        chunk = await mic_queue.get()
                        await ws.send(chunk)
                
                async def receive_audio():
                    audio_count = 0
                    async for msg in ws:
                        if isinstance(msg, bytes):
                            try:
                                arr = np.frombuffer(msg, dtype=np.int16)
                                if len(arr) > 0:
                                    out_stream.write(arr)
                                    audio_count += 1
                                    if audio_count % 50 == 0:
                                        print(f"🔊 Audio chunks: {audio_count}")
                            except Exception as e:
                                print(f"Audio error: {e}")
                        else:
                            try:
                                data = json.loads(msg)
                                print(f"📨 {data.get('type', 'message')}")
                            except:
                                print(f"📨 {msg[:50]}...")
                
                # Run both tasks
                await asyncio.gather(send_mic(), receive_audio())
                
            except Exception as e:
                print(f"❌ Audio setup error: {e}")
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
        print(f"❌ WebSocket error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(simple_vapi_test())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")

