/* ============================================================
   vues_3d.js — Hôte des vues 3D de JARVIS (ex-mode hologramme)
   Explorateur spatial, carte domotique, cortex, échecs et radar réseau
   s'affichent ici, ouverts directement à la voix (voir hud/vues_3d.ts).
   Rendu Three.js commun (lueur + aberration chromatique), fond étoilé et
   contrôle par les mains via la webcam (MediaPipe).
   Les identifiants DOM « holo-* » sont conservés : les vues les utilisent.
   Exports : ouvrirDansHote(type) / fermerHote() / vueOuverte()
   ============================================================ */

import * as THREE from 'three';
import { EffectComposer }  from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass }      from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass }      from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass }      from 'three/addons/postprocessing/OutputPass.js';

const COLOR = {
  CYAN:      0x00e5ff,
  ORANGE:    0xff8a1a,
  RED:       0xff2e4d,
};

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

const HAND_CONNECTIONS = [
  [0,1],[1,2],[2,3],[3,4],
  [0,5],[5,6],[6,7],[7,8],
  [5,9],[9,10],[10,11],[11,12],
  [9,13],[13,14],[14,15],[15,16],
  [13,17],[0,17],[17,18],[18,19],[19,20],
];

/* ── Suivi des mains (MediaPipe) ─────────────────────────── */
class HandTracker {
  constructor(video, app) {
    this.video = video;
    this.app = app;
    this.results = null;
    this.onResults = null;
    this.ready = false;
    if (typeof Hands === 'undefined') throw new Error('MediaPipe Hands not loaded');
    this.hands = new Hands({
      locateFile: (file) =>
        `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/${file}`,
    });
    this.hands.setOptions({
      maxNumHands: 2,
      modelComplexity: 1,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });
    this.hands.onResults((r) => { this.results = r; this.ready = true; if (this.onResults) this.onResults(r); });
    this._camera = null;
  }

  async start() {
    if (typeof Hands === 'undefined') throw new Error('MediaPipe Hands non chargé.');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }
      });
      this.video.srcObject = stream;
      await new Promise((resolve) => {
        this.video.onloadedmetadata = () => { this.video.play(); resolve(); };
      });

      // Camera utility MediaPipe : envoie CHAQUE frame sans throttle
      // Crucial pour la détection fiable des 2 mains simultanément
      if (typeof Camera !== 'undefined') {
        this._camera = new Camera(this.video, {
          onFrame: async () => {
            if (!this.app._running) return;
            try { await this.hands.send({ image: this.video }); } catch (e) {}
          },
          width: 1280,
          height: 720,
        });
        await this._camera.start();
      } else {
        // Fallback sans throttle si Camera utility absent
        const processFrame = async () => {
          if (!this.app._running || this.video.paused || this.video.ended) return;
          try { await this.hands.send({ image: this.video }); } catch (e) {}
          requestAnimationFrame(processFrame);
        };
        processFrame();
      }
    } catch (err) {
      let msg = 'Erreur caméra: ';
      if (err.name === 'NotAllowedError') msg = 'Accès caméra REFUSÉ.';
      else if (err.name === 'NotFoundError') msg = 'Aucune caméra détectée.';
      else if (err.name === 'NotReadableError') msg = 'Caméra occupée par une autre appli.';
      else msg += err.message;
      throw new Error(msg);
    }
  }

  stop() {
    if (this._camera) { try { this._camera.stop(); } catch(e) {} this._camera = null; }
    if (this.video && this.video.srcObject) {
      this.video.srcObject.getTracks().forEach(t => t.stop());
      this.video.srcObject = null;
    }
  }
}

