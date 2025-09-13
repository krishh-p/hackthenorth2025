import { MenuManager, MenuAction } from "./MenuManager";
import { MenuButtonConfig } from "./ButtonMenu";

@component
export class MenuExample extends BaseScriptComponent {
  @input
  private menuManager: MenuManager;

  onAwake() {
    this.createEvent("OnStartEvent").bind(this.onStart.bind(this));
  }

  onStart() {
    if (this.menuManager) {
      this.menuManager.onMenuAction.add(this.handleMenuAction.bind(this));

      // Example: Create a custom menu with AI-related buttons
      const aiButtons: MenuButtonConfig[] = [
        { id: "generate_image", text: "Generate Image" },
        { id: "ask_question", text: "Ask AI Question" },
        { id: "voice_command", text: "Voice Command" },
        { id: "settings", text: "Settings" },
        { id: "help", text: "Help" },
        { id: "close", text: "Close" }
      ];

      // Customize the menu with AI-related buttons
      this.menuManager.customizeMenu(aiButtons);
    }
  }

  private handleMenuAction(action: MenuAction) {
    print(`Menu action triggered: ${action.actionType} from button: ${action.buttonId}`);

    switch (action.actionType) {
      case "unknown_action":
        // Handle custom button actions
        switch (action.buttonId) {
          case "generate_image":
            print("Triggering image generation...");
            // Here you would integrate with your existing ImageGenerator component
            break;

          case "ask_question":
            print("Opening AI assistant for questions...");
            // Here you would integrate with your existing AI assistant components
            break;

          case "voice_command":
            print("Activating voice commands...");
            // Here you would integrate with your existing voice recognition
            break;

          case "settings":
            print("Opening settings...");
            // Here you could open another menu or settings panel
            break;

          case "help":
            print("Showing help information...");
            break;
        }
        break;

      case "menu_closed":
        print("Menu was closed by user");
        break;

      default:
        print(`Unhandled action type: ${action.actionType}`);
        break;
    }
  }
}