#!/usr/bin/env python3
"""
Example client for the FastAPI voicebot server
"""
import asyncio
import httpx
import json

async def test_api():
    """Test the FastAPI endpoints"""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        print("Testing Voicebot Chat API")
        print("=" * 40)
        
        # Test health endpoint
        print("\n1. Testing health endpoint...")
        response = await client.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Test text chat
        print("\n2. Testing text chat...")
        chat_request = {
            "message": "Hello! Can you help me with something?"
        }
        response = await client.post(f"{base_url}/chat/text", json=chat_request)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Test start chat (will fail without API keys, but shows structure)
        print("\n3. Testing start chat (may fail without API keys)...")
        try:
            response = await client.post(f"{base_url}/chat/start", json={})
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Expected error (no API keys): {e}")

if __name__ == "__main__":
    asyncio.run(test_api())