/* ── GestureSystem ───────────────────────────────────────── */
class GestureSystem {
  constructor() {
    this.history = [[], []];
    this.indexHistory = [[], []];
    this.openFlag = [false, false];
    this.fistFlag = [false, false];
    this.lastMicToggleTime = 0;
  }
  static dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }
  static pinchValue(hand) { return GestureSystem.dist(hand[4], hand[8]); }
  static isPinched(hand)  { return GestureSystem.pinchValue(hand) < 0.08; }
  static pinchCenter(hand) { return { x: (hand[4].x + hand[8].x) * 0.5, y: (hand[4].y + hand[8].y) * 0.5, z: ((hand[4].z || 0) + (hand[8].z || 0)) * 0.5 }; }
  static isOpenHand(hand) {
    const palm = hand[0], tips = [4,8,12,16,20];
    let avg = 0; for (const t of tips) avg += GestureSystem.dist(hand[t], palm); avg /= tips.length;
    const extended = hand[8].y < hand[5].y && hand[12].y < hand[9].y && hand[16].y < hand[13].y && hand[20].y < hand[17].y;
    return avg > 0.27 && extended;
  }
  static isFist(hand) {
    const palm = hand[0], tips = [8,12,16,20];
    let avg = 0; for (const t of tips) avg += GestureSystem.dist(hand[t], palm); avg /= tips.length;
    const curled = hand[8].y > hand[6].y && hand[12].y > hand[10].y && hand[16].y > hand[14].y && hand[20].y > hand[18].y;
    return avg < 0.12 && curled;
  }
  pushHistory(handIdx, hand) {
    if (!hand) { this.history[handIdx].length = 0; return; }
    const wrist = hand[0];
    this.history[handIdx].push({ x: wrist.x, y: wrist.y, t: performance.now() });
    while (this.history[handIdx].length > 18) this.history[handIdx].shift();
  }
  pushIndexHistory(handIdx, hand) {
    if (!hand) { this.indexHistory[handIdx].length = 0; return; }
    const indexTip = hand[8];
    const now = performance.now();
    this.indexHistory[handIdx].push({ x: indexTip.x, y: indexTip.y, t: now });
    while (this.indexHistory[handIdx].length > 0 && now - this.indexHistory[handIdx][0].t > 2500) {
      this.indexHistory[handIdx].shift();
    }
  }
  detectCircle(handIdx) {
    const points = this.indexHistory[handIdx];
    if (!points || points.length < 20) return false;

    let sumX = 0, sumY = 0;
    for (const p of points) {
      sumX += p.x;
      sumY += p.y;
    }
    const centerX = sumX / points.length;
    const centerY = sumY / points.length;

    let sumR = 0;
    const radii = [];
    for (const p of points) {
      const r = Math.hypot(p.x - centerX, p.y - centerY);
      radii.push(r);
      sumR += r;
    }
    const avgR = sumR / points.length;

    if (avgR < 0.035 || avgR > 0.25) return false;

    let sumSqDiff = 0;
    for (const r of radii) {
      const diff = r - avgR;
      sumSqDiff += diff * diff;
    }
    const stdDev = Math.sqrt(sumSqDiff / points.length);
    const coeffOfVariation = stdDev / avgR;

    if (coeffOfVariation > 0.22) return false;

    let totalAngle = 0;
    let prevAngle = null;
    for (const p of points) {
      const angle = Math.atan2(p.y - centerY, p.x - centerX);
      if (prevAngle !== null) {
        let diff = angle - prevAngle;
        while (diff < -Math.PI) diff += 2 * Math.PI;
        while (diff > Math.PI) diff -= 2 * Math.PI;
        totalAngle += diff;
      }
      prevAngle = angle;
    }

    if (Math.abs(totalAngle) < 5.0) return false;

    return true;
  }
  detectSwipe(handIdx) {
    const hist = this.history[handIdx];
    if (!hist || hist.length < 5) return null;
    
    const now = performance.now();
    // Garde l'historique propre des entrées de plus de 500ms
    while (hist.length > 0 && now - hist[0].t > 500) {
      hist.shift();
    }
    
    if (hist.length < 5) return null;
    
    const newest = hist[hist.length - 1];
    for (let i = 0; i < hist.length - 3; i++) {
      const old = hist[i];
      const dt = newest.t - old.t;
      if (dt > 400) continue; // Seulement les mouvements rapides (< 400ms)
      
      const dx = newest.x - old.x;
      const dy = newest.y - old.y;
      
      if (Math.abs(dx) > 0.16 && Math.abs(dx) > Math.abs(dy) * 1.5) {
        hist.length = 0;
        return dx > 0 ? 'left' : 'right';
      }
    }
    return null;
  }
}

