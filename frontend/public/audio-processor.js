// AudioWorklet processor: Float32 PCM → Int16 PCM, posted back to main thread
class AudioProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel && channel.length > 0) {
      const pcm = new Int16Array(channel.length);
      for (let i = 0; i < channel.length; i++) {
        const clamped = Math.max(-1, Math.min(1, channel[i]));
        pcm[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
      }
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor('keralty-audio-processor', AudioProcessor);
