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
                logger.info(f"Connected to Vapi WebSocket for call: {call_id}")
                
                # Send connection established message to client
                await manager.send_to_client(call_id, {
                    "type": "vapi_connected",
                    "call_id": call_id,
                    "message": "Connected to Vapi"
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
                            audio_data = base64.b64decode(message.get("data", ""))
                            await manager.vapi_connections[call_id].send(audio_data)
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
                    
                    // Automatically connect to Vapi
                    if (window.vapiCallData) {
                        addMessage('Connecting to Vapi...');
                        ws.send(JSON.stringify({
                            type: 'connect_to_vapi',
                            vapi_url: window.vapiCallData.websocket_url // This will be the real Vapi URL
                        }));
                    }
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'audio_from_vapi') {
                        addMessage('Received audio from Vapi');
                        // Play the audio
                        playAudioFromBase64(data.data);
                    } else if (data.type === 'vapi_connected') {
                        addMessage('🎉 Connected to Vapi! You can now speak.');
                        updateStatus('Connected to Vapi - Ready to chat!', true);
                    } else if (data.type === 'vapi_error') {
                        addMessage('❌ Vapi Error: ' + data.error);
                    } else {
                        addMessage('Received: ' + JSON.stringify(data));
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
                    audioChunks = [];
                    
                    // Send audio chunks continuously while recording
                    mediaRecorder.ondataavailable = function(event) {
                        if (event.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
                            const reader = new FileReader();
                            reader.onload = function() {
                                const base64 = reader.result.split(',')[1];
                                ws.send(JSON.stringify({
                                    type: 'audio_to_vapi',
                                    data: base64
                                }));
                            };
                            reader.readAsDataURL(event.data);
                        }
                        audioChunks.push(event.data);
                    };
                    
                    mediaRecorder.onstop = function() {
                        addMessage('Recording stopped');
                        // Stop all tracks to release microphone
                        stream.getTracks().forEach(track => track.stop());
                    };
                    
                    // Start recording with small chunks for real-time streaming
                    mediaRecorder.start(100); // 100ms chunks
                    document.getElementById('recordBtn').disabled = true;
                    document.getElementById('stopBtn').disabled = false;
                    addMessage('🎤 Recording started - speak now!');
                    
                } catch (error) {
                    addMessage('Error accessing microphone: ' + error);
                }
            }
            
            function stopRecording() {
                if (mediaRecorder) {
                    mediaRecorder.stop();
                    document.getElementById('recordBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                    addMessage('Recording stopped');
                }
            }
            
            function playAudioFromBase64(base64Data) {
                try {
                    // Convert base64 to blob
                    const binaryString = atob(base64Data);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    
                    // Create audio blob (assuming 16-bit PCM, 16kHz, mono)
                    const audioBlob = new Blob([bytes], { type: 'audio/wav' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    
                    // Play the audio
                    const audio = new Audio();
                    audio.src = audioUrl;
                    audio.play().catch(e => {
                        console.error('Error playing audio:', e);
                        addMessage('Error playing audio: ' + e.message);
                    });
                    
                    // Clean up the URL after playing
                    audio.onended = () => {
                        URL.revokeObjectURL(audioUrl);
                    };
                    
                } catch (error) {
                    console.error('Error processing audio:', error);
                    addMessage('Error processing audio: ' + error.message);
                }
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
