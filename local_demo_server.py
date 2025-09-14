#!/usr/bin/env python3
"""
Hybrid Demo Server - Web interface with local audio processing
Combines your working audio_voice_test.py with a web demo interface
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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import threading
import queue
import uvicorn

load_dotenv()

# Audio configs (same as your working script)
SR = 16000
DTYPE = "int16"
BLOCK_SIZE = 320

# Global state
vapi_ws = None
audio_queue = queue.Queue()
is_recording = False
demo_websocket = None

app = FastAPI(title="Local Audio Demo")

class VapiAudioHandler:
    """Handles Vapi audio connection using your working local approach"""
    
    def __init__(self):
        self.vapi_ws = None
        self.is_connected = False
        
    async def connect_to_vapi(self):
        """Connect to Vapi using your working method"""
        api_key = os.getenv("VAPI_API_KEY")
        assistant_id = os.getenv("VAPI_ASSISTANT_ID")
        
        if not api_key or not assistant_id:
            print("Missing VAPI_API_KEY or VAPI_ASSISTANT_ID")
            return False
            
        try:
            # Start Vapi call (same as your working script)
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
                        print(f"✅ Vapi call created, connecting to: {ws_url}")
                        
                        # Connect to Vapi WebSocket
                        ssl_context = ssl.create_default_context(cafile=certifi.where())
                        self.vapi_ws = await websockets.connect(ws_url, ssl=ssl_context)
                        self.is_connected = True
                        
                        # Start audio handling
                        await self.handle_vapi_connection()
                        return True
                else:
                    print(f"❌ Failed to create call: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    async def handle_vapi_connection(self):
        """Handle Vapi WebSocket messages (same as your working script)"""
        global is_recording, demo_websocket
        
        try:
            # Start local audio input/output
            self.start_audio_streams()
            
            async for message in self.vapi_ws:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "")
                    
                    if msg_type == "speech-update":
                        if data.get("status") == "started":
                            print("🎤 AI speaking...")
                            if demo_websocket:
                                await demo_websocket.send_text(json.dumps({"type": "ai_speaking", "status": "started"}))
                        elif data.get("status") == "ended":
                            print("✅ AI finished")
                            if demo_websocket:
                                await demo_websocket.send_text(json.dumps({"type": "ai_speaking", "status": "ended"}))
                    
                    elif msg_type == "audio" and data.get("format") == "raw":
                        # Play audio using local sounddevice (your working method)
                        audio_data = data.get("data", "")
                        if audio_data:
                            self.play_audio_chunk(audio_data)
                    
                    elif msg_type == "status-update":
                        print(f"📊 Status: {data}")
                        if demo_websocket:
                            await demo_websocket.send_text(json.dumps({"type": "status", "data": data}))
                            
                except json.JSONDecodeError:
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Vapi connection closed")
            self.is_connected = False
        except Exception as e:
            print(f"❌ Vapi handler error: {e}")
            self.is_connected = False
    
    def start_audio_streams(self):
        """Start local audio input/output (your working method)"""
        global is_recording
        
        def audio_callback(indata, outdata, frames, time, status):
            """Audio callback for real-time processing"""
            if status:
                print(f"Audio status: {status}")
            
            # Send microphone input to Vapi
            if self.is_connected and self.vapi_ws:
                try:
                    # Convert to bytes and send (same as your working script)
                    audio_bytes = indata.astype(DTYPE).tobytes()
                    asyncio.create_task(self.vapi_ws.send(audio_bytes))
                except:
                    pass
            
            # Clear output (Vapi audio is played separately)
            outdata.fill(0)
        
        # Start audio stream (same parameters as your working script)
        print("🎤 Starting local audio streams...")
        is_recording = True
        
        with sd.Stream(
            samplerate=SR,
            blocksize=BLOCK_SIZE,
            dtype=DTYPE,
            channels=1,
            callback=audio_callback
        ):
            print("🎉 Audio streams active - speak now!")
            # Keep stream alive
            while self.is_connected:
                asyncio.sleep(0.1)
    
    def play_audio_chunk(self, base64_data):
        """Play audio chunk using sounddevice (your working method)"""
        try:
            import base64
            audio_bytes = base64.b64decode(base64_data)
            audio_array = np.frombuffer(audio_bytes, dtype=DTYPE)
            
            # Play using sounddevice (same as your working script)
            sd.play(audio_array, samplerate=SR)
            
        except Exception as e:
            print(f"Audio playback error: {e}")

# Global handler instance
vapi_handler = VapiAudioHandler()

@app.get("/")
async def demo_page():
    """Clean demo interface"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Local Audio Demo - Hack the North 2025</title>
        <style>
            body { 
                font-family: 'Segoe UI', sans-serif; 
                max-width: 800px; 
                margin: 50px auto; 
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .container {
                background: rgba(255,255,255,0.1);
                padding: 40px;
                border-radius: 20px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            }
            h1 { 
                text-align: center; 
                margin-bottom: 30px;
                font-size: 2.5em;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            .status { 
                padding: 15px; 
                margin: 15px 0; 
                border-radius: 10px; 
                font-weight: bold;
                text-align: center;
                transition: all 0.3s ease;
            }
            .status.connected { background: rgba(76, 175, 80, 0.3); }
            .status.disconnected { background: rgba(244, 67, 54, 0.3); }
            .status.speaking { background: rgba(255, 193, 7, 0.3); }
            
            button { 
                display: block;
                width: 200px;
                margin: 20px auto; 
                padding: 15px 30px; 
                font-size: 18px; 
                border: none; 
                border-radius: 50px; 
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            
            .connect-btn {
                background: linear-gradient(45deg, #4CAF50, #45a049);
                color: white;
            }
            .connect-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(76, 175, 80, 0.4);
            }
            .connect-btn:disabled {
                background: #666;
                cursor: not-allowed;
                transform: none;
            }
            
            .messages {
                background: rgba(0,0,0,0.2);
                padding: 20px;
                border-radius: 10px;
                max-height: 300px;
                overflow-y: auto;
                margin-top: 20px;
            }
            .message {
                margin: 10px 0;
                padding: 8px 12px;
                border-radius: 5px;
                background: rgba(255,255,255,0.1);
            }
            
            .instructions {
                background: rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎤 Voice AI Demo</h1>
            
            <div class="instructions">
                <h3>🚀 Professional Audio Quality</h3>
                <p>This demo uses local audio processing for crystal-clear voice interaction</p>
            </div>
            
            <div id="status" class="status disconnected">
                🔴 Disconnected - Click Connect to Start
            </div>
            
            <button id="connectBtn" class="connect-btn" onclick="connect()">
                Connect to AI
            </button>
            
            <div class="messages" id="messages"></div>
        </div>

        <script>
            let ws = null;
            
            function addMessage(msg) {
                const messages = document.getElementById('messages');
                const div = document.createElement('div');
                div.className = 'message';
                div.textContent = new Date().toLocaleTimeString() + ': ' + msg;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
            }
            
            function updateStatus(text, isConnected, isSpeaking = false) {
                const status = document.getElementById('status');
                status.textContent = text;
                status.className = 'status ' + (isSpeaking ? 'speaking' : (isConnected ? 'connected' : 'disconnected'));
            }
            
            function connect() {
                const btn = document.getElementById('connectBtn');
                btn.disabled = true;
                btn.textContent = 'Connecting...';
                
                ws = new WebSocket('ws://localhost:8000/ws');
                
                ws.onopen = function() {
                    updateStatus('🟢 Connected - AI is ready!', true);
                    addMessage('Connected to local audio system');
                    btn.textContent = 'Connected';
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'ai_speaking') {
                        if (data.status === 'started') {
                            updateStatus('🎤 AI is speaking...', true, true);
                        } else if (data.status === 'ended') {
                            updateStatus('🟢 Connected - Your turn to speak!', true);
                        }
                    } else if (data.type === 'status') {
                        addMessage('Status: ' + JSON.stringify(data.data));
                    }
                };
                
                ws.onclose = function() {
                    updateStatus('🔴 Disconnected', false);
                    addMessage('Disconnected from audio system');
                    btn.disabled = false;
                    btn.textContent = 'Connect to AI';
                };
                
                ws.onerror = function(error) {
                    addMessage('Connection error: ' + error);
                    btn.disabled = false;
                    btn.textContent = 'Connect to AI';
                };
            }
        </script>
    </body>
    </html>
    """)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for demo interface"""
    global demo_websocket
    
    await websocket.accept()
    demo_websocket = websocket
    
    try:
        # Start Vapi connection when demo connects
        await websocket.send_text(json.dumps({"type": "status", "message": "Starting Vapi connection..."}))
        
        # Connect to Vapi in background
        asyncio.create_task(vapi_handler.connect_to_vapi())
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any demo commands here if needed
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        demo_websocket = None

if __name__ == "__main__":
    print("🚀 Starting Local Audio Demo Server")
    print("=" * 40)
    print("✅ Uses your working local audio processing")
    print("🌐 Provides clean web interface for demos")
    print("🎤 Crystal clear audio quality")
    print("=" * 40)
    print("\n🌐 Open http://localhost:8000 for demo interface")
    print("🎯 Perfect for hackathon presentations!\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
