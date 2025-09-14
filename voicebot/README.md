# Train in a Snap!  

**Immersive AR training powered by Snapchat Spectacles, Snap APIs, and Vapi Voice AI**  

---

## Inspiration  
We wanted to build safer, faster ways to practice **emergency training**. At first, we planned to use Meta Quest 3 and LiDAR scans, but pivoted to **Snapchat Spectacles** so we could leverage Snap’s AR capabilities and create a more lightweight, wearable solution.  

---

## What it does  
**Train in a Snap!** generates an **augmented reality training environment** where users complete tasks guided by **real-time voice instructions**. Using the **Snapchat Snap3D API**, the system creates objects needed for a scenario (like a fire extinguisher or first-aid kit) and anchors them in place with **Spatial Persistence**.  

The **Vapi Voicebot** then instructs the user through the scenario step by step:  
- “Find the extinguisher.”  
- “Pick it up and aim at the fire.”  
- “Sweep side to side until the flames disappear.”  

This results in a **hands-free, interactive training experience** blending generative AR with conversational AI.  

---

## How we built it  
1. **Snapchat Spectacles + Lens Studio** for AR anchoring and persistence.  
2. **Snap3D API** to dynamically generate scenario-specific 3D objects.  
3. **Vapi Voicebot API** to provide natural, real-time spoken instructions.  
4. Backend **broadcasts** that instruction back to the Spectacles over the same **WebSocket**.

---

## Challenges we ran into  
- Learning Snap’s new **Snap3D + Spatial Persistence APIs** under time pressure.  
- Syncing **generated objects** with **voice instructions** so tasks felt natural.  
- Pivoting quickly from Meta Quest 3 to Snap Spectacles while preserving our vision.  

---

## Accomplishments that we're proud of  
- Built a **working AR prototype** that combines Snap’s AR generation with live voice guidance.  
- Designed an experience that feels natural, intuitive, and useful for safety training.  
- Pulled off a pivot and still hit two sponsor tracks.  

---

## What we learned  
- How to use **Snapchat Spectacles APIs** beyond simple lenses.  
- How to **dynamically generate AR content** with Snap3D.  
- The power of **voice + AR multimodal interfaces**.  

---

## What’s next for Train in a Snap!  
- Expand scenarios: first aid, evacuation, workplace safety.  
- Add **multi-user AR** so teams can train together.  
- Smarter AI guidance that adapts dynamically to user performance.  
- Enterprise use cases: onboarding, tutorials, and industrial training.  

---

## 🎤 Voicebot Component

The **Vapi Voicebot** is a standalone web application that provides the voice AI functionality for our AR training system. It features:

### ✨ Features
- **Real-time voice conversations** with AI
- **Professional audio processing** using Web Audio API  
- **Clean, minimalist UI** with dark theme
- **AudioWorklet-based capture** for high-quality microphone input
- **Jitter buffer playback** for smooth AI voice output
- **WebSocket-based streaming** for low latency
- **Cloud-ready deployment** on Heroku

### 🚀 Live Demo
**[Try the Voicebot](https://hackthenorth2025-voicebot-fdeea2d593ac.herokuapp.com/)**

### 🏗️ Technical Architecture
```
[Browser Audio] → [WebSocket] → [FastAPI Server] → [Vapi WebSocket] → [AI Response] → [Browser Audio]
```

- **Frontend**: Vanilla JavaScript with Web Audio API
- **Backend**: FastAPI with WebSocket proxy  
- **AI Service**: Vapi for voice processing
- **Audio**: 16kHz PCM16 mono format

### 📁 Voicebot Structure
```
voicebot/
├── fastapi_server_cloud.py    # Main server application
├── worklets/
│   └── capture-16k.js         # AudioWorklet for microphone capture
├── requirements.txt           # Python dependencies
├── Procfile                   # Heroku deployment config
└── README.md                  # This file
```

---

## Submission Tracks  
- **Snap: Spectacles AR Hackathon – Game On!**  
- **Vapi: Best Voice AI Application**  

---