/* ── Rendu, fond étoilé, dessin des mains ────────────────── */
class HologramRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
    this.camera.position.set(0, 0, 5);
    this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, powerPreference: 'high-performance', failIfMajorPerformanceCaveat: false });
    this.renderer.setPixelRatio(1.0);
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setClearColor(0x000000, 0);
    this.composer = new EffectComposer(this.renderer);
    this.composer.setSize(window.innerWidth, window.innerHeight);
    this.renderPass = new RenderPass(this.scene, this.camera);
    this.renderPass.clear = true; this.renderPass.clearAlpha = 0;
    this.composer.addPass(this.renderPass);
    const bW = Math.round(window.innerWidth / 2), bH = Math.round(window.innerHeight / 2);
    this.bloomPass = new UnrealBloomPass(new THREE.Vector2(bW, bH), 0.22, 0.4, 0.30);
    this.composer.addPass(this.bloomPass);
    const chromaShader = {
      uniforms: { tDiffuse: { value: null }, offset: { value: 0.0025 }, time: { value: 0 } },
      vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
      fragmentShader: `uniform sampler2D tDiffuse; uniform float offset; uniform float time; varying vec2 vUv; void main() { vec2 dir = vUv - 0.5; float ofs = offset * (0.6 + length(dir) * 1.4); float r = texture2D(tDiffuse, vUv + dir * ofs).r; float g = texture2D(tDiffuse, vUv).g; float b = texture2D(tDiffuse, vUv - dir * ofs).b; float a = texture2D(tDiffuse, vUv).a; float scan = 0.95 + 0.05 * sin((vUv.y * 1000.0) + time * 10.0); gl_FragColor = vec4(r,g,b,a) * scan; }`,
    };
    this.chromaPass = new ShaderPass(chromaShader);
    this.composer.addPass(this.chromaPass);
    this.composer.addPass(new OutputPass());
    const gl = this.renderer.getContext();
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    this.gpuName = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'Unknown GPU';
    this._addLights(); this._addPointers();
    this._resizeHandler = () => this._onResize();
    window.addEventListener('resize', this._resizeHandler);
  }
  _addPointers() {
    this.pointers = [];
    for (let i = 0; i < 2; i++) {
      const g = new THREE.SphereGeometry(0.06, 8, 8), m = new THREE.MeshBasicMaterial({ color: i===0 ? 0x00ffff : 0xffaa00, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending });
      const mesh = new THREE.Mesh(g, m); mesh.visible = false; this.scene.add(mesh); this.pointers.push(mesh);
    }
  }
  _addLights() {
    this.scene.add(new THREE.AmbientLight(0x223344, 0.2));
    const l1 = new THREE.PointLight(COLOR.CYAN, 0.4, 25); l1.position.set(2, 3, 4); this.scene.add(l1);
    const l2 = new THREE.PointLight(COLOR.ORANGE, 0.3, 25); l2.position.set(-3, -2, 3); this.scene.add(l2);
    const l3 = new THREE.PointLight(COLOR.RED, 0.2, 20); l3.position.set(0, 4, -2); this.scene.add(l3);
  }
  _onResize() {
    const W = window.innerWidth, H = window.innerHeight;
    this.camera.aspect = W/H; this.camera.updateProjectionMatrix();
    this.renderer.setSize(W, H); this.composer.setSize(W, H);
    this.bloomPass.resolution.set(Math.round(W/2), Math.round(H/2));
  }
  ndcToWorld(ndcX, ndcY, planeZ = 0) {
    const v = new THREE.Vector3(ndcX, ndcY, 0.5); v.unproject(this.camera);
    const dir = v.sub(this.camera.position).normalize(), t = (planeZ - this.camera.position.z) / dir.z;
    return this.camera.position.clone().add(dir.multiplyScalar(t));
  }
  render(dt) { this.chromaPass.uniforms.time.value += dt; this.composer.render(); }
  dispose() { window.removeEventListener('resize', this._resizeHandler); this.renderer.dispose(); }
}

/* ── Starfield ───────────────────────────────────────────── */
class Starfield {
  constructor(canvas) {
    this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.stars = []; this.resize();
    for (let i = 0; i < 100; i++) this.stars.push({ x: Math.random()*this.w, y: Math.random()*this.h, s: Math.random()*1.4+0.2, a: Math.random()*0.6+0.35, phase: Math.random()*Math.PI*2, speed: Math.random()*0.6+0.2, vx: -(Math.random()*0.04+0.005) });
    this._resizeH = () => this.resize();
    window.addEventListener('resize', this._resizeH);
  }
  resize() { this.w = this.canvas.width = window.innerWidth; this.h = this.canvas.height = window.innerHeight; }
  update(t) {
    const ctx = this.ctx; ctx.clearRect(0, 0, this.w, this.h);
    for (const s of this.stars) {
      const a = s.a * (0.55 + 0.45 * Math.sin(t * s.speed + s.phase));
      ctx.fillStyle = `rgba(180,240,255,${a.toFixed(3)})`; ctx.beginPath(); ctx.arc(s.x, s.y, s.s, 0, Math.PI*2); ctx.fill();
      s.x += s.vx; if (s.x < -2) s.x = this.w + 2;
    }
  }
  dispose() { window.removeEventListener('resize', this._resizeH); }
}

