const video = document.getElementById('video');
const audio = document.getElementById('audio');
const watch = document.getElementById('watch');
const stop = document.getElementById('stop');
const sound = document.getElementById('sound');
const enableSound = document.getElementById('enable-sound');
const fullscreen = document.getElementById('fullscreen');
const statusText = document.getElementById('status');
let pc = null;
let audioPc = null;
let audioPlayer = null;
let requests = [];
let connectionTimer = null;
let generation = 0;
window.cast = {get pc() {return pc;}, get audioPc() {return audioPc;}};

function disconnect(message = 'Transmissão parada.') {
  generation++;
  clearTimeout(connectionTimer);
  for (const request of requests) request.abort();
  requests = [];
  for (const peer of [pc, audioPc]) {
    if (peer) {peer.onconnectionstatechange = null; peer.close();}
  }
  pc = audioPc = null;
  audioPlayer?.close();
  audioPlayer = null;
  delete video.dataset.audioDiagnostics;
  video.srcObject = audio.srcObject = null;
  enableSound.hidden = true;
  watch.disabled = false;
  stop.disabled = true;
  statusText.textContent = message;
}

async function openPeer(kind, target, attempt) {
  const peer = new RTCPeerConnection({iceServers: [], bundlePolicy: 'max-bundle'});
  if (kind === 'video') pc = peer;
  else audioPc = peer;
  const media = new MediaStream();
  target.srcObject = media;
  target.muted = false;
  peer.ontrack = event => {
    media.addTrack(event.track);
    target.play().catch(() => {
      if (generation !== attempt) return;
      if (kind === 'audio') {
        enableSound.hidden = false;
        statusText.textContent = 'Imagem conectada. Pressione Ativar som.';
      }
    });
  };
  peer.onconnectionstatechange = () => {
    if (generation !== attempt) return;
    if (peer.connectionState === 'connected' && kind === 'video') {
      clearTimeout(connectionTimer);
      statusText.textContent = 'Conectado. Continue jogando no portátil.';
    } else if (['failed', 'disconnected'].includes(peer.connectionState)) {
      if (kind === 'video') disconnect('A conexão caiu. Confira o Wi-Fi e pressione Assistir.');
      else statusText.textContent = 'Imagem conectada. Reconecte para recuperar o som.';
    }
  };
  const {receiver} = peer.addTransceiver(kind, {direction: 'recvonly'});
  if ('playoutDelayHint' in receiver) receiver.playoutDelayHint = 0;
  if ('jitterBufferTarget' in receiver) receiver.jitterBufferTarget = 0;
  await peer.setLocalDescription(await peer.createOffer());
  await new Promise(resolve => {
    if (peer.iceGatheringState === 'complete') return resolve();
    const timer = setTimeout(resolve, 2500);
    peer.addEventListener('icegatheringstatechange', () => {
      if (peer.iceGatheringState === 'complete') {clearTimeout(timer); resolve();}
    });
  });
  if (generation !== attempt) return;
  const request = new AbortController();
  requests.push(request);
  const response = await fetch('/offer', {
    method: 'POST', headers: {'Content-Type': 'application/sdp'},
    body: peer.localDescription.sdp, signal: request.signal,
  });
  const answer = await response.text();
  if (generation !== attempt) return;
  if (!response.ok) throw new Error('O portátil não conseguiu iniciar a transmissão. Tente novamente.');
  await peer.setRemoteDescription({type: 'answer', sdp: answer});
}

async function connect() {
  disconnect('Conectando ao portátil…');
  const attempt = generation;
  if (!window.RTCPeerConnection) {
    statusText.textContent = 'Este navegador não permite a transmissão. Tente outro navegador no Android.';
    return;
  }
  watch.disabled = true;
  stop.disabled = false;
  connectionTimer = setTimeout(() => {
    if (generation === attempt) disconnect('Não foi possível conectar. Confira o Wi-Fi e tente novamente.');
  }, 25000);
  try {
    const audioReady = sound.checked ? startAudio(attempt) : Promise.resolve();
    // Independent receivers avoid making video wait for the audio playout clock.
    await openPeer('video', video, attempt);
    await audioReady;
  } catch (error) {
    if (generation === attempt) disconnect(error.message || 'Não foi possível conectar. Tente novamente.');
  }
}

async function startAudio(attempt) {
  let fallbackStarted = false;
  let player = null;
  const fallback = async () => {
    if (fallbackStarted || generation !== attempt) return;
    fallbackStarted = true;
    player?.close();
    if (audioPlayer === player) audioPlayer = null;
    try {await openPeer('audio', audio, attempt);}
    catch (_) {
      if (generation === attempt) statusText.textContent = 'Imagem conectada. Reconecte para recuperar o som.';
    }
  };
  try {
    player = new DirectAudio(video);
    audioPlayer = player;
    await player.start(fallback);
  } catch (_) {await fallback();}
}

watch.addEventListener('click', connect);
stop.addEventListener('click', () => disconnect());
sound.addEventListener('change', () => {if (pc) connect();});
enableSound.addEventListener('click', () => {
  audio.play().then(() => {enableSound.hidden = true; statusText.textContent = 'Conectado com som.';})
    .catch(() => {statusText.textContent = 'Não foi possível reproduzir o som neste navegador.';});
});
video.addEventListener('volumechange', () => {
  audio.volume = video.volume; audio.muted = video.muted;
  audioPlayer?.syncVolume();
});
fullscreen.addEventListener('click', async () => {
  try {
    if (video.requestFullscreen) await video.requestFullscreen();
    else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
  } catch (_) {statusText.textContent = 'Use o botão de tela cheia do navegador.';}
});
window.addEventListener('pagehide', () => disconnect());

setInterval(async () => {
  if (!pc || pc.connectionState !== 'connected') return;
  try {
    const report = [];
    for (const peer of [pc, audioPc]) {
      if (!peer || peer.connectionState !== 'connected') continue;
      const stats = await peer.getStats();
      for (const item of stats.values()) {
        if (item.type === 'inbound-rtp') report.push({
          kind: item.kind, fps: item.framesPerSecond, frames: item.framesDecoded,
          dropped: item.framesDropped, jitter: item.jitter,
          buffer: item.jitterBufferDelay, emitted: item.jitterBufferEmittedCount,
          target: item.jitterBufferTargetDelay, decode: item.totalDecodeTime,
          processing: item.totalProcessingDelay, lost: item.packetsLost,
          timestamp: item.timestamp,
        });
        if (item.type === 'candidate-pair' && item.state === 'succeeded')
          report.push({rtt: item.currentRoundTripTime});
      }
    }
    video.dataset.diagnostics = JSON.stringify(report);
    video.dataset.audioDiagnostics = JSON.stringify(audioPlayer ? audioPlayer.diagnostics() : {mode: 'opus'});
  } catch (_) { /* A disconnected receiver has no measurements. */ }
}, 2000);
