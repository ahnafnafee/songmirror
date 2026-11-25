import { mkdir, readFile, writeFile } from "node:fs/promises";

// Original score locked to the film's cue grid. All instruments are synthesized.
const score = JSON.parse(await readFile(new URL("../cues.json", import.meta.url), "utf8"));
const rate = 44100;
const beat = 60 / score.bpm;
const duration = beat * score.beats;
const logoBeat = score.scenes.find(scene => scene.id === "outro").beat;
const track = [new Float32Array(rate * duration), new Float32Array(rate * duration)];
const tau = 2 * Math.PI;
const chords = [
  [45, 57, 60, 64, 67, 71],
  [41, 53, 57, 60, 64, 67],
  [48, 60, 64, 67, 71, 74],
  [43, 55, 59, 62, 67, 69],
];
const phrase = [1, 3, 4, 2, 3, 5, 4, 2];
let noiseSeed = 84791;
function noise() {
  noiseSeed = (Math.imul(1664525, noiseSeed) + 1013904223) >>> 0;
  return (noiseSeed / 0xffffffff) * 2 - 1;
}

function addNote(time, midi, volume, decay, pan) {
  const start = Math.round(time * rate);
  const pitch = tau * 440 * 2 ** ((midi - 69) / 12);
  const tail = Math.round(rate * decay * 6);
  for (let offset = 0; offset < tail && start + offset < track[0].length; offset++) {
    const t = offset / rate;
    const phase = pitch * t;
    const envelope = Math.min(1, t / 0.014) * Math.exp(-t / decay);
    const partials = Math.sin(phase) + 0.21 * Math.sin(phase * 2) + 0.065 * Math.sin(phase * 3);
    const sample = volume * envelope * partials;
    track[0][start + offset] += sample * (1 - pan);
    track[1][start + offset] += sample * pan;
  }
}

function hit(time, gain, shape, tail, pan = 0.5) {
  const start = Math.round(time * rate);
  const length = Math.min(Math.round(tail * rate), track[0].length - start);
  for (let offset = 0; offset < length; offset++) {
    const t = offset / rate;
    const sample = gain * shape(t);
    track[0][start + offset] += sample * (1 - pan);
    track[1][start + offset] += sample * pan;
  }
}

for (let bar = 0; bar * beat * 4 < duration; bar++) {
  const chord = chords[bar % chords.length];
  const start = bar * beat * 4;
  const open = bar < 2;
  addNote(start, chord[0], open ? 0.19 : 0.35, 0.52, 0.5);
  addNote(start + beat * 2, chord[0], open ? 0.11 : 0.23, 0.3, 0.5);
  phrase.forEach((note, index) => {
    if (open && index % 2 === 1) return;
    const time = start + index * beat / 2;
    const pan = index % 2 === 0 ? 0.31 : 0.69;
    addNote(time, chord[note], index % 4 === 0 ? 0.27 : 0.18, open ? 0.3 : 0.2, pan);
    addNote(time + beat * 0.7, chord[note], 0.058, 0.32, 1 - pan);
    addNote(time + beat * 1.4, chord[note], 0.022, 0.36, pan);
  });
}

for (let pulse = 0; pulse < score.beats; pulse++) {
  const cue = score.scenes.some(scene => scene.beat === pulse);
  const open = pulse < 8;
  const t0 = pulse * beat;
  if (pulse === score.breakBeat) continue;
  if (pulse % 2 === 0 || cue) {
    hit(t0, open ? 0.29 : cue ? 0.72 : 0.53,
      t => Math.sin(tau * (52 * t + 3.1 * (1 - Math.exp(-t * 37)))) * Math.exp(-t * (open ? 15 : 19)), 0.32);
  } else if (!open && pulse < logoBeat) {
    hit(t0, 0.21, t => (noise() * 0.7 + Math.sin(t * tau * 185) * 0.3) * Math.exp(-t * 34), 0.12);
  }
  if (!open && pulse < logoBeat) {
    hit(t0 + beat * 0.5, 0.14, t => (noise() - noise()) * Math.exp(-t * 64), 0.067, pulse % 2 ? 0.69 : 0.31);
  }
  if (cue && !open) addNote(t0, pulse === logoBeat ? 81 : 76, 0.16, 0.33, 0.52);
}

const dataSize = track[0].length * 4;
const wav = Buffer.alloc(44 + dataSize);
wav.write("RIFF", 0);
wav.writeUInt32LE(36 + dataSize, 4);
wav.write("WAVEfmt ", 8);
wav.writeUInt32LE(16, 16);
wav.writeUInt16LE(1, 20);
wav.writeUInt16LE(2, 22);
wav.writeUInt32LE(rate, 24);
wav.writeUInt32LE(rate * 4, 28);
wav.writeUInt16LE(4, 32);
wav.writeUInt16LE(16, 34);
wav.write("data", 36);
wav.writeUInt32LE(dataSize, 40);
for (let frame = 0; frame < track[0].length; frame++) {
  const t = frame / rate;
  const fade = Math.min(1, t * 90, (duration - t) / 1.2);
  const gate = t >= score.breakBeat * beat && t < logoBeat * beat ? 0 : fade;
  wav.writeInt16LE(Math.round(Math.tanh(track[0][frame] * 1.32) * gate * 32767), 44 + frame * 4);
  wav.writeInt16LE(Math.round(Math.tanh(track[1][frame] * 1.32) * gate * 32767), 46 + frame * 4);
}

const audio = new URL("../public/audio/", import.meta.url);
await mkdir(audio, { recursive: true });
await writeFile(new URL("soundtrack.wav", audio), wav);
