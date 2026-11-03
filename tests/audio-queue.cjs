const assert = require('node:assert/strict');
const {DirectAudio} = require('../handheld/audio.js');

function player() {
  const p = Object.create(DirectAudio.prototype);
  Object.assign(p,{left:new Float32Array(48000),right:new Float32Array(48000),
    read:0,write:0,count:0,target:1536,primed:false,closed:false,tail:new Uint8Array(0),
    received:0,played:0,underruns:0,dropped:0,peak:0,maxPushGap:0,maxRenderGap:0,
    maxQueue:0,lastPush:0,lastRender:0});
  return p;
}

// Arbitrary HTTP boundaries must not change signed, interleaved stereo samples.
const p = player();
const samples = [-32768,32767,16384,-16384,1,-1,0,1234];
const bytes = new Uint8Array(samples.length*2);
const view = new DataView(bytes.buffer);
samples.forEach((sample,i)=>view.setInt16(i*2,sample,true));
let offset=0;
for(const size of [1,2,5,3,5]) {p.push(bytes.slice(offset,offset+size));offset+=size;}
assert.equal(p.count,4); assert.equal(p.tail.length,0);
p.target=1;
const channels=[new Float32Array(4),new Float32Array(4)];
p.render({getChannelData:i=>channels[i]});
for(let i=0;i<4;i++) {
  assert.equal(channels[0][i],samples[i*2]/32768);
  assert.equal(channels[1][i],samples[i*2+1]/32768);
}
assert.equal(p.count,0); assert.equal(p.played,4);

// A delayed burst must recover to a bounded queue rather than keep old sound.
const q=player(); q.push(new Uint8Array(48000*4));
assert.equal(q.count,q.target); assert.equal(q.dropped,48000-q.target);

// Missing samples produce silence and an explicit rebuffer state.
q.primed=true; q.count=0;
const silence=[new Float32Array(256).fill(1),new Float32Array(256).fill(1)];
q.render({getChannelData:i=>silence[i]});
assert(silence.every(channel=>channel.every(sample=>sample===0)));
assert.equal(q.underruns,1); assert.equal(q.primed,false);
console.log('PCM sample integrity, stream fragmentation, queue bounds and recovery passed.');