/* ── HandOverlay ─────────────────────────────────────────── */
class HandOverlay {
  constructor(canvas) {
    this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.resize();
    this._resizeH = () => this.resize();
    window.addEventListener('resize', this._resizeH);
  }
  resize() { this.w = this.canvas.width = window.innerWidth; this.h = this.canvas.height = window.innerHeight; }
  draw(results, mirror = true) {
    const ctx = this.ctx; ctx.clearRect(0, 0, this.w, this.h);
    if (!results || !results.multiHandLandmarks) return;
    const xp = (lm) => mirror ? (1 - lm.x) * this.w : lm.x * this.w;
    for (let hi = 0; hi < results.multiHandLandmarks.length; hi++) {
      const hand = results.multiHandLandmarks[hi];
      const pinched = GestureSystem.isPinched(hand), openHand = GestureSystem.isOpenHand(hand), fist = GestureSystem.isFist(hand);
      let color = '#00e5ff'; if (pinched) color = '#ff8a1a'; if (openHand) color = '#6ff8ff'; if (fist) color = '#ff2e4d';
      ctx.lineWidth = 1.6; ctx.strokeStyle = color; ctx.shadowColor = color; ctx.shadowBlur = 14;
      for (const [a, b] of HAND_CONNECTIONS) {
        const pa = hand[a], pb = hand[b];
        ctx.beginPath(); ctx.moveTo(xp(pa), pa.y*this.h); ctx.lineTo(xp(pb), pb.y*this.h); ctx.stroke();
      }
      ctx.fillStyle = color; ctx.shadowBlur = 10;
      for (let i = 0; i < hand.length; i++) {
        const p = hand[i]; let r = 3.5;
        if (i === 4 || i === 8) r = pinched ? 7 : 5; if (i === 0) r = 5;
        ctx.beginPath(); ctx.arc(xp(p), p.y*this.h, r, 0, Math.PI*2); ctx.fill();
      }
      const t = hand[4], idx = hand[8];
      ctx.strokeStyle = pinched ? '#ffb454' : '#00e5ff'; ctx.shadowColor = ctx.strokeStyle; ctx.lineWidth = pinched ? 3 : 1.2; ctx.setLineDash(pinched ? [] : [4,4]);
      ctx.beginPath(); ctx.moveTo(xp(t), t.y*this.h); ctx.lineTo(xp(idx), idx.y*this.h); ctx.stroke(); ctx.setLineDash([]);
      if (pinched) {
        const cx = (xp(t) + xp(idx)) * 0.5, cy = (t.y + idx.y) * 0.5 * this.h;
        ctx.strokeStyle = '#ffb454'; ctx.shadowBlur = 24; ctx.lineWidth = 1.3;
        ctx.beginPath(); ctx.arc(cx, cy, 22+Math.sin(performance.now()*0.012)*4, 0, Math.PI*2); ctx.stroke();
        ctx.beginPath(); ctx.arc(cx, cy, 34+Math.sin(performance.now()*0.012+1)*4, 0, Math.PI*2); ctx.stroke();
      }
    }
    ctx.shadowBlur = 0;
  }
  dispose() { window.removeEventListener('resize', this._resizeH); }
}

/* ── Hôte des vues 3D ────────────────────────────────────── */
// Une seule vue à la fois. Chaque vue reçoit la scène et la caméra du rendu commun,
// sa méthode update(dt) est appelée à chaque image et, si elle sait les gérer, les
// positions 3D et pincements des deux mains (updateHandsInteraction).
const VUES = {
  explorer: { classe: 'SpatialFileExplorer', globale: '_spatialExplorer', ws: true },
  domotic:  { classe: 'DomoticMap',          globale: '_domoticMap',      ws: true },
  cortex:   { classe: 'CortexMap',           globale: '_cortexMap',       ws: true },
  chess:    { classe: 'ChessMap',            globale: '_chessMap',        ws: true },
  radar:    { classe: 'NetworkRadar',        globale: '_networkRadar',    ws: false },
};

class HoteVues3D {
  constructor(container) {
    this.container = container;
    const q = (id) => container.querySelector('#' + id);
    this.video       = q('holo-webcam');
    this.threeCanvas = q('holo-three-canvas');
    this.handCanvas  = q('holo-hand-canvas');
    this.starCanvas  = q('holo-starfield');
    this.toast       = q('holo-gesture-toast');

    this._running = true;
    this._raf = null;
    this._mirror = true;
    this.wasPinched = [false, false];

    this.starfield   = new Starfield(this.starCanvas);
    this.handOverlay = new HandOverlay(this.handCanvas);
    this.renderer    = new HologramRenderer(this.threeCanvas);
    this.gestures    = new GestureSystem();

    this.type = null;   // 'explorer' | 'domotic' | 'cortex' | 'chess' | 'radar'
    this.vue = null;    // instance de la vue ouverte

    this.tracker = null;
    this.lastResults = null;
    this.handPos3D = [null, null];
    this._lastT = performance.now();
    this._toastTimer = 0;

    this._loop = this._loop.bind(this);
    this._raf = requestAnimationFrame(this._loop);
  }

  /** Ouvre la vue demandée (en fermant l'autre) et renvoie son instance, ou null. */
  ouvrir(type) {
    if (this.type === type && this.vue?.active) return this.vue;
    this.fermerVue();
    const def = VUES[type];
    if (!def) { console.warn('[VUES 3D] Vue inconnue :', type); return null; }
    const Classe = window[def.classe];
    if (!Classe) { console.warn(`[VUES 3D] Module ${def.classe} non chargé`); return null; }
    const ws = window._jarvisWs;
    if (def.ws && !ws) { console.warn(`[VUES 3D] WebSocket non disponible pour ${type}`); return null; }
    this.vue = def.ws ? new Classe(this.renderer.scene, this.renderer.camera, ws)
                      : new Classe(this.renderer.scene, this.renderer.camera);
    this.type = type;
    window[def.globale] = this.vue;
    this.vue.activate();
    if (type === 'chess' && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'chess_action', action: 'get_state' }));
    }
    return this.vue;
  }

  /** Ferme la vue ouverte (la partie d'échecs en cours est arrêtée côté backend). */
  fermerVue() {
    if (!this.vue) return;
    const def = VUES[this.type];
    if (this.type === 'explorer' && typeof this.vue.destroy === 'function') this.vue.destroy();
    else this.vue.deactivate();
    if (this.type === 'chess') {
      const ws = window._jarvisWs;
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'chess_action', action: 'stop' }));
    }
    window[def.globale] = null;
    this.vue = null;
    this.type = null;
  }

  async start() {
    try {
      if (typeof Hands === 'undefined') throw new Error('MediaPipe non chargé');
      this.tracker = new HandTracker(this.video, this);
      this.tracker.onResults = (r) => { this.lastResults = r; };
      this.tracker.start().catch(err => this._afficherToast('⚠ CAM: ' + (err.message || 'accès refusé').slice(0, 40), true));
    } catch (err) {
      this._afficherToast('⚠ CAM: ' + (err.message || 'accès refusé').slice(0, 40), true);
    }
  }

  destroy() {
    this._running = false;
    if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
    this.fermerVue();
    if (this.tracker) { this.tracker.stop(); this.tracker = null; }
    if (this.video && this.video.srcObject) {
      this.video.srcObject.getTracks().forEach(t => t.stop());
      this.video.srcObject = null;
    }
    clearTimeout(this._toastTimer);
    this.toast?.classList.remove('visible');
    this.starfield.dispose();
    this.handOverlay.dispose();
    this.renderer.dispose();
  }

  _afficherToast(texte, erreur = false) {
    if (!this.toast) return;
    this.toast.textContent = texte;
    this.toast.style.color = erreur ? '#ff2e4d' : '';
    this.toast.style.borderColor = erreur ? '#ff2e4d' : '';
    this.toast.classList.add('visible');
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this.toast?.classList.remove('visible');
      if (this.toast) { this.toast.style.color = ''; this.toast.style.borderColor = ''; }
    }, erreur ? 4000 : 850);
  }

  _getScreenCoords(lm) {
    if (!lm) return { x: 0, y: 0 };
    return {
      x: this._mirror ? (1 - lm.x) * window.innerWidth : lm.x * window.innerWidth,
      y: lm.y * window.innerHeight,
    };
  }

  _processGestures() {
    const results = this.lastResults, hands = (results && results.multiHandLandmarks) || [];

    for (let i = 0; i < 2; i++) {
      const h = hands[i];

      // Geste circulaire de l'index : coupe / réactive le micro de JARVIS
      this.gestures.pushIndexHistory(i, h);
      if (h) {
        const now = performance.now();
        if (now - this.gestures.lastMicToggleTime > 2000 && this.gestures.detectCircle(i)) {
          this.gestures.lastMicToggleTime = now;
          this.gestures.indexHistory[i].length = 0;
          const ws = window._jarvisWs;
          if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'toggle_mic' }));
          this._afficherToast('MIC TOGGLE');
        }
      }

      if (!h) { this.handPos3D[i] = null; continue; }
      const c = GestureSystem.pinchCenter(h), ndcX = this._mirror ? -(c.x*2-1) : (c.x*2-1), ndcY = -(c.y*2-1), planeZ = clamp(-c.z*1.5, -1.5, 1.5);
      this.handPos3D[i] = this.renderer.ndcToWorld(ndcX, ndcY, planeZ);
      const pinched = GestureSystem.isPinched(h);
      if (this.renderer.pointers[i]) {
        this.renderer.pointers[i].visible = true;
        this.renderer.pointers[i].position.copy(this.handPos3D[i]);
        this.renderer.pointers[i].scale.setScalar(pinched ? 0.6 : 1.0);
      }

      // Un pincement clique le bouton HTML sous l'index (panneaux des vues)
      if (pinched && !this.wasPinched[i]) {
        this.wasPinched[i] = true;
        const screenPos = this._getScreenCoords(h[8]);
        const oldPointer = this.handCanvas.style.pointerEvents;
        this.handCanvas.style.pointerEvents = 'none';
        this.threeCanvas.style.pointerEvents = 'none';
        const el = document.elementFromPoint(screenPos.x, screenPos.y);
        this.handCanvas.style.pointerEvents = oldPointer;
        this.threeCanvas.style.pointerEvents = oldPointer;
        const btn = el && el.closest('button');
        if (btn) {
          btn.click();
          const originalTransform = btn.style.transform;
          btn.style.transform = 'scale(0.92)';
          setTimeout(() => { btn.style.transform = originalTransform; }, 150);
        }
      } else if (!pinched) {
        this.wasPinched[i] = false;
      }
    }

    // Pincer pour attraper / déplacer, deux mains pincées pour tourner
    if (this.vue?.active && typeof this.vue.updateHandsInteraction === 'function') {
      const pinched0 = !!(hands[0] && GestureSystem.isPinched(hands[0]));
      const pinched1 = !!(hands[1] && GestureSystem.isPinched(hands[1]));
      this.vue.updateHandsInteraction(this.handPos3D[0], pinched0, this.handPos3D[1], pinched1);
    }
  }

  _loop(now) {
    if (!this._running) return;
    const dt = Math.min((now - this._lastT) / 1000, 0.05);
    this._lastT = now;
    this._processGestures();
    if (this.vue?.active) this.vue.update(dt);
    this.starfield.update(now / 1000);
    this.handOverlay.draw(this.lastResults, this._mirror);
    this.renderer.render(dt);
    this._raf = requestAnimationFrame(this._loop);
  }
}

/* ── Exports ─────────────────────────────────────────────── */
let _hote = null;

/** Ouvre une vue 3D dans l'hôte (créé au besoin, webcam comprise) ; renvoie son instance ou null. */
export function ouvrirDansHote(type) {
  if (!_hote) {
    const container = document.getElementById('holo-overlay');
    if (!container) return null;
    _hote = new HoteVues3D(container);
    _hote.start();
  }
  return _hote.ouvrir(type);
}

/** Ferme la vue ouverte et libère tout (rendu, webcam). */
export function fermerHote() {
  if (!_hote) return;
  _hote.destroy();
  _hote = null;
}

/** { type, vue } de la vue ouverte, ou null. */
export function vueOuverte() {
  return _hote && _hote.vue ? { type: _hote.type, vue: _hote.vue } : null;
}
