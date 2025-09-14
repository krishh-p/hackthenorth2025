/**
 * WebSocketController - Simple debug script to test WebSocket connectivity
 */

@component
export class WebSocketController extends BaseScriptComponent {
  @input
  @hint('WebSocket server URL')
  serverUrl: string = 'ws://localhost:8080';

  // @input
  // @hint('Text component to display debug info')
  // debugText: Text;

  private internetModule: InternetModule = require('LensStudio:InternetModule');
  private webSocket: WebSocket;
  private isConnected: boolean = false;

  onAwake() {
    this.createEvent('OnStartEvent').bind(() => {
      this.debug('Starting WebSocket debug script...');
      this.connect();
    });

    this.createEvent('UpdateEvent').bind(() => {
      this.update();
    });
  }

  private connect() {
    this.debug('Attempting to connect to: ' + this.serverUrl);

    if (!this.internetModule) {
      this.debug('ERROR: Internet Module not available');
      return;
    }

    try {
      this.webSocket = this.internetModule.createWebSocket(this.serverUrl);
      this.webSocket.binaryType = 'blob';

      this.webSocket.onopen = (event) => {
        this.debug('✅ WebSocket CONNECTED!');
        this.isConnected = true;
      };

      this.webSocket.onmessage = (event) => {
        const rawData = event.data as string; // The raw text or Blob from the socket
        let parsed;
        try {
          parsed = JSON.parse(rawData); // Parse JSON if you know you're sending JSON
        } catch (e) {
          parsed = rawData; // Fallback if it's not valid JSON
        }
        this.debug('📨 Received message: ' + JSON.stringify(parsed));
      };

      this.webSocket.onclose = (event) => {
        this.debug('❌ WebSocket CLOSED: ' + event.reason);
        this.isConnected = false;
      };

      this.webSocket.onerror = (event) => {
        this.debug('💥 WebSocket ERROR: ' + event);
      };
    } catch (error) {
      this.debug('❌ Connection failed: ' + error);
    }
  }

  private sendTestMessage() {
    if (this.isConnected && this.webSocket) {
      const message = {
        type: 'debug_test',
        message: 'Hello from Spectacles debug script!',
        timestamp: Date.now(),
      };

      this.webSocket.send(JSON.stringify(message));
      this.debug('📤 Sent test message');
    }
  }

  private update() {
    // No periodic messages needed
  }

  private updateDebugText(text: string) {
    // if (this.debugText) {
    //   this.debugText.text = text;
    // }
  }

  private debug(message: string) {
    print('[WebSocketDebug] ' + message);
  }

  public sendObjectPinched(objectName: string, position: vec3) {
    if (this.isConnected && this.webSocket) {
      const message = {
        type: 'object_pinched',
        objectName: objectName,
        position: {
          x: position.x,
          y: position.y,
          z: position.z
        },
        timestamp: Date.now()
      };

      this.webSocket.send(JSON.stringify(message));
      this.debug('📤 Sent object pinched: ' + objectName);
    } else {
      this.debug('⚠️ Cannot send object pinched - WebSocket not connected');
    }
  }
}