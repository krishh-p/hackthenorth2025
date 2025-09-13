# Box Selection Prefab Setup Guide

This guide explains how to create a selection prefab for the box that will appear in the widget selection menu.

## Prerequisites

- Your main BoxPrefab should already be created and working
- The `BoxSelection.ts` script should be available
- Familiarity with the main box setup

## Step-by-Step Setup

### 1. Create the Selection Object

1. In the **Objects Panel**, right-click and select **Add New > Scene Object**
2. Rename it to "BoxSelection"
3. This will be the menu icon that users drag to place boxes

### 2. Add the Box Mesh for Menu Display

1. Add a **Render Mesh Visual** component to the BoxSelection object
2. Set the **Mesh** to "Cube" (same as your main box)
3. Create or assign a **Material** (can be the same as your main box, or a simplified version)
4. Scale it appropriately for menu display (the script will also apply scaling)

### 3. Add Required Components

#### A. WidgetSelection Component (REQUIRED)
1. Click **Add Component > Script**
2. Select **WidgetSelection** (this is the core selection logic)
3. This component handles all the drag-to-place functionality

#### B. BoxSelection Component (Optional)
1. Click **Add Component > Script**
2. Select **BoxSelection** (the custom script we created)
3. This provides box-specific customizations

#### C. Interactable Component (REQUIRED)
1. Click **Add Component > Interaction > Interactable**
2. This makes the menu item draggable
3. Keep default settings

#### D. Billboard Component (REQUIRED)
1. Click **Add Component > Interaction > Billboard**
2. Set **Billboard Type** to "Y-Axis" or "Full" depending on preference
3. This makes the menu icon face the user during drag

#### E. Screen Transform Component (REQUIRED for UI)
1. Click **Add Component > UI > Screen Transform**
2. This positions the selection in the menu UI
3. The WidgetSelectionUI will configure this automatically

### 4. Configure Components

#### Configure BoxSelection Script:
1. **Box Mesh**: Drag the Render Mesh Visual component here
2. **Label Text**: Leave empty unless you want a text label

#### Configure WidgetSelection Script:
1. **Interactable**: Drag the Interactable component here
2. This should auto-populate, but verify it's assigned

### 5. Create Optional Text Label

If you want a "Box" label under the icon:

1. Right-click on BoxSelection and add **Add New > UI > Text**
2. Rename it to "BoxLabel"
3. Configure the text:
   - Set **Text** to "Box"
   - Adjust **Font Size** (e.g., 12)
   - Set **Color** as desired
4. Position it below the box mesh
5. In BoxSelection script, drag this text to the **Label Text** field

### 6. Save as Prefab

1. Right-click on the "BoxSelection" object
2. Select **Save as Prefab**
3. Name it "BoxSelectionPrefab"
4. Save in your Assets/Prefabs folder (same location as other selection prefabs)

## Adding to Widget Selection Menu

### Method 1: Add to WidgetSelectionUI (Recommended)

1. Find the **WidgetSelectionUI** object in your scene (usually under UI hierarchy)
2. In the Inspector, locate the **WidgetSelectionUI** script component
3. Find the **Widget Selections** array
4. Increase the array size by 1
5. Drag your "BoxSelectionPrefab" into the new slot
6. The box icon will now appear in the widget selection menu

### Method 2: Manual Scene Setup

If you can't find WidgetSelectionUI, you can add it manually:

1. Find where other selection prefabs are instantiated (look for BlueNoteSelection, etc.)
2. Instantiate your BoxSelectionPrefab in the same parent object
3. Position it alongside other selection icons
4. Ensure proper ScreenTransform configuration

## Testing the Selection

1. **Save your project**
2. **Preview on device** or in Lens Studio preview
3. **Open the widget menu** (usually a button in the UI)
4. **Verify the box icon appears** in the selection menu
5. **Test dragging** the box icon from the menu to place a box in the world

### Expected Behavior:
- Box icon appears in widget selection menu
- Icon can be dragged from menu
- Dragging creates a new box in the world at the drop location
- Box snaps to surfaces when dropped
- Multiple boxes can be placed

## Troubleshooting

### Box icon doesn't appear in menu:
- Verify BoxSelectionPrefab is added to WidgetSelectionUI array
- Check that all required components are present
- Ensure prefab is saved correctly

### Can't drag the box icon:
- Verify Interactable component is added and enabled
- Check that WidgetSelection component is configured
- Ensure Billboard component is present

### Box doesn't spawn when dropped:
- Verify your main BoxPrefab is added to AreaManager's Widget Prefabs array
- Check that the widget index matches between selection and main prefab
- Ensure AreaManager is properly configured

### Visual issues:
- Adjust Render Mesh Visual material and scale
- Check ScreenTransform positioning
- Verify Billboard component settings

## Customization Options

### Custom Icon:
- Replace the cube mesh with a custom 3D model
- Use different materials/textures for the menu version
- Add particle effects or animations

### Custom Label:
- Add descriptive text below the icon
- Use different fonts or styling
- Support multiple languages

### Visual Feedback:
- Add hover effects
- Implement selection highlighting
- Add drag preview functionality

## File Structure

After completing setup, you should have:

```
Assets/SpatialPersistance/Box/
├── InteractableBox.ts          # Main box logic
├── BoxSelection.ts             # Selection menu logic
├── SETUP_GUIDE.md             # Main box setup
└── BOX_SELECTION_SETUP.md     # This file

Assets/Prefabs/
├── BoxPrefab.prefab           # Main box prefab
└── BoxSelectionPrefab.prefab  # Menu selection prefab
```

This setup ensures your box integrates seamlessly with the existing widget selection system!