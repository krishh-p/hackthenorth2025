import { Interactable } from "SpectaclesInteractionKit.lspkg/Components/Interaction/Interactable/Interactable";
import Event, { PublicApi } from "SpectaclesInteractionKit.lspkg/Utils/Event";

export type ButtonClickEvent = {
  buttonId: string;
  buttonText: string;
};

@component
export class SimpleButton extends BaseScriptComponent {
  @input
  private textComponent: Text;

  @input
  private buttonId: string = "";

  private interactable: Interactable;

  private onClickEvent: Event<ButtonClickEvent> = new Event<ButtonClickEvent>();
  readonly onClick: PublicApi<ButtonClickEvent> = this.onClickEvent.publicApi();

  onAwake() {
    this.createEvent("OnStartEvent").bind(this.onStart.bind(this));
  }

  onStart() {
    this.interactable = this.sceneObject.getComponent(Interactable.getTypeName());

    if (this.interactable) {
      this.interactable.onTriggerEnd.add(() => {
        this.onClickEvent.invoke({
          buttonId: this.buttonId,
          buttonText: this.textComponent ? this.textComponent.text : ""
        });
      });
    } else {
      print("Warning: SimpleButton component requires an Interactable component on the same object");
    }
  }

  public set text(text: string) {
    if (this.textComponent) {
      this.textComponent.text = text;
    }
  }

  public get text(): string {
    return this.textComponent ? this.textComponent.text : "";
  }

  public set id(id: string) {
    this.buttonId = id;
  }

  public get id(): string {
    return this.buttonId;
  }
}