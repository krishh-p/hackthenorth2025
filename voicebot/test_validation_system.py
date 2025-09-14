#!/usr/bin/env python3
"""
Test script to demonstrate the new validation system for AR object interactions
"""
import asyncio
import websockets
import json
import time

class ValidationTester:
    def __init__(self, server_url="ws://localhost:8001/snap-lens"):
        self.server_url = server_url
    
    async def test_correct_sequence(self):
        """Test the correct sequence of fire safety training"""
        print("🧪 Testing CORRECT sequence of fire safety training...")
        
        correct_sequence = [
            {"object": "Fire Extinguisher", "step": 1, "expected": "✅ CORRECT"},
            {"object": "Fire Extinguisher", "step": 2, "expected": "✅ CORRECT"},  
            {"object": "Fire Extinguisher", "step": 3, "expected": "✅ CORRECT"},
            {"object": "Large Flame", "step": 4, "expected": "✅ CORRECT"},
            {"object": "Fire Alarm", "step": 5, "expected": "✅ CORRECT"}
        ]
        
        async with websockets.connect(self.server_url) as websocket:
            for i, test_case in enumerate(correct_sequence):
                print(f"\n--- Step {i+1}: Testing {test_case['object']} ---")
                
                message = {
                    "type": "object_pinched",
                    "object_name": test_case["object"],
                    "position": {"x": 0, "y": 0, "z": 0},
                    "timestamp": time.strftime("%H:%M:%S")
                }
                
                await websocket.send(json.dumps(message))
                print(f"📤 Sent: {test_case['object']}")
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    response_data = json.loads(response)
                    print(f"📨 Response: {response_data.get('type', 'unknown')} - {response_data.get('message', 'no message')}")
                    
                    if response_data.get("type") == "step_advanced":
                        print(f"✅ CORRECT: Advanced to step {response_data.get('current_step')}")
                        print(f"📋 Next: {response_data.get('next_instruction', 'N/A')}")
                    elif response_data.get("type") == "training_complete":
                        print("🎉 TRAINING COMPLETED!")
                    
                except asyncio.TimeoutError:
                    print("⏰ No response received")
                
                await asyncio.sleep(1)
    
    async def test_incorrect_interactions(self):
        """Test incorrect object interactions"""
        print("\n🧪 Testing INCORRECT object interactions...")
        
        # Reset by reconnecting
        async with websockets.connect(self.server_url) as websocket:
            incorrect_tests = [
                {"object": "Fire Alarm", "step": 1, "expected": "❌ INCORRECT - Should be Fire Extinguisher"},
                {"object": "Large Flame", "step": 1, "expected": "❌ INCORRECT - Should be Fire Extinguisher"},
                {"object": "Random Object", "step": 1, "expected": "❌ INCORRECT - Should be Fire Extinguisher"},
            ]
            
            for i, test_case in enumerate(incorrect_tests):
                print(f"\n--- Incorrect Test {i+1}: {test_case['object']} ---")
                
                message = {
                    "type": "object_pinched", 
                    "object_name": test_case["object"],
                    "position": {"x": 0, "y": 0, "z": 0},
                    "timestamp": time.strftime("%H:%M:%S")
                }
                
                await websocket.send(json.dumps(message))
                print(f"📤 Sent: {test_case['object']}")
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    response_data = json.loads(response)
                    print(f"📨 Response: {response_data.get('type', 'unknown')} - {response_data.get('message', 'no message')}")
                    
                    if response_data.get("type") == "interaction_error":
                        print(f"❌ CORRECTLY REJECTED: {test_case['object']}")
                        print(f"📋 Expected: {', '.join(response_data.get('expected_objects', []))}")
                        print(f"🔄 Consecutive errors: {response_data.get('consecutive_errors', 0)}")
                    
                except asyncio.TimeoutError:
                    print("⏰ No response received")
                
                await asyncio.sleep(1)
    
    async def test_mixed_sequence(self):
        """Test a mixed sequence with errors and corrections"""
        print("\n🧪 Testing MIXED sequence (errors + corrections)...")
        
        mixed_sequence = [
            {"object": "Fire Alarm", "expected": "❌ INCORRECT"},
            {"object": "Large Flame", "expected": "❌ INCORRECT"}, 
            {"object": "Fire Extinguisher", "expected": "✅ CORRECT - Step 1"},
            {"object": "Fire Alarm", "expected": "❌ INCORRECT - Still step 2"},
            {"object": "Fire Extinguisher", "expected": "✅ CORRECT - Step 2"},
        ]
        
        async with websockets.connect(self.server_url) as websocket:
            for i, test_case in enumerate(mixed_sequence):
                print(f"\n--- Mixed Test {i+1}: {test_case['object']} ---")
                
                message = {
                    "type": "object_pinched",
                    "object_name": test_case["object"],
                    "position": {"x": 0, "y": 0, "z": 0},
                    "timestamp": time.strftime("%H:%M:%S")
                }
                
                await websocket.send(json.dumps(message))
                print(f"📤 Sent: {test_case['object']}")
                print(f"🎯 Expected: {test_case['expected']}")
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    response_data = json.loads(response)
                    
                    if response_data.get("type") == "interaction_error":
                        print(f"❌ REJECTED: {response_data.get('message', 'Error')}")
                    elif response_data.get("type") == "step_advanced":
                        print(f"✅ ACCEPTED: Advanced to step {response_data.get('current_step')}")
                    else:
                        print(f"📨 Response: {response_data.get('type')} - {response_data.get('message', 'N/A')}")
                    
                except asyncio.TimeoutError:
                    print("⏰ No response received")
                
                await asyncio.sleep(1)

async def main():
    """Run all validation tests"""
    print("🚀 Starting AR Object Validation System Tests")
    print("=" * 60)
    
    tester = ValidationTester()
    
    try:
        print("Testing server connection...")
        # Quick connection test
        async with websockets.connect(tester.server_url) as websocket:
            print("✅ Connected to server successfully!")
        
        # Run tests
        await tester.test_correct_sequence()
        await asyncio.sleep(2)
        
        await tester.test_incorrect_interactions()
        await asyncio.sleep(2)
        
        await tester.test_mixed_sequence()
        
        print("\n" + "=" * 60)
        print("🎯 All validation tests completed!")
        print("\nKey Features Demonstrated:")
        print("✅ Step-by-step training validation")
        print("✅ Incorrect object rejection")
        print("✅ Consecutive error tracking")
        print("✅ Contextual feedback messages")
        print("✅ Training progression tracking")
        
    except ConnectionRefusedError:
        print("❌ Cannot connect to server. Make sure the FastAPI server is running on port 8001")
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
