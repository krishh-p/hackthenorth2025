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
                    "transport": {"provider": "vapi.websocket"}
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
                    # Handle binary audio data
                    if isinstance(message, bytes):
                        # Raw binary audio from Vapi - convert to base64 for client
                        import base64
                        audio_b64 = base64.b64encode(message).decode('utf-8')
                        if call_id in self.client_connections:
                            await self.client_connections[call_id].send_text(json.dumps({
                                "type": "audio_chunk",
                                "data": audio_b64
                            }))
                        continue
                    
                    # Handle text/JSON messages
                    data = json.loads(message)
                    msg_type = data.get("type", "")
                    
                    # Send all Vapi messages to client
                    if call_id in self.client_connections:
                        await self.client_connections[call_id].send_text(json.dumps({
                            "type": "vapi_message",
                            "data": data
                        }))
                    
                    # Handle audio specifically (legacy format)
                    if msg_type == "audio" and data.get("format") == "raw":
                        audio_data = data.get("data", "")
                        if audio_data and call_id in self.client_connections:
                            # Send audio directly to client for immediate playback
                            await self.client_connections[call_id].send_text(json.dumps({
                                "type": "audio_chunk",
                                "data": audio_data
                            }))
                            
                except json.JSONDecodeError:
                    # Skip non-JSON messages
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
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0a0a0a;
                color: #ffffff;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                line-height: 1.6;
            }
            
            .container {
                max-width: 420px;
                width: 90%;
                background: #111111;
                border: 1px solid #222222;
                border-radius: 12px;
                padding: 32px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.4);
            }
            
            h1 { 
                text-align: center; 
                margin-bottom: 8px;
                font-size: 20px;
                font-weight: 600;
                color: #ffffff;
                letter-spacing: -0.01em;
            }
            
            .subtitle {
                text-align: center;
                margin-bottom: 32px;
                color: #888888;
                font-size: 14px;
                font-weight: 400;
            }
            
            .status { 
                padding: 12px 16px; 
                margin-bottom: 24px; 
                border-radius: 8px; 
                font-weight: 500;
                text-align: center;
                transition: all 0.2s ease;
                font-size: 14px;
            }
            
            .status.connected { 
                background: #0d1f0d;
                border: 1px solid #22c55e;
                color: #4ade80;
            }
            
            .status.disconnected { 
                background: #1f0d0d;
                border: 1px solid #ef4444;
                color: #f87171;
            }
            
            .status.speaking { 
                background: #1f1a0d;
                border: 1px solid #f59e0b;
                color: #fbbf24;
                animation: pulse 2s infinite;
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.8; }
            }
            
            .controls {
                display: flex;
                flex-direction: column;
                gap: 12px;
                margin-bottom: 24px;
            }
            
            .btn { 
                padding: 14px 20px; 
                font-size: 14px; 
                border: none; 
                border-radius: 8px; 
                cursor: pointer;
                transition: all 0.2s ease;
                font-weight: 500;
                position: relative;
                overflow: hidden;
            }
            
            .connect-btn {
                background: #ffffff;
                color: #000000;
            }
            .connect-btn:hover:not(:disabled) {
                background: #f5f5f5;
                transform: translateY(-1px);
            }
            .connect-btn:disabled {
                background: #333333;
                color: #666666;
                cursor: not-allowed;
                transform: none;
            }
            
            .disconnect-btn {
                background: #1a1a1a;
                color: #ffffff;
                border: 1px solid #333333;
            }
            .disconnect-btn:hover:not(:disabled) {
                background: #222222;
                border-color: #444444;
                transform: translateY(-1px);
            }
            .disconnect-btn:disabled {
                background: #111111;
                color: #555555;
                border-color: #222222;
                cursor: not-allowed;
            }
            
            .record-btn {
                background: #ef4444;
                color: #ffffff;
            }
            .record-btn:hover:not(:disabled) {
                background: #dc2626;
                transform: translateY(-1px);
            }
            .record-btn:disabled {
                background: #333333;
                color: #666666;
                cursor: not-allowed;
            }
            
            .test-btn {
                background: #1a1a1a;
                color: #888888;
                border: 1px solid #333333;
                font-size: 13px;
            }
            .test-btn:hover {
                background: #222222;
                color: #aaaaaa;
                border-color: #444444;
                transform: translateY(-1px);
            }
            
            .messages {
                background: #0a0a0a;
                border: 1px solid #222222;
                padding: 16px;
                border-radius: 8px;
                max-height: 200px;
                overflow-y: auto;
                font-size: 13px;
            }
            
            .message {
                padding: 6px 0;
                color: #cccccc;
                border-bottom: 1px solid #1a1a1a;
                line-height: 1.4;
            }
            
            .message:last-child {
                border-bottom: none;
            }
            
            .messages::-webkit-scrollbar {
                width: 4px;
            }
            
            .messages::-webkit-scrollbar-track {
                background: #111111;
            }
            
            .messages::-webkit-scrollbar-thumb {
                background: #333333;
                border-radius: 2px;
            }
            
            .messages::-webkit-scrollbar-thumb:hover {
                background: #444444;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AI Voice Assistant</h1>
            <div class="subtitle">Professional voice AI for seamless conversations</div>
            
            <div id="status" class="status disconnected">
                Ready to Connect
            </div>
            
            <div class="controls">
                <button id="connectBtn" class="connect-btn btn" onclick="connect()">
                    Connect
                </button>
                <button id="disconnectBtn" class="disconnect-btn btn" onclick="disconnect()" disabled>
                    Disconnect
                </button>
                <button id="recordBtn" class="record-btn btn" onclick="startRecording()" disabled>
                    Start Recording
                </button>
                <button id="testAudioBtn" class="test-btn btn" onclick="testAudio()">
                    Test Audio
                </button>
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
                try {
                    ensureAudioCtx();
                    console.log('🔊 Playing audio chunk, context state:', audioContext.state);

                    // decode base64 -> Int16Array (PCM16 @ 16k)
                    const bin = atob(base64Data);
                    const bytes = new Uint8Array(bin.length);
                    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
                    if (bytes.length % 2 !== 0) {
                        console.warn('⚠️ Invalid audio data length');
                        return;
                    }
                    const pcm16 = new Int16Array(bytes.buffer);
                    console.log('📊 Audio samples:', pcm16.length);

                    // Convert to Float32 for AudioBuffer
                    const float = new Float32Array(pcm16.length);
                    for (let i = 0; i < pcm16.length; i++) {
                        float[i] = Math.max(-1, Math.min(1, pcm16[i] / 32768)) * 4.0; // 4x volume boost for testing
                    }

                    const buf = audioContext.createBuffer(1, float.length, SR_IN);
                    buf.copyToChannel(float, 0, 0);

                    // Initialize playhead once a little in the future
                    const now = audioContext.currentTime;
                    if (playhead < now + 0.01) playhead = now + BUFFER_AHEAD;

                    const src = audioContext.createBufferSource();
                    src.buffer = buf;
                    
                    // Add gain node for extra volume
                    const gainNode = audioContext.createGain();
                    gainNode.gain.value = 3.0; // Extra volume boost
                    
                    src.connect(gainNode);
                    gainNode.connect(audioContext.destination);

                    // duration in seconds at 16k: samples / 16000
                    const dur = float.length / SR_IN;
                    src.start(playhead);
                    playhead += dur;
                    
                    console.log('✅ Audio scheduled at', playhead, 'duration:', dur);
                    // Removed continuous audio chunk messages for cleaner UI
                } catch (error) {
                    console.error('❌ Audio playback error:', error);
                    addMessage('🔊 Audio error: ' + error.message);
                }
            }
            
            function testAudio() {
                try {
                    ensureAudioCtx();
                    addMessage('🔊 Testing audio system...');
                    
                    // Generate a simple 440Hz sine wave (A note) for 1 second
                    const sampleRate = 16000;
                    const duration = 1.0; // 1 second
                    const samples = sampleRate * duration;
                    const buffer = audioContext.createBuffer(1, samples, sampleRate);
                    const channelData = buffer.getChannelData(0);
                    
                    // Generate sine wave
                    for (let i = 0; i < samples; i++) {
                        channelData[i] = Math.sin(2 * Math.PI * 440 * i / sampleRate) * 0.3; // 440Hz at 30% volume
                    }
                    
                    // Create and play the test sound
                    const source = audioContext.createBufferSource();
                    source.buffer = buffer;
                    
                    const gainNode = audioContext.createGain();
                    gainNode.gain.value = 2.0; // 2x volume
                    
                    source.connect(gainNode);
                    gainNode.connect(audioContext.destination);
                    
                    source.start();
                    
                    addMessage('✅ Test sound played! If you heard a tone, audio is working.');
                } catch (error) {
                    console.error('❌ Test audio failed:', error);
                    addMessage('❌ Audio test failed: ' + error.message);
                }
            }
            
            function connect() {
                const connectBtn = document.getElementById('connectBtn');
                const disconnectBtn = document.getElementById('disconnectBtn');
                connectBtn.disabled = true;
                connectBtn.textContent = 'Connecting...';
                
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = protocol + '//' + window.location.host + '/ws/demo_call';
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function() {
                    updateStatus('🟢 Connected - Ready to speak!', 'connected');
                    addMessage('Connected to professional AI voice system');
                    connectBtn.textContent = 'Connected';
                    connectBtn.disabled = true;
                    disconnectBtn.disabled = false;
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
                    connectBtn.disabled = false;
                    connectBtn.textContent = 'Connect to AI';
                    disconnectBtn.disabled = true;
                    document.getElementById('recordBtn').disabled = true;
                    document.getElementById('recordBtn').textContent = 'Start Recording';
                };
                
                ws.onerror = function(error) {
                    addMessage('Connection error occurred');
                    connectBtn.disabled = false;
                    connectBtn.textContent = 'Connect to AI';
                    disconnectBtn.disabled = true;
                };
            }
            
            function disconnect() {
                if (ws) {
                    ws.close();
                    addMessage('Manually disconnected from AI');
                }
            }
            
            // Professional AudioWorklet-based recording with fallback
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
                    }
                    
                    // Try AudioWorklet first
                    try {
                        console.log('🎤 Loading AudioWorklet...');
                        await audioContext.audioWorklet.addModule('/worklets/capture-16k.js');
                        
                        const src = audioContext.createMediaStreamSource(stream);
                        const worklet = new AudioWorkletNode(audioContext, 'capture-16k');
                        src.connect(worklet);
                        
                        worklet.port.onmessage = (ev) => {
                            if (ws && ws.readyState === WebSocket.OPEN) {
                                console.log('🎤 Sending mic data (AudioWorklet), size:', ev.data.byteLength);
                                ws.send(ev.data);
                            }
                        };

                        addMessage('🎤 AudioWorklet capture active - speak now!');
                        
                    } catch (workletError) {
                        console.warn('AudioWorklet failed, using ScriptProcessor fallback:', workletError);
                        
                        // Fallback to ScriptProcessor
                        const src = audioContext.createMediaStreamSource(stream);
                        const processor = audioContext.createScriptProcessor(1024, 1, 1);
                        
                        processor.onaudioprocess = (event) => {
                            if (ws && ws.readyState === WebSocket.OPEN) {
                                const inputData = event.inputBuffer.getChannelData(0);
                                
                                // Convert float32 to int16 PCM
                                const pcm16 = new Int16Array(inputData.length);
                                for (let i = 0; i < inputData.length; i++) {
                                    const s = Math.max(-1, Math.min(1, inputData[i]));
                                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                                }
                                
                                console.log('🎤 Sending mic data (ScriptProcessor), size:', pcm16.byteLength);
                                ws.send(pcm16.buffer);
                            }
                        };
                        
                        src.connect(processor);
                        processor.connect(audioContext.destination);
                        
                        addMessage('🎤 ScriptProcessor capture active - speak now!');
                    }

                    document.getElementById('recordBtn').textContent = 'Recording...';
                    document.getElementById('recordBtn').disabled = true;
                    
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
        
        try:
            # Handle client messages
            while True:
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
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            
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
