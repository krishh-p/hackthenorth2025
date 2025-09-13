import { Interactable } from "SpectaclesInteractionKit.lspkg/Components/Interaction/Interactable/Interactable";
import { InteractableManipulation } from "SpectaclesInteractionKit.lspkg/Components/Interaction/InteractableManipulation/InteractableManipulation";
import { Billboard } from "SpectaclesInteractionKit.lspkg/Components/Interaction/Billboard/Billboard";
import { InteractableOutlineFeedback } from "SpectaclesInteractionKit.lspkg/Components/Helpers/InteractableOutlineFeedback";
import { Widget } from "../Widget";
import { SnapToWorld } from "../WorldQuery/SnapToWorld";
import {
  lerp,
  mapValue,
  clamp,
} from "SpectaclesInteractionKit.lspkg/Utils/mathUtils";
import { easingFunctions } from "SpectaclesInteractionKit.lspkg/Utils/animate";

@component
export class InteractableBox extends BaseScriptComponent {
  @input
  @allowUndefined
  private boxMesh: RenderMeshVisual;

  @input
  @hint("Physics body for gravity after dropping (optional)")
  @allowUndefined
  private physicsBody: BodyComponent;

  @input
  @hint("Outline material that appears when the box is being manipulated")
  @allowUndefined
  private manipulateOutlineMaterial: Material;

  @input
  @hint("Text component for Widget compatibility (leave empty for boxes)")
  @allowUndefined
  private textComponent: Text;

  private widget: Widget;
  private interactable: Interactable;
  private manipulationComponent: InteractableManipulation;
  private billboard: Billboard;
  private outlineFeedback: InteractableOutlineFeedback;
  private snapToWorld: SnapToWorld;

  private meshMaterial: Material;
  private isBeingManipulated = false;
  private lastHoveredTime: number = -1;
  private timeToShowOutlineAfterHover = 2;

  private doInterpolate = false;
  private interpolateStartTime = 0;
  private interpolateEndTime = 0;
  private interpolateRotStart: quat = quat.quatIdentity();
  private interpolateRotEnd: quat = quat.quatIdentity();
  private interpolatePosStart: vec3 = vec3.zero();
  private interpolatePosEnd: vec3 = vec3.zero();
  private easingFunction = easingFunctions["ease-out-quart"];

  onAwake() {
    this.createEvent("OnStartEvent").bind(this.onStart.bind(this));
    this.createEvent("UpdateEvent").bind(this.onUpdate.bind(this));
  }

  private onStart() {
    if (this.boxMesh) {
      this.meshMaterial = this.boxMesh.mainMaterial.clone();
      this.boxMesh.mainMaterial = this.meshMaterial;
    }

    this.snapToWorld = SnapToWorld.getInstance();
    this.widget = this.sceneObject.getComponent(Widget.getTypeName());
    this.interactable = this.sceneObject.getComponent(Interactable.getTypeName());
    this.manipulationComponent = this.sceneObject.getComponent(InteractableManipulation.getTypeName());
    this.billboard = this.sceneObject.getComponent(Billboard.getTypeName());
    this.outlineFeedback = this.sceneObject.getComponent(InteractableOutlineFeedback.getTypeName());

    if (this.interactable) {
      this.setupInteractionEvents();
    }

    if (this.manipulationComponent) {
      this.setupManipulationEvents();
    }
  }

  private setupInteractionEvents() {
    this.interactable.onDragStart.add((eventData) => {
      if (eventData.propagationPhase === "Target") {
        this.onDragStart(eventData);
      }
    });

    this.interactable.onDragUpdate.add((eventData) => {
      if (eventData.propagationPhase === "Target") {
        this.onDragUpdate(eventData);
      }
    });

    this.interactable.onDragEnd.add((eventData) => {
      if (eventData.propagationPhase === "Target") {
        this.onDragEnd(eventData);
      }
    });

    this.interactable.onHoverUpdate.add(() => {
      this.lastHoveredTime = getTime();
    });
  }

  private setupManipulationEvents() {
    this.manipulationComponent.onManipulationStart.add((event) => {
      this.onManipulationStart();
    });

    this.manipulationComponent.onManipulationEnd.add((event) => {
      this.onManipulationEnd();
    });
  }

