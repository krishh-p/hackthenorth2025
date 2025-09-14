#!/usr/bin/env python3
"""
Server-side audio processing version
Moves all audio handling to the server to avoid browser limitations
"""
import asyncio
import json
import websockets
import ssl
import certifi
import httpx
import os
import base64
# import numpy as np  # Not needed for cloud version
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="Professional Audio Voicebot")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve AudioWorklet files
@app.get("/worklets/{filename}")
async def serve_worklet(filename: str):
    """Serve AudioWorklet files"""
    worklet_path = f"worklets/{filename}"
    if os.path.exists(worklet_path):
        return FileResponse(worklet_path, media_type="application/javascript")
    return {"error": "Worklet not found"}

class ServerAudioManager:
    """Handles all audio processing on server side"""
    
    def __init__(self):
        self.vapi_connections = {}
        self.client_connections = {}
        
    async def create_vapi_call(self):
        """Create Vapi call and return WebSocket URL"""
        api_key = os.getenv("VAPI_API_KEY")
        assistant_id = os.getenv("VAPI_ASSISTANT_ID")
        
        if not api_key or not assistant_id:
            raise Exception("Missing VAPI_API_KEY or VAPI_ASSISTANT_ID")
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.vapi.ai/call",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "assistantId": assistant_id,
                    "transport": {
                        "provider": "vapi.websocket",
                        "options": {
                            "audio": {
                                "sampleRate": 16000,
                                "encoding": "linear16",
                                "channels": 1
                            }
                        }
                    }
                }
            )
            
            if response.status_code == 201:
                call_data = response.json()
                return call_data.get("transport", {}).get("websocketCallUrl")
            else:
                raise Exception(f"Failed to create call: {response.status_code}")
    
    async def connect_to_vapi(self, call_id):
        """Connect to Vapi WebSocket"""
        try:
            vapi_url = await self.create_vapi_call()
            if not vapi_url:
                return False
                
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            vapi_ws = await websockets.connect(vapi_url, ssl=ssl_context)
            self.vapi_connections[call_id] = vapi_ws
            
            # Handle Vapi messages
            asyncio.create_task(self.handle_vapi_messages(call_id, vapi_ws))
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Vapi: {e}")
            return False
    
    async def handle_vapi_messages(self, call_id, vapi_ws):
        """Handle messages from Vapi"""
        try:
            async for message in vapi_ws:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "")
                    
                    # Send all Vapi messages to client
                    if call_id in self.client_connections:
                        await self.client_connections[call_id].send_text(json.dumps({
                            "type": "vapi_message",
                            "data": data
                        }))
                    
                    # Handle audio specifically
                    if msg_type == "audio" and data.get("format") == "raw":
                        audio_data = data.get("data", "")
                        if audio_data and call_id in self.client_connections:
                            # Send audio directly to client for immediate playback
                            await self.client_connections[call_id].send_text(json.dumps({
                                "type": "audio_chunk",
                                "data": audio_data
                            }))
                            
                except json.JSONDecodeError:
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Vapi connection closed for call {call_id}")
        except Exception as e:
            logger.error(f"Vapi message handler error: {e}")
        finally:
            if call_id in self.vapi_connections:
                del self.vapi_connections[call_id]

# Global manager
audio_manager = ServerAudioManager()

