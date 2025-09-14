import { PinchButton } from "SpectaclesInteractionKit.lspkg/Components/UI/PinchButton/PinchButton";
import { Snap3DInteractableFactory } from "./Snap3DInteractableFactory";
import { AnchorModule } from "Spatial Anchors.lspkg/AnchorModule";
import { AnchorSession, AnchorSessionOptions } from "Spatial Anchors.lspkg/AnchorSession";
import { Anchor } from "Spatial Anchors.lspkg/Anchor";
import { AnchorComponent } from "Spatial Anchors.lspkg/AnchorComponent";
import { WorldAnchor } from "Spatial Anchors.lspkg/WorldAnchor";

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
    private anchorModule: AnchorModule;

    @input
    private camera: SceneObject;

    @input
    private objectsParent: SceneObject;
    @ui.group_end

    private pinchButton: PinchButton;
    private isGenerating: boolean = false;
    private anchorSession?: AnchorSession;

    public createdObjects: string[] = [];
    private objectAnchors: Map<string, WorldAnchor> = new Map();

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

        if (!this.anchorModule) {
            print("ERROR: ButtonSnap3DGenerator requires an AnchorModule to be assigned");
            return;
        }

        if (!this.camera) {
            print("ERROR: ButtonSnap3DGenerator requires a camera SceneObject to be assigned");
            return;
        }

        if (!this.objectsParent) {
            print("ERROR: ButtonSnap3DGenerator requires an objectsParent SceneObject to be assigned");
            return;
        }

        if (!this.centerPosition) {
            this.centerPosition = this.sceneObject;
            print("WARNING: No center position assigned, using script's SceneObject");
        }

        this.createEvent('OnStartEvent').bind(() => {
            this.initializeAnchorSession();
        });

        this.pinchButton.onButtonPinched.add(this.generateAllObjects.bind(this));
    }

    private async initializeAnchorSession() {
        try {
            const anchorSessionOptions = new AnchorSessionOptions();
            anchorSessionOptions.scanForWorldAnchors = true;

            this.anchorSession = await this.anchorModule.openSession(anchorSessionOptions);
            this.anchorSession.onAnchorNearby.add(this.onAnchorNearby.bind(this));

            print("Anchor session initialized successfully");
        } catch (error) {
            print("Failed to initialize anchor session: " + error);
        }
    }

    private onAnchorNearby(anchor: Anchor) {
        print("Found existing anchor: " + anchor.id);
        this.restoreObjectAtAnchor(anchor);
    }

    private restoreObjectAtAnchor(anchor: Anchor) {
        // In a real implementation, you would need to store metadata about what object
        // was at this anchor (prompt, type, etc.) and recreate it.
        // For now, we'll just log that we found an anchor.
        print(`Restoring object at anchor ${anchor.id} - position: (${anchor.toWorldFromAnchor.column3.x.toFixed(2)}, ${anchor.toWorldFromAnchor.column3.y.toFixed(2)}, ${anchor.toWorldFromAnchor.column3.z.toFixed(2)})`);

        // TODO: Implement object restoration logic based on stored anchor metadata
        // This would involve:
        // 1. Retrieving stored object data (prompt, type) associated with anchor.id
        // 2. Recreating the 3D object using snap3DFactory
        // 3. Positioning it at the anchor location
        // 4. Adding AnchorComponent to link the object to the anchor
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

        if (!this.anchorSession) {
            print("ERROR: Anchor session not ready. Please wait for initialization.");
            return;
        }

        this.playGenerateSound();
        this.isGenerating = true;

        print(`Generating ${this.objectPrompts.length} objects with spatial anchors...`);

        // Generate objects sequentially, waiting for each to complete
        this.generateNextObject(0);
    }


    private async generateNextObject(index: number) {
        if (index >= this.objectPrompts.length) {
            this.isGenerating = false;
            print("All objects generated successfully!");
            return;
        }

        const prompt = this.objectPrompts[index];
        const spawnPosition = this.calculateSpawnPosition(index, this.objectPrompts.length);

        print(`Generating object ${index + 1}/${this.objectPrompts.length}: ${prompt}`);

        try {
            // Create the 3D object first
            const objectId = await this.snap3DFactory.createInteractable3DObject(prompt, spawnPosition, this.objectsParent);
            print(`✓ Generated object ${index + 1}: ${prompt}`);

            // Create anchor for the object
            await this.createAnchorForObject(objectId, spawnPosition, prompt);

            // Wait a moment then generate the next object
            const delayedCall = this.createEvent("DelayedCallbackEvent");
            delayedCall.bind(() => {
                this.generateNextObject(index + 1);
            });
            delayedCall.reset(1.0); // 1 second delay between objects

        } catch (error) {
            print(`✗ Failed to generate object ${index + 1}: ${prompt} - ${error}`);

            // Continue to next object even if this one failed
            const delayedCall = this.createEvent("DelayedCallbackEvent");
            delayedCall.bind(() => {
                this.generateNextObject(index + 1);
            });
            delayedCall.reset(1.0);
        }
    }

    private async createAnchorForObject(objectId: string, position: vec3, prompt: string) {
        if (!this.anchorSession) {
            print("ERROR: Anchor session not initialized");
            return;
        }

        try {
            // Create world transform matrix for the anchor position
            const anchorTransform = mat4.fromTranslation(position);

            // Create the world anchor
            const anchor = await this.anchorSession.createWorldAnchor(anchorTransform);

            // Clean up the object ID and create unique identifier
            const cleanPrompt = objectId.replace("Successfully created mesh with prompt: ", "");
            const timestamp = Date.now();
            const uniqueId = `${timestamp}:${cleanPrompt}`;

            // Store the anchor mapping
            this.objectAnchors.set(uniqueId, anchor);
            this.createdObjects.push(uniqueId);

            // Save the anchor for persistence
            await this.anchorSession.saveAnchor(anchor);

            print(`✓ Created anchor for object: ${prompt} at position (${position.x.toFixed(2)}, ${position.y.toFixed(2)}, ${position.z.toFixed(2)})`);
            print(`Created objects list: [${this.createdObjects.join(", ")}]`);

        } catch (error) {
            print(`✗ Failed to create anchor for object: ${prompt} - ${error}`);
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