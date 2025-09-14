import { PinchButton } from "SpectaclesInteractionKit.lspkg/Components/UI/PinchButton/PinchButton";
import { Snap3DInteractableFactory } from "./Snap3DInteractableFactory";

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


    private generateNextObject(index: number) {
        if (index >= this.objectPrompts.length) {
            this.isGenerating = false;
            print("All objects generated successfully!");
            return;
        }

        const prompt = this.objectPrompts[index];
        const spawnPosition = this.calculateSpawnPosition(index, this.objectPrompts.length);

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