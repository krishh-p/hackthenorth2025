import Event, { PublicApi } from "SpectaclesInteractionKit.lspkg/Utils/Event";
import { SimpleButton, ButtonClickEvent } from "./SimpleButton";
import { ContainerFrame } from "SpectaclesInteractionKit.lspkg/Components/UI/ContainerFrame/ContainerFrame";

export type MenuButtonConfig = {
  id: string;
  text: string;
  position?: vec3;
};

@component
export class ButtonMenu extends BaseScriptComponent {
  @input
  private buttonPrefab: ObjectPrefab;

  @input
  private buttonSpacing: number = 3;

  @input
  private menuContainer: SceneObject;

  private buttons: SimpleButton[] = [];
  private buttonConfigs: MenuButtonConfig[] = [];

  private onButtonClickEvent: Event<ButtonClickEvent> = new Event<ButtonClickEvent>();
  readonly onButtonClick: PublicApi<ButtonClickEvent> = this.onButtonClickEvent.publicApi();

  private container: ContainerFrame;

  onAwake() {
    this.createEvent("OnStartEvent").bind(this.onStart.bind(this));
  }

  onStart() {
    if (this.menuContainer) {
      this.container = this.menuContainer.getComponent(ContainerFrame.getTypeName());
    }
  }

  public createButtons(configs: MenuButtonConfig[]) {
    this.clearButtons();
    this.buttonConfigs = configs;

    if (this.container && configs.length > 0) {
      const height = (configs.length - 1) * this.buttonSpacing + 6;
      this.container.innerSize = new vec2(this.container.innerSize.x, height);
    }

    let yOffset = (configs.length - 1) * this.buttonSpacing / 2;

    for (const config of configs) {
      this.createButton(config, yOffset);
      yOffset -= this.buttonSpacing;
    }

    this.setMenuVisible(true);
  }

  private createButton(config: MenuButtonConfig, yOffset: number) {
    if (!this.buttonPrefab) {
      print("Warning: ButtonMenu requires a buttonPrefab to be assigned");
      return;
    }

    const buttonObject = this.buttonPrefab.instantiate(this.sceneObject);
    const simpleButton = buttonObject.getComponent(SimpleButton.getTypeName());

    if (simpleButton) {
      simpleButton.id = config.id;
      simpleButton.text = config.text;

      const position = config.position || new vec3(0, yOffset, 0);
      buttonObject.getTransform().setLocalPosition(position);

      simpleButton.onClick.add((event) => {
        this.onButtonClickEvent.invoke(event);
      });

      this.buttons.push(simpleButton);
    } else {
      print("Warning: Button prefab must have a SimpleButton component");
    }
  }

  public clearButtons() {
    for (const button of this.buttons) {
      if (button && button.sceneObject) {
        button.sceneObject.destroy();
      }
    }
    this.buttons = [];
  }

  public setMenuVisible(visible: boolean) {
    this.sceneObject.enabled = visible;
  }

  public addButton(config: MenuButtonConfig) {
    this.buttonConfigs.push(config);
    this.createButtons(this.buttonConfigs);
  }

  public removeButton(buttonId: string) {
    this.buttonConfigs = this.buttonConfigs.filter(config => config.id !== buttonId);
    this.createButtons(this.buttonConfigs);
  }
}