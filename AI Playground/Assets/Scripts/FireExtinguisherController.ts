import { Interactable } from "SpectaclesInteractionKit.lspkg/Components/Interaction/Interactable/Interactable";
import { InteractableManipulation } from "SpectaclesInteractionKit.lspkg/Components/Interaction/InteractableManipulation/InteractableManipulation";
import { Interactor } from "SpectaclesInteractionKit.lspkg/Core/Interactor/Interactor";
import { InteractorEvent } from "SpectaclesInteractionKit.lspkg/Core/Interactor/InteractorEvent";
import { FireBehavior } from "./FireBehavior";
import { WebSocketController } from "./WebSocketController";

@component
export class FireExtinguisherController extends BaseScriptComponent {
  private interactable: Interactable;
  private manipulation: InteractableManipulation;
  private currentInteractor: Interactor;
  private isActive: boolean = false;
  private currentTargetFire: FireBehavior;
  private webSocketController: WebSocketController;

  @input
  @ui.group_start("Fire Extinguisher Settings")
  private extinguisherRange: number = 30.0; // Max range for extinguishing (much closer)
  @ui.group_end

  // Optional audio/visual components (not @input to avoid required field errors)
  private spraySound: AudioTrackAsset = null;
  private audioComponent: AudioComponent = null;
  private sprayParticles: SceneObject = null;

  onAwake() {
    this.setupInteraction();
    print(`🧯 Fire extinguisher initialized: ${this.sceneObject.name}`);
  }

  public setWebSocketController(controller: WebSocketController) {
    this.webSocketController = controller;
    print(`✓ WebSocketController set for fire extinguisher`);
  }

  private setupInteraction() {
    // Get or create Interactable component
    this.interactable = this.sceneObject.getComponent(Interactable.getTypeName()) as Interactable;
    if (!this.interactable) {
      this.interactable = this.sceneObject.createComponent(Interactable.getTypeName()) as Interactable;
    }

    // Get or create InteractableManipulation component
    this.manipulation = this.sceneObject.getComponent(InteractableManipulation.getTypeName()) as InteractableManipulation;
    if (!this.manipulation) {
      this.manipulation = this.sceneObject.createComponent(InteractableManipulation.getTypeName()) as InteractableManipulation;
    }

    // Set up interaction event handlers
    this.interactable.onTriggerStart.add(this.onExtinguisherActivated.bind(this));
    this.interactable.onTriggerEnd.add(this.onExtinguisherDeactivated.bind(this));

    print(`✓ Fire extinguisher interaction setup complete`);
  }

  private onExtinguisherActivated(interactorEvent: InteractorEvent) {
    this.currentInteractor = interactorEvent.interactor;
    this.isActive = true;

    print(`🧯 Fire extinguisher activated by user`);

    // Play spray sound
    this.playSpraySound();

    // Show spray particles if available
    if (this.sprayParticles) {
      this.sprayParticles.enabled = true;
    }

    // Send WebSocket notification
    if (this.webSocketController) {
      const position = this.sceneObject.getTransform().getWorldPosition();
      this.sendExtinguisherEvent(position, "activated");
    }

    // Start the update loop to continuously check for fire targets
    this.createEvent("UpdateEvent").bind(this.updateExtinguisher.bind(this));
  }

  private onExtinguisherDeactivated(interactorEvent: InteractorEvent) {
    this.isActive = false;
    this.currentInteractor = null;

    print(`🧯 Fire extinguisher deactivated`);

    // Stop targeting any current fire
    if (this.currentTargetFire && this.currentTargetFire.sceneObject && !isNull(this.currentTargetFire.sceneObject)) {
      this.currentTargetFire.stopExtinguishing();
      this.currentTargetFire = null;
    }

    // Hide spray particles
    if (this.sprayParticles) {
      this.sprayParticles.enabled = false;
    }

    // Send WebSocket notification
    if (this.webSocketController) {
      const position = this.sceneObject.getTransform().getWorldPosition();
      this.sendExtinguisherEvent(position, "deactivated");
    }
  }

