/** Push-to-talk: buffer voice while mic is ON, send to Gemini when mic is OFF. */

const WORKLET_BASE = "/static/js/audio-processors";
const INPUT_SAMPLE_RATE = 16000;

export async function requestMicrophoneStream() {
  if (!window.isSecureContext) throw new Error("Microphone requires HTTPS or localhost.");
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone not supported.");
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: INPUT_SAMPLE_RATE,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
    });
  } catch (err) {
    if (err?.name === "NotAllowedError") {
      throw new Error("Microphone blocked — allow it in browser site settings.");
    }
    throw err;
  }
}

class AudioStreamer {
  constructor(geminiClient) {
    this.client = geminiClient;
    this.audioContext = null;
    this.audioWorklet = null;
    this.mediaStream = null;
    this.isStreaming = false;
    this.recording = false;
    this.pcmChunks = [];
    this.sampleRate = INPUT_SAMPLE_RATE;
  }

  async startWithStream(mediaStream) {
    this.mediaStream = mediaStream;
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: this.sampleRate,
    });
    if (this.audioContext.state === "suspended") await this.audioContext.resume();

    await this.audioContext.audioWorklet.addModule(WORKLET_BASE + "/capture.worklet.js");
    this.audioWorklet = new AudioWorkletNode(this.audioContext, "audio-capture-processor");
    this.audioWorklet.port.onmessage = (event) => {
      if (!this.isStreaming || !this.recording || event.data.type !== "audio") return;
      this.pcmChunks.push(this.convertToPCM16(event.data.data));
    };

    this.audioContext.createMediaStreamSource(this.mediaStream).connect(this.audioWorklet);
    this.isStreaming = true;
  }

  beginRecording() {
    if (this.recording) return;
    this.recording = true;
    this.pcmChunks = [];
  }

  /** Flush buffer: send audio chunks then signal mic off to Gemini. */
  endRecording() {
    if (!this.recording) return false;
    this.recording = false;

    if (!this.pcmChunks.length || !this.client?.connected) {
      this.pcmChunks = [];
      return false;
    }

    for (const chunk of this.pcmChunks) {
      this.client.sendAudioMessage(this.arrayBufferToBase64(chunk));
    }
    this.client.sendAudioStreamEnd();
    this.pcmChunks = [];
    return true;
  }

  isRecording() {
    return this.recording;
  }

  stop() {
    this.isStreaming = false;
    this.recording = false;
    this.pcmChunks = [];
    this.audioWorklet?.disconnect();
    this.audioWorklet?.port.close();
    this.audioWorklet = null;
    this.audioContext?.close();
    this.audioContext = null;
    this.mediaStream?.getTracks().forEach((t) => t.stop());
    this.mediaStream = null;
  }

  convertToPCM16(float32Array) {
    const int16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      int16[i] = s * 0x7fff;
    }
    return int16.buffer;
  }

  arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary);
  }
}

class AudioPlayer {
  constructor() {
    this.audioContext = null;
    this.workletNode = null;
    this.gainNode = null;
    this.isInitialized = false;
    this.sampleRate = 24000;
  }

  async init() {
    if (this.isInitialized) return;
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: this.sampleRate });
    await this.audioContext.audioWorklet.addModule(WORKLET_BASE + "/playback.worklet.js");
    this.workletNode = new AudioWorkletNode(this.audioContext, "pcm-processor");
    this.gainNode = this.audioContext.createGain();
    this.workletNode.connect(this.gainNode);
    this.gainNode.connect(this.audioContext.destination);
    this.isInitialized = true;
  }

  async play(base64Audio) {
    if (!this.isInitialized) await this.init();
    if (this.audioContext.state === "suspended") await this.audioContext.resume();
    const binary = atob(base64Audio);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const input = new Int16Array(bytes.buffer, 0, Math.floor(bytes.length / 2));
    const float32 = new Float32Array(input.length);
    for (let i = 0; i < input.length; i++) float32[i] = input[i] / 32768;
    this.workletNode.port.postMessage(float32);
  }

  interrupt() {
    this.workletNode?.port.postMessage("interrupt");
  }

  destroy() {
    this.audioContext?.close();
    this.audioContext = null;
    this.isInitialized = false;
  }
}

export { AudioStreamer, AudioPlayer };
