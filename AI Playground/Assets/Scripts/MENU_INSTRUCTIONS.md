# Button Menu System for AI Playground

This menu system provides a simple way to create interactive button menus without placing objects in the world, similar to the Spatial Persistence area manager but simplified for button-only interactions.

## Components

### 1. SimpleButton.ts
Individual button component that handles user interactions.
- **Inputs:**
  - `textComponent`: Text component for button label
  - `buttonId`: Unique identifier for the button
- **Events:** `onClick` - fires when button is pressed
- **Requirements:** Object must have an `Interactable` component

### 2. ButtonMenu.ts
Manages multiple buttons in a menu layout.
- **Inputs:**
  - `buttonPrefab`: ObjectPrefab for creating buttons
  - `buttonSpacing`: Vertical spacing between buttons (default: 3)
  - `menuContainer`: SceneObject with ContainerFrame for layout
- **Methods:**
  - `createButtons(configs)`: Create buttons from configuration array
  - `clearButtons()`: Remove all buttons
  - `setMenuVisible(visible)`: Show/hide menu
- **Events:** `onButtonClick` - fires when any button is pressed

### 3. MenuManager.ts
High-level menu coordinator and action handler.
- **Inputs:**
  - `buttonMenu`: ButtonMenu component
  - `showMenuOnStart`: Whether to show menu on start (default: true)
- **Methods:**
  - `showMenu(buttons?)`: Display menu with optional button configuration
  - `hideMenu()`: Hide the menu
  - `toggleMenu()`: Toggle menu visibility
  - `customizeMenu(buttons)`: Set custom button configuration
- **Events:** `onMenuAction` - fires for processed menu actions

### 4. MenuExample.ts
Example implementation showing how to create an AI-themed menu.

## Setup Instructions

1. Create a button prefab with:
   - An object with `Interactable` component
   - `SimpleButton` component attached
   - `Text` component for the button label
   - Assign the Text component to SimpleButton's `textComponent` input

2. Create a menu container with:
   - `ContainerFrame` component for layout management
   - Child object for button placement

3. Create a MenuManager object and assign:
   - The ButtonMenu component
   - Configure the ButtonMenu with your button prefab and container

4. Optionally use MenuExample as a template for handling custom actions

## Usage Examples

```typescript
// Create custom buttons
const customButtons: MenuButtonConfig[] = [
  { id: "action1", text: "My Action" },
  { id: "action2", text: "Another Action" }
];

// Show menu with custom buttons
menuManager.showMenu(customButtons);

// Handle button actions
menuManager.onMenuAction.add((action) => {
  print(`Button ${action.buttonId} was pressed`);
});
```

## Integration with AI Playground

This menu system can be easily integrated with existing AI Playground components:
- Connect "Generate Image" button to `ImageGenerator.ts`
- Connect "Ask AI Question" to `GeminiAssistant.ts` or `OpenAIAssistant.ts`
- Connect "Voice Command" to `ASRQueryController.ts`

The menu provides a clean, interactive way to access AI features without cluttering the 3D space with persistent objects.