@app.get("/")
async def demo_page():
    """Optimized demo page with server-side audio processing"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Voicebot Demo - Hack the North 2025</title>
        <style>
            body { 
                font-family: 'Segoe UI', sans-serif; 
                max-width: 900px; 
                margin: 30px auto; 
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
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
                font-size: 3em;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4, #feca57);
                background-size: 300% 300%;
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                animation: gradientShift 3s ease infinite;
            }
            @keyframes gradientShift {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            .status { 
                padding: 20px; 
                margin: 20px 0; 
                border-radius: 15px; 
                font-weight: bold;
                text-align: center;
                transition: all 0.3s ease;
                font-size: 1.2em;
            }
            .status.connected { 
                background: linear-gradient(45deg, #4CAF50, #45a049);
                box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
            }
            .status.disconnected { 
                background: linear-gradient(45deg, #f44336, #d32f2f);
                box-shadow: 0 4px 15px rgba(244, 67, 54, 0.3);
            }
            .status.speaking { 
                background: linear-gradient(45deg, #ff9800, #f57c00);
                box-shadow: 0 4px 15px rgba(255, 152, 0, 0.3);
                animation: pulse 1.5s infinite;
            }
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.02); }
                100% { transform: scale(1); }
            }
            
            .controls {
                display: flex;
                justify-content: center;
                gap: 20px;
                margin: 30px 0;
                flex-wrap: wrap;
            }
            
            button { 
                padding: 15px 30px; 
                font-size: 18px; 
                border: none; 
                border-radius: 50px; 
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
                min-width: 150px;
            }
            
            .connect-btn {
                background: linear-gradient(45deg, #4CAF50, #45a049);
                color: white;
            }
            .connect-btn:hover:not(:disabled) {
                transform: translateY(-3px);
                box-shadow: 0 6px 20px rgba(76, 175, 80, 0.4);
            }
            .connect-btn:disabled {
                background: #666;
                cursor: not-allowed;
                transform: none;
            }
            
            .record-btn {
                background: linear-gradient(45deg, #ff4444, #cc0000);
                color: white;
            }
            .record-btn:hover:not(:disabled) {
                transform: translateY(-3px);
                box-shadow: 0 6px 20px rgba(255, 68, 68, 0.4);
            }
            .record-btn:disabled {
                background: #666;
                cursor: not-allowed;
            }
            
            .messages {
                background: rgba(0,0,0,0.3);
                padding: 25px;
                border-radius: 15px;
                max-height: 400px;
                overflow-y: auto;
                margin-top: 30px;
                border: 1px solid rgba(255,255,255,0.1);
            }
            .message {
                margin: 12px 0;
                padding: 10px 15px;
                border-radius: 8px;
                background: rgba(255,255,255,0.1);
                border-left: 4px solid #4CAF50;
            }
            
            .hero {
                text-align: center;
                margin: 30px 0;
                padding: 25px;
                background: rgba(255,255,255,0.1);
                border-radius: 15px;
                border: 1px solid rgba(255,255,255,0.2);
            }
            .hero h2 {
                margin-bottom: 15px;
                font-size: 1.8em;
            }
            .hero p {
                font-size: 1.1em;
                opacity: 0.9;
            }
            
            .feature-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }
            .feature {
                background: rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 15px;
                text-align: center;
                border: 1px solid rgba(255,255,255,0.2);
            }
            .feature h3 {
                margin-bottom: 10px;
                font-size: 1.3em;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎤 AI Voice Assistant</h1>
            
            <div class="hero">
                <h2>🚀 Next-Generation Voice AI</h2>
                <p>Experience seamless voice interaction powered by advanced AI technology</p>
            </div>
            
            <div id="status" class="status disconnected">
                🔴 Ready to Connect
            </div>
            
            <div class="controls">
                <button id="connectBtn" class="connect-btn" onclick="connect()">
                    Connect to AI
                </button>
                <button id="recordBtn" class="record-btn" onclick="startRecording()" disabled>
                    Start Recording
                </button>
            </div>
            
            <div class="feature-grid">
                <div class="feature">
                    <h3>🎯 Real-time Processing</h3>
                    <p>Instant voice recognition and response</p>
                </div>
                <div class="feature">
                    <h3>🧠 Smart AI</h3>
                    <p>Advanced natural language understanding</p>
                </div>
                <div class="feature">
                    <h3>🔊 Clear Audio</h3>
                    <p>High-quality voice synthesis</p>
                </div>
            </div>
            
            <div class="messages" id="messages">
                <div class="message">System ready - Click Connect to begin</div>
            </div>
        </div>

        <script>
            // Professional audio system with AudioWorklet and jitter buffer
            let ws = null;
            let audioContext = null;
            let outNode = null;
            
            // Jitter buffer state
            let playQueue = [];
            let playhead = 0;           // seconds (AudioContext time)
            const BUFFER_AHEAD = 0.25;  // 250ms headroom for smooth playback
            const CHUNK_SAMPLES = 320;  // 20ms @ 16k
            const SR_IN = 16000;
            
            function addMessage(msg) {
                const messages = document.getElementById('messages');
                const div = document.createElement('div');
                div.className = 'message';
                div.innerHTML = '<strong>' + new Date().toLocaleTimeString() + ':</strong> ' + msg;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
            }
            
            function updateStatus(text, className) {
                const status = document.getElementById('status');
                status.textContent = text;
                status.className = 'status ' + className;
            }
            
            function ensureAudioCtx() {
                if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
                if (audioContext.state === 'suspended') audioContext.resume();
            }
            
            // Professional jitter buffer for smooth playback
            function schedulePcm16(base64Data) {
                ensureAudioCtx();

                // decode base64 -> Int16Array (PCM16 @ 16k)
                const bin = atob(base64Data);
                const bytes = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
                if (bytes.length % 2 !== 0) return;
                const pcm16 = new Int16Array(bytes.buffer);

                // Convert to Float32 for AudioBuffer
                const float = new Float32Array(pcm16.length);
                for (let i = 0; i < pcm16.length; i++) {
                    float[i] = Math.max(-1, Math.min(1, pcm16[i] / 32768)) * 2.5; // 2.5x volume boost
                }

                const buf = audioContext.createBuffer(1, float.length, SR_IN);
                buf.copyToChannel(float, 0, 0);

                // Initialize playhead once a little in the future
                const now = audioContext.currentTime;
                if (playhead < now + 0.01) playhead = now + BUFFER_AHEAD;

                const src = audioContext.createBufferSource();
                src.buffer = buf;
                src.connect(audioContext.destination);

                // duration in seconds at 16k: samples / 16000
                const dur = float.length / SR_IN;
                src.start(playhead);
                playhead += dur;
            }
            
            function connect() {
                const btn = document.getElementById('connectBtn');
                btn.disabled = true;
                btn.textContent = 'Connecting...';
                
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = protocol + '//' + window.location.host + '/ws/demo_call';
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function() {
                    updateStatus('🟢 Connected - Ready to speak!', 'connected');
                    addMessage('Connected to professional AI voice system');
                    btn.textContent = 'Connected';
                    document.getElementById('recordBtn').disabled = false;
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'audio_chunk') {
                        schedulePcm16(data.data); // Use professional jitter buffer
                    } else if (data.type === 'vapi_message') {
                        const vapiData = data.data;
                        if (vapiData.type === 'speech-update') {
                            if (vapiData.status === 'started') {
                                updateStatus('🎤 AI is speaking...', 'speaking');
                            } else if (vapiData.status === 'ended') {
                                updateStatus('🟢 Your turn to speak!', 'connected');
                            }
                        }
                    } else if (data.type === 'ping') {
                        // Keep-alive ping, no action needed
                    }
                };
                
                ws.onclose = function() {
                    updateStatus('🔴 Disconnected', 'disconnected');
                    addMessage('Disconnected from AI assistant');
                    btn.disabled = false;
                    btn.textContent = 'Connect to AI';
                    document.getElementById('recordBtn').disabled = true;
                };
                
                ws.onerror = function(error) {
                    addMessage('Connection error occurred');
                    btn.disabled = false;
                    btn.textContent = 'Connect to AI';
                };
            }
            
            // Professional AudioWorklet-based recording
            async function startRecording() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({
                        audio: { 
                            channelCount: 1, 
                            echoCancellation: true, 
                            noiseSuppression: true,
                            autoGainControl: true
                        }
                    });

                    if (!audioContext) {
                        audioContext = new (window.AudioContext || window.webkitAudioContext)();
                        await audioContext.audioWorklet.addModule('/worklets/capture-16k.js');
                    }

                    const src = audioContext.createMediaStreamSource(stream);
                    const worklet = new AudioWorkletNode(audioContext, 'capture-16k');
                    src.connect(worklet);
                    
                    worklet.port.onmessage = (ev) => {
                        if (ws && ws.readyState === WebSocket.OPEN) {
                            // Send binary ArrayBuffer (PCM16 mono 16k) directly
                            ws.send(ev.data);
                        }
                    };

                    document.getElementById('recordBtn').textContent = 'Recording...';
                    document.getElementById('recordBtn').disabled = true;
                    addMessage('🎤 Professional audio capture active - speak now!');
                    
                } catch (error) {
                    addMessage('Microphone access error: ' + error.message);
                    console.error('Recording error:', error);
                }
            }
        </script>
    </body>
    </html>
    """)

