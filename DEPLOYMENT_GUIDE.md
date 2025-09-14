# 🚀 Heroku Deployment Guide for Voicebot

## 🚨 Key Changes for Cloud Deployment

### **The Problem with Local Audio**
Your original `audio_voice_test.py` won't work on Heroku because:
- ❌ No microphones/speakers on cloud servers
- ❌ No audio drivers (ALSA, PulseAudio, etc.)
- ❌ `sounddevice` library requires hardware

### **The Solution: Browser-Based Audio**
- ✅ Move audio capture to web browser
- ✅ Use WebSocket for real-time streaming
- ✅ Server acts as proxy between browser and Vapi

## 📁 Files Created for Cloud Deployment

### **Core Files**
- `fastapi_server_cloud.py` - Cloud-ready server (no audio hardware deps)
- `requirements_cloud.txt` - Dependencies without audio libraries
- `Procfile` - Heroku process definition
- `runtime.txt` - Python version specification
- `app.json` - Heroku app configuration

### **Architecture Changes**

```
OLD (Local):
[Microphone] → [Python Script] → [Vapi API] → [Speakers]

NEW (Cloud):
[Browser Audio] → [WebSocket] → [FastAPI Server] → [Vapi WebSocket] → [Browser Audio]
```

## 🛠️ Deployment Steps

### **1. Prepare Your Code**

Replace your local server with the cloud version:
```bash
# Use the cloud-ready server instead of the original
cp fastapi_server_cloud.py fastapi_server.py
cp requirements_cloud.txt requirements.txt
```

### **2. Install Heroku CLI**
```bash
# macOS
brew tap heroku/brew && brew install heroku

# Or download from: https://devcenter.heroku.com/articles/heroku-cli
```

### **3. Login to Heroku**
```bash
heroku login
```

### **4. Create Heroku App**
```bash
# Create new app
heroku create your-voicebot-app-name

# Or use the app.json for one-click deploy
# https://heroku.com/deploy?template=https://github.com/your-repo
```

### **5. Set Environment Variables**
```bash
heroku config:set VAPI_API_KEY=your_actual_vapi_key
heroku config:set VAPI_ASSISTANT_ID=your_actual_assistant_id

# Verify settings
heroku config
```

### **6. Deploy**
```bash
# Initialize git if not already done
git init
git add .
git commit -m "Initial commit"

# Add Heroku remote
heroku git:remote -a your-voicebot-app-name

# Deploy
git push heroku main
```

### **7. Test Deployment**
```bash
# Open your app
heroku open

# Check logs
heroku logs --tail

# Test endpoints
curl https://your-app.herokuapp.com/health
```

## 🌐 Using the Deployed API

### **Endpoints Available**
- `GET /` - Health check
- `GET /health` - Detailed status
- `GET /demo` - Interactive web demo
- `POST /chat/start` - Start Vapi session
- `POST /chat/text` - Text-only chat
- `WS /ws/{call_id}` - WebSocket for real-time audio

### **Web Demo**
Visit `https://your-app.herokuapp.com/demo` for a complete web interface that:
- ✅ Captures browser microphone
- ✅ Connects to your API via WebSocket
- ✅ Streams audio to/from Vapi
- ✅ Plays AI responses through browser speakers

## 🔧 Frontend Integration

