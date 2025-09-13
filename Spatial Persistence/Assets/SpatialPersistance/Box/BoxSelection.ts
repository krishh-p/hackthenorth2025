import { WidgetSelection } from "../MenuUI/WidgetSelection";

@component
export class BoxSelection extends BaseScriptComponent {
  @input
  @hint("The box mesh visual for the menu icon")
  @allowUndefined
  private boxMesh: RenderMeshVisual;

  @input
  @hint("Optional label text for the box selection")
  @allowUndefined
  private labelText: Text;

  private widgetSelection: WidgetSelection;

  onAwake() {
    this.createEvent("OnStartEvent").bind(this.onStart.bind(this));
  }

  private onStart() {
    // Get the WidgetSelection component that handles the drag logic
    this.widgetSelection = this.sceneObject.getComponent(WidgetSelection.getTypeName());

    // Set up the label if provided
    if (this.labelText) {
      this.labelText.text = "Box";
    }

    // Optional: Scale the box mesh for menu display
    if (this.boxMesh) {
      // Make the menu version smaller and more suitable for UI
      this.boxMesh.getTransform().setLocalScale(new vec3(0.8, 0.8, 0.8));
    }
  }

  /**
   * Get the widget selection component for external configuration
   */
  public getWidgetSelection(): WidgetSelection {
    return this.widgetSelection;
  }

  /**
   * Set the label text programmatically
   */
  public setLabel(text: string): void {
    if (this.labelText) {
      this.labelText.text = text;
    }
  }

  /**
   * Initialize the selection with an index (called by WidgetSelectionUI)
   */
  public initialize(index: number): void {
    if (this.widgetSelection) {
      this.widgetSelection.initialize(index);
    }
  }
}