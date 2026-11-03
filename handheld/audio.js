/* Short PCM queue. ScriptProcessor also works on local HTTP Android browsers,
   where AudioWorklet requires a secure origin. Opus remains the fallback. */
class DirectAudio {
  constructor(video) {
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context || !window.ReadableStream) throw new Error('Use o som compatível.');
    this.context = new Context({latencyHint: 'interactive', sampleRate: 48000});
    if (this.context.sampleRate !== 48000 || !this.context.createScriptProcessor) {
      this.context.close();
      throw new Error('Use o som compatível.');
    }
    this.video = video;
    this.controller = new AbortController();
    this.token = Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2,'0')).join('');
    this.left = new Float32Array(48000);
    this.right = new Float32Array(48000);
    this.read = this.write = this.count = 0;
    this.target = 1536; // 32 ms covers the handheld's bursty audio delivery.
    this.primed = this.closed = false;
    this.tail = new Uint8Array(0);
    this.received = this.played = this.underruns = this.dropped = 0;
    this.peak = 0;
    this.maxPushGap = this.maxRenderGap = this.maxQueue = 0;
    this.lastPush = this.lastRender = 0;
    this.gain = this.context.createGain();
    this.processor = this.context.createScriptProcessor(256, 0, 2);
    this.processor.onaudioprocess = event => this.render(event.outputBuffer);
    this.processor.connect(this.gain);
    this.gain.connect(this.context.destination);
    this.syncVolume();
  }

  syncVolume() {
    this.gain.gain.value = this.video.muted ? 0 : this.video.volume;
  }

  async start(onFailure) {
    let timer;
    try {
      await Promise.race([this.open(onFailure), new Promise((_, reject) => {
        timer = setTimeout(() => {
          this.controller.abort();
          reject(new Error('Som direto indisponível.'));
        }, 5000);
      })]);
    } finally {
      clearTimeout(timer);
    }
  }

  async open(onFailure) {
    // Called from Assistir's click, before awaiting any network operation.
    await this.context.resume();
    if (this.closed) return;
    const response = await fetch('/audio.pcm', {signal: this.controller.signal,
      cache: 'no-store', headers: {'X-Cast-Audio': this.token}});
    if (!response.ok || !response.body) throw new Error('Som direto indisponível.');
    this.reader = response.body.getReader();
    const first = await this.reader.read();
    if (first.done || this.closed) throw new Error('Som direto encerrado.');
    this.push(first.value);
    this.heartbeat = setInterval(() => {
      fetch('/audio-alive', {method: 'POST', body: this.token, signal: this.controller.signal}).catch(() => {});
    }, 2000);
    this.pump(onFailure);
  }

  async pump(onFailure) {
    try {
      while (!this.closed) {
        const {value, done} = await this.reader.read();
        if (done) throw new Error('A conexão do som caiu.');
        this.push(value);
      }
    } catch (error) {
      if (!this.closed) onFailure(error);
    }
  }

  push(bytes) {
    const now = performance.now();
    if (this.lastPush) this.maxPushGap = Math.max(this.maxPushGap, now - this.lastPush);
    this.lastPush = now;
    if (this.tail.length) {
      const joined = new Uint8Array(this.tail.length + bytes.length);
      joined.set(this.tail); joined.set(bytes, this.tail.length); bytes = joined;
    }
    const frames = Math.floor(bytes.length / 4);
    this.tail = bytes.slice(frames * 4);
    const view = new DataView(bytes.buffer, bytes.byteOffset, frames * 4);
    const skip = Math.max(0, frames - this.left.length);
    for (let i = skip; i < frames; i++) {
      if (this.count === this.left.length) {
        this.read = (this.read + 1) % this.left.length;
        this.count--; this.dropped++;
      }
      const l = view.getInt16(i*4, true) / 32768;
      const r = view.getInt16(i*4+2, true) / 32768;
      this.left[this.write] = l; this.right[this.write] = r;
      this.peak = Math.max(this.peak, Math.abs(l), Math.abs(r));
      this.write = (this.write + 1) % this.left.length;
      this.count++;
    }
    this.received += frames;
    this.maxQueue = Math.max(this.maxQueue, this.count);
    if (this.count > 3840) {
      const discard = this.count - this.target;
      this.read = (this.read + discard) % this.left.length;
      this.count -= discard; this.dropped += discard;
    }
  }

  render(buffer) {
    const now = performance.now();
    if (this.lastRender) this.maxRenderGap = Math.max(this.maxRenderGap, now - this.lastRender);
    this.lastRender = now;
    const l = buffer.getChannelData(0), r = buffer.getChannelData(1);
    l.fill(0); r.fill(0);
    if (this.closed) return;
    if (!this.primed && this.count >= this.target) this.primed = true;
    if (!this.primed) return;
    const available = Math.min(l.length, this.count);
    for (let i = 0; i < available; i++) {
      l[i] = this.left[this.read]; r[i] = this.right[this.read];
      this.read = (this.read + 1) % this.left.length;
    }
    this.count -= available; this.played += available;
    if (available < l.length) {
      this.primed = false; this.underruns++;
      this.target = Math.min(2304, this.target + 240);
    }
  }

  diagnostics() {
    return {mode: 'pcm', state: this.context.state, queueMs: this.count / 48,
      baseMs: this.context.baseLatency * 1000,
      outputMs: this.context.outputLatency * 1000,
      received: this.received, played: this.played, underruns: this.underruns,
      dropped: this.dropped, peak: this.peak, targetMs: this.target / 48,
      maxQueueMs: this.maxQueue / 48, maxPushGapMs: this.maxPushGap,
      maxRenderGapMs: this.maxRenderGap};
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    clearInterval(this.heartbeat);
    fetch('/audio-stop', {method: 'POST', body: this.token, keepalive: true}).catch(() => {});
    this.controller.abort();
    this.reader?.cancel().catch(() => {});
    this.processor.onaudioprocess = null;
    this.processor.disconnect(); this.gain.disconnect();
    this.context.close().catch(() => {});
  }
}

// Test entry point when loaded by Node; browsers keep the regular script API.
if (typeof module !== 'undefined') module.exports = {DirectAudio};
