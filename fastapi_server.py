#!/usr/bin/env python3
"""
FastAPI server for voicebot chat functionality
"""
import asyncio
import json
import websockets
import ssl
import certifi
import httpx
import os
import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Voicebot Chat API",
    description="FastAPI server for Vapi voicebot integration",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
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

class VapiService:
    """Service class to handle Vapi API interactions"""
    
    def __init__(self):
        self.api_key = os.getenv("VAPI_API_KEY")
        self.default_assistant_id = os.getenv("VAPI_ASSISTANT_ID")
        
        if not self.api_key:
            logger.error("VAPI_API_KEY not found in environment variables")
        if not self.default_assistant_id:
            logger.error("VAPI_ASSISTANT_ID not found in environment variables")
    
    async def create_call(self, assistant_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new Vapi call and return call data"""
        if not self.api_key:
            raise HTTPException(status_code=500, detail="VAPI_API_KEY not configured")
        
        assistant_id = assistant_id or self.default_assistant_id
        if not assistant_id:
            raise HTTPException(status_code=400, detail="Assistant ID is required")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.vapi.ai/call",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "assistantId": assistant_id,
                        "transport": {"provider": "vapi.websocket"}
                    },
                    timeout=30.0
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

# Initialize Vapi service
vapi_service = VapiService()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Voicebot Chat API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "api_key_configured": bool(vapi_service.api_key),
        "assistant_id_configured": bool(vapi_service.default_assistant_id)
    }

@app.post("/chat/start", response_model=ChatResponse)
async def start_chat(request: ChatRequest):
    """
    Start a new chat session with Vapi
    Returns WebSocket URL for real-time voice communication
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
        
        return ChatResponse(
            success=True,
            message="Chat session started successfully",
            call_id=call_id,
            websocket_url=ws_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in start_chat: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.websocket("/chat/ws/{call_id}")
async def websocket_chat(websocket: WebSocket, call_id: str):
    """
    WebSocket endpoint for real-time chat communication
    This proxies between client and Vapi WebSocket
    """
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for call: {call_id}")
    
    try:
        # In a real implementation, you'd get the Vapi WebSocket URL from the call_id
        # For now, this is a placeholder for the WebSocket proxy logic
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "call_id": call_id,
            "message": "WebSocket connection established"
        }))
        
        # Keep connection alive and handle messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Echo back for now - in production, forward to Vapi
                response = {
                    "type": "echo",
                    "original_message": message,
                    "timestamp": asyncio.get_event_loop().time()
                }
                
                await websocket.send_text(json.dumps(response))
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for call: {call_id}")
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
        logger.info(f"WebSocket connection closed for call: {call_id}")

@app.post("/chat/text", response_model=ChatResponse)
async def text_chat(request: ChatRequest):
    """
    Simple text-based chat endpoint (without voice)
    This is a simplified version for text-only interactions
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    try:
        # For now, return a simple echo response
        # In a real implementation, you'd integrate with your AI service
        response_message = f"Echo: {request.message}"
        
        return ChatResponse(
            success=True,
            message=response_message
        )
        
    except Exception as e:
        logger.error(f"Error in text_chat: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    
    print("Starting Voicebot Chat API server...")
    print(f"Server will be available at: http://localhost:{port}")
    print(f"API docs will be available at: http://localhost:{port}/docs")
    
    uvicorn.run(
        "fastapi_server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