  private updateExtinguisher() {
    if (!this.isActive) {
      return;
    }

    // Find the nearest fire object within range
    const nearbyFire = this.findNearestFire();

    if (nearbyFire !== this.currentTargetFire) {
      // Stop extinguishing previous fire
      if (this.currentTargetFire && this.currentTargetFire.sceneObject && !isNull(this.currentTargetFire.sceneObject)) {
        this.currentTargetFire.stopExtinguishing();
        print(`🧯 Stopped extinguishing: ${this.currentTargetFire.sceneObject.name}`);
      }

      // Start extinguishing new fire
      this.currentTargetFire = nearbyFire;
      if (this.currentTargetFire && this.currentTargetFire.sceneObject && !isNull(this.currentTargetFire.sceneObject)) {
        this.currentTargetFire.startExtinguishing();
        print(`🎯 Now extinguishing nearby fire: ${this.currentTargetFire.sceneObject.name}`);
      }
    }
  }

  private findNearestFire(): FireBehavior | null {
    const extinguisherPosition = this.sceneObject.getTransform().getWorldPosition();
    let nearestFire: FireBehavior | null = null;
    let nearestDistance = this.extinguisherRange;

    // Search through all objects in the scene for fire behaviors
    // This is a simple brute-force approach - could be optimized with a fire registry
    const allObjects = this.getAllSceneObjects();

    for (const obj of allObjects) {
      if (!obj || isNull(obj)) {
        continue;
      }

      const fireBehavior = obj.getComponent(FireBehavior.getTypeName()) as FireBehavior;
      if (fireBehavior && !fireBehavior.isExtinguished() && fireBehavior.sceneObject && !isNull(fireBehavior.sceneObject)) {
        const firePosition = obj.getTransform().getWorldPosition();
        const distance = extinguisherPosition.distance(firePosition);

        if (distance <= nearestDistance) {
          nearestDistance = distance;
          nearestFire = fireBehavior;
        }
      }
    }

    if (nearestFire) {
      print(`🔍 Found fire at distance: ${nearestDistance.toFixed(2)} units`);
    }

    return nearestFire;
  }

  private getAllSceneObjects(): SceneObject[] {
    // Simple method to get all objects in scene
    // Start from the root and traverse down
    const allObjects: SceneObject[] = [];

    // Get the scene root - we'll traverse from the parent object
    let currentObj = this.sceneObject;
    while (currentObj.getParent()) {
      currentObj = currentObj.getParent();
    }

    // Recursively collect all objects
    this.collectChildObjects(currentObj, allObjects);

    return allObjects;
  }

  private collectChildObjects(obj: SceneObject, collection: SceneObject[]) {
    collection.push(obj);

    for (let i = 0; i < obj.getChildrenCount(); i++) {
      const child = obj.getChild(i);
      this.collectChildObjects(child, collection);
    }
  }

  private playSpraySound() {
    if (this.audioComponent && this.spraySound) {
      this.audioComponent.audioTrack = this.spraySound;
      this.audioComponent.play(1);
    }
  }

  private sendExtinguisherEvent(position: vec3, status: string) {
    if (!this.webSocketController) {
      return;
    }

    const message = {
      type: 'extinguisher_used',
      objectName: this.sceneObject.name,
      status: status, // "activated", "deactivated"
      targetFire: this.currentTargetFire ? this.currentTargetFire.sceneObject.name : null,
      position: {
        x: position.x,
        y: position.y,
        z: position.z
      },
      timestamp: Date.now()
    };

    // Send via WebSocket
    if (this.webSocketController.send) {
      this.webSocketController.send(JSON.stringify(message));
      print(`📤 Sent extinguisher event: ${status}`);
    } else {
      print(`📤 Would send extinguisher event: ${status}`);
    }
  }

  // Public methods for external systems
  public isExtinguisherActive(): boolean {
    return this.isActive;
  }

  public getCurrentTarget(): FireBehavior | null {
    return this.currentTargetFire;
  }
}