### **JavaScript Example**
```javascript
// Start a voice session
async function startVoiceChat() {
  // 1. Create Vapi session
  const response = await fetch('/chat/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  });
  
  const data = await response.json();
  
  if (data.success) {
    // 2. Connect to WebSocket
    const ws = new WebSocket(`wss://your-app.herokuapp.com/ws/${data.call_id}`);
    
    // 3. Set up browser audio
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream);
    
    // 4. Send audio to server
    mediaRecorder.ondataavailable = (event) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result.split(',')[1];
        ws.send(JSON.stringify({
          type: 'audio_to_vapi',
          data: base64
        }));
      };
      reader.readAsDataURL(event.data);
    };
    
    // 5. Receive audio from server
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'audio_from_vapi') {
        // Play audio in browser
        playAudioFromBase64(message.data);
      }
    };
    
    mediaRecorder.start(100); // Send audio chunks every 100ms
  }
}
```

### **React/Vue/Angular Integration**
The WebSocket API works with any frontend framework:

```javascript
// React Hook Example
function useVoicebot() {
  const [ws, setWs] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  
  const connect = async () => {
    const response = await fetch('/chat/start', { method: 'POST' });
    const data = await response.json();
    
    const websocket = new WebSocket(`/ws/${data.call_id}`);
    websocket.onopen = () => setIsConnected(true);
    websocket.onclose = () => setIsConnected(false);
    
    setWs(websocket);
  };
  
  return { connect, isConnected, ws };
}
```

## 🔒 Production Considerations

### **Security**
```javascript
// Update CORS for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specify your domain
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### **Scaling**
```bash
# Scale up dynos
heroku ps:scale web=2

# Use better dyno types
heroku ps:resize web=standard-1x
```

### **Monitoring**
```bash
# Add logging addon
heroku addons:create papertrail

# Monitor performance
heroku addons:create newrelic
```

### **Environment Management**
```bash
# Staging environment
heroku create your-app-staging
heroku config:set VAPI_API_KEY=staging_key --app your-app-staging

# Production environment  
heroku create your-app-production
heroku config:set VAPI_API_KEY=prod_key --app your-app-production
```

## 🐛 Troubleshooting

### **Common Issues**

**1. "No audio devices" error**
```
❌ Error: sounddevice not found
✅ Solution: Use fastapi_server_cloud.py (no audio hardware deps)
```

**2. WebSocket connection fails**
```bash
# Check logs
heroku logs --tail

# Verify WebSocket support
curl -H "Upgrade: websocket" https://your-app.herokuapp.com/ws/test
```

**3. Vapi connection errors**
```bash
# Verify environment variables
heroku config

# Test API key
curl -H "Authorization: Bearer YOUR_KEY" https://api.vapi.ai/assistant
```

**4. Browser audio permissions**
```javascript
// Handle permission errors
navigator.mediaDevices.getUserMedia({ audio: true })
  .catch(err => {
    if (err.name === 'NotAllowedError') {
      alert('Please allow microphone access');
    }
  });
```

### **Debugging Commands**
```bash
# View app logs
heroku logs --tail

# Check dyno status
heroku ps

# Test endpoints
heroku run curl http://localhost:$PORT/health

# SSH into dyno (for debugging)
heroku run bash
```

## 📊 Performance Optimization

### **Audio Streaming**
- Use small audio chunks (100-200ms)
- Implement audio buffering on client side
- Consider WebRTC for lower latency

### **WebSocket Management**
- Implement connection pooling
- Add reconnection logic
- Handle network interruptions gracefully

### **Caching**
```python
# Add Redis for session management
import redis
r = redis.from_url(os.environ.get("REDIS_URL"))
```

## 🔄 Continuous Deployment

### **GitHub Actions**
```yaml
# .github/workflows/deploy.yml
name: Deploy to Heroku
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: akhileshns/heroku-deploy@v3.12.12
        with:
          heroku_api_key: ${{secrets.HEROKU_API_KEY}}
          heroku_app_name: "your-app-name"
          heroku_email: "your-email@example.com"
```

## 📱 Mobile Considerations

The web-based approach works on mobile browsers:
- iOS Safari: ✅ WebRTC supported
- Android Chrome: ✅ Full audio API support
- PWA: Can be installed as native app

## 🎯 Summary

**What Changed:**
- ❌ Removed local audio dependencies (`sounddevice`, `numpy`)
- ✅ Added browser-based audio capture
- ✅ WebSocket proxy architecture
- ✅ Cloud-ready deployment files

**What You Get:**
- 🌐 Web-accessible voicebot
- 📱 Mobile browser support
- ⚡ Real-time audio streaming
- 🔄 Scalable architecture
- 🛡️ Production-ready setup

Your voicebot is now ready for cloud deployment with **better accessibility** and **wider compatibility** than the local version!