PING_INTERVAL = 20

@app.websocket("/ws/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    """Professional WebSocket endpoint with binary audio support"""
    await websocket.accept()
    audio_manager.client_connections[call_id] = websocket
    
    try:
        # Connect to Vapi
        connected = await audio_manager.connect_to_vapi(call_id)
        if not connected:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Failed to connect to Vapi"
            }))
            await websocket.close()
            return

        async def keepalive():
            """Keep connection alive with periodic pings"""
            while websocket.application_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
                await asyncio.sleep(PING_INTERVAL)

        ka_task = asyncio.create_task(keepalive())
        
        # Handle client messages
        while True:
            try:
                # Prefer binary mic audio (PCM16 data)
                msg = await websocket.receive()
                
                if "bytes" in msg and msg["bytes"] is not None:
                    # Binary PCM16 data from AudioWorklet
                    data_bytes = msg["bytes"]
                    vapi_ws = audio_manager.vapi_connections.get(call_id)
                    if vapi_ws:
                        try:
                            # Forward binary PCM16 directly to Vapi
                            await vapi_ws.send(data_bytes)
                        except Exception as e:
                            logger.error(f"Error forwarding binary to Vapi: {e}")
                            
                elif "text" in msg and msg["text"] is not None:
                    # Handle control messages if needed
                    try:
                        message = json.loads(msg["text"])
                        # Process any control commands here
                    except json.JSONDecodeError:
                        pass
                else:
                    break
                    
            except WebSocketDisconnect:
                logger.info(f"Client WebSocket disconnected: {call_id}")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    finally:
        # Cleanup
        ka_task.cancel()
        if call_id in audio_manager.client_connections:
            del audio_manager.client_connections[call_id]
        if call_id in audio_manager.vapi_connections:
            try:
                await audio_manager.vapi_connections[call_id].close()
                del audio_manager.vapi_connections[call_id]
            except:
                pass

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("🚀 Starting Professional Audio Voicebot")
    print("=" * 50)
    print("✅ AudioWorklet PCM16 capture")
    print("🎤 Professional jitter buffer")
    print("🌐 Binary WebSocket transport")
    print("=" * 50)
    
    uvicorn.run("fastapi_server_cloud:app", host="0.0.0.0", port=port, log_level="info")
