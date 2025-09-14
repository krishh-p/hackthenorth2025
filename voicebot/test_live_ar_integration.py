#!/usr/bin/env python3
"""
Live AR Event Integration Test
Send AR events to the voice assistant during a live conversation
"""
import json
import websocket
import threading
import time

class LiveARTester:
    def __init__(self):
        self.ws = None
        self.connected = False
        
    def connect(self):
        """Connect to the WebSocket server"""
        heroku_url = "wss://hackthenorth2025-voicebot-fdeea2d593ac.herokuapp.com/snap-lens"
        print(f"🔗 Connecting to {heroku_url}")
        
        self.ws = websocket.WebSocketApp(heroku_url,
                                        on_open=self.on_open,
                                        on_message=self.on_message,
                                        on_error=self.on_error,
                                        on_close=self.on_close)
        
        # Start connection in a separate thread
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()
        
        # Wait for connection
        time.sleep(2)
        return self.connected
    
    def on_open(self, ws):
        """Handle connection open"""
        print("✅ Connected to AR Event WebSocket!")
        self.connected = True
    
    def on_message(self, ws, message):
        """Handle incoming messages"""
        try:
            data = json.loads(message)
            if data.get('vapi_notified'):
                print(f"🎯 AR Event sent to voice assistant: {data.get('type')}")
        except:
            pass
    
    def on_error(self, ws, error):
        """Handle errors"""
        print(f"❌ WebSocket Error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle connection close"""
        print("🔌 WebSocket connection closed")
        self.connected = False
    
    def send_fire_extinguisher_grab(self):
        """Send fire extinguisher grab event"""
        if not self.connected:
            print("❌ Not connected to WebSocket")
            return
            
        event = {
            "type": "object_pinched",
            "object_name": "Fire Extinguisher",
            "position": {"x": -18.00, "y": -20.00, "z": -50.00},
            "should_speak": True,
            "client_type": "snap_lens",
            "timestamp": int(time.time() * 1000)
        }
        
        self.ws.send(json.dumps(event))
        print("🔥 SENT: Fire extinguisher grabbed!")
        print("   → Voice assistant should acknowledge and give next instruction")
    
    def send_pin_pull(self):
        """Send pin pull event"""
        if not self.connected:
            print("❌ Not connected to WebSocket")
            return
            
        event = {
            "type": "ar_event",
            "event_type": "pull_pin",
            "object_name": "Fire Extinguisher",
            "result": "success",
            "should_speak": True,
            "client_type": "snap_lens",
            "timestamp": int(time.time() * 1000),
            "data": {"pin_removed": True}
        }
        
        self.ws.send(json.dumps(event))
        print("📌 SENT: Pin pulled from fire extinguisher!")
        print("   → Voice assistant should acknowledge and give next instruction")
    
    def send_aim_extinguisher(self):
        """Send aim extinguisher event"""
        if not self.connected:
            print("❌ Not connected to WebSocket")
            return
            
        event = {
            "type": "ar_event",
            "event_type": "aim_extinguisher",
            "object_name": "Fire Extinguisher",
            "result": "success",
            "should_speak": True,
            "client_type": "snap_lens",
            "timestamp": int(time.time() * 1000),
            "data": {"aimed_at_base": True}
        }
        
        self.ws.send(json.dumps(event))
        print("🎯 SENT: Aimed extinguisher at fire base!")
        print("   → Voice assistant should acknowledge and give next instruction")
    
    def send_fire_extinguished(self):
        """Send fire extinguished event"""
        if not self.connected:
            print("❌ Not connected to WebSocket")
            return
            
        event = {
            "type": "ar_event",
            "event_type": "extinguish_fire",
            "object_name": "Fire",
            "result": "success",
            "should_speak": True,
            "client_type": "snap_lens",
            "timestamp": int(time.time() * 1000),
            "data": {"fire_extinguished": True, "time_taken": 45}
        }
        
        self.ws.send(json.dumps(event))
        print("🚒 SENT: Fire successfully extinguished!")
        print("   → Voice assistant should congratulate and complete training")
    
    def send_pull_fire_alarm(self):
        """Send pull fire alarm event"""
        if not self.connected:
            print("❌ Not connected to WebSocket")
            return
            
        event = {
            "type": "object_pinched",
            "object_name": "Fire Alarm",
            "position": {"x": -15.00, "y": -18.00, "z": -48.00},
            "should_speak": True,
            "client_type": "snap_lens",
            "timestamp": int(time.time() * 1000)
        }
        
        self.ws.send(json.dumps(event))
        print("🚨 SENT: Fire alarm pulled!")
        print("   → Voice assistant should acknowledge alarm activation")
    
    def send_failed_action(self, action_type, object_name):
        """Send failed action event"""
        if not self.connected:
            print("❌ Not connected to WebSocket")
            return
            
        event = {
            "type": "ar_event",
            "event_type": action_type,
            "object_name": object_name,
            "result": "failed",
            "should_speak": True,
            "client_type": "snap_lens",
            "timestamp": int(time.time() * 1000),
            "data": {"error": "Action failed"}
        }
        
        self.ws.send(json.dumps(event))
        print(f"❌ SENT: Failed {action_type} on {object_name}!")
        print("   → Voice assistant should provide help and guidance")

def main():
    print("🧪 Live AR Event Integration Tester")
    print("=" * 50)
    print("This will send AR events to your live voice assistant conversation")
    print()
    
    tester = LiveARTester()
    
    if not tester.connect():
        print("❌ Failed to connect to WebSocket")
        return
    
    print()
    print("🎙️  INSTRUCTIONS:")
    print("1. Start voice conversation at: https://hackthenorth2025-voicebot-fdeea2d593ac.herokuapp.com/")
    print("2. Click Connect → Start Recording")
    print("3. Let the assistant talk about fire safety")
    print("4. Use the commands below when appropriate:")
    print()
    
    while True:
        print("\n📋 Available Commands:")
        print("1 - Send 'Fire Extinguisher Grabbed' event")
        print("2 - Send 'Pin Pulled' event") 
        print("3 - Send 'Aimed at Fire' event")
        print("4 - Send 'Fire Extinguished' event")
        print("5 - Send 'Pull Fire Alarm' event")
        print("6 - Send 'Failed Action' event")
        print("q - Quit")
        print()
        
        choice = input("Enter command (1-6 or q): ").strip().lower()
        
        if choice == 'q':
            print("👋 Goodbye!")
            break
        elif choice == '1':
            tester.send_fire_extinguisher_grab()
        elif choice == '2':
            tester.send_pin_pull()
        elif choice == '3':
            tester.send_aim_extinguisher()
        elif choice == '4':
            tester.send_fire_extinguished()
        elif choice == '5':
            tester.send_pull_fire_alarm()
        elif choice == '6':
            action = input("Enter action type (e.g., 'pull_pin', 'aim_extinguisher'): ").strip()
            obj_name = input("Enter object name (e.g., 'Fire Extinguisher'): ").strip()
            tester.send_failed_action(action, obj_name)
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    main()
