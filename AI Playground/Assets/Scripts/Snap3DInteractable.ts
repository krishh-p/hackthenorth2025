import { setTimeout } from "SpectaclesInteractionKit.lspkg/Utils/FunctionTimingUtils";
import { Interactable } from "SpectaclesInteractionKit.lspkg/Components/Interaction/Interactable/Interactable";
import { InteractableManipulation } from "SpectaclesInteractionKit.lspkg/Components/Interaction/InteractableManipulation/InteractableManipulation";
import { InteractionManager } from "SpectaclesInteractionKit.lspkg/Core/InteractionManager/InteractionManager";
import { WebSocketController } from "./WebSocketController";

@component
export class Snap3DInteractable extends BaseScriptComponent {
  @input
  private modelParent: SceneObject;
  @input
  private img: Image;
  @input
  private promptDisplay: Text;
  @input
  private spinner: SceneObject;
  @input
  private mat: Material;
  @input
  private displayPlate: SceneObject;
  @input
  private colliderObj: SceneObject;
  private tempModel: SceneObject = null;
  private finalModel: SceneObject = null;
  private size: number = 20;
  private sizeVec: vec3 = null;
  private interactable: Interactable;
  private manipulation: InteractableManipulation;
  private webSocketController: WebSocketController;

  onAwake() {
    // Clone the image material to avoid modifying the original
    let imgMaterial = this.img.mainMaterial;
    imgMaterial.mainPass.baseTex = this.img.mainPass.baseTex;
    this.img.enabled = false;

    let offsetBelow = 0;
    this.sizeVec = vec3.one().uniformScale(this.size);
    this.displayPlate
      .getTransform()
      .setLocalPosition(new vec3(0, -this.size * 0.5 - offsetBelow, 0));
    this.colliderObj.getTransform().setLocalScale(this.sizeVec);
    this.img.getTransform().setLocalScale(this.sizeVec);

    this.setupInteraction();
  }

  public setWebSocketController(controller: WebSocketController) {
    this.webSocketController = controller;
    print(`✓ WebSocketController set for object: ${this.promptDisplay.text}`);
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

    // Set up pinch event handlers
    this.interactable.onHoverEnter.add(this.onHoverEnter.bind(this));
    this.interactable.onHoverExit.add(this.onHoverExit.bind(this));
    this.interactable.onTriggerStart.add(this.onPinchStart.bind(this));
    this.interactable.onTriggerEnd.add(this.onPinchEnd.bind(this));

    print(`✓ Interaction setup complete for object: ${this.promptDisplay.text}`);
  }

  private onHoverEnter() {
    print(`Hovering over: ${this.promptDisplay.text}`);
    // Optional: Add visual feedback for hover
  }

  private onHoverExit() {
    print(`Hover exit: ${this.promptDisplay.text}`);
    // Optional: Remove visual feedback
  }

  private onPinchStart() {
    print(`✓ Pinch started on: ${this.promptDisplay.text}`);

    // Send pinch event via WebSocket
    if (this.webSocketController) {
      const position = this.sceneObject.getTransform().getWorldPosition();
      print(`🔍 DEBUG: About to send WebSocket message for: ${this.promptDisplay.text}`);
      print(`🔍 DEBUG: Position: x=${position.x.toFixed(3)}, y=${position.y.toFixed(3)}, z=${position.z.toFixed(3)}`);
      print(`🔍 DEBUG: WebSocketController found: ${this.webSocketController !== null}`);

      this.webSocketController.sendObjectPinched(this.promptDisplay.text, position);

      print(`🔍 DEBUG: WebSocket sendObjectPinched called successfully`);
    } else {
      print(`⚠️ Cannot send WebSocket message - controller not found`);
    }
  }

  private onPinchEnd() {
    print(`✓ Pinch ended on: ${this.promptDisplay.text}`);
    // Add pinch release logic here if needed
  }

  setPrompt(prompt: string) {
    this.promptDisplay.text = prompt;
  }

  setImage(image: Texture) {
    this.img.enabled = true;
    this.img.mainPass.baseTex = image;
  }

  setModel(model: GltfAsset, isFinal: boolean) {
    this.img.enabled = false;
    if (isFinal) {
      if (!isNull(this.finalModel)) {
        this.finalModel.destroy();
      }
      this.spinner.enabled = false;
      this.finalModel = model.tryInstantiate(this.modelParent, this.mat);
      this.finalModel.getTransform().setLocalScale(this.sizeVec);
    } else {
      this.tempModel = model.tryInstantiate(this.modelParent, this.mat);
      this.tempModel.getTransform().setLocalScale(this.sizeVec);
    }
  }

  onFailure(error: string) {
    this.img.enabled = false;
    this.spinner.enabled = false;
    if (this.tempModel) {
      this.tempModel.destroy();
    }
    if (this.finalModel) {
      this.finalModel.destroy();
    }
    this.promptDisplay.text = "Error: " + error;
    setTimeout(() => {
      this.destroy();
    }, 5000); // Hide error after 5 seconds
  }
}
