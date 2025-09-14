#!/usr/bin/env python3
"""
Cloud-ready FastAPI server for voicebot (Heroku compatible)
No local audio dependencies - uses browser-based audio via WebSocket
"""
import asyncio
import json
import websockets
import ssl
import certifi
import httpx
import os
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import base64

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Voicebot Chat API - Cloud Ready",
    description="FastAPI server for Vapi voicebot integration (Heroku compatible)",
    version="2.0.0"
)

# Add CORS middleware - more permissive for cloud deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ChatRequest(BaseModel):
    message: Optional[str] = None
    assistant_id: Optional[str] = None

class ChatResponse(BaseModel):
    success: bool
    message: str
    call_id: Optional[str] = None
    websocket_url: Optional[str] = None
    error: Optional[str] = None

class AudioMessage(BaseModel):
    type: str  # 'audio', 'control', 'text'
    data: Optional[str] = None  # base64 encoded audio or text
    format: Optional[str] = None  # 'wav', 'mp3', etc.

class ConnectionManager:
    """Manages WebSocket connections between clients and Vapi"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.vapi_connections: Dict[str, websockets.WebSocketServerProtocol] = {}
    
    async def connect(self, websocket: WebSocket, call_id: str):
        await websocket.accept()
        self.active_connections[call_id] = websocket
        logger.info(f"Client connected for call: {call_id}")
    
    def disconnect(self, call_id: str):
        if call_id in self.active_connections:
            del self.active_connections[call_id]
        if call_id in self.vapi_connections:
            # Close Vapi connection if exists
            asyncio.create_task(self.close_vapi_connection(call_id))
        logger.info(f"Client disconnected for call: {call_id}")
    
    async def close_vapi_connection(self, call_id: str):
        if call_id in self.vapi_connections:
            try:
                await self.vapi_connections[call_id].close()
                del self.vapi_connections[call_id]
            except Exception as e:
                logger.error(f"Error closing Vapi connection: {e}")
    
    async def send_to_client(self, call_id: str, message: dict):
        if call_id in self.active_connections:
            try:
                await self.active_connections[call_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to client {call_id}: {e}")
                self.disconnect(call_id)

# Global connection manager
manager = ConnectionManager()

class VapiService:
    """Service class to handle Vapi API interactions - cloud optimized"""
    
    def __init__(self):
        self.api_key = os.getenv("VAPI_API_KEY")
        self.default_assistant_id = os.getenv("VAPI_ASSISTANT_ID")
        
        if not self.api_key:
            logger.warning("VAPI_API_KEY not found in environment variables")
        if not self.default_assistant_id:
            logger.warning("VAPI_ASSISTANT_ID not found in environment variables")
    
    async def create_call(self, assistant_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new Vapi call and return call data"""
        if not self.api_key:
            raise HTTPException(status_code=500, detail="VAPI_API_KEY not configured")
        
        assistant_id = assistant_id or self.default_assistant_id
        if not assistant_id:
            raise HTTPException(status_code=400, detail="Assistant ID is required")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.vapi.ai/call",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "assistantId": assistant_id,
                        "transport": {"provider": "vapi.websocket"}
                    }
                )
                
                if response.status_code == 201:
                    call_data = response.json()
                    logger.info(f"Created Vapi call: {call_data.get('id', 'unknown')}")
                    return call_data
                else:
                    logger.error(f"Vapi call failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Vapi API error: {response.text}"
                    )
                    
        except httpx.RequestError as e:
            logger.error(f"Network error creating Vapi call: {e}")
            raise HTTPException(status_code=503, detail=f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating Vapi call: {e}")
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    
    async def connect_to_vapi(self, ws_url: str, call_id: str):
        """Connect to Vapi WebSocket and handle audio streaming"""
        ssl_context = ssl.create_default_context()
        ssl_context.load_verify_locations(cafile=certifi.where())
        
        try:
            async with websockets.connect(ws_url, ssl=ssl_context) as vapi_ws:
                manager.vapi_connections[call_id] = vapi_ws
                logger.info(f"✅ Connected to Vapi WebSocket for call: {call_id}")
                logger.info(f"Vapi WebSocket URL: {ws_url}")
                
                # Send connection established message to client
                await manager.send_to_client(call_id, {
                    "type": "vapi_connected",
                    "call_id": call_id,
                    "message": "Connected to Vapi - ready for audio!"
                })
                
                # Listen for messages from Vapi
                async for message in vapi_ws:
                    try:
                        if isinstance(message, bytes):
                            # Audio data from Vapi - forward to client
                            audio_b64 = base64.b64encode(message).decode('utf-8')
                            await manager.send_to_client(call_id, {
                                "type": "audio_from_vapi",
                                "data": audio_b64,
                                "format": "raw"
                            })
                        else:
                            # Text message from Vapi
                            try:
                                data = json.loads(message)
                                await manager.send_to_client(call_id, {
                                    "type": "message_from_vapi",
                                    "data": data
                                })
                            except json.JSONDecodeError:
                                await manager.send_to_client(call_id, {
                                    "type": "raw_message_from_vapi",
                                    "data": str(message)
                                })
                    except Exception as e:
                        logger.error(f"Error processing Vapi message: {e}")
                        
        except Exception as e:
            logger.error(f"Vapi WebSocket error for call {call_id}: {e}")
            await manager.send_to_client(call_id, {
                "type": "vapi_error",
                "error": str(e)
            })
        finally:
            if call_id in manager.vapi_connections:
                del manager.vapi_connections[call_id]

# Initialize Vapi service
vapi_service = VapiService()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Voicebot Chat API is running (Cloud Ready)", 
        "status": "healthy",
        "version": "2.0.0",
        "deployment": "cloud"
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "api_key_configured": bool(vapi_service.api_key),
        "assistant_id_configured": bool(vapi_service.default_assistant_id),
        "deployment_ready": True,
        "audio_handling": "browser_based"
    }

