# Voicebot FastAPI Server

A FastAPI backend server that provides REST and WebSocket endpoints for integrating with the Vapi voice AI platform.

## Features

- **REST API endpoints** for starting chat sessions and text-based interactions
- **WebSocket support** for real-time voice communication
- **CORS enabled** for frontend integration
- **Health check endpoints** for monitoring
- **Comprehensive error handling** and logging
- **Environment-based configuration**

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Setup

Create a `.env` file in the voicebot directory:

```env
VAPI_API_KEY=your_vapi_api_key_here
VAPI_ASSISTANT_ID=your_assistant_id_here
PORT=8000
```

### 3. Start the Server

```bash
python fastapi_server.py
```

The server will be available at:
- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Health Check

```http
GET /
GET /health
```

Returns server status and configuration info.

**Response:**
```json
{
  "status": "healthy",
  "api_key_configured": true,
  "assistant_id_configured": true
}
```

### Start Voice Chat Session

```http
POST /chat/start
```

Creates a new Vapi voice chat session and returns WebSocket URL for real-time communication.

**Request Body:**
```json
{
  "assistant_id": "optional_assistant_id"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Chat session started successfully",
  "call_id": "call_123456",
  "websocket_url": "wss://vapi.ai/ws/call_123456",
  "error": null
}
```

### Text Chat

```http
POST /chat/text
```

Simple text-based chat endpoint (without voice).

**Request Body:**
```json
{
  "message": "Hello, how can you help me?"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Echo: Hello, how can you help me?",
  "call_id": null,
  "websocket_url": null,
  "error": null
}
```

### WebSocket Chat

```websocket
WS /chat/ws/{call_id}
```

Real-time WebSocket endpoint for voice chat communication.

**Usage:**
1. First call `/chat/start` to get a call_id
2. Connect to `/chat/ws/{call_id}`
3. Send/receive JSON messages for real-time interaction

## Usage Examples

### Python Client Example

```python
import asyncio
import httpx

async def start_voice_chat():
    async with httpx.AsyncClient() as client:
        # Start a chat session
        response = await client.post("http://localhost:8000/chat/start")
        data = response.json()
        
        if data["success"]:
            print(f"Chat started: {data['call_id']}")
            print(f"WebSocket URL: {data['websocket_url']}")
        else:
            print(f"Error: {data['error']}")

asyncio.run(start_voice_chat())
```

### cURL Examples

**Health Check:**
```bash
curl -X GET "http://localhost:8000/health"
```

**Text Chat:**
```bash
curl -X POST "http://localhost:8000/chat/text" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

**Start Voice Chat:**
```bash
curl -X POST "http://localhost:8000/chat/start" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### JavaScript/Frontend Integration

```javascript
// Start a voice chat session
async function startVoiceChat() {
  const response = await fetch('http://localhost:8000/chat/start', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({})
  });
  
  const data = await response.json();
  
  if (data.success) {
    console.log('Chat started:', data.call_id);
    // Connect to WebSocket for real-time communication
    connectWebSocket(data.call_id);
  }
}

// WebSocket connection
function connectWebSocket(callId) {
  const ws = new WebSocket(`ws://localhost:8000/chat/ws/${callId}`);
  
  ws.onopen = () => {
    console.log('WebSocket connected');
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
  };
  
  ws.onclose = () => {
    console.log('WebSocket disconnected');
  };
}
```

## Development

### Running with Auto-reload

```bash
uvicorn fastapi_server:app --reload --host 0.0.0.0 --port 8000
```

### Testing

Run the included test client:

```bash
python client_example.py
```

### API Documentation

FastAPI automatically generates interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VAPI_API_KEY` | Yes | Your Vapi API key |
| `VAPI_ASSISTANT_ID` | Yes | Default Vapi assistant ID |
| `PORT` | No | Server port (default: 8000) |

### CORS Configuration

The server is configured with permissive CORS settings for development. For production, update the CORS middleware in `fastapi_server.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specify your domains
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

## Integration with Original Voice Script

The FastAPI server extracts and modularizes the core functionality from `audio_voice_test.py`:

- **Vapi API integration** → `VapiService` class
- **WebSocket handling** → `/chat/ws/{call_id}` endpoint  
- **Error handling** → Comprehensive HTTP error responses
- **Configuration** → Environment-based setup

You can still use the original `audio_voice_test.py` for direct voice testing, while the FastAPI server provides a clean API interface for frontend integration.

## Troubleshooting

### Common Issues

1. **"VAPI_API_KEY not configured"**
   - Ensure your `.env` file contains valid Vapi credentials
   - Check that the `.env` file is in the same directory as the server script

2. **Port already in use**
   - Change the PORT in your `.env` file or kill the existing process
   - Use `lsof -i :8000` to find processes using port 8000

3. **CORS errors in browser**
   - The server includes CORS headers, but check your frontend URL matches the allowed origins

### Logs

The server uses Python's logging module. Increase verbosity by setting:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Production Deployment

For production deployment, consider:

1. **Use a production WSGI server** like Gunicorn
2. **Configure proper CORS** origins
3. **Add authentication/authorization** 
4. **Set up SSL/TLS** certificates
5. **Configure logging** and monitoring
6. **Add rate limiting** and request validation

Example production command:
```bash
gunicorn fastapi_server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```
