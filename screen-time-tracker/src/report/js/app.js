/**
 * The scroll rig: one continuous camera journey
 *   eye → down the optic nerve → arrival at the brain,
 * scrubbed by scroll position, with the HTML overlay fading per section.
 */
import * as THREE from '../vendor/three.module.js';
import { loadReport, fmt } from './data.js';
import {
  makeStarfield, makeEye, makeNerve, makeBubbleAnchors, makeBrain, BRAIN_CENTER,
} from './scene.js';

const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor('#02030a', 1);
renderer.toneMapping = THREE.ACESFilmicToneMapping;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 200);

scene.add(new THREE.AmbientLight('#20304f', 1.6));
const key = new THREE.PointLight('#7fb8ff', 60, 40);
key.position.set(3, 3, 4);
scene.add(key);

/* ---------- actors ---------- */
const starfield = makeStarfield();
const eye = makeEye();
const nerve = makeNerve();
const brain = makeBrain();
scene.add(starfield, eye, nerve, brain);

/* ---------- camera keyframes (p, position, lookAt) ---------- */
const KEYS = [
  // hero: look left of the eye so it floats right of the copy
  { p: 0.00, pos: new THREE.Vector3(-1.35, 0.1, 4.6), look: new THREE.Vector3(-1.35, 0, 0) },
  { p: 0.16, pos: new THREE.Vector3(0, 0.05, 2.7), look: new THREE.Vector3(0, 0, 0) },
  { p: 0.30, pos: new THREE.Vector3(2.0, 0.5, 0.4), look: new THREE.Vector3(0.3, -0.1, -2.5) },
  { p: 0.46, pos: new THREE.Vector3(2.4, 0.4, -4.2), look: new THREE.Vector3(1.0, -0.1, -7.5) },
  { p: 0.62, pos: new THREE.Vector3(2.9, 0.5, -9.0), look: new THREE.Vector3(2.0, -0.2, -12.5) },
  { p: 0.76, pos: new THREE.Vector3(4.6, 0.8, -12.6), look: BRAIN_CENTER },
  { p: 1.00, pos: new THREE.Vector3(3.4, 0.9, -13.4), look: BRAIN_CENTER },
];

const ease = (x) => x * x * (3 - 2 * x); // smoothstep

function scrubCamera(p) {
  let a = KEYS[0], b = KEYS[KEYS.length - 1];
  for (let i = 0; i < KEYS.length - 1; i++) {
    if (p >= KEYS[i].p && p <= KEYS[i + 1].p) { a = KEYS[i]; b = KEYS[i + 1]; break; }
  }
  const t = a === b ? 0 : ease((p - a.p) / (b.p - a.p));
  camera.position.lerpVectors(a.pos, b.pos, t);
  const look = new THREE.Vector3().lerpVectors(a.look, b.look, t);
  camera.lookAt(look);
}

/* ---------- overlay sections ---------- */
const panels = [...document.querySelectorAll('.panel')].map((el) => ({
  el,
  from: parseFloat(el.dataset.from),
  to: parseFloat(el.dataset.to),
}));

function updateOverlay(p) {
  const FADE = 0.045;
  for (const s of panels) {
    let o = 0;
    if (p >= s.from && p <= s.to) {
      const fadeIn = s.from <= 0 ? 1 : (p - s.from) / FADE;   // first panel starts visible
      const fadeOut = s.to >= 1 ? 1 : (s.to - p) / FADE;      // last panel stays visible
      o = Math.min(1, fadeIn, fadeOut);
    }
    s.el.style.opacity = o.toFixed(3);
    s.el.style.transform = `translateY(${(1 - o) * 14}px)`;
    s.el.style.pointerEvents = o > 0.5 ? 'auto' : 'none';
  }
}

/* ---------- report data → DOM + bubbles ---------- */
let bubbleAnchors = [];
let bubbleEls = [];
let suggestionsRevealed = false;

function totalOf(report) {
  return report.totalSeconds ?? report.apps.reduce((a, x) => a + x.seconds, 0);
}

