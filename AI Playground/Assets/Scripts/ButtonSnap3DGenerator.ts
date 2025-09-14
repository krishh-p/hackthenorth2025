import { PinchButton } from "SpectaclesInteractionKit.lspkg/Components/UI/PinchButton/PinchButton";
import { Snap3DInteractableFactory } from "./Snap3DInteractableFactory";
import { AnchorComponent } from "Spatial Anchors.lspkg/AnchorComponent";

@component
export class ButtonSnap3DGenerator extends BaseScriptComponent {
    @ui.separator
    @ui.label("Example of using generative 3D with Snap3D")
    @input
    snap3DFactory: Snap3DInteractableFactory;
    @ui.separator

    @input
    @ui.group_start("Object Prompts")
    private objectPrompts: string[] = [
        "A red apple",
        "A blue book",
        "A yellow pencil"
    ];
    @ui.group_end

    @input
    @ui.group_start("Spawn Settings")
    private spawnRadius: number = 2.0;

    @input
    private spawnHeight: number = 0.0;

    @input
    private centerPosition: SceneObject;
    @ui.group_end

    @input
    @ui.group_start("Audio Feedback")
    private audioComponent: AudioComponent;

    @input
    private generateSound: AudioTrackAsset;
    @ui.group_end

    @input
    @ui.group_start("Spatial Anchoring")
    private enableAnchoring: boolean = true;

    @input
    private anchoredParent: SceneObject;
    @ui.group_end

    private pinchButton: PinchButton;
    private isGenerating: boolean = false;

    public createdObjects: string[] = [];

    onAwake() {
        this.pinchButton = this.getSceneObject().getComponent(PinchButton.getTypeName()) as PinchButton;

        if (!this.pinchButton) {
            print("ERROR: ButtonSnap3DGenerator requires a PinchButton component on the same SceneObject");
            return;
        }

        if (!this.snap3DFactory) {
            print("ERROR: ButtonSnap3DGenerator requires a Snap3DInteractableFactory to be assigned");
            return;
        }

        if (!this.centerPosition) {
            this.centerPosition = this.sceneObject;
            print("WARNING: No center position assigned, using script's SceneObject");
        }

        // Initialize spatial anchoring if enabled
        if (this.enableAnchoring) {
            this.setupAnchoring();
        }

        this.pinchButton.onButtonPinched.add(this.generateAllObjects.bind(this));
    }

    private generateAllObjects() {
        if (this.isGenerating) {
            print("Already generating objects, please wait...");
            return;
        }

        if (this.objectPrompts.length === 0) {
            print("No object prompts specified");
            return;
        }

        this.playGenerateSound();
        this.isGenerating = true;

        print(`Generating ${this.objectPrompts.length} objects...`);

        // Generate objects sequentially, waiting for each to complete
        this.generateNextObject(0);
    }

    private setupAnchoring() {
        if (!this.anchoredParent) {
            print("WARNING: Anchoring enabled but no anchoredParent assigned. Objects will not be spatially anchored.");
            return;
        }

        // Ensure the anchored parent has an AnchorComponent
        let anchorComponent = this.anchoredParent.getComponent(AnchorComponent.getTypeName()) as AnchorComponent;
        if (!anchorComponent) {
            print("WARNING: AnchoredParent does not have an AnchorComponent. Please add one for spatial persistence.");
            return;
        }

        print("Spatial anchoring setup complete. Objects will be anchored to the specified parent.");
        print("Note: Make sure the AnchorComponent on the parent has a valid anchor assigned.");
    }

    private getAnchoredSpawnPosition(basePosition: vec3): vec3 {
        if (!this.enableAnchoring || !this.anchoredParent) {
            return basePosition;
        }

        // Transform the position relative to the anchored parent
        const parentTransform = this.anchoredParent.getTransform();
        const localPosition = parentTransform.getInvertedWorldTransform().multiplyPoint(basePosition);
        return parentTransform.getWorldTransform().multiplyPoint(localPosition);
    }

    private generateNextObject(index: number) {
        if (index >= this.objectPrompts.length) {
            this.isGenerating = false;
            print("All objects generated successfully!");
            return;
        }

        const prompt = this.objectPrompts[index];
        const basePosition = this.calculateSpawnPosition(index, this.objectPrompts.length);
        const spawnPosition = this.getAnchoredSpawnPosition(basePosition);

        print(`Generating object ${index + 1}/${this.objectPrompts.length}: ${prompt}`);

        this.snap3DFactory.createInteractable3DObject(prompt, spawnPosition)
            .then((objectId: string) => {
                print(`✓ Generated object ${index + 1}: ${prompt}`);

                // Clean up the object ID to remove the success message prefix
                const cleanPrompt = objectId.replace("Successfully created mesh with prompt: ", "");

                // Create unique ID with timestamp
                const timestamp = Date.now();
                const uniqueId = `${timestamp}:${cleanPrompt}`;

                // Add to the list of created objects
                this.createdObjects.push(uniqueId);
                print(`Created objects list: [${this.createdObjects.join(", ")}]`);

                // If anchoring is enabled, parent the generated object under the anchored parent
                if (this.enableAnchoring && this.anchoredParent) {
                    this.parentGeneratedObject(uniqueId);
                }

                // Wait a moment then generate the next object
                const delayedCall = this.createEvent("DelayedCallbackEvent");
                delayedCall.bind(() => {
                    this.generateNextObject(index + 1);
                });
                delayedCall.reset(1.0); // 1 second delay between objects
            })
            .catch((error) => {
                print(`✗ Failed to generate object ${index + 1}: ${prompt} - ${error}`);

                // Continue to next object even if this one failed
                const delayedCall = this.createEvent("DelayedCallbackEvent");
                delayedCall.bind(() => {
                    this.generateNextObject(index + 1);
                });
                delayedCall.reset(1.0);
            });
    }

    private parentGeneratedObject(objectId: string) {
        // Find the generated object by its ID/name and parent it under the anchored parent
        // Note: This assumes the Snap3DInteractableFactory creates objects with identifiable names
        const sceneObjectCount = global.scene.getRootObjectsCount();
        for (let i = 0; i < sceneObjectCount; i++) {
            const sceneObject = global.scene.getRootObject(i);
            if (sceneObject.name.includes(objectId) || sceneObject.name.includes("Snap3DInteractable")) {
                // Check if this is the most recently created object
                const currentTime = getTime();
                const timeSinceCreation = currentTime - (sceneObject as any).creationTime || 0;

                if (timeSinceCreation < 2.0) { // Within 2 seconds of creation
                    sceneObject.setParent(this.anchoredParent);
                    print(`Anchored object: ${sceneObject.name}`);
                    break;
                }
            }
        }
    }

    private calculateSpawnPosition(index: number, totalObjects: number): vec3 {
        const centerPos = this.centerPosition.getTransform().getWorldPosition();

        if (totalObjects === 1) {
            return new vec3(centerPos.x, centerPos.y + this.spawnHeight, centerPos.z);
        }

        // Arrange objects in a circle around the center position
        const angleStep = (2 * Math.PI) / totalObjects;
        const angle = index * angleStep;

        const x = centerPos.x + this.spawnRadius * Math.cos(angle);
        const z = centerPos.z + this.spawnRadius * Math.sin(angle);
        const y = centerPos.y + this.spawnHeight;

        return new vec3(x, y, z);
    }

    private playGenerateSound() {
        if (this.audioComponent && this.generateSound) {
            this.audioComponent.audioTrack = this.generateSound;
            this.audioComponent.play(1);
        }
    }
}