  private onDragStart(eventData: any) {
    this.isBeingManipulated = true;
    this.snapToWorld.startManipulating(eventData);

    if (this.billboard) {
      this.billboard.enabled = true;
    }

    if (this.physicsBody) {
      this.physicsBody.dynamic = false;
    }

    this.addManipulateOutline();
  }

  private onDragUpdate(eventData: any) {
    this.snapToWorld.updateManipulating(eventData);
  }

  private onDragEnd(eventData: any) {
    this.isBeingManipulated = false;

    let transformOnBoxInWorld = this.snapToWorld.getCurrentTransform();
    if (transformOnBoxInWorld) {
      const ANIMATION_LENGTH = 0.45;
      this.interpolateStartTime = getTime();
      this.interpolateEndTime = this.interpolateStartTime + ANIMATION_LENGTH;

      this.interpolatePosStart = this.getSceneObject().getTransform().getWorldPosition();
      this.interpolatePosEnd = transformOnBoxInWorld.getWorldPosition();

      this.interpolateRotStart = this.getSceneObject().getTransform().getWorldRotation();
      this.interpolateRotEnd = transformOnBoxInWorld.getWorldRotation();

      this.doInterpolate = true;
    }

    this.snapToWorld.endManipulating(eventData);

    if (this.billboard) {
      this.billboard.enabled = false;
    }

    this.removeManipulateOutline();
  }

  private onManipulationStart() {
    if (this.physicsBody) {
      this.physicsBody.dynamic = false;
    }
  }

  private onManipulationEnd() {
    if (this.physicsBody) {
      this.physicsBody.dynamic = true;
    }
  }

  private onUpdate() {
    this.updateInterpolation();
    this.updateOutlineFeedback();
  }

  private updateInterpolation() {
    if (this.doInterpolate) {
      let frac = mapValue(
        getTime(),
        this.interpolateStartTime,
        this.interpolateEndTime,
        0,
        1
      );

      if (frac >= 1.0) {
        this.doInterpolate = false;
        if (this.widget) {
          this.widget.updateContent();
        }
      }

      frac = clamp(frac, 0, 1);
      frac = this.easingFunction(frac);

      let p = vec3.lerp(this.interpolatePosStart, this.interpolatePosEnd, frac);
      let rot = quat.slerp(this.interpolateRotStart, this.interpolateRotEnd, frac);

      this.getSceneObject().getTransform().setWorldPosition(p);
      this.getSceneObject().getTransform().setWorldRotation(rot);
    }
  }

  private updateOutlineFeedback() {
    if (!this.isBeingManipulated) {
      const showOutline = getTime() - this.timeToShowOutlineAfterHover < this.lastHoveredTime;
      if (this.outlineFeedback) {
        this.outlineFeedback.enabled = showOutline;
      }
    }
  }

  private addManipulateOutline(): void {
    if (!this.manipulateOutlineMaterial || !this.boxMesh) return;

    const matCount = this.boxMesh.getMaterialsCount();
    let addMaterial = true;

    for (let k = 0; k < matCount; k++) {
      const material = this.boxMesh.getMaterial(k);
      if (material.isSame(this.manipulateOutlineMaterial)) {
        addMaterial = false;
        break;
      }
    }

    if (addMaterial) {
      const materials = this.boxMesh.materials;
      materials.unshift(this.manipulateOutlineMaterial);
      this.boxMesh.materials = materials;
    }

    if (this.outlineFeedback) {
      this.outlineFeedback.enabled = false;
    }
  }

  private removeManipulateOutline(): void {
    if (!this.manipulateOutlineMaterial || !this.boxMesh) return;

    let materials = [];
    const matCount = this.boxMesh.getMaterialsCount();

    for (let k = 0; k < matCount; k++) {
      const material = this.boxMesh.getMaterial(k);
      if (material.isSame(this.manipulateOutlineMaterial)) {
        continue;
      }
      materials.push(material);
    }

    this.boxMesh.clearMaterials();
    for (var k = 0; k < materials.length; k++) {
      this.boxMesh.addMaterial(materials[k]);
    }

    if (this.outlineFeedback) {
      this.outlineFeedback.enabled = true;
    }
  }

  public deleteBox(): void {
    if (this.widget) {
      this.widget.delete();
    } else {
      this.sceneObject.destroy();
    }
  }
}