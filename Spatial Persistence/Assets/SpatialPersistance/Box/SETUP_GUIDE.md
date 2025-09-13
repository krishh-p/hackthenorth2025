# Interactive Box Setup Guide for Lens Studio

This guide explains how to set up the interactive box in your Spatial Persistence project using the `InteractableBox.ts` script.

## Prerequisites

- Lens Studio v5.10.0+
- Spectacles OS Version v5.62+
- The `InteractableBox.ts` script (already created)

## Step-by-Step Setup in Lens Studio

### 1. Create the Base Scene Object

1. In the **Objects Panel**, right-click and select **Add New > Scene Object**
2. Rename it to "InteractableBox"
3. This will be the root object that holds all components

### 2. Add the Box Mesh

1. Right-click on the "InteractableBox" object and select **Add New > Mesh Visual**
2. Rename the child object to "BoxMesh"
3. In the **Inspector** for the BoxMesh:
   - Set **Mesh** to "Cube" (built-in primitive)
   - Create or assign a **Material** (PBR material recommended)
   - Adjust the **Scale** as desired (e.g., 0.1, 0.1, 0.1 for a small box)

### 3. Add Required Components to the Main Object

Add these components to the main "InteractableBox" object:

#### A. Script Component
1. Click **Add Component > Script**
2. In the Script field, select **InteractableBox** (the TypeScript file you created)

#### B. Interactable Component
1. Click **Add Component > Interaction > Interactable**
2. Keep default settings - this enables basic drag interactions

#### C. InteractableManipulation Component
1. Click **Add Component > Interaction > InteractableManipulation**
2. This provides advanced manipulation events and physics integration

#### D. Collider Component
1. Click **Add Component > Physics > Collider**
2. Set **Shape** to "Box"
3. Adjust **Size** to match your mesh (e.g., 0.1, 0.1, 0.1)
4. Set **Collision Group** as needed for your project

#### E. Billboard Component (Optional)
1. Click **Add Component > Interaction > Billboard**
2. This makes the box face the camera during interactions
3. Set **Billboard Type** to "Y-Axis" for realistic orientation

#### F. InteractableOutlineFeedback Component
1. Click **Add Component > Helpers > InteractableOutlineFeedback**
2. This provides visual feedback when hovering over the box
3. Create an outline material and assign it to the **Outline Material** field

#### G. Widget Component (REQUIRED for menu integration)
1. Click **Add Component > Script**
2. Select the **Widget** script (from the existing project)
3. In the Widget component settings:
   - Leave **Text** field empty (or create a dummy text object)
   - This integrates with the spatial persistence system

#### H. Body Component (Optional - for Physics)
1. Click **Add Component > Physics > Body**
2. Set **Type** to "Dynamic" if you want the box to fall due to gravity
3. Set **Mass** appropriately (e.g., 1.0)

### 4. Configure the InteractableBox Script

In the **Inspector** for the InteractableBox script component, assign:

1. **Box Mesh**: Drag the "BoxMesh" child object here
2. **Physics Body**: Drag the Body component if you added one
3. **Manipulate Outline Material**: Create and assign a material for manipulation feedback

### 5. Create Materials

#### Basic Box Material
1. In **Resources Panel**, right-click and select **Add New > Material > PBR Material**
2. Name it "BoxMaterial"
3. Set desired color and properties
4. Assign to the BoxMesh's Material field

#### Outline Materials
1. Create a material for hover feedback (e.g., blue outline)
2. Create a material for manipulation feedback (e.g., orange outline)
3. Assign these to the respective components

### 6. Position the Box

1. In the **Scene Panel**, select the "InteractableBox" object
2. Use the **Transform** gizmos to position it in your scene
3. Recommended to place it on a surface for better user experience

### 7. Create the Box Prefab

1. Once all components are configured, right-click on the "InteractableBox" object
2. Select **Save as Prefab**
3. Name it "BoxPrefab" and save it in your Assets folder
4. This prefab will be used in the widget selection system

### 8. Add Box to Widget Selection Menu

To make the box appear in the placement menu:

1. Find the **AreaManager** object in your scene
2. In the Inspector, locate the **AreaManager** script component
3. In the **Widget Prefabs** array, increase the size by 1
4. Drag your "BoxPrefab" into the new slot
5. The box will now appear in the widget selection menu

### 9. Create Box Selection Prefab (Optional)

For a custom menu icon:
1. Create a new Scene Object called "BoxSelection"
2. Add a smaller version of your box mesh for the menu
3. Add **WidgetSelection** script component
4. Add **Interactable** and **Billboard** components
5. Save as prefab and add to the **WidgetSelectionUI** component's **Widget Selections** array

### 10. Test the Implementation

1. Save your project
2. Preview on device or in Lens Studio preview
3. Test interactions:
   - **Menu**: Box should appear in the widget selection menu
   - **Placement**: Drag from menu to place a box in the world
   - **Hover**: Should show outline feedback
   - **Pinch/Tap and Drag**: Should move the box
   - **Release**: Should snap to nearby surfaces with smooth animation

## Integration with Spatial Persistence

To make the box persist across sessions:

1. Ensure the Widget component is properly configured
2. The box will automatically integrate with the `AreaManager` system
3. Position and rotation will be saved when the box is moved

## Troubleshooting

### Common Issues:

1. **Box doesn't respond to interactions**:
   - Verify all required components are added
   - Check that the Interactable component is enabled
   - Ensure the Collider is properly sized

2. **No visual feedback on hover**:
   - Check InteractableOutlineFeedback component is added
   - Verify outline material is assigned
   - Ensure the material has proper render order

3. **Box doesn't snap to surfaces**:
   - Verify SnapToWorld system is working in your scene
   - Check that the Widget component is properly configured
   - Ensure the script references are correctly assigned

4. **Physics issues**:
   - Verify Body component settings
   - Check collision groups and layers
   - Ensure proper mass and scale settings

## Optional Enhancements

1. **Custom Textures**: Apply custom textures to make the box more visually interesting
2. **Sound Effects**: Add audio feedback for interactions
3. **Particle Effects**: Add visual effects when placing the box
4. **Multiple Box Types**: Create variations with different materials or sizes
5. **Menu Integration**: Add the box to the widget selection menu

## Code Customization

The `InteractableBox.ts` script can be customized for specific behaviors:

- Modify interaction thresholds
- Change animation timing and easing
- Add custom visual effects
- Integrate with other game systems
- Add specific physics behaviors

## Performance Considerations

- Keep the box mesh simple (low poly count)
- Use efficient materials (avoid complex shaders)
- Limit the number of simultaneous interactive boxes
- Consider LOD (Level of Detail) for distant boxes

## Related Documentation

- [Spectacles Interaction Kit Documentation](https://developers.snap.com/spectacles/spectacles-frameworks/spectacles-interaction-kit)
- [Lens Studio Scripting Guide](https://developers.snap.com/lens-studio/api)
- [Spatial Persistence Best Practices](https://developers.snap.com/spectacles/best-practices)