// /worklets/capture-16k.js
class Capture16kProcessor extends AudioWorkletProcessor {
  // Resample from context.sampleRate (usually 48000) -> 16000, mono
  constructor() {
    super();
    this._remnant = new Float32Array(0);
    this._ratio = sampleRate / 16000; // e.g., 48000/16000 = 3
  }

  // naive downsampler (good enough for speech)
  _downsampleTo16k(float32) {
    const step = this._ratio;
    const outLen = Math.floor(float32.length / step);
    const out = new Int16Array(outLen);
    let j = 0;
    for (let i = 0; i < outLen; i++) {
      const idx = Math.floor(i * step);
      // clamp to [-1, 1] then PCM16
      let s = float32[idx];
      s = Math.max(-1, Math.min(1, s));
      out[j++] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return out;
  }

  process(inputs) {
    if (!inputs || inputs.length === 0 || inputs[0].length === 0) return true;
    const ch0 = inputs[0][0]; // mono capture
    // concat remnant + current
    const merged = new Float32Array(this._remnant.length + ch0.length);
    merged.set(this._remnant, 0);
    merged.set(ch0, this._remnant.length);

    // resample to 16k
    const pcm16 = this._downsampleTo16k(merged);

    // Keep no remnant (simple integral ratio path); if non-integral, keep fractional remainder
    // For 48k->16k, ratio=3 so we're fine
    this._remnant = new Float32Array(0);

    this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    return true;
  }
}
registerProcessor('capture-16k', Capture16kProcessor);