@app.post("/chat/start", response_model=ChatResponse)
async def start_chat(request: ChatRequest):
    """
    Start a new chat session with Vapi
    Returns call_id for WebSocket connection
    """
    try:
        call_data = await vapi_service.create_call(request.assistant_id)
        
        ws_url = call_data.get("transport", {}).get("websocketCallUrl")
        call_id = call_data.get("id")
        
        if not ws_url:
            return ChatResponse(
                success=False,
                message="Failed to get WebSocket URL from Vapi",
                error="No websocket URL in response"
            )
        
        # Store the Vapi WebSocket URL for later connection
        # We'll connect when the client connects to our WebSocket
        return ChatResponse(
            success=True,
            message="Chat session created - connect to WebSocket",
            call_id=call_id,
            websocket_url=f"/ws/{call_id}"  # Our WebSocket endpoint
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in start_chat: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.websocket("/ws/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    """
    WebSocket endpoint that proxies between browser and Vapi
    Handles browser-based audio streaming
    """
    await manager.connect(websocket, call_id)
    
    try:
        # Get the Vapi WebSocket URL for this call by creating a new session
        try:
            call_data = await vapi_service.create_call()
            vapi_ws_url = call_data.get("transport", {}).get("websocketCallUrl")
            
            await websocket.send_text(json.dumps({
                "type": "connected",
                "call_id": call_id,
                "message": "Connected to proxy server",
                "vapi_url": vapi_ws_url,
                "instructions": "Connection to Vapi will start automatically"
            }))
            
            # Automatically start Vapi connection
            if vapi_ws_url:
                asyncio.create_task(
                    vapi_service.connect_to_vapi(vapi_ws_url, call_id)
                )
            
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Failed to create Vapi session: {str(e)}"
            }))
        
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                message_type = message.get("type")
                
                if message_type == "connect_to_vapi":
                    # Client requests connection to Vapi
                    vapi_ws_url = message.get("vapi_url")
                    if vapi_ws_url and vapi_ws_url.startswith("wss://"):
                        # Start Vapi connection in background
                        asyncio.create_task(
                            vapi_service.connect_to_vapi(vapi_ws_url, call_id)
                        )
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"Invalid vapi_url: {vapi_ws_url}"
                        }))
                
                elif message_type == "audio_to_vapi":
                    # Forward audio data to Vapi
                    if call_id in manager.vapi_connections:
                        try:
                            # Decode base64 audio data
                            audio_data = base64.b64decode(message.get("data", ""))
                            
                            # Send raw binary data directly to Vapi (like the local version)
                            await manager.vapi_connections[call_id].send(audio_data)
                            
                            # Debug: Log successful sends occasionally
                            if hasattr(manager, '_audio_send_count'):
                                manager._audio_send_count += 1
                            else:
                                manager._audio_send_count = 1
                                
                            if manager._audio_send_count % 50 == 1:
                                logger.info(f"Sent {manager._audio_send_count} audio chunks to Vapi")
                                
                        except Exception as e:
                            logger.error(f"Error sending audio to Vapi: {e}")
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Not connected to Vapi"
                        }))
                
                elif message_type == "text_message":
                    # Handle text messages
                    text = message.get("text", "")
                    await websocket.send_text(json.dumps({
                        "type": "text_response",
                        "message": f"Received: {text}"
                    }))
                
                else:
                    # Echo unknown message types
                    await websocket.send_text(json.dumps({
                        "type": "echo",
                        "original": message
                    }))
                    
            except WebSocketDisconnect:
                logger.info(f"Client disconnected: {call_id}")
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                logger.error(f"Error in WebSocket handler: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Server error: {str(e)}"
                }))
                
    except Exception as e:
        logger.error(f"WebSocket error for call {call_id}: {e}")
    finally:
        manager.disconnect(call_id)

@app.post("/chat/text", response_model=ChatResponse)
async def text_chat(request: ChatRequest):
    """Simple text-based chat endpoint (works without Vapi)"""
    if not request.message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    try:
        # Simple echo response - replace with actual AI integration
        response_message = f"Cloud Echo: {request.message}"
        
        return ChatResponse(
            success=True,
            message=response_message
        )
        
    except Exception as e:
        logger.error(f"Error in text_chat: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Serve static files for web interface
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    # Directory doesn't exist - that's OK for API-only deployment
    pass

@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    """Simple demo page for testing browser audio"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Voicebot Demo</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .connected { background-color: #d4edda; color: #155724; }
            .disconnected { background-color: #f8d7da; color: #721c24; }
            button { padding: 10px 20px; margin: 5px; font-size: 16px; }
            #messages { height: 300px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; }
        </style>
    </head>
    <body>
        <h1>Voicebot Demo - Cloud Ready</h1>
        
        <div id="status" class="status disconnected">Disconnected</div>
        
        <div>
            <button onclick="connect()">Connect</button>
            <button onclick="disconnect()">Disconnect</button>
            <button onclick="startRecording()" id="recordBtn">Start Recording</button>
            <button onclick="stopRecording()" id="stopBtn" disabled>Stop Recording</button>
        </div>
        
        <div>
            <input type="text" id="textInput" placeholder="Type a message..." style="width: 70%;">
            <button onclick="sendText()">Send Text</button>
        </div>
        
        <div id="messages"></div>
        
        <script>
            let ws = null;
            let mediaRecorder = null;
            let audioChunks = [];
            
            function updateStatus(message, connected = false) {
                const status = document.getElementById('status');
                status.textContent = message;
                status.className = 'status ' + (connected ? 'connected' : 'disconnected');
            }
            
            function addMessage(message) {
                const messages = document.getElementById('messages');
                const div = document.createElement('div');
                div.textContent = new Date().toLocaleTimeString() + ': ' + message;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
            }
            
            async function connect() {
                try {
                    // First, start a Vapi session
                    addMessage('Starting Vapi session...');
                    const response = await fetch('/chat/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({})
                    });
                    
                    const data = await response.json();
                    
                    if (!data.success) {
                        addMessage('Error starting Vapi session: ' + (data.error || 'Unknown error'));
                        return;
                    }
                    
                    addMessage('Vapi session created: ' + data.call_id);
                    
                    // Connect to WebSocket with real call ID
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const wsUrl = protocol + '//' + window.location.host + '/ws/' + data.call_id;
                    
                    ws = new WebSocket(wsUrl);
                    
                    // Store the Vapi WebSocket URL for connection
                    window.vapiCallData = data;
                    
                } catch (error) {
                    addMessage('Error: ' + error.message);
                }
                
                ws.onopen = function() {
                    updateStatus('Connected to WebSocket', true);
                    addMessage('Connected to server');
                    
                    // Initialize audio context on user interaction
                    if (!window.audioContext) {
                        window.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    }
                    
                    // Resume audio context if suspended
                    if (window.audioContext.state === 'suspended') {
                        window.audioContext.resume();
                    }
                    
                    // Vapi connection is now handled automatically on server side
                    // No need to send connect_to_vapi message
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'audio_from_vapi') {
                        // Play the audio (removed spam log)
                        playAudioFromBase64(data.data);
                    } else if (data.type === 'vapi_connected') {
                        addMessage('🎉 Connected to Vapi! You can now speak.');
                        updateStatus('Connected to Vapi - Ready to chat!', true);
                    } else if (data.type === 'vapi_error') {
                        addMessage('❌ Vapi Error: ' + data.error);
                    } else if (data.type === 'message_from_vapi') {
                        // Only log important messages
                        const msgData = data.data;
                        if (msgData.type === 'speech-update') {
                            if (msgData.status === 'started') {
                                addMessage('🎤 AI is speaking...');
                            } else if (msgData.status === 'ended') {
                                addMessage('✅ AI finished speaking');
                            }
                        } else if (msgData.type === 'status-update') {
                            if (msgData.status === 'ended') {
                                addMessage('📞 Call ended: ' + msgData.endedReason);
                            }
                        }
                    } else {
                        // Log other important messages only
                        if (data.type !== 'connected') {
                            addMessage('Received: ' + JSON.stringify(data));
                        }
                    }
                };
                
                ws.onclose = function() {
                    updateStatus('Disconnected', false);
                    addMessage('Disconnected from server');
                };
                
                ws.onerror = function(error) {
                    addMessage('WebSocket error: ' + error);
                };
            }
            
            function disconnect() {
                if (ws) {
                    ws.close();
                    ws = null;
                }
            }
            
            function sendText() {
                const input = document.getElementById('textInput');
                if (ws && input.value) {
                    ws.send(JSON.stringify({
                        type: 'text_message',
                        text: input.value
                    }));
                    addMessage('Sent: ' + input.value);
                    input.value = '';
                }
            }
            
            async function startRecording() {
                try {
                    // Request high-quality audio stream with exact Vapi specs
                    const stream = await navigator.mediaDevices.getUserMedia({ 
                        audio: {
                            sampleRate: 48000, // Use browser's native rate, we'll resample
                            channelCount: 1,
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true,
                            latency: 0.01 // Request low latency
                        }
                    });
                    
                    // Initialize audio context with optimal settings
                    if (!window.audioContext) {
                        window.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                            sampleRate: 48000, // Match browser native
                            latencyHint: 'interactive'
                        });
                    }
                    
                    // Resume audio context if suspended
                    if (window.audioContext.state === 'suspended') {
                        await window.audioContext.resume();
                    }
                    
                    const source = window.audioContext.createMediaStreamSource(stream);
                    
                    // Create resampler to convert 48kHz to 16kHz for Vapi
                    const resamplerBufferSize = 1024; // Smaller for lower latency
                    const processor = window.audioContext.createScriptProcessor(resamplerBufferSize, 1, 1);
                    
                    let audioSentCount = 0;
                    let resampleBuffer = [];
                    const targetSampleRate = 16000;
                    const sourceSampleRate = window.audioContext.sampleRate;
                    const resampleRatio = sourceSampleRate / targetSampleRate;
                    
                    processor.onaudioprocess = function(e) {
                        if (ws && ws.readyState === WebSocket.OPEN) {
                            const inputData = e.inputBuffer.getChannelData(0);
                            
                            // Calculate RMS for voice detection
                            let rms = 0;
                            for (let i = 0; i < inputData.length; i++) {
                                rms += inputData[i] * inputData[i];
                            }
                            rms = Math.sqrt(rms / inputData.length);
                            
                            // Resample from browser sample rate to 16kHz
                            const outputLength = Math.floor(inputData.length / resampleRatio);
                            const resampledData = new Float32Array(outputLength);
                            
                            for (let i = 0; i < outputLength; i++) {
                                const sourceIndex = i * resampleRatio;
                                const index = Math.floor(sourceIndex);
                                const fraction = sourceIndex - index;
                                
                                // Linear interpolation for better quality
                                if (index + 1 < inputData.length) {
                                    resampledData[i] = inputData[index] * (1 - fraction) + inputData[index + 1] * fraction;
                                } else {
                                    resampledData[i] = inputData[index];
                                }
                            }
                            
                            // Voice enhancement and gain boost
                            const pcmData = new Int16Array(resampledData.length);
                            for (let i = 0; i < resampledData.length; i++) {
                                let sample = resampledData[i];
                                
                                // Apply good gain boost but not too much
                                sample *= 2.5; // 2.5x gain boost (was 4x, now reduced)
                                
                                // Apply noise gate - reduce background noise
                                if (Math.abs(sample) < 0.02) {
                                    sample *= 0.1; // Reduce quiet sounds (background noise)
                                }
                                
                                // Apply slight compression for better voice clarity
                                sample = sample > 0 ? Math.pow(sample, 0.8) : -Math.pow(-sample, 0.8);
                                
                                // Hard limiting to prevent clipping
                                sample = Math.max(-0.95, Math.min(0.95, sample));
                                
                                pcmData[i] = Math.round(sample * 32767);
                            }
                            
                            // Efficient binary conversion
                            const bytes = new Uint8Array(pcmData.buffer);
                            const base64 = btoa(String.fromCharCode.apply(null, bytes));
                            
                            ws.send(JSON.stringify({
                                type: 'audio_to_vapi',
                                data: base64
                            }));
                            
                            // Show voice level for debugging
                            audioSentCount++;
                            if (audioSentCount % 30 === 1) { // Every ~1 second
                                const voiceLevel = (rms * 100).toFixed(1);
                                addMessage(`🎤 Mic active (${audioSentCount} chunks, voice level: ${voiceLevel}%)`);
                            }
                        }
                    };
                    
                    source.connect(processor);
                    processor.connect(window.audioContext.destination);
                    
                    // Store references for cleanup
                    window.micStream = stream;
                    window.micProcessor = processor;
                    window.micSource = source;
                    
                    document.getElementById('recordBtn').disabled = true;
                    document.getElementById('stopBtn').disabled = false;
                    addMessage(`🎤 Recording started - ${sourceSampleRate}Hz → 16kHz resampling active`);
                    
                } catch (error) {
                    addMessage('Error accessing microphone: ' + error.message);
                    console.error('Microphone error:', error);
                }
            }
            
            function stopRecording() {
                // Clean up Web Audio API components
                if (window.micProcessor) {
                    window.micProcessor.disconnect();
                    window.micProcessor = null;
                }
                if (window.micSource) {
                    window.micSource.disconnect();
                    window.micSource = null;
                }
                if (window.micStream) {
                    window.micStream.getTracks().forEach(track => track.stop());
                    window.micStream = null;
                }
                
                document.getElementById('recordBtn').disabled = false;
                document.getElementById('stopBtn').disabled = true;
                addMessage('🔇 Recording stopped');
            }
            
            // True continuous buffer streaming - no chunks, no gaps
            class ContinuousBufferStreamer {
                constructor() {
                    this.continuousBuffer = new Float32Array(0);
                    this.playbackPosition = 0;
                    this.isStreaming = false;
                    this.sampleRate = 16000;
                    this.scriptProcessor = null;
                    this.gainNode = null;
                }
                
                addAudioChunk(base64Data) {
                    try {
                        // Convert base64 to PCM data
                        const binaryString = atob(base64Data);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {
                            bytes[i] = binaryString.charCodeAt(i);
                        }
                        
                        if (bytes.length % 2 !== 0 || bytes.length === 0) return;
                        
                        const pcmData = new Int16Array(bytes.buffer);
                        
                        // Initialize audio context if needed
                        if (!window.audioContext) {
                            window.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                                latencyHint: 'interactive'
                            });
                        }
                        
                        if (window.audioContext.state === 'suspended') {
                            window.audioContext.resume();
                        }
                        
                        // Convert PCM to float32 and append to continuous buffer
                        const newSamples = new Float32Array(pcmData.length);
                        for (let i = 0; i < pcmData.length; i++) {
                            let sample = pcmData[i] / 32768.0;
                            // Apply volume boost and gentle limiting
                            sample *= 3.0; // 3x volume boost
                            sample = Math.max(-0.95, Math.min(0.95, sample));
                            newSamples[i] = sample;
                        }
                        
                        // Append to continuous buffer
                        const oldBuffer = this.continuousBuffer;
                        this.continuousBuffer = new Float32Array(oldBuffer.length + newSamples.length);
                        this.continuousBuffer.set(oldBuffer);
                        this.continuousBuffer.set(newSamples, oldBuffer.length);
                        
                        // Start streaming if not already
                        if (!this.isStreaming) {
                            this.startContinuousStream();
                        }
                        
                        // Clean up old data to prevent memory buildup
                        if (this.continuousBuffer.length > this.sampleRate * 10) { // Keep max 10 seconds
                            const keepSamples = this.sampleRate * 5; // Keep 5 seconds
                            const newBuffer = new Float32Array(keepSamples);
                            newBuffer.set(this.continuousBuffer.slice(-keepSamples));
                            this.continuousBuffer = newBuffer;
                            this.playbackPosition = Math.max(0, this.playbackPosition - (this.continuousBuffer.length - keepSamples));
                        }
                        
                    } catch (error) {
                        console.error('Error processing audio chunk:', error);
                    }
                }
                
                startContinuousStream() {
                    if (this.isStreaming || !window.audioContext) return;
                    
                    this.isStreaming = true;
                    
                    // Create gain node
                    this.gainNode = window.audioContext.createGain();
                    this.gainNode.gain.value = 1.0;
                    this.gainNode.connect(window.audioContext.destination);
                    
                    // Create script processor for continuous playback
                    this.scriptProcessor = window.audioContext.createScriptProcessor(4096, 0, 1);
                    
                    this.scriptProcessor.onaudioprocess = (e) => {
                        const outputBuffer = e.outputBuffer.getChannelData(0);
                        const outputLength = outputBuffer.length;
                        
                        // Fill output buffer from continuous buffer
                        for (let i = 0; i < outputLength; i++) {
                            if (this.playbackPosition < this.continuousBuffer.length) {
                                outputBuffer[i] = this.continuousBuffer[this.playbackPosition];
                                this.playbackPosition++;
                            } else {
                                outputBuffer[i] = 0; // Silence when no data
                            }
                        }
                    };
                    
                    this.scriptProcessor.connect(this.gainNode);
                }
                
                clear() {
                    this.continuousBuffer = new Float32Array(0);
                    this.playbackPosition = 0;
                    this.isStreaming = false;
                    
                    if (this.scriptProcessor) {
                        this.scriptProcessor.disconnect();
                        this.scriptProcessor = null;
                    }
                    
                    if (this.gainNode) {
                        this.gainNode.disconnect();
                        this.gainNode = null;
                    }
                }
            }
            
            // Initialize the continuous buffer streamer
            const audioStreamer = new ContinuousBufferStreamer();
            
            function playAudioFromBase64(base64Data) {
                audioStreamer.addAudioChunk(base64Data);
            }
            
            // Allow Enter key to send text
            document.getElementById('textInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendText();
                }
            });
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment (Heroku sets this automatically)
    port = int(os.getenv("PORT", 8000))
    
    print("Starting Cloud-Ready Voicebot Chat API server...")
    print(f"Server will be available at: http://localhost:{port}")
    print(f"API docs will be available at: http://localhost:{port}/docs")
    print(f"Demo page will be available at: http://localhost:{port}/demo")
    
    uvicorn.run(
        "fastapi_server_cloud:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
