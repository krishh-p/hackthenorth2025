import { HandVisual } from "SpectaclesInteractionKit.lspkg/Components/Interaction/HandVisual/HandVisual";
import { ButtonSnap3DGenerator } from "./ButtonSnap3DGenerator";
import { WebSocketController } from "./WebSocketController";

@component
export class ObjectPinchWatcher extends BaseScriptComponent {
  @input
  @hint('Reference to the ButtonSnap3DGenerator')
  buttonSnap3DGenerator: ButtonSnap3DGenerator;

  @input
  @hint('Reference to the WebSocketController')
  webSocketController: WebSocketController;

  @input
  @hint('Use right hand? (true = Right hand, false = Left hand)')
  useRightHand: boolean = true;

  @input
  @hint('Distance threshold for pinch detection')
  pinchThreshold: number = 8.0;

  @input
  @hint('Minimum time between pinch detections (in seconds)')
  pinchCooldown: number = 1.0;

  private handVisual: HandVisual;
  private lastPinchTimes: Map<string, number> = new Map();
  private isInitialized: boolean = false;

  onAwake() {
    this.createEvent('OnStartEvent').bind(() => {
      this.initializeHandTracking();
    });

    this.createEvent('UpdateEvent').bind(() => {
      this.update();
    });
  }

  private initializeHandTracking() {
    if (!this.buttonSnap3DGenerator) {
      print('ERROR: ObjectPinchWatcher requires ButtonSnap3DGenerator reference');
      return;
    }

    if (!this.webSocketController) {
      print('ERROR: ObjectPinchWatcher requires WebSocketController reference');
      return;
    }

    // Find the appropriate hand visual
    let foundHandVisual: HandVisual | null = null;
    const rootCount = global.scene.getRootObjectsCount();

    for (let i = 0; i < rootCount; i++) {
      const rootObject = global.scene.getRootObject(i);
      foundHandVisual = this.searchForHandVisual(rootObject);
      if (foundHandVisual) break;
    }

    if (!foundHandVisual) {
      const handTypeName = this.useRightHand ? "Right" : "Left";
      print(`ERROR: Could not find ${handTypeName} hand visual in the scene`);
      return;
    }

    this.handVisual = foundHandVisual;
    this.isInitialized = true;
    print(`ObjectPinchWatcher initialized with ${this.useRightHand ? 'Right' : 'Left'} hand tracking`);
  }

  private searchForHandVisual(sceneObject: SceneObject): HandVisual | null {
    try {
      const handVisual = sceneObject.getComponent(HandVisual.getTypeName()) as HandVisual;
      if (handVisual) {
        const handName = sceneObject.name.toLowerCase();
        const isCorrectHand =
          (!this.useRightHand && handName.includes("left")) ||
          (this.useRightHand && handName.includes("right"));

        if (isCorrectHand) {
          return handVisual;
        }
      }
    } catch (e) {
      // Object doesn't have HandVisual component, continue searching
    }

    // Search through children
    for (let i = 0; i < sceneObject.getChildrenCount(); i++) {
      const child = sceneObject.getChild(i);
      const result = this.searchForHandVisual(child);
      if (result) return result;
    }

    return null;
  }

  private update() {
    if (!this.isInitialized || !this.handVisual) return;
    if (!this.buttonSnap3DGenerator.objectsParent) return;

    // Get hand position
    const indexTip = this.handVisual.indexTip;
    const thumbTip = this.handVisual.thumbTip;

    if (!indexTip || !thumbTip) return;

    const indexPos = indexTip.getTransform().getWorldPosition();
    const thumbPos = thumbTip.getTransform().getWorldPosition();

    // Check if fingers are pinched (close together)
    const fingerDistance = indexPos.distance(thumbPos);
    const isPinching = fingerDistance < this.pinchThreshold;

    if (!isPinching) return;

    // Get midpoint between fingers for collision detection
    const pinchPosition = indexPos.add(thumbPos).uniformScale(0.5);

    // Check all children of objectsParent for pinch collisions
    const objectsParent = this.buttonSnap3DGenerator.objectsParent;
    const childrenCount = objectsParent.getChildrenCount();

    for (let i = 0; i < childrenCount; i++) {
      const child = objectsParent.getChild(i);
      if (!child.enabled) continue;

      const childPosition = child.getTransform().getWorldPosition();
      const distanceToObject = pinchPosition.distance(childPosition);

      // Check if pinch is close enough to the object (within reasonable range)
      const objectInteractionRange = 15.0; // Adjust as needed
      if (distanceToObject < objectInteractionRange) {
        this.handleObjectPinch(child);
      }
    }
  }

  private handleObjectPinch(object: SceneObject) {
    const currentTime = getTime();
    const objectName = object.name;

    // Check cooldown
    const lastPinchTime = this.lastPinchTimes.get(objectName) || 0;
    if (currentTime - lastPinchTime < this.pinchCooldown) {
      return; // Still in cooldown
    }

    // Update last pinch time
    this.lastPinchTimes.set(objectName, currentTime);

    // Get object position
    const objectPosition = object.getTransform().getWorldPosition();

    // Send WebSocket message
    this.webSocketController.sendObjectPinched(objectName, objectPosition);

    // Visual feedback (optional - scale the object briefly)
    this.providePinchFeedback(object);

    print(`🤏 Object pinched: ${objectName} at position (${objectPosition.x.toFixed(2)}, ${objectPosition.y.toFixed(2)}, ${objectPosition.z.toFixed(2)})`);
  }

  private providePinchFeedback(object: SceneObject) {
    // Simple scale feedback - scale up briefly then return to normal
    const originalScale = object.getTransform().getLocalScale();
    const feedbackScale = originalScale.uniformScale(1.2);

    // Scale up
    object.getTransform().setLocalScale(feedbackScale);

    // Scale back down after a short delay
    const delayedCall = this.createEvent("DelayedCallbackEvent");
    delayedCall.bind(() => {
      if (!isNull(object)) {
        object.getTransform().setLocalScale(originalScale);
      }
    });
    delayedCall.reset(0.2); // 200ms feedback duration
  }
}