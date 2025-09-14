import { WebSocketController } from "./WebSocketController";

@component
export class FireBehavior extends BaseScriptComponent {
  private originalScale: vec3;
  private currentScale: vec3;
  private isBeingExtinguished: boolean = false;
  private extinguishRate: number = 0.3; // Scale reduction per second
  private minimumScale: number = 0.0; // Minimum scale before destruction (0% of original)
  private webSocketController: WebSocketController;

  @input
  @ui.group_start("Fire Settings")
  private fireIntensity: number = 1.0;
  @ui.group_end

  // Optional audio components (not @input to avoid required field errors)
  private extinguishSound: AudioTrackAsset = null;
  private audioComponent: AudioComponent = null;

  onAwake() {
    this.originalScale = this.sceneObject.getTransform().getLocalScale();
    this.currentScale = this.originalScale;

    print(`🔥 Fire object created with scale: ${this.originalScale.x.toFixed(2)}`);
  }

  public setWebSocketController(controller: WebSocketController) {
    this.webSocketController = controller;
  }

  public startExtinguishing() {
    if (this.isBeingExtinguished) {
      return; // Already being extinguished
    }

    this.isBeingExtinguished = true;
    print(`🧯 Starting to extinguish fire: ${this.sceneObject.name}`);

    // Play extinguish sound
    this.playExtinguishSound();

    // Send WebSocket notification
    if (this.webSocketController) {
      const position = this.sceneObject.getTransform().getWorldPosition();
      this.sendFireExtinguishEvent(position, "started");
    }

    // Start the extinguishing process
    this.createEvent("UpdateEvent").bind(this.updateExtinguishing.bind(this));
  }

  public stopExtinguishing() {
    if (!this.isBeingExtinguished || !this.sceneObject || isNull(this.sceneObject)) {
      return;
    }

    this.isBeingExtinguished = false;
    print(`🔥 Stopped extinguishing fire: ${this.sceneObject.name}`);

    // Send WebSocket notification
    if (this.webSocketController && this.sceneObject && !isNull(this.sceneObject)) {
      const position = this.sceneObject.getTransform().getWorldPosition();
      this.sendFireExtinguishEvent(position, "stopped");
    }
  }

  private updateExtinguishing() {
    if (!this.isBeingExtinguished || !this.sceneObject || isNull(this.sceneObject)) {
      return;
    }

    // Calculate scale reduction based on frame time
    const deltaTime = getDeltaTime();
    const scaleReduction = this.extinguishRate * deltaTime;

    // Reduce scale uniformly
    const newScaleValue = Math.max(
      this.currentScale.x - scaleReduction,
      this.originalScale.x * this.minimumScale
    );

    this.currentScale = new vec3(newScaleValue, newScaleValue, newScaleValue);

    // Check if object still exists before setting scale
    if (this.sceneObject && !isNull(this.sceneObject)) {
      this.sceneObject.getTransform().setLocalScale(this.currentScale);
    }

    // Check if fire is completely extinguished
    if (newScaleValue <= this.originalScale.x * this.minimumScale) {
      this.fullyExtinguished();
    } else {
      // Update fire intensity based on current scale
      this.fireIntensity = newScaleValue / this.originalScale.x;
      print(`🔥 Fire scale reduced to: ${newScaleValue.toFixed(3)} (${(this.fireIntensity * 100).toFixed(1)}% intensity)`);
    }
  }

  private fullyExtinguished() {
    print(`✅ Fire completely extinguished: ${this.sceneObject.name}`);

    // Send WebSocket notification
    if (this.webSocketController) {
      const position = this.sceneObject.getTransform().getWorldPosition();
      this.sendFireExtinguishEvent(position, "extinguished");
    }

    // Keep the fire at 0 scale instead of destroying it
    this.fireIntensity = 0.0;
    this.isBeingExtinguished = false; // Stop the update loop
    print(`🔥 Fire kept at 0% intensity - not destroying object`);
  }

  private playExtinguishSound() {
    if (this.audioComponent && this.extinguishSound) {
      this.audioComponent.audioTrack = this.extinguishSound;
      this.audioComponent.play(1);
    }
  }

  private sendFireExtinguishEvent(position: vec3, status: string) {
    if (!this.webSocketController) {
      return;
    }

    const message = {
      type: 'fire_extinguished',
      objectName: this.sceneObject.name,
      status: status, // "started", "stopped", "extinguished"
      intensity: this.fireIntensity,
      position: {
        x: position.x,
        y: position.y,
        z: position.z
      },
      timestamp: Date.now()
    };

    // Use a similar method to sendObjectPinched - we'll need to add this to WebSocketController
    if (this.webSocketController.send) {
      this.webSocketController.send(JSON.stringify(message));
      print(`📤 Sent fire extinguish event: ${status}`);
    }
  }

  // Public getter for external systems
  public getFireIntensity(): number {
    return this.fireIntensity;
  }

  public isExtinguished(): boolean {
    return this.fireIntensity <= this.minimumScale || !this.sceneObject || isNull(this.sceneObject);
  }
}