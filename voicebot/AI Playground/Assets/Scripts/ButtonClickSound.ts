import { PinchButton } from "SpectaclesInteractionKit.lspkg/Components/UI/PinchButton/PinchButton";

@component
export class ButtonClickSound extends BaseScriptComponent {
    @input
    private audioComponent: AudioComponent;

    @input
    private clickSound: AudioTrackAsset;

    @input
    private volume: number = 1.0;

    private pinchButton: PinchButton;

    onAwake() {
        this.pinchButton = this.getSceneObject().getComponent(PinchButton.getTypeName()) as PinchButton;

        if (!this.pinchButton) {
            print("ERROR: ButtonClickSound requires a PinchButton component on the same SceneObject");
            return;
        }

        if (!this.audioComponent) {
            print("ERROR: ButtonClickSound requires an AudioComponent to be assigned");
            return;
        }

        if (!this.clickSound) {
            print("ERROR: ButtonClickSound requires a click sound AudioTrackAsset to be assigned");
            return;
        }

        this.pinchButton.onButtonPinched.add(this.playClickSound.bind(this));
    }

    private playClickSound() {
        if (this.audioComponent && this.clickSound) {
            this.audioComponent.audioTrack = this.clickSound;
            this.audioComponent.volume = this.volume;
            this.audioComponent.play(1);
        }
    }
}