async function hydrate() {
  const report = await loadReport();
  const total = totalOf(report);

  document.getElementById('reportDate').textContent = report.date;
  document.getElementById('statTotal').textContent = fmt(total);
  document.getElementById('statTop').textContent = report.apps[0]
    ? `${report.apps[0].name} · ${fmt(report.apps[0].seconds)}` : '—';
  document.getElementById('statIdle').textContent = fmt(report.idleSeconds || 0);

  // nerve bubbles
  const { group, anchors } = makeBubbleAnchors(report.apps, nerve.userData.curve);
  scene.add(group);
  bubbleAnchors = anchors;
  group.userData.parent = group;
  nerve.userData.bubbles = group;

  const bubbleRoot = document.getElementById('bubbles');
  bubbleEls = anchors.map((a) => {
    const el = document.createElement('div');
    el.className = 'bubble';
    const pct = total ? Math.round((a.app.seconds / total) * 100) : 0;
    el.innerHTML = `
      <div class="b-name">${a.app.name}</div>
      <div class="b-time">${fmt(a.app.seconds)} · ${pct}%</div>
      <div class="b-cat">${a.app.category}</div>
      <div class="b-bar" style="width:${Math.max(pct, 6)}%"></div>`;
    bubbleRoot.appendChild(el);
    return el;
  });

  // suggestion cards
  const cardsRoot = document.getElementById('suggestions');
  for (const s of report.suggestions || []) {
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `<div class="k ${s.kind}">${s.kind}</div><h3>${s.title}</h3><p>${s.body}</p>`;
    cardsRoot.appendChild(el);
  }

  // 7-day history bars
  const hist = report.history || [];
  const max = Math.max(...hist.map((h) => h.totalSeconds), 1);
  const barsRoot = document.getElementById('historyBars');
  for (const h of hist) {
    const el = document.createElement('div');
    el.className = 'hbar';
    const day = new Date(h.date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short' });
    el.innerHTML = `<div class="bar" style="height:${Math.round((h.totalSeconds / max) * 80) + 4}px"></div><span>${day}</span>`;
    barsRoot.appendChild(el);
  }

  return { group, anchors };
}

const proj = new THREE.Vector3();
function updateBubbles(p) {
  const w = window.innerWidth, h = window.innerHeight;
  bubbleAnchors.forEach((a, i) => {
    const el = bubbleEls[i];
    // each bubble owns a window of the nerve leg of the journey
    const centre = 0.33 + (a.u - 0.16) * 0.42;
    const vis = Math.max(0, 1 - Math.abs(p - centre) / 0.12);
    proj.copy(a.world).project(camera);
    const behind = proj.z > 1;
    const o = behind ? 0 : Math.min(1, vis * 1.6);
    el.style.opacity = o.toFixed(3);
    a.orb.material.opacity = 0.15 + o * 0.75;
    a.line.material.opacity = o * 0.5;
    a.halo.material.uniforms.uStrength.value = o * 0.9;
    if (!behind) {
      el.style.left = `${((proj.x + 1) / 2) * w}px`;
      el.style.top = `${((1 - proj.y) / 2) * h}px`;
    }
  });
}

function revealSuggestions(p) {
  if (p > 0.8 && !suggestionsRevealed) {
    suggestionsRevealed = true;
    document.querySelectorAll('.card').forEach((el, i) => {
      setTimeout(() => el.classList.add('reveal'), 150 * i);
    });
  }
}

/* ---------- scroll + render loop ---------- */
let target = 0;
let progress = 0;

function readScroll() {
  const max = document.body.scrollHeight - window.innerHeight;
  target = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
}
window.addEventListener('scroll', readScroll, { passive: true });

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();
readScroll();

const clock = new THREE.Clock();
function frame() {
  const t = clock.getElapsedTime();
  progress += (target - progress) * 0.07; // smooth scrub

  scrubCamera(progress);
  updateOverlay(progress);
  updateBubbles(progress);
  revealSuggestions(progress);

  starfield.userData.update(t);
  eye.userData.update(t);
  nerve.userData.update(t);
  nerve.userData.bubbles?.userData.update?.(t);
  const brainReveal = Math.min(1, Math.max(0, (progress - 0.58) / 0.16));
  brain.userData.update(t, brainReveal);

  // the eye gently fades/shrinks once we are far past it
  const eyeFade = 1 - Math.min(1, Math.max(0, (progress - 0.34) / 0.2));
  eye.scale.setScalar(0.6 + 0.4 * eyeFade);

  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

hydrate().then(() => frame());
