import Event, { PublicApi } from "SpectaclesInteractionKit.lspkg/Utils/Event";
import { ButtonMenu, MenuButtonConfig } from "./ButtonMenu";
import { ButtonClickEvent } from "./SimpleButton";

export type MenuAction = {
  actionType: string;
  buttonId: string;
  data?: any;
};

@component
export class MenuManager extends BaseScriptComponent {
  @input
  private buttonMenu: ButtonMenu;

  @input
  private showMenuOnStart: boolean = true;

  private onMenuActionEvent: Event<MenuAction> = new Event<MenuAction>();
  readonly onMenuAction: PublicApi<MenuAction> = this.onMenuActionEvent.publicApi();

  private defaultButtons: MenuButtonConfig[] = [
    { id: "action1", text: "Action 1" },
    { id: "action2", text: "Action 2" },
    { id: "action3", text: "Action 3" },
    { id: "close", text: "Close Menu" }
  ];

  onAwake() {
    this.createEvent("OnStartEvent").bind(this.onStart.bind(this));
  }

  onStart() {
    if (this.buttonMenu) {
      this.buttonMenu.onButtonClick.add(this.handleButtonClick.bind(this));
    }

    if (this.showMenuOnStart) {
      this.showMenu();
    }
  }

  public showMenu(buttons?: MenuButtonConfig[]) {
    if (!this.buttonMenu) {
      print("Warning: MenuManager requires a ButtonMenu component to be assigned");
      return;
    }

    const buttonsToShow = buttons || this.defaultButtons;
    this.buttonMenu.createButtons(buttonsToShow);
  }

  public hideMenu() {
    if (this.buttonMenu) {
      this.buttonMenu.setMenuVisible(false);
    }
  }

  public toggleMenu() {
    if (this.buttonMenu) {
      const isVisible = this.buttonMenu.sceneObject.enabled;
      if (isVisible) {
        this.hideMenu();
      } else {
        this.showMenu();
      }
    }
  }

  private handleButtonClick(event: ButtonClickEvent) {
    switch (event.buttonId) {
      case "action1":
        this.onMenuActionEvent.invoke({
          actionType: "custom_action_1",
          buttonId: event.buttonId
        });
        print("Action 1 triggered!");
        break;

      case "action2":
        this.onMenuActionEvent.invoke({
          actionType: "custom_action_2",
          buttonId: event.buttonId
        });
        print("Action 2 triggered!");
        break;

      case "action3":
        this.onMenuActionEvent.invoke({
          actionType: "custom_action_3",
          buttonId: event.buttonId
        });
        print("Action 3 triggered!");
        break;

      case "close":
        this.hideMenu();
        this.onMenuActionEvent.invoke({
          actionType: "menu_closed",
          buttonId: event.buttonId
        });
        break;

      default:
        this.onMenuActionEvent.invoke({
          actionType: "unknown_action",
          buttonId: event.buttonId,
          data: { buttonText: event.buttonText }
        });
        print(`Unknown button clicked: ${event.buttonId} - ${event.buttonText}`);
        break;
    }
  }

  public customizeMenu(buttons: MenuButtonConfig[]) {
    this.defaultButtons = buttons;
    if (this.buttonMenu && this.buttonMenu.sceneObject.enabled) {
      this.showMenu(buttons);
    }
  }

  public addCustomButton(config: MenuButtonConfig) {
    this.defaultButtons.push(config);
    if (this.buttonMenu && this.buttonMenu.sceneObject.enabled) {
      this.showMenu(this.defaultButtons);
    }
  }
}