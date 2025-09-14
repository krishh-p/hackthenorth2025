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
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="Server Audio Voicebot")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            let ws = null;
            let mediaRecorder = null;
            let audioContext = null;
            let isRecording = false;
            
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
            
            // Optimized audio playback with minimal latency
            function playAudioChunk(base64Data) {
                try {
                    if (!audioContext) {
                        audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    }
                    
                    if (audioContext.state === 'suspended') {
                        audioContext.resume();
                    }
                    
                    // Decode base64 to PCM
                    const binaryString = atob(base64Data);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    
                    if (bytes.length % 2 !== 0) return;
                    
                    const pcmData = new Int16Array(bytes.buffer);
                    const audioBuffer = audioContext.createBuffer(1, pcmData.length, 16000);
                    const channelData = audioBuffer.getChannelData(0);
                    
                    // Convert and play immediately
                    for (let i = 0; i < pcmData.length; i++) {
                        channelData[i] = (pcmData[i] / 32768.0) * 3.0; // 3x volume
                    }
                    
                    const source = audioContext.createBufferSource();
                    source.buffer = audioBuffer;
                    source.connect(audioContext.destination);
                    source.start();
                    
                } catch (error) {
                    console.error('Audio playback error:', error);
                }
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
                    addMessage('Connected to AI voice assistant');
                    btn.textContent = 'Connected';
                    document.getElementById('recordBtn').disabled = false;
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'audio_chunk') {
                        playAudioChunk(data.data);
                    } else if (data.type === 'vapi_message') {
                        const vapiData = data.data;
                        if (vapiData.type === 'speech-update') {
                            if (vapiData.status === 'started') {
                                updateStatus('🎤 AI is speaking...', 'speaking');
                            } else if (vapiData.status === 'ended') {
                                updateStatus('🟢 Your turn to speak!', 'connected');
                            }
                        }
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
            
            async function startRecording() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ 
                        audio: { 
                            sampleRate: 16000,
                            channelCount: 1,
                            echoCancellation: true,
                            noiseSuppression: true
                        } 
                    });
                    
                    mediaRecorder = new MediaRecorder(stream, {
                        mimeType: 'audio/webm;codecs=opus'
                    });
                    
                    mediaRecorder.ondataavailable = function(event) {
                        if (event.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
                            const reader = new FileReader();
                            reader.onload = function() {
                                const arrayBuffer = reader.result;
                                const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
                                ws.send(JSON.stringify({
                                    type: 'audio_data',
                                    data: base64
                                }));
                            };
                            reader.readAsArrayBuffer(event.data);
                        }
                    };
                    
                    mediaRecorder.start(100); // 100ms chunks
                    isRecording = true;
                    
                    document.getElementById('recordBtn').textContent = 'Recording...';
                    document.getElementById('recordBtn').disabled = true;
                    addMessage('🎤 Recording started - speak now!');
                    
                } catch (error) {
                    addMessage('Microphone access error: ' + error.message);
                }
            }
        </script>
    </body>
    </html>
    """)

@app.websocket("/ws/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    """WebSocket endpoint for voice chat"""
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
            return
        
        # Handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "audio_data":
                    # Forward audio to Vapi
                    if call_id in audio_manager.vapi_connections:
                        try:
                            audio_data = base64.b64decode(message.get("data", ""))
                            await audio_manager.vapi_connections[call_id].send(audio_data)
                        except Exception as e:
                            logger.error(f"Error forwarding audio to Vapi: {e}")
                            
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    finally:
        # Cleanup
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
    print("🚀 Starting Server-Side Audio Voicebot")
    print("=" * 50)
    print("✅ Server-side audio processing")
    print("🌐 Optimized for deployment")
    print("🎤 Minimal browser audio complexity")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
