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
from typing import Set, Dict
# import numpy as np  # Not needed for cloud version
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
import uvicorn
import logging
import time

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

# Status endpoint for Snap Lens WebSocket
@app.get("/status")
async def status():
    """Status endpoint showing server info and connected clients"""
    return JSONResponse(snap_lens_manager.get_status())

# Clear all connections endpoint (for testing cleanup)
@app.post("/clear-connections")
async def clear_connections():
    """Clear all WebSocket connections - useful for cleaning up test clients"""
    initial_count = len(snap_lens_manager.connections)
    
    # Close all connections
    for connection in snap_lens_manager.connections.copy():
        try:
            await connection.close()
        except:
            pass
    
    snap_lens_manager.connections.clear()
    
    return JSONResponse({
        "message": f"Cleared {initial_count} connections",
        "remaining_clients": len(snap_lens_manager.connections)
    })

# Snap Lens WebSocket endpoint
@app.websocket("/snap-lens")
async def snap_lens_websocket(websocket: WebSocket):
    """WebSocket endpoint for Snap Lens communication"""
    await snap_lens_manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            message = await websocket.receive_text()
            
            # ===== DETAILED PAYLOAD LOGGING =====
            logger.info("=" * 80)
            logger.info("📨 INCOMING WEBSOCKET MESSAGE FROM SNAP LENS")
            logger.info(f"📅 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"📏 Message Length: {len(message)} characters")
            logger.info("📋 Raw Message:")
            logger.info(f"   {message}")
            logger.info("-" * 40)
            
            try:
                data = json.loads(message)
                logger.info("✅ JSON Parsing: SUCCESS")
                logger.info("📦 Parsed Payload:")
                for key, value in data.items():
                    logger.info(f"   {key}: {value}")
                
                msg_type = data.get("type", "unknown")
                logger.info(f"🎯 Message Type: '{msg_type}'")
                logger.info("=" * 80)
                
                # Handle different message types
                if msg_type == "command":
                    logger.info("🎮 Processing COMMAND message")
                    await snap_lens_manager.handle_command(websocket, data)
                elif msg_type == "auth":
                    logger.info("🔐 Processing AUTH message")
                    await snap_lens_manager.handle_auth(websocket, data)
                elif msg_type == "object_pinched":
                    logger.info("🤏 Processing OBJECT_PINCHED message")
                    await snap_lens_manager.handle_object_pinched(websocket, data)
                elif msg_type == "ar_event":
                    logger.info("🥽 Processing AR_EVENT message")
                    await snap_lens_manager.handle_ar_event(websocket, data)
                else:
                    logger.warning(f"❓ UNKNOWN MESSAGE TYPE: '{msg_type}'")
                    await snap_lens_manager.send_to_client(websocket, {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    })
                    
            except json.JSONDecodeError as e:
                logger.error("❌ JSON Parsing: FAILED")
                logger.error(f"   Error: {str(e)}")
                logger.error(f"   Raw message: {message}")
                logger.info("=" * 80)
                await snap_lens_manager.send_to_client(websocket, {
                    "type": "error",
                    "message": "Invalid JSON format"
                })
                
    except WebSocketDisconnect:
        logger.info("Snap Lens client disconnected normally")
    except Exception as e:
        logger.error(f"Snap Lens WebSocket error: {e}")
    finally:
        snap_lens_manager.disconnect(websocket)

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
    
    async def send_ar_event_to_vapi(self, call_id: str, event_type: str, object_name: str, result: str = "success", should_speak: bool = False, additional_context: Dict = None):
        """Send AR event context to Vapi assistant with enhanced validation info"""
        if call_id not in self.vapi_connections:
            logger.warning(f"No Vapi connection found for call {call_id}")
            return False
            
        vapi_ws = self.vapi_connections[call_id]
        
        try:
            # 1) Silent background context update - always send this
            timestamp = time.strftime("%H:%M")
            
            # Build enhanced system message with validation context
            base_content = f"AR_EVENT: {event_type} object='{object_name}' result={result} at {timestamp}"
            
            if additional_context:
                if "step" in additional_context:
                    base_content += f" step={additional_context['step']}"
                if "expected_action" in additional_context:
                    base_content += f" expected_action='{additional_context['expected_action']}'"
                if "expected_objects" in additional_context:
                    base_content += f" expected_objects={additional_context['expected_objects']}"
                if "consecutive_errors" in additional_context:
                    base_content += f" consecutive_errors={additional_context['consecutive_errors']}"
                if "current_description" in additional_context:
                    base_content += f" current_instruction='{additional_context['current_description']}'"
            
            system_message = {
                "type": "add-message",
                "message": {
                    "role": "system", 
                    "content": base_content
                }
            }
            
            await vapi_ws.send(json.dumps(system_message))
            logger.info(f"Sent AR event to Vapi: {event_type} {object_name} {result}")
            
            # 2) Optional immediate speech response
            if should_speak:
                response_message = self._generate_ar_response(event_type, object_name, result, additional_context)
                if response_message:
                    say_message = {
                        "type": "say",
                        "message": response_message
                    }
                    await vapi_ws.send(json.dumps(say_message))
                    logger.info(f"Sent speech response to Vapi: {response_message}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send AR event to Vapi: {e}")
            return False
    
    def _generate_ar_response(self, event_type: str, object_name: str, result: str, additional_context: Dict = None) -> str:
        """Generate contextual speech responses for AR events with validation awareness"""
        
        # Handle incorrect interactions
        if event_type == "incorrect_interaction":
            if additional_context and "expected_objects" in additional_context:
                expected_objects = additional_context["expected_objects"]
                consecutive_errors = additional_context.get("consecutive_errors", 0)
                
                if consecutive_errors == 1:
                    return f"That's not quite right. You need to find the {', '.join(expected_objects)} for this step."
                elif consecutive_errors == 2:
                    return f"Remember, for this step you should be looking for the {', '.join(expected_objects)}. Take your time and look around."
                else:
                    return f"Let me help you. You're currently on step {additional_context.get('step', '?')}. You need to {additional_context.get('current_description', 'continue with the training')}."
            else:
                return "That's not the correct object for this step. Look around for the right item to continue."
        
        # Handle correct interactions
        if event_type == "correct_interaction" and result == "success":
            step = additional_context.get("step", 1) if additional_context else 1
            
            # Step-specific positive feedback
            if step == 1 and "fire extinguisher" in object_name.lower():
                return "Excellent! You found the fire extinguisher. Now pull the pin and aim at the base of the fire."
            elif step == 2 and "fire extinguisher" in object_name.lower():
                return "Perfect! Pin removed. Now aim the extinguisher at the base of the fire and squeeze the handle."
            elif step == 3 and "fire extinguisher" in object_name.lower():
                return "Good aim! Now squeeze the handle and sweep side to side to extinguish the flames."
            elif step == 4 and ("fire" in object_name.lower() or "flame" in object_name.lower()):
                return "Outstanding! The fire is extinguished. Now pull the fire alarm to alert others in the building."
            elif step == 5 and "fire alarm" in object_name.lower():
                return "Perfect! You've pulled the fire alarm. Everyone will now be alerted to evacuate safely."
            else:
                return f"Great job with the {object_name}! Keep following the emergency procedures."
        
        # Legacy support for older event types
        if result != "success" and event_type != "incorrect_interaction":
            return f"I noticed you had trouble with the {object_name}. Let me help guide you."
        
        # Fallback responses for legacy events
        if event_type == "object_interaction" or event_type == "object_pinched":
            if "fire extinguisher" in object_name.lower():
                return "Great job grabbing the fire extinguisher! Now pull the pin and aim at the base of the fire."
            elif "fire alarm" in object_name.lower():
                return "Good work activating the fire alarm! Now let's focus on the fire extinguisher."
            elif "flame" in object_name.lower():
                return "I see you're near the fire. Remember to stay at a safe distance and use the extinguisher."
            else:
                return f"Nice work interacting with the {object_name}. Keep following the safety procedures."
        
        elif event_type == "pull_extinguisher":
            return "Perfect! You've got the fire extinguisher. Now pull the pin and aim at the base of the fire."
        elif event_type == "pull_pin":
            return "Excellent! Pin removed. Now aim the nozzle at the base of the fire and squeeze the handle."
        elif event_type == "aim_extinguisher":
            return "Good positioning! Now squeeze the handle to discharge the extinguisher."
        elif event_type == "extinguish_fire":
            return "Outstanding! You've successfully extinguished the fire. Great job following proper fire safety procedures."
        elif event_type == "task_complete":
            return "Congratulations! You've completed the fire safety training successfully."
        else:
            return f"I see you completed the {event_type} step. Keep up the good work!"
    
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

class SnapLensConnectionManager:
    """Manages WebSocket connections for Snap Lens communication"""
    
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self.start_time = time.time()
        self.audio_manager_ref = None  # Reference to ServerAudioManager
        
        # Training scenario state tracking
        self.training_scenarios = {
            "fire_emergency": {
                "steps": [
                    {"step": 1, "expected_objects": ["fire extinguisher"], "action": "grab", "description": "Find and grab the fire extinguisher"},
                    {"step": 2, "expected_objects": ["fire extinguisher"], "action": "pull_pin", "description": "Pull the pin from the fire extinguisher"},
                    {"step": 3, "expected_objects": ["fire extinguisher"], "action": "aim", "description": "Aim the extinguisher at the base of the fire"},
                    {"step": 4, "expected_objects": ["fire", "flame"], "action": "extinguish", "description": "Spray the fire to extinguish it"},
                    {"step": 5, "expected_objects": ["fire alarm"], "action": "pull", "description": "Pull the fire alarm to alert others"}
                ]
            }
        }
        
        # Current training state
        self.current_scenario = "fire_emergency"
        self.current_step = 1
        self.session_state = {
            "completed_steps": [],
            "last_correct_action": None,
            "consecutive_errors": 0
        }
    
    def validate_object_interaction(self, object_name: str, action_type: str = "grab") -> Dict:
        """Validate if the object interaction matches the current training step"""
        current_scenario = self.training_scenarios.get(self.current_scenario)
        if not current_scenario:
            return {"valid": False, "reason": "No active training scenario"}
        
        current_step_info = None
        for step_info in current_scenario["steps"]:
            if step_info["step"] == self.current_step:
                current_step_info = step_info
                break
        
        if not current_step_info:
            return {"valid": False, "reason": "Invalid training step"}
        
        # Normalize object name for comparison
        object_name_lower = object_name.lower().strip()
        expected_objects = [obj.lower() for obj in current_step_info["expected_objects"]]
        
        # Check if the object matches any expected objects for this step
        object_match = any(expected_obj in object_name_lower or object_name_lower in expected_obj 
                          for expected_obj in expected_objects)
        
        if object_match:
            return {
                "valid": True,
                "step": self.current_step,
                "expected_action": current_step_info["action"],
                "description": current_step_info["description"],
                "object_matched": object_name
            }
        else:
            return {
                "valid": False,
                "reason": f"Wrong object for step {self.current_step}",
                "expected_objects": current_step_info["expected_objects"],
                "current_description": current_step_info["description"],
                "received_object": object_name
            }
    
    def advance_training_step(self):
        """Advance to the next training step"""
        self.session_state["completed_steps"].append(self.current_step)
        self.current_step += 1
        self.session_state["consecutive_errors"] = 0
        
        logger.info(f"Advanced to training step {self.current_step}")
        
        # Check if training is complete
        max_steps = len(self.training_scenarios[self.current_scenario]["steps"])
        if self.current_step > max_steps:
            logger.info("Training scenario completed!")
            return True
        return False
    
    def record_error(self):
        """Record an incorrect interaction"""
        self.session_state["consecutive_errors"] += 1
        logger.warning(f"Training error recorded. Consecutive errors: {self.session_state['consecutive_errors']}")
    
    def get_current_step_info(self) -> Dict:
        """Get information about the current training step"""
        current_scenario = self.training_scenarios.get(self.current_scenario)
        if not current_scenario:
            return {}
        
        for step_info in current_scenario["steps"]:
            if step_info["step"] == self.current_step:
                return step_info
        return {}
    
    async def connect(self, websocket: WebSocket):
        """Add a new WebSocket connection"""
        await websocket.accept()
        self.connections.add(websocket)
        
        # Enhanced connection logging
        client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
        logger.info("🔗" + "=" * 60)
        logger.info("🔗 NEW SNAP LENS CLIENT CONNECTED")
        logger.info(f"🔗 Client IP: {client_info}")
        logger.info(f"🔗 Total Active Clients: {len(self.connections)}")
        logger.info(f"🔗 Connection Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("🔗" + "=" * 60)
        
        # Send welcome message
        await self.send_to_client(websocket, {
            "type": "info",
            "message": "Connected to Snap Lens Communication Server"
        })
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.connections.discard(websocket)
        
        # Enhanced disconnect logging
        client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
        logger.info("🔌" + "=" * 60)
        logger.info("🔌 SNAP LENS CLIENT DISCONNECTED")
        logger.info(f"🔌 Client IP: {client_info}")
        logger.info(f"🔌 Remaining Clients: {len(self.connections)}")
        logger.info(f"🔌 Disconnect Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("🔌" + "=" * 60)
    
    async def send_to_client(self, websocket: WebSocket, message: dict):
        """Send message to a specific client"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict, exclude: WebSocket = None):
        """Broadcast message to all connected clients except the sender"""
        if not self.connections:
            return
            
        disconnected = []
        for connection in self.connections.copy():
            if connection != exclude:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error broadcasting to client: {e}")
                    disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def handle_command(self, websocket: WebSocket, data: dict):
        """Handle navigation commands from clients"""
        command = data.get("command")
        if not command:
            await self.send_to_client(websocket, {
                "type": "error",
                "message": "No command specified"
            })
            return
        
        # Check if this is a test client (optional filtering)
        client_type = data.get("client_type", "unknown")
        
        logger.info(f"Received command: {command} from client_type: {client_type}")
        
        # Create the message to broadcast
        broadcast_message = {
            "type": "command",
            "command": command,
            "client_type": client_type
        }
        
        # Broadcast the command to all other clients
        await self.broadcast(broadcast_message, exclude=websocket)
        
        # Send confirmation back to sender
        await self.send_to_client(websocket, {
            "type": "command",
            "status": "received",
            "command": command
        })
        
        # Log the command
        if command == "next":
            logger.info("Moving to next slide - broadcasted to all clients")
        elif command == "previous":
            logger.info("Moving to previous slide - broadcasted to all clients")
    
    async def handle_auth(self, websocket: WebSocket, data: dict):
        """Handle authentication (simplified for demo)"""
        logger.info("Authentication attempt from Snap Lens client")
        
        # In a real implementation, validate credentials
        # For this demo, accept any auth attempt
        await self.send_to_client(websocket, {
            "type": "auth",
            "status": "success",
            "message": "Authentication successful"
        })
    
    async def handle_object_pinched(self, websocket: WebSocket, data: dict):
        """Handle object pinched events from Snap Lens with validation"""
        object_name = data.get("object_name", "Unknown object")
        position = data.get("position", {})
        should_speak = data.get("should_speak", True)
        
        logger.info(f"Object pinched: {object_name} at position {position}")
        
        # Validate the object interaction against current training step
        validation_result = self.validate_object_interaction(object_name)
        
        if validation_result["valid"]:
            # Correct object interaction
            logger.info(f"✅ CORRECT INTERACTION: {object_name} matches step {self.current_step}")
            
            # Send positive AR event to Vapi assistant
            if self.audio_manager_ref:
                for call_id in self.audio_manager_ref.vapi_connections.keys():
                    await self.audio_manager_ref.send_ar_event_to_vapi(
                        call_id=call_id,
                        event_type="correct_interaction",
                        object_name=object_name,
                        result="success",
                        should_speak=should_speak,
                        additional_context={
                            "step": self.current_step,
                            "expected_action": validation_result["expected_action"],
                            "description": validation_result["description"]
                        }
                    )
                    break
            
            # Advance to next training step
            training_complete = self.advance_training_step()
            
            if training_complete:
                # Send completion message
                await self.send_to_client(websocket, {
                    "type": "training_complete",
                    "status": "completed",
                    "message": "🎉 Fire emergency training completed successfully!",
                    "object_name": object_name
                })
            else:
                # Send next step information
                next_step_info = self.get_current_step_info()
                await self.send_to_client(websocket, {
                    "type": "step_advanced",
                    "status": "correct",
                    "object_name": object_name,
                    "current_step": self.current_step,
                    "next_instruction": next_step_info.get("description", "Continue training"),
                    "expected_objects": next_step_info.get("expected_objects", [])
                })
        else:
            # Incorrect object interaction
            logger.warning(f"❌ INCORRECT INTERACTION: {object_name} - {validation_result['reason']}")
            self.record_error()
            
            # Send corrective AR event to Vapi assistant
            if self.audio_manager_ref:
                for call_id in self.audio_manager_ref.vapi_connections.keys():
                    await self.audio_manager_ref.send_ar_event_to_vapi(
                        call_id=call_id,
                        event_type="incorrect_interaction",
                        object_name=object_name,
                        result="error",
                        should_speak=should_speak,
                        additional_context={
                            "step": self.current_step,
                            "expected_objects": validation_result.get("expected_objects", []),
                            "current_description": validation_result.get("current_description", ""),
                            "consecutive_errors": self.session_state["consecutive_errors"]
                        }
                    )
                    break
            
            # Send error feedback to client
            current_step_info = self.get_current_step_info()
            await self.send_to_client(websocket, {
                "type": "interaction_error",
                "status": "incorrect",
                "object_name": object_name,
                "message": f"Wrong object! Expected: {', '.join(validation_result.get('expected_objects', []))}",
                "current_step": self.current_step,
                "current_instruction": current_step_info.get("description", ""),
                "expected_objects": validation_result.get("expected_objects", []),
                "received_object": object_name,
                "consecutive_errors": self.session_state["consecutive_errors"]
            })
        
        # Create enhanced broadcast message with validation status
        broadcast_message = {
            "type": "object_pinched",
            "object_name": object_name,
            "position": position,
            "timestamp": data.get("timestamp"),
            "client_type": data.get("client_type", "snap_lens"),
            "validation_status": "correct" if validation_result["valid"] else "incorrect",
            "current_step": self.current_step,
            "vapi_notified": self.audio_manager_ref is not None
        }
        
        # Broadcast the object pinched event to all other clients
        await self.broadcast(broadcast_message, exclude=websocket)
    
    async def handle_ar_event(self, websocket: WebSocket, data: dict):
        """Handle general AR events from Snap Lens"""
        event_type = data.get("event_type", "unknown")
        object_name = data.get("object_name", "Unknown object")
        result = data.get("result", "success")
        should_speak = data.get("should_speak", False)  # Default to silent for general events
        additional_data = data.get("data", {})
        
        logger.info(f"AR Event: {event_type} - {object_name} - {result}")
        
        # Send AR event to Vapi assistant if available
        if self.audio_manager_ref:
            for call_id in self.audio_manager_ref.vapi_connections.keys():
                await self.audio_manager_ref.send_ar_event_to_vapi(
                    call_id=call_id,
                    event_type=event_type,
                    object_name=object_name,
                    result=result,
                    should_speak=should_speak
                )
                break  # Send to first active connection for demo
        
        # Create the message to broadcast to other clients
        broadcast_message = {
            "type": "ar_event",
            "event_type": event_type,
            "object_name": object_name,
            "result": result,
            "data": additional_data,
            "timestamp": data.get("timestamp"),
            "client_type": data.get("client_type", "snap_lens"),
            "vapi_notified": self.audio_manager_ref is not None
        }
        
        # Broadcast the AR event to all other clients
        await self.broadcast(broadcast_message, exclude=websocket)
        
        # Send confirmation back to sender
        await self.send_to_client(websocket, {
            "type": "ar_event",
            "status": "received",
            "event_type": event_type,
            "object_name": object_name,
            "result": result,
            "message": f"AR event received: {event_type} on {object_name}",
            "vapi_notified": self.audio_manager_ref is not None
        })
    
    def get_status(self) -> dict:
        """Get current server status"""
        return {
            "status": "running",
            "clients": len(self.connections),
            "uptime": int(time.time() - self.start_time)
        }

# Global managers
audio_manager = ServerAudioManager()
snap_lens_manager = SnapLensConnectionManager()

# Link managers for AR event integration
snap_lens_manager.audio_manager_ref = audio_manager

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
                    Connect to AI
                </button>
                <button id="disconnectBtn" class="disconnect-btn btn" onclick="disconnect()" disabled>
                    Disconnect
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
            const BUFFER_AHEAD = 0.1;   // Reduced to 100ms for lower latency
            const CHUNK_SAMPLES = 320;  // 20ms @ 16k
            const SR_IN = 16000;
            let isAISpeaking = false;   // Track AI speech state
            let audioQueue = [];        // Queue for managing audio chunks
            let lastAudioTime = 0;      // Track last audio playback time
            
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
                if (!audioContext) {
                    audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    console.log('🎵 Created new AudioContext, state:', audioContext.state);
                }
                
                if (audioContext.state === 'suspended') {
                    console.log('🔧 AudioContext suspended, attempting to resume...');
                    audioContext.resume().then(() => {
                        console.log('✅ AudioContext resumed successfully');
                    }).catch(err => {
                        console.error('❌ Failed to resume AudioContext:', err);
                    });
                }
                
                return audioContext.state === 'running';
            }
            
            // Add user interaction handler to ensure audio context starts
            document.addEventListener('click', function() {
                if (audioContext && audioContext.state === 'suspended') {
                    console.log('🖱️ User click detected, resuming audio context...');
                    audioContext.resume();
                }
            });
            
            // Low-latency audio playback with better synchronization
            function schedulePcm16(base64Data) {
                try {
                    ensureAudioCtx();
                    
                    // decode base64 -> Int16Array (PCM16 @ 16k)
                    const bin = atob(base64Data);
                    const bytes = new Uint8Array(bin.length);
                    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
                    if (bytes.length % 2 !== 0) {
                        console.warn('⚠️ Odd byte length, skipping audio chunk');
                        return;
                    }
                    const pcm16 = new Int16Array(bytes.buffer);

                    // Convert to Float32 for AudioBuffer
                    const float = new Float32Array(pcm16.length);
                    for (let i = 0; i < pcm16.length; i++) {
                        float[i] = Math.max(-1, Math.min(1, pcm16[i] / 32768)) * 2.5;
                    }

                    const buf = audioContext.createBuffer(1, float.length, SR_IN);
                    buf.copyToChannel(float, 0, 0);

                    const now = audioContext.currentTime;
                    const dur = float.length / SR_IN;
                    
                    // Improved timing logic for better synchronization
                    if (!isAISpeaking) {
                        // First chunk - start immediately with minimal buffer
                        playhead = now + 0.05; // Only 50ms delay for first chunk
                        isAISpeaking = true;
                        console.log('🎵 Starting AI speech, playhead:', playhead.toFixed(3));
                    } else {
                        // Subsequent chunks - maintain continuity but avoid excessive buffering
                        const timeSinceLastAudio = now - lastAudioTime;
                        if (playhead < now || timeSinceLastAudio > 0.5) {
                            // Reset if we're behind or there's been a gap
                            playhead = now + 0.05;
                            console.log('🔧 Resetting playhead due to timing gap');
                        }
                    }

                    const src = audioContext.createBufferSource();
                    src.buffer = buf;
                    
                    // Add gain node for volume control
                    const gainNode = audioContext.createGain();
                    gainNode.gain.value = 2.5;
                    
                    src.connect(gainNode);
                    gainNode.connect(audioContext.destination);

                    // Track audio sources for management
                    currentAudioSources.push(src);

                    // Track when audio ends for better timing
                    src.onended = function() {
                        lastAudioTime = audioContext.currentTime;
                        // Remove from tracking array
                        const index = currentAudioSources.indexOf(src);
                        if (index > -1) {
                            currentAudioSources.splice(index, 1);
                        }
                        console.log('🎵 Audio chunk ended at:', lastAudioTime.toFixed(3));
                    };

                    console.log('🎵 Playing audio at:', playhead.toFixed(3), 'duration:', dur.toFixed(3));
                    src.start(playhead);
                    playhead += dur;
                    
                } catch (error) {
                    console.error('❌ Audio playback error:', error);
                    addMessage('🔊 Audio error: ' + error.message);
                    
                    // Reset state on error
                    isAISpeaking = false;
                    playhead = 0;
                }
            }
            
            // Function to reset audio state when speech ends
            function resetAudioState() {
                isAISpeaking = false;
                playhead = 0;
                lastAudioTime = 0;
                audioQueue = []; // Clear any queued audio
                console.log('🔄 Audio state reset');
            }
            
            // Add audio chunk management to prevent overlap
            let currentAudioSources = [];
            
            function stopAllAudio() {
                console.log('🛑 Stopping all audio sources');
                currentAudioSources.forEach(source => {
                    try {
                        source.stop();
                    } catch (e) {
                        // Source may already be stopped
                    }
                });
                currentAudioSources = [];
                resetAudioState();
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
                    updateStatus('🟢 Connected - Initializing microphone...', 'connected');
                    addMessage('Connected to professional AI voice system');
                    connectBtn.textContent = 'Connected';
                    connectBtn.disabled = true;
                    disconnectBtn.disabled = false;
                    
                    // Automatically start recording when connected
                    setTimeout(() => {
                        startRecording();
                    }, 500);
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'audio_chunk') {
                        console.log('🎵 Received audio chunk, length:', data.data ? data.data.length : 0);
                        
                        // Only play audio if we're in the right state
                        if (data.data && data.data.length > 0) {
                            schedulePcm16(data.data);
                        }
                    } else if (data.type === 'vapi_message') {
                        const vapiData = data.data;
                        console.log('📨 Vapi message:', vapiData.type, vapiData);
                        
                        if (vapiData.type === 'speech-update') {
                            if (vapiData.status === 'started') {
                                updateStatus('🎤 AI is speaking...', 'speaking');
                                addMessage('🎤 AI started speaking');
                                // Stop any existing audio and reset state for new speech
                                stopAllAudio();
                            } else if (vapiData.status === 'ended') {
                                updateStatus('🟢 Your turn to speak!', 'connected');
                                addMessage('✅ AI finished speaking');
                                // Allow current audio to finish but reset state after a brief delay
                                setTimeout(() => {
                                    if (currentAudioSources.length === 0) {
                                        resetAudioState();
                                    }
                                }, 200);
                            }
                        } else if (vapiData.type === 'conversation-update') {
                            console.log('💬 Conversation update:', vapiData);
                        } else if (vapiData.type === 'function-call') {
                            console.log('🔧 Function call:', vapiData);
                        }
                    } else if (data.type === 'ping') {
                        // Keep-alive ping, no action needed
                        console.log('💓 Ping received');
                    } else {
                        console.log('📨 Unknown message type:', data.type, data);
                    }
                };
                
                ws.onclose = function() {
                    updateStatus('🔴 Disconnected', 'disconnected');
                    addMessage('Disconnected from AI assistant');
                    connectBtn.disabled = false;
                    connectBtn.textContent = 'Connect to AI';
                    disconnectBtn.disabled = true;
                    
                    // Clean up audio state on disconnect
                    stopAllAudio();
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
            
            // AudioWorklet-based recording with fallback
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
                        await audioContext.audioWorklet.addModule('/worklets/capture-16k.js');
                        
                        const src = audioContext.createMediaStreamSource(stream);
                        const worklet = new AudioWorkletNode(audioContext, 'capture-16k');
                        src.connect(worklet);
                        
                        worklet.port.onmessage = (ev) => {
                            if (ws && ws.readyState === WebSocket.OPEN) {
                                ws.send(ev.data);
                            }
                        };

                        updateStatus('🎤 Microphone active - Speak now!', 'connected');
                        addMessage('🎤 AudioWorklet capture active - ready for conversation!');
                        
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
                                
                                // Send PCM data to server
                                ws.send(pcm16.buffer);
                            }
                        };
                        
                        src.connect(processor);
                        processor.connect(audioContext.destination);
                        
                        updateStatus('🎤 Microphone active - Speak now!', 'connected');
                        addMessage('🎤 ScriptProcessor capture active - ready for conversation!');
                    }
                    
                } catch (error) {
                    addMessage('Microphone access error: ' + error.message);
                    console.error('Recording error:', error);
                }
            }
        </script>
    </body>
    </html>
    """)

@app.get("/snap-lens-test")
async def snap_lens_test_page():
    """Simple test page for Snap Lens WebSocket functionality"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Snap Lens WebSocket Test</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            
            h1 {
                color: #4285f4;
                text-align: center;
                margin-bottom: 30px;
            }
            
            .container {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            
            .card {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 20px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                background-color: white;
            }
            
            .controls {
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
                flex-wrap: wrap;
            }
            
            button {
                background-color: #4285f4;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
                transition: background-color 0.2s;
            }
            
            button:hover {
                background-color: #3367d6;
            }
            
            button:disabled {
                background-color: #ccc;
                cursor: not-allowed;
            }
            
            input[type="text"] {
                padding: 12px;
                border: 1px solid #ccc;
                border-radius: 4px;
                flex-grow: 1;
                font-size: 16px;
            }
            
            .status {
                margin-top: 10px;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
                text-align: center;
            }
            
            .status.connected {
                background-color: #e6f4ea;
                color: #0f9d58;
            }
            
            .status.disconnected {
                background-color: #fce8e6;
                color: #db4437;
            }
            
            .log-container {
                height: 300px;
                overflow-y: auto;
                background-color: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
                font-family: monospace;
                border: 1px solid #ddd;
            }
            
            .log-entry {
                margin-bottom: 5px;
                border-bottom: 1px solid #eee;
                padding-bottom: 5px;
            }
            
            .log-entry.sent {
                color: #4285f4;
            }
            
            .log-entry.received {
                color: #0f9d58;
            }
            
            .log-entry.error {
                color: #db4437;
            }
            
            .log-entry .timestamp {
                color: #666;
                font-size: 0.8em;
                margin-right: 10px;
            }
            
            .navigation-buttons {
                display: flex;
                justify-content: center;
                gap: 20px;
                margin: 20px 0;
            }
            
            .navigation-buttons button {
                font-size: 18px;
                padding: 15px 30px;
                min-width: 180px;
            }
        </style>
    </head>
    <body>
        <h1>Snap Lens WebSocket Test</h1>
        
        <div class="container">
            <div class="card">
                <h2>Connection</h2>
                <div class="controls">
                    <input type="text" id="server-url" value="" placeholder="WebSocket URL (leave empty for current server)" />
                    <button id="connect-button">Connect</button>
                    <button id="disconnect-button" disabled>Disconnect</button>
                </div>
                <div id="connection-status" class="status disconnected">Not connected</div>
            </div>
            
            <div class="card">
                <h2>Commands</h2>
                <div class="navigation-buttons">
                    <button id="previous-button" disabled>Send Previous Command</button>
                    <button id="next-button" disabled>Send Next Command</button>
                </div>
                <div class="controls">
                    <button id="auth-button" disabled>Send Auth</button>
                </div>
            </div>
            
            <div class="card">
                <h2>Communication Log</h2>
                <div id="log-container" class="log-container"></div>
                <button onclick="clearLog()" style="margin-top: 10px;">Clear Log</button>
            </div>
        </div>
        
        <script>
            // DOM elements
            const serverUrlInput = document.getElementById('server-url');
            const connectButton = document.getElementById('connect-button');
            const disconnectButton = document.getElementById('disconnect-button');
            const connectionStatus = document.getElementById('connection-status');
            const previousButton = document.getElementById('previous-button');
            const nextButton = document.getElementById('next-button');
            const authButton = document.getElementById('auth-button');
            const logContainer = document.getElementById('log-container');
            
            // State
            let socket = null;
            
            // Initialize
            function initialize() {
                // Set default WebSocket URL
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const defaultUrl = protocol + '//' + window.location.host + '/snap-lens';
                serverUrlInput.value = defaultUrl;
                
                // Set up event listeners
                connectButton.addEventListener('click', connect);
                disconnectButton.addEventListener('click', disconnect);
                previousButton.addEventListener('click', () => sendCommand('previous'));
                nextButton.addEventListener('click', () => sendCommand('next'));
                authButton.addEventListener('click', sendAuth);
                
                addLogEntry('Page initialized', 'info');
            }
            
            // Connect to WebSocket
            function connect() {
                let url = serverUrlInput.value.trim();
                if (!url) {
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    url = protocol + '//' + window.location.host + '/snap-lens';
                }
                
                addLogEntry(`Connecting to ${url}...`, 'info');
                updateConnectionStatus('Connecting...', 'disconnected');
                
                try {
                    socket = new WebSocket(url);
                    
                    socket.onopen = function(event) {
                        updateConnectionStatus('Connected', 'connected');
                        addLogEntry('Connected to Snap Lens WebSocket server', 'info');
                        connectButton.disabled = true;
                        disconnectButton.disabled = false;
                        previousButton.disabled = false;
                        nextButton.disabled = false;
                        authButton.disabled = false;
                    };
                    
                    socket.onmessage = function(event) {
                        const message = event.data;
                        addLogEntry(`Received: ${message}`, 'received');
                        
                        try {
                            const data = JSON.parse(message);
                            // Handle specific message types if needed
                            if (data.type === 'command') {
                                addLogEntry(`Command received: ${data.command}`, 'received');
                            } else if (data.type === 'object_pinched') {
                                addLogEntry(`Object pinched: ${data.object_name} at ${JSON.stringify(data.position)}`, 'received');
                            }
                        } catch (error) {
                            // Message parsing failed, but that's okay
                        }
                    };
                    
                    socket.onclose = function(event) {
                        updateConnectionStatus('Disconnected', 'disconnected');
                        addLogEntry(`Connection closed (${event.code}): ${event.reason || 'No reason provided'}`, 'info');
                        resetButtons();
                    };
                    
                    socket.onerror = function(event) {
                        addLogEntry('WebSocket error occurred', 'error');
                        updateConnectionStatus('Error', 'disconnected');
                        resetButtons();
                    };
                    
                } catch (error) {
                    addLogEntry(`Error creating WebSocket: ${error.message}`, 'error');
                    updateConnectionStatus('Error', 'disconnected');
                }
            }
            
            // Disconnect from WebSocket
            function disconnect() {
                if (socket) {
                    socket.close();
                    socket = null;
                    addLogEntry('Manually disconnected', 'info');
                }
            }
            
            // Send command
            function sendCommand(command) {
                if (!socket || socket.readyState !== WebSocket.OPEN) {
                    addLogEntry('Not connected to server', 'error');
                    return;
                }
                
                const message = {
                    type: 'command',
                    command: command
                };
                
                const messageStr = JSON.stringify(message);
                socket.send(messageStr);
                addLogEntry(`Sent: ${messageStr}`, 'sent');
            }
            
            // Send auth
            function sendAuth() {
                if (!socket || socket.readyState !== WebSocket.OPEN) {
                    addLogEntry('Not connected to server', 'error');
                    return;
                }
                
                const message = {
                    type: 'auth',
                    credentials: 'demo-user'
                };
                
                const messageStr = JSON.stringify(message);
                socket.send(messageStr);
                addLogEntry(`Sent: ${messageStr}`, 'sent');
            }
            
            // Update connection status
            function updateConnectionStatus(text, className) {
                connectionStatus.textContent = text;
                connectionStatus.className = `status ${className}`;
            }
            
            // Reset buttons to disconnected state
            function resetButtons() {
                connectButton.disabled = false;
                disconnectButton.disabled = true;
                previousButton.disabled = true;
                nextButton.disabled = true;
                authButton.disabled = true;
            }
            
            // Add log entry
            function addLogEntry(message, type = 'info') {
                const entry = document.createElement('div');
                entry.className = `log-entry ${type}`;
                
                const timestamp = document.createElement('span');
                timestamp.className = 'timestamp';
                timestamp.textContent = new Date().toLocaleTimeString();
                
                entry.appendChild(timestamp);
                entry.appendChild(document.createTextNode(message));
                
                logContainer.appendChild(entry);
                logContainer.scrollTop = logContainer.scrollHeight;
            }
            
            // Clear log
            function clearLog() {
                logContainer.innerHTML = '';
                addLogEntry('Log cleared', 'info');
            }
            
            // Initialize the page
            initialize();
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
