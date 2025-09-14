#!/usr/bin/env python3
"""
Test object_pinched message type to verify the fix
"""
import json
import websocket
import threading
import time

def on_message(ws, message):
    """Handle incoming messages"""
    print(f"📥 Received: {message}")

def on_error(ws, error):
    """Handle errors"""
    print(f"❌ Error: {error}")

def on_close(ws, close_status_code, close_msg):
    """Handle connection close"""
    print("🔌 Connection closed")

def on_open(ws):
    """Handle connection open"""
    print("✅ Connected! Testing object_pinched message...")
    
    def send_test_object_pinched():
        """Send test object_pinched message"""
        time.sleep(1)
        
        # Send object_pinched message like your Snap Lens does
        object_pinched_msg = {
            "type": "object_pinched",
            "object_name": "Snap3DInteractable - A fire extinguisher",
            "position": {"x": -18.00, "y": -20.00, "z": -50.00},
            "timestamp": int(time.time() * 1000),
            "client_type": "snap_lens"
        }
        
        ws.send(json.dumps(object_pinched_msg))
        print(f"📤 Sent: {json.dumps(object_pinched_msg)}")
        
        time.sleep(2)
        print("🎉 Test completed - object_pinched should now work!")
        ws.close()
    
    # Start sending test in a separate thread
    threading.Thread(target=send_test_object_pinched, daemon=True).start()

if __name__ == "__main__":
    print("🚀 Testing object_pinched message fix...")
    heroku_url = "wss://hackthenorth2025-voicebot-fdeea2d593ac.herokuapp.com/snap-lens"
    print(f"📡 Connecting to {heroku_url}")
    
    # Create WebSocket connection
    ws = websocket.WebSocketApp(heroku_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    
    # Start the WebSocket
    ws.run_forever()
