/**
 * Voice Assistant ÔÇö Classical Multi-mode particle visualization.
 * Saved as a fallback backup.
 */

import * as THREE from "three";

export type OrbState = "idle" | "listening" | "thinking" | "speaking" | "searching";

export interface Orb {
  setState(s: OrbState): void;
  setVolume(v: number): void;
  setAnalyser(a: AnalyserNode | null): void;
  triggerDemo(): void;
  writeWord(w: string): void;
  setTheme(t: string): void;
  destroy(): void;
}

function generateTextPoints(word: string, targetCount: number): THREE.Vector3[] {
  const canvas2d = document.createElement("canvas");
  canvas2d.width = 1024;
  canvas2d.height = 512;
  const ctx = canvas2d.getContext("2d");
  if (!ctx) return [];
  
  // Taille dynamique pour s'adapter parfaitement à la longueur
  const fontSize = Math.max(85, Math.min(145, Math.floor(1024 / (word.length * 0.65))));
  
  // Utilisation d'Arial sans-serif gras pour un contour ultra-net sans empattement
  ctx.fillStyle = "#ffffff";
  ctx.font = `bold ${fontSize}px Arial, Helvetica, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(word.toUpperCase(), 512, 256);
  
  const imgData = ctx.getImageData(0, 0, 1024, 512);
  const data = imgData.data;
  
  // Collecter les pixels avec un seuil plus sélectif pour supprimer le flou des bords
  const candidates: {x: number, y: number}[] = [];
  for (let y = 0; y < 512; y += 2) {
    for (let x = 0; x < 1024; x += 2) {
      const idx = (y * 1024 + x) * 4;
      if (data[idx + 3] > 60) {
        candidates.push({ x, y });
      }
    }
  }
  
  const points: THREE.Vector3[] = [];
  if (candidates.length === 0) return [];
  
  // Tirage des points avec jitter très fin pour un contour parfaitement défini
  for (let i = 0; i < targetCount; i++) {
    const cand = candidates[Math.floor(Math.random() * candidates.length)];
    
    // Dispersion minime (netteté maximale)
    const jitterX = (Math.random() - 0.5) * 1.5;
    const jitterY = (Math.random() - 0.5) * 1.5;
    
    const px = (((cand.x + jitterX) - 512) / 1024) * 60;
    const py = -(((cand.y + jitterY) - 256) / 512) * 30;
    const pz = (Math.random() - 0.5) * 0.6; // Profondeur très faible pour éviter le flou de perspective
    points.push(new THREE.Vector3(px, py, pz));
  }
  return points;
}

export function createOrb(canvas: HTMLCanvasElement): Orb {
  let destroyed = false;
  const N = 2000;

  const mouse = new THREE.Vector2(-9999, -9999);
  const raycaster = new THREE.Raycaster();

  // Variables pour le morphing de texte 3D (écrit le mot)
  let textMorphActive = false;
  let textMorphStartTime = 0;
  const textMorphDuration = 7.0; // Durée par défaut de 7 secondes
  let textTargetPositions: THREE.Vector3[] = [];

  function onPointerMove(e: PointerEvent) {
    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
  }
  function onPointerLeave() {
    mouse.x = -9999;
    mouse.y = -9999;
  }
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerleave", onPointerLeave);

  const w = window.innerWidth;
  const h = window.innerHeight;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(w, h);
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(
    45,
    w / h,
    1,
    1000
  );
  camera.position.z = 75;

  // ÔöÇÔöÇ Particles ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
  const N_PINK = Math.floor(N * 0.03); // 60 particles
  const N_CYAN = N - N_PINK; // 1940 particles

  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(N * 3);
  const vel = new Float32Array(N * 3);
  const phase = new Float32Array(N);

  for (let i = 0; i < N; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = Math.pow(Math.random(), 0.5) * 25;
    pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    pos[i * 3 + 2] = r * Math.cos(phi);
    phase[i] = Math.random() * 1000;
  }

  // Split positions using TypedArray views sharing the same underlying ArrayBuffer
  const cyanPosView = new Float32Array(pos.buffer, N_PINK * 3 * 4, N_CYAN * 3);
  const pinkPosView = new Float32Array(pos.buffer, 0, N_PINK * 3);

  geo.setAttribute("position", new THREE.BufferAttribute(cyanPosView, 3));

  const pinkGeo = new THREE.BufferGeometry();
  pinkGeo.setAttribute("position", new THREE.BufferAttribute(pinkPosView, 3));

  const mat = new THREE.PointsMaterial({
    color: 0x4ca8e8,
    size: 0.4,
    transparent: true,
    opacity: 0.6,
    sizeAttenuation: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const pinkMat = new THREE.PointsMaterial({
    color: 0xff007f, // flashy neon pink
    size: 0.45, // slightly larger for visibility
    transparent: true,
    opacity: 0.85,
    sizeAttenuation: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const points = new THREE.Points(geo, mat);
  scene.add(points);

  const pinkPoints = new THREE.Points(pinkGeo, pinkMat);
  scene.add(pinkPoints);

  // ÔöÇÔöÇ Connection lines ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
  const MAX_LINES = 8000;
  const linePos = new Float32Array(MAX_LINES * 6);
  const lineGeo = new THREE.BufferGeometry();
  lineGeo.setAttribute("position", new THREE.BufferAttribute(linePos, 3));
  lineGeo.setDrawRange(0, 0);

  const lineMat = new THREE.LineBasicMaterial({
    color: 0x4ca8e8,
    transparent: true,
    opacity: 0.0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const lines = new THREE.LineSegments(lineGeo, lineMat);
  scene.add(lines);

  // ÔöÇÔöÇ Electrons ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
  const MAX_ELECTRONS = 200;
  const electronGeo = new THREE.BufferGeometry();
  const electronPos = new Float32Array(MAX_ELECTRONS * 3);
  electronGeo.setAttribute(
    "position",
    new THREE.BufferAttribute(electronPos, 3)
  );
  electronGeo.setDrawRange(0, 0);

  const electronMat = new THREE.PointsMaterial({
    color: 0xffffff,
    size: 0.8,
    transparent: true,
    opacity: 1.0,
    sizeAttenuation: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const electronPoints = new THREE.Points(electronGeo, electronMat);
  scene.add(electronPoints);

  // ── Rings Shader (mode Anneaux) ───────────────────────────────────────────
  const ringsGeo = new THREE.PlaneGeometry(2, 2);
  const ringsUniforms = {
    iTime:           { value: 0 },
    iResolution:     { value: new THREE.Vector3(window.innerWidth, window.innerHeight, window.innerWidth / window.innerHeight) },
    hue:             { value: 0 },
    hover:           { value: 0 },
    rot:             { value: 0 },
    hoverIntensity:  { value: 0.2 },
    backgroundColor: { value: new THREE.Vector3(0, 0, 0) },
    audioIntensity:  { value: 0 }
  };

  const ringsVert = `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = vec4(position.xyz, 1.0);
    }
  `;

  const ringsFrag = `
    precision highp float;
    uniform float iTime;
    uniform vec3 iResolution;
    uniform float hue;
    uniform float hover;
    uniform float rot;
    uniform float hoverIntensity;
    uniform vec3 backgroundColor;
    uniform float audioIntensity;
    varying vec2 vUv;

    vec3 rgb2yiq(vec3 c) {
      float y = dot(c, vec3(0.299, 0.587, 0.114));
      float i = dot(c, vec3(0.596, -0.274, -0.322));
      float q = dot(c, vec3(0.211, -0.523, 0.312));
      return vec3(y, i, q);
    }
    vec3 yiq2rgb(vec3 c) {
      float r = c.x + 0.956 * c.y + 0.621 * c.z;
      float g = c.x - 0.272 * c.y - 0.647 * c.z;
      float b = c.x - 1.106 * c.y + 1.703 * c.z;
      return vec3(r, g, b);
    }
    vec3 adjustHue(vec3 color, float hueDeg) {
      float hueRad = hueDeg * 3.14159265 / 180.0;
      vec3 yiq = rgb2yiq(color);
      float cosA = cos(hueRad);
      float sinA = sin(hueRad);
      float i = yiq.y * cosA - yiq.z * sinA;
      float q = yiq.y * sinA + yiq.z * cosA;
      yiq.y = i; yiq.z = q;
      return yiq2rgb(yiq);
    }
    vec3 hash33(vec3 p3) {
      p3 = fract(p3 * vec3(0.1031, 0.11369, 0.13787));
      p3 += dot(p3, p3.yxz + 19.19);
      return -1.0 + 2.0 * fract(vec3(p3.x+p3.y, p3.x+p3.z, p3.y+p3.z) * p3.zyx);
    }
    float snoise3(vec3 p) {
      const float K1 = 0.333333333;
      const float K2 = 0.166666667;
      vec3 i = floor(p + (p.x+p.y+p.z)*K1);
      vec3 d0 = p - (i - (i.x+i.y+i.z)*K2);
      vec3 e = step(vec3(0.0), d0 - d0.yzx);
      vec3 i1 = e*(1.0-e.zxy);
      vec3 i2 = 1.0-e.zxy*(1.0-e);
      vec3 d1 = d0-(i1-K2); vec3 d2=d0-(i2-K1); vec3 d3=d0-0.5;
      vec4 h = max(0.6-vec4(dot(d0,d0),dot(d1,d1),dot(d2,d2),dot(d3,d3)),0.0);
      vec4 n = h*h*h*h*vec4(dot(d0,hash33(i)),dot(d1,hash33(i+i1)),dot(d2,hash33(i+i2)),dot(d3,hash33(i+1.0)));
      return dot(vec4(31.316),n);
    }
    vec4 extractAlpha(vec3 colorIn) {
      float a = max(max(colorIn.r,colorIn.g),colorIn.b);
      return vec4(colorIn.rgb/(a+1e-5),a);
    }
    const vec3 baseColor1 = vec3(0.611765,0.262745,0.996078);
    const vec3 baseColor2 = vec3(0.298039,0.760784,0.913725);
    const vec3 baseColor3 = vec3(0.062745,0.078431,0.600000);
    const float noiseScale = 0.28;
    float light1(float intensity,float attenuation,float dist){return intensity/(1.0+dist*attenuation);}
    float light2(float intensity,float attenuation,float dist){return intensity/(1.0+dist*dist*attenuation);}
    vec4 draw(vec2 uv){
      vec3 color1=adjustHue(baseColor1,hue);
      vec3 color2=adjustHue(baseColor2,hue);
      vec3 color3=adjustHue(baseColor3,hue);
      float ang=atan(uv.y,uv.x); float len=length(uv);
      float invLen=len>0.0?1.0/len:0.0;
      float bgLuminance=dot(backgroundColor,vec3(0.299,0.587,0.114));
      float n0=snoise3(vec3(uv*noiseScale,iTime*1.3))*0.5+0.5;
      float innerRadius=0.55+audioIntensity*0.004;
      float wobbleAmp=0.008+audioIntensity*0.04;
      float minRadius=innerRadius+(1.0-innerRadius)*(0.5-wobbleAmp*0.5);
      float maxRadius=innerRadius+(1.0-innerRadius)*(0.5+wobbleAmp*0.5);
      float r0=mix(minRadius,maxRadius,n0);
      float d0=distance(uv,(r0*invLen)*uv);
      float v0=light1(1.0,10.0,d0);
      v0*=smoothstep(r0*1.05,r0,len);
      float innerFade=smoothstep(r0*0.8,r0*0.95,len);
      v0*=mix(innerFade,1.0,bgLuminance*0.7);
      float cl=cos(ang+iTime*2.0)*0.5+0.5;
      float a=iTime*-1.0;
      vec2 pos=vec2(cos(a),sin(a))*r0;
      float d=distance(uv,pos);
      float v1=light2(1.5,5.0,d); v1*=light1(1.0,50.0,d0);
      float v2=smoothstep(1.0,mix(innerRadius,1.0,n0*0.5),len);
      float v3=smoothstep(innerRadius,mix(innerRadius,1.0,0.5),len);
      vec3 colBase=mix(color1,color2,cl);
      float fadeAmount=mix(1.0,0.1,bgLuminance);
      vec3 darkCol=mix(color3,colBase,v0); darkCol=(darkCol+v1)*v2*v3; darkCol=clamp(darkCol,0.0,1.0);
      vec3 lightCol=(colBase+v1)*mix(1.0,v2*v3,fadeAmount); lightCol=mix(backgroundColor,lightCol,v0); lightCol=clamp(lightCol,0.0,1.0);
      return extractAlpha(mix(darkCol,lightCol,bgLuminance));
    }
    vec4 mainImage(vec2 fragCoord){
      vec2 center=iResolution.xy*0.5; float size=min(iResolution.x,iResolution.y);
      vec2 uv=(fragCoord-center)/size*3.6;
      float s=sin(rot); float c=cos(rot);
      uv=vec2(c*uv.x-s*uv.y,s*uv.x+c*uv.y);
      // No hover distortion on rings coordinates
      return draw(uv);
    }
    void main(){
      vec2 fragCoord=vUv*iResolution.xy;
      vec4 col=mainImage(fragCoord);
      gl_FragColor=vec4(col.rgb*col.a,col.a);
    }
  `;

  const ringsMat = new THREE.ShaderMaterial({
    vertexShader: ringsVert,
    fragmentShader: ringsFrag,
    uniforms: ringsUniforms,
    transparent: true,
    depthWrite: false,
    depthTest: false
  });
  const ringsMesh = new THREE.Mesh(ringsGeo, ringsMat);
  ringsMesh.frustumCulled = false;
  ringsMesh.visible = false;
  scene.add(ringsMesh);

  // ── Gold Shader (mode Or — Explosion Stellaire) ────────────────────────────
  const goldGeo = new THREE.PlaneGeometry(2, 2);
  const goldUniforms = {
    iTime:        { value: 0 },
    iResolution:  { value: new THREE.Vector3(window.innerWidth, window.innerHeight, window.innerWidth / window.innerHeight) },
    hover:        { value: 0 },
    rot:          { value: 0 },
    audioIntensity: { value: 0 }
  };

  const goldVert = `
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = vec4(position.xyz, 1.0); }
  `;

  const goldFrag = `
    precision highp float;
    uniform float iTime;
    uniform vec3  iResolution;
    uniform float hover;
    uniform float rot;
    uniform float audioIntensity;
    varying vec2 vUv;

    const float PI  = 3.14159265358979;
    const float TAU = 6.28318530718;

    vec2 rot2(vec2 p, float a) {
      float c = cos(a), s = sin(a);
      return vec2(c*p.x - s*p.y, s*p.x + c*p.y);
    }

    // ── SDF ellipse approximatif ultra-robuste (Pas de division par zéro) ──
    float sdEllipseApprox(vec2 p, float a, float b) {
      float k0 = length(p / vec2(a, b));
      float k1 = length(p / vec2(a * a, b * b));
      return k0 * (k0 - 1.0) / max(k1, 1e-6);
    }

    // ── Tube néon sur ellipse (cœur net + glow extérieur) ────────────────
    float neonRing(vec2 p, float a, float b, float phi,
                   float coreW, float glowW) {
      vec2 pr  = rot2(p, -phi);
      float d  = abs(sdEllipseApprox(pr, a, b));
      float core = exp(-d * d / (coreW * coreW));
      float glow = exp(-d * d / (glowW * glowW)) * 0.45;
      return core + glow;
    }

    // ── Position noeud sur ellipse ────────────────────────────────────────
    vec2 ellipsePoint(float t, float a, float b, float phi) {
      return rot2(vec2(a * cos(t), b * sin(t)), phi);
    }

    // ── Noeud lumineux (point + halo doux + croix lens flare) ────────────
    float lensNode(vec2 uv, vec2 pos, float brightness) {
      float d    = length(uv - pos);
      float core = exp(-d * d * 1800.0) * brightness;
      float halo = exp(-d * d * 180.0)  * brightness * 0.4;
      // Lens flare subtil : 4 branches fines
      vec2  dp   = uv - pos;
      float flare = exp(-abs(dp.x) * 60.0) * exp(-dp.y * dp.y * 400.0) * brightness * 0.25
                  + exp(-abs(dp.y) * 60.0) * exp(-dp.x * dp.x * 400.0) * brightness * 0.20;
      return core + halo + flare;
    }

    void main() {
      vec2 fc     = vUv * iResolution.xy;
      vec2 center = iResolution.xy * 0.5;
      float sz    = min(iResolution.x, iResolution.y);
      vec2 uv     = (fc - center) / sz * 2.0;

      float sr = sin(rot), cr = cos(rot);
      uv = vec2(cr*uv.x - sr*uv.y, sr*uv.x + cr*uv.y);


      float r     = length(uv);
      float audio = audioIntensity;
      float t     = iTime;
      float ar    = audio * 0.022;

      // Palette
      vec3 cCore  = vec3(1.00, 0.99, 0.90);
      vec3 cGold  = vec3(1.00, 0.82, 0.14);
      vec3 cAmber = vec3(0.85, 0.52, 0.05);
      vec3 cDeep  = vec3(0.40, 0.22, 0.02);

      vec3  col   = vec3(0.0);
      float alpha = 0.0;

      // Épaisseurs neon : coreW = demi-largeur du trait net, glowW = halo
      float cW = 0.0045;  // trait net ~4px
      float gW = 0.018;   // halo doux

      // ── Anneau équatorial (quasi-cercle, légère ondulation) ──────────────
      {
        float phi = t * 0.055;
        float tlt = 0.10 + 0.06 * sin(t * 0.16);
        float a = 0.70 + ar, b = (0.70 + ar) * (1.0 - tlt);
        float v = neonRing(uv, a, b, phi, cW, gW);
        col  += mix(cDeep, cAmber, smoothstep(0.0, 1.0, v)) * v * 0.95;
        alpha = max(alpha, min(1.0, v) * 0.80);
      }

      // ── Méridien 1 (incliné ~65°, rotation lente) ───────────────────────
      {
        float phi = t * -0.085 + 0.0;
        float tlt = 0.65 + 0.08 * sin(t * 0.12 + 1.1);
        float a = 0.66 + ar, b = (0.66 + ar) * (1.0 - tlt);
        float v = neonRing(uv, a, b, phi, cW, gW);
        col  += mix(cAmber, cGold, smoothstep(0.0, 1.0, v)) * v * 1.1;
        alpha = max(alpha, min(1.0, v) * 0.88);
      }

      // ── Méridien 2 (perpendiculaire, contra-rotation) ───────────────────
      {
        float phi = t * 0.095 + PI * 0.5;
        float tlt = 0.60 + 0.09 * sin(t * 0.14 + 2.4);
        float a = 0.63 + ar, b = (0.63 + ar) * (1.0 - tlt);
        float v = neonRing(uv, a, b, phi, cW, gW);
        col  += mix(cAmber, cGold, smoothstep(0.0, 1.0, v)) * v * 1.1;
        alpha = max(alpha, min(1.0, v) * 0.88);
      }

      // ── Écliptique (45°, plus brillant, intermédiaire) ──────────────────
      {
        float phi = t * -0.13 + PI * 0.25;
        float tlt = 0.42 + 0.07 * sin(t * 0.18 + 0.6);
        float a = 0.48 + ar * 0.8, b = (0.48 + ar * 0.8) * (1.0 - tlt);
        float v = neonRing(uv, a, b, phi, cW * 1.1, gW * 1.2);
        col  += mix(cGold, cCore, smoothstep(0.2, 1.2, v)) * v * 1.4;
        alpha = max(alpha, min(1.0, v) * 0.94);
      }

      // ── Anneau intérieur (petit, presque circulaire) ─────────────────────
      {
        float phi = t * 0.21;
        float tlt = 0.28 + 0.09 * sin(t * 0.21 + 3.0);
        float a = 0.26 + ar * 0.5, b = (0.26 + ar * 0.5) * (1.0 - tlt);
        float v = neonRing(uv, a, b, phi, cW * 1.2, gW);
        col  += mix(cGold, cCore, smoothstep(0.3, 1.3, v)) * v * 1.5;
        alpha = max(alpha, min(1.0, v) * 1.0);
      }

      // ── Noeuds avec lens flare ────────────────────────────────────────────

      // 2 noeuds sur écliptique (opposition)
      for (int i = 0; i < 2; i++) {
        float tlt = 0.42 + 0.07 * sin(t * 0.18 + 0.6);
        float phi = t * -0.13 + PI * 0.25;
        float a = 0.48 + ar * 0.8, b = (0.48 + ar * 0.8) * (1.0 - tlt);
        float sa  = t * 0.48 + float(i) * PI;
        vec2  pos = ellipsePoint(sa, a, b, phi);
        float nv  = lensNode(uv, pos, 1.0 + audio * 0.5);
        col  += cCore * nv;
        alpha = max(alpha, min(1.0, nv));
      }

      // 1 noeud sur méridien 1
      {
        float tlt = 0.65 + 0.08 * sin(t * 0.12 + 1.1);
        float phi = t * -0.085;
        float a = 0.66 + ar, b = (0.66 + ar) * (1.0 - tlt);
        float sa  = t * 0.36;
        vec2  pos = ellipsePoint(sa, a, b, phi);
        float nv  = lensNode(uv, pos, 0.85);
        col  += cGold * nv;
        alpha = max(alpha, min(1.0, nv) * 0.95);
      }

      // 1 noeud sur méridien 2
      {
        float tlt = 0.60 + 0.09 * sin(t * 0.14 + 2.4);
        float phi = t * 0.095 + PI * 0.5;
        float a = 0.63 + ar, b = (0.63 + ar) * (1.0 - tlt);
        float sa  = -t * 0.42 + PI * 0.7;
        vec2  pos = ellipsePoint(sa, a, b, phi);
        float nv  = lensNode(uv, pos, 0.85);
        col  += cGold * nv;
        alpha = max(alpha, min(1.0, nv) * 0.95);
      }

      // ── Noyau central (petit, net, pulse douce) ──────────────────────────
      float pulse = 1.0 + audio * 0.38 + sin(t * 5.0) * 0.04;
      float core  = exp(-r * r * 170.0 / pulse) * pulse * 1.3;
      float glow  = exp(-r * r * 20.0) * 0.14;
      col  += mix(cGold, cCore, smoothstep(0.0, 0.06, r)) * (core + glow);
      alpha = max(alpha, min(1.0, core + glow) * 0.98);

      // ── Fondu propre ──────────────────────────────────────────────────────
      alpha *= smoothstep(0.95, 0.22, r);

      gl_FragColor = vec4(col * alpha, alpha);
    }
  `;

  const goldMat = new THREE.ShaderMaterial({
    vertexShader: goldVert,
    fragmentShader: goldFrag,
    uniforms: goldUniforms,
    transparent: true,
    depthWrite: false,
    depthTest: false
  });
  const goldMesh = new THREE.Mesh(goldGeo, goldMat);
  goldMesh.frustumCulled = false;
  goldMesh.visible = false;
  scene.add(goldMesh);

  let goldTime = 0;
  let goldRot  = 0;
  // ──────────────────────────────────────────────────────────────────────────

  let ringsTime = 0;
  let currentRingsSpeed = 0.12;
  let currentRot = 0;
  // ─────────────────────────────────────────────────────────────────────────

  interface Electron {
    sx: number; sy: number; sz: number;
    ex: number; ey: number; ez: number;
    t: number;
    speed: number;
  }
  const activeElectrons: Electron[] = [];
  let electronSpawnRate = 0;
  let targetElectronRate = 0;
  let lastElectronSpawn = 0;

  let activeConnections: {
    x1: number; y1: number; z1: number;
    x2: number; y2: number; z2: number;
  }[] = [];

  // ÔöÇÔöÇ Base state vars ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
  let state: OrbState = "idle";
  let targetRadius = 25, currentRadius = 25;
  let targetSpeed = 0.3, currentSpeed = 0.3;
  let targetBright = 0.6, currentBright = 0.6;
  let targetSize = 0.4, currentSize = 0.4;
  let lineAmount = 0, targetLineAmount = 0;
  const lineDistance = 8;

  let spinX = 0, spinY = 0, spinZ = 0;
  let transitionEnergy = 0;
  let lastState: OrbState = "idle";
  let cloudZ = 0, cloudZVel = 0;

  // ÔöÇÔöÇ Speaking-specific vars ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
  let vortexStrength = 0, targetVortex = 0;
  let breathAmp = 0, targetBreathAmp = 0;
  let shockwave = 0;
  let prevBass = 0;
  let burstCooldown = 1.5;

  // Delta time tracking
  let prevT = 0;

  // ÔöÇÔöÇ Audio ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
  let analyser: AnalyserNode | null = null;
  let externalVolume = 0;
  let freqData = new Uint8Array(64);
  let bass = 0, mid = 0, treble = 0;

  const clock = new THREE.Clock();

  // ÔöÇÔöÇ Colour helpers ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
  const THEME_COLORS: Record<string, {
    primary: number;
    secondary: number;
    think: number;
    speak: number;
    bright: number;
  }> = {
    cyan: {
      primary: 0x4ca8e8,
      secondary: 0xff007f, // flashy neon pink
      think: 0x6ec4ff,
      speak: 0x5ab8f0,
      bright: 0xb8eeff,
    },
    emerald: {
      primary: 0x00e575, // emerald green
      secondary: 0xff5500, // flashy hot orange
      think: 0x55ffb0,
      speak: 0x22f28b,
      bright: 0xbeffd8,
    },
    amber: {
      primary: 0xffaa00, // amber orange
      secondary: 0x7f00ff, // flashy purple/indigo
      think: 0xffcc44,
      speak: 0xffb833,
      bright: 0xffeed5,
    },
    red: {
      primary: 0xff2a2a, // tactical red
      secondary: 0x00e5ff, // flashy neon cyan
      think: 0xff6666,
      speak: 0xff4444,
      bright: 0xffcccc,
    },
    gold: {
      primary: 0xffd700, // gold yellow
      secondary: 0xd000ff, // flashy fuchsia/purple
      think: 0xffe875,
      speak: 0xffde33,
      bright: 0xfff9be,
    },
    anneaux: {
      primary: 0x9b42fc,   // violet electrique
      secondary: 0x4cc2e9, // cyan complementaire
      think: 0x4cc2e9,
      speak: 0x9b42fc,
      bright: 0xe3edfc,
    }
  };

  let currentSecondaryHex = 0xff007f;
  let currentThemeName = "cyan";

  const COL_BASE = new THREE.Color(0x4ca8e8);
  const COL_THINK = new THREE.Color(0x6ec4ff);
  const COL_SPEAK = new THREE.Color(0x5ab8f0);
  const COL_BRIGHT = new THREE.Color(0xb8eeff);
  const COL_FLASH = new THREE.Color(0xffffff);
  const _tmpColor = new THREE.Color();
  const _rainbowCol = new THREE.Color();

  // ÔöÇÔöÇ Demo state ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
  let demoActive = false;
  let demoStartTime = 0;
  let demoBurstNextAt = 0;
  const DEMO_DURATION = 10.0;

  // ÔöÇÔöÇ Animate ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
  function animate() {
    if (destroyed) return;
    requestAnimationFrame(animate);

    const t = clock.getElapsedTime();
    const dt = Math.min(t - prevT, 0.05);
    prevT = t;

    if (demoActive && t - demoStartTime >= DEMO_DURATION) {
      demoActive = false;
    }

    if (textMorphActive && t - textMorphStartTime >= textMorphDuration) {
      textMorphActive = false;
      textTargetPositions = [];
    }

    const demoElapsed = demoActive ? (t - demoStartTime) : -1;
    const demoBigBang = demoActive && demoElapsed < 2.0;
    const demoVortex = demoActive && demoElapsed >= 2.0 && demoElapsed < 5.0;
    const demoPulse = demoActive && demoElapsed >= 5.0 && demoElapsed < 7.5;
    const demoCollapse = demoActive && demoElapsed >= 7.5;

    // ── Per-state targets ───────────────────────────────────────────────────────
    if (textMorphActive) {
      targetRadius = 0.0; targetSpeed = 0.08; targetBright = 1.0; targetSize = 0.5;
      targetLineAmount = 0.12; targetElectronRate = 0;
      targetVortex = 0; targetBreathAmp = 0;
    } else if (demoActive) {
      if (demoBigBang) {
        targetRadius = 22.5; targetSpeed = 1.0; targetBright = 1.0; targetSize = 0.75;
        targetLineAmount = 1.0; targetElectronRate = 0.04;
        targetVortex = 0.5; targetBreathAmp = 1.2;
      } else if (demoVortex) {
        targetRadius = 21.6; targetSpeed = 0.9; targetBright = 1.0; targetSize = 0.65;
        targetLineAmount = 1.0; targetElectronRate = 0.04;
        targetVortex = 4.5; targetBreathAmp = 1.0;
      } else if (demoPulse) {
        targetRadius = 19.8; targetSpeed = 0.7; targetBright = 0.95; targetSize = 0.55;
        targetLineAmount = 0.9; targetElectronRate = 0.03;
        targetVortex = 2.0; targetBreathAmp = 1.2;
      } else {
        targetRadius = 7.2; targetSpeed = 0.5; targetBright = 0.85; targetSize = 0.5;
        targetLineAmount = 0.7; targetElectronRate = 0.015;
        targetVortex = 1.0; targetBreathAmp = 0.5;
      }
    } else {
      switch (state) {
        case "idle":
          targetRadius = 13.5; targetSpeed = 0.2; targetBright = 0.55; targetSize = 0.35;
          targetLineAmount = 0.15; targetElectronRate = 0;
          targetVortex = 0; targetBreathAmp = 0;
          break;

        case "listening":
          targetRadius = 11.7; targetSpeed = 0.3; targetBright = 0.7; targetSize = 0.42;
          targetLineAmount = 0.4; targetElectronRate = 0;
          targetVortex = 0; targetBreathAmp = 0;
          break;

        case "thinking":
          targetRadius = 8.1; targetSpeed = 0.5; targetBright = 0.8; targetSize = 0.32;
          targetLineAmount = 1.0; targetElectronRate = 0.015;
          targetVortex = 0; targetBreathAmp = 0;
          break;

        case "speaking":
          targetRadius = 10.8; targetSpeed = 0.45; targetBright = 0.85; targetSize = 0.48;
          targetLineAmount = 0.8; targetElectronRate = 0.02;
          targetVortex = 0.3; targetBreathAmp = 1.2;
          break;
      }
    }

    const L = demoActive ? 0.06 : 0.035;
    currentRadius += (targetRadius - currentRadius) * L;
    currentSpeed += (targetSpeed - currentSpeed) * L;
    currentBright += (targetBright - currentBright) * L;
    currentSize += (targetSize - currentSize) * L;
    lineAmount += (targetLineAmount - lineAmount) * L;
    electronSpawnRate += (targetElectronRate - electronSpawnRate) * L;
    vortexStrength += (targetVortex - vortexStrength) * (demoActive ? 0.08 : 0.025);
    breathAmp += (targetBreathAmp - breathAmp) * (demoActive ? 0.08 : 0.025);

    if (textMorphActive) {
      // Interpolation rapide vers 0 pour figer le mot face à la caméra de manière parfaitement lisible
      spinX += (0 - spinX) * 0.12;
      spinY += (0 - spinY) * 0.12;
      spinZ += (0 - spinZ) * 0.12;
    } else {
      if (state !== lastState) { transitionEnergy = 1.0; lastState = state; }
      transitionEnergy *= 0.985;
      if (transitionEnergy > 0.05) {
        spinX += transitionEnergy * 0.012 * Math.sin(t * 1.7);
        spinY += transitionEnergy * 0.015;
        spinZ += transitionEnergy * 0.008 * Math.cos(t * 1.3);
      }
      if (demoActive) {
        spinY += 0.008 * (demoVortex ? 3.0 : 1.0);
        spinX += Math.sin(t * 0.7) * 0.003;
      }
    }

    bass = 0; mid = 0; treble = 0;
    if (analyser) {
      analyser.getByteFrequencyData(freqData);
      let bS = 0, mS = 0, tS = 0;
      for (let i = 0; i < 8;  i++) bS += freqData[i];
      for (let i = 8; i < 24; i++) mS += freqData[i];
      for (let i = 24;i < 48; i++) tS += freqData[i];
      bass   = bS / (8  * 255);
      mid    = mS / (16 * 255);
      treble = tS / (24 * 255);
    } else {
      bass = externalVolume * 0.8;
      mid = externalVolume * 0.4;
      treble = externalVolume * 0.2;
    }

    const bassJump = Math.max(0, bass - prevBass - 0.04) * 5.0;
    shockwave = Math.max(shockwave * 0.82, bassJump);
    prevBass = bass;

    if (demoActive) {
      if (t >= demoBurstNextAt) {
        const intensity = demoBigBang ? 0.45 : demoVortex ? 0.35 : demoPulse ? 0.4 : 0.25;
        shockwave = Math.max(shockwave, intensity);
        if (demoBigBang && demoElapsed < 0.05) {
          shockwave = 1.0;
        }
        const interval = demoBigBang ? 0.5 : demoVortex ? 0.7 : demoPulse ? 0.9 : 1.5;
        demoBurstNextAt = t + interval + Math.random() * 0.3;
      }
    } else {
      if (state === "speaking") {
        burstCooldown -= dt;
        if (burstCooldown <= 0) {
          shockwave = Math.max(shockwave, 0.28);
          burstCooldown = 1.3 + Math.random() * 0.5;
        }
      } else {
        burstCooldown = 1.5;
      }
    }

    let zTarget = Math.sin(t * 0.12) * 8;
    if (state === "thinking") zTarget = Math.sin(t * 0.3) * 15 + Math.sin(t * 0.9) * 6;
    else if (state === "speaking") zTarget = Math.sin(t * 0.18) * 7 - bass * 8;
    else if (demoActive) zTarget = Math.sin(t * 0.4) * 12;
    cloudZVel += (zTarget - cloudZ) * 0.008;
    cloudZVel *= 0.94;
    cloudZ += cloudZVel;

    if (textMorphActive) {
      points.rotation.set(0, 0, 0);
      points.position.z = 0;
      pinkPoints.rotation.set(0, 0, 0);
      pinkPoints.position.z = 0;
      lines.rotation.set(0, 0, 0);
      lines.position.z = 0;
    } else {
      points.rotation.x = spinX; points.rotation.y = spinY; points.rotation.z = spinZ;
      points.position.z = cloudZ;
      pinkPoints.rotation.x = spinX; pinkPoints.rotation.y = spinY; pinkPoints.rotation.z = spinZ;
      pinkPoints.position.z = cloudZ;
      lines.rotation.x = spinX; lines.rotation.y = spinY; lines.rotation.z = spinZ;
      lines.position.z = cloudZ;
    }

    const p = geo.getAttribute("position") as THREE.BufferAttribute;
    const pinkP = pinkGeo.getAttribute("position") as THREE.BufferAttribute;
    const a = pos; // Use full parent-scoped Float32Array containing all N particles
    const speaking = state === "speaking" && !demoActive;

    let localRayDir: THREE.Vector3 | null = null;
    let localRayOrig: THREE.Vector3 | null = null;
    if (mouse.x > -9000) {
      raycaster.setFromCamera(mouse, camera);
      const tempRay = raycaster.ray.clone();
      points.updateMatrixWorld();
      const invMat = points.matrixWorld.clone().invert();
      tempRay.applyMatrix4(invMat);
      localRayDir = tempRay.direction;
      localRayOrig = tempRay.origin;
    }

    for (let i = 0; i < N; i++) {
      const i3 = i * 3;
      const x = a[i3], y = a[i3 + 1], z = a[i3 + 2];
      const px = phase[i];

      // ÔöÇÔöÇ Cursor repulsion (Piste 2) ÔöÇÔöÇ
      if (localRayDir && localRayOrig) {
        const ox = x - localRayOrig.x;
        const oy = y - localRayOrig.y;
        const oz = z - localRayOrig.z;
        const projT = ox * localRayDir.x + oy * localRayDir.y + oz * localRayDir.z;
        const cx = localRayOrig.x + projT * localRayDir.x;
        const cy = localRayOrig.y + projT * localRayDir.y;
        const cz = localRayOrig.z + projT * localRayDir.z;
        const rx = x - cx;
        const ry = y - cy;
        const rz = z - cz;
        const rDistSq = rx * rx + ry * ry + rz * rz;
        const repRange = 4.0;
        if (rDistSq < repRange * repRange) {
          const rDist = Math.sqrt(rDistSq) || 0.01;
          const push = (1.0 - rDist / repRange) * 0.06 * (demoActive ? 2.5 : 1.0);
          vel[i3] += (rx / rDist) * push;
          vel[i3 + 1] += (ry / rDist) * push;
          vel[i3 + 2] += (rz / rDist) * push;
        }
      }

      if (!textMorphActive) {
        vel[i3] += Math.sin(t * 0.05 + px) * 0.001 * currentSpeed;
        vel[i3 + 1] += Math.cos(t * 0.06 + px * 1.3) * 0.001 * currentSpeed;
        vel[i3 + 2] += Math.sin(t * 0.055 + px * 0.7) * 0.001 * currentSpeed;
        vel[i3] += Math.sin(t * 0.02 + px * 2.1 + y * 0.1) * 0.0008 * currentSpeed;
        vel[i3 + 1] += Math.cos(t * 0.025 + px * 1.7 + z * 0.1) * 0.0008 * currentSpeed;
        vel[i3 + 2] += Math.sin(t * 0.022 + px * 0.9 + x * 0.1) * 0.0008 * currentSpeed;
      }

      const dist = Math.sqrt(x * x + y * y + z * z) || 0.01;

      const radiusTarget = (speaking || demoActive)
        ? currentRadius * (1.0 + Math.sin(t * 3.5 + px * 0.2) * 0.15 * breathAmp)
        : currentRadius;

      // Annuler l'attraction vers la sphère si on dessine le texte
      let pullBase = 0.0;
      if (!textMorphActive) {
        pullBase = demoCollapse
          ? Math.max(0, dist - radiusTarget) * 0.015 + 0.002
          : Math.max(0, dist - radiusTarget) * 0.002 + 0.0003;
      }
      vel[i3] -= (x / dist) * pullBase;
      vel[i3 + 1] -= (y / dist) * pullBase;
      vel[i3 + 2] -= (z / dist) * pullBase;

      // Force d'attraction vers le mot (sans frémissement pour être 100% stable et net)
      if (textMorphActive && textTargetPositions.length > 0) {
        const target = textTargetPositions[i % textTargetPositions.length];

        // Attraction rapide et directe vers les coordonnées vectorielles nettes
        vel[i3] += (target.x - x) * 0.14;
        vel[i3 + 1] += (target.y - y) * 0.14;
        vel[i3 + 2] += (target.z - z) * 0.14;

        // Amortissement fort pour figer immédiatement le mouvement
        vel[i3] *= 0.70;
        vel[i3 + 1] *= 0.70;
        vel[i3 + 2] *= 0.70;
      }

      if (bass > 0.05 && !textMorphActive) {
        const bf = (speaking || demoActive) ? bass * 0.025 : bass * 0.015;
        vel[i3] += (x / dist) * bf;
        vel[i3 + 1] += (y / dist) * bf;
        vel[i3 + 2] += (z / dist) * bf;
      }

      if (mid > 0.1 && !textMorphActive) {
        const pulse = Math.sin(t * 8 + px);
        const mf = (speaking || demoActive) ? mid * 0.018 : mid * 0.01;
        vel[i3] += (x / dist) * mf * pulse;
        vel[i3 + 1] += (y / dist) * mf * pulse;
      }

      if (speaking && !textMorphActive) {
        if (vortexStrength > 0.01) {
          const wave = Math.sin(dist * 0.8 - t * 12.0) * vortexStrength * 0.0035;
          vel[i3] += (x / dist) * wave;
          vel[i3 + 1] += (y / dist) * wave;
          vel[i3 + 2] += (z / dist) * wave;
        }

        if (shockwave > 0.005) {
          vel[i3] += (x / dist) * shockwave * 0.08;
          vel[i3 + 1] += (y / dist) * shockwave * 0.04;
          vel[i3 + 2] += (z / dist) * shockwave * 0.08;
        }

        if (breathAmp > 0.005) {
          const bp = Math.sin(t * 7.5 + px * 0.4) * breathAmp * 0.0015;
          vel[i3] += (x / dist) * bp;
          vel[i3 + 1] += (y / dist) * bp;
          vel[i3 + 2] += (z / dist) * bp;
        }

        if (treble > 0.08) {
          const jitter = (Math.random() - 0.5) * treble * 0.03;
          vel[i3] += jitter;
          vel[i3 + 1] += jitter * 0.5;
          vel[i3 + 2] += jitter;
        }
      }

      if (demoActive) {
        if (vortexStrength > 0.01) {
          const xzLen = Math.sqrt(x * x + z * z) || 0.01;
          vel[i3] += (-z / xzLen) * vortexStrength * 0.004;
          vel[i3 + 2] += (x / xzLen) * vortexStrength * 0.004;
          if (demoVortex) {
            const xyLen = Math.sqrt(x * x + y * y) || 0.01;
            vel[i3] += (-y / xyLen) * vortexStrength * 0.0015;
            vel[i3 + 1] += (x / xyLen) * vortexStrength * 0.0015;
          }
          vel[i3 + 1] += Math.sin(px * 2.3 + t) * vortexStrength * 0.001;
        }

        if (shockwave > 0.005) {
          vel[i3] += (x / dist) * shockwave * 0.18;
          vel[i3 + 1] += (y / dist) * shockwave * 0.18;
          vel[i3 + 2] += (z / dist) * shockwave * 0.18;
        }

        if (breathAmp > 0.005) {
          const bp = Math.sin(t * 9.0 + px * 0.5) * breathAmp * 0.0035;
          vel[i3] += (x / dist) * bp;
          vel[i3 + 1] += (y / dist) * bp;
          vel[i3 + 2] += (z / dist) * bp;
        }

        if (demoPulse) {
          const ringFreq = 5.0;
          const ring = Math.sin(dist * ringFreq - t * 12.0 + px) * 0.003;
          vel[i3] += (x / dist) * ring;
          vel[i3 + 1] += (y / dist) * ring;
          vel[i3 + 2] += (z / dist) * ring;
        }

        if (demoBigBang) {
          const chaos = (Math.random() - 0.5) * 0.04;
          vel[i3] += chaos;
          vel[i3 + 1] += chaos * 0.7;
          vel[i3 + 2] += chaos;
        }
      }

      const damp = demoActive ? 0.988 : 0.992;
      vel[i3] *= damp;
      vel[i3 + 1] *= damp;
      vel[i3 + 2] *= damp;
      a[i3] += vel[i3];
      a[i3 + 1] += vel[i3 + 1];
      a[i3 + 2] += vel[i3 + 2];
    }
    p.needsUpdate = true;
    pinkP.needsUpdate = true;

    if (lineAmount > 0.01) {
      const lp = lineGeo.getAttribute("position") as THREE.BufferAttribute;
      const la = lp.array as Float32Array;
      let lineCount = 0;

      // Idle (0.15) => clamped to 250 lines, Listening (0.4) => ~1280 lines, Speaking (0.8) => ~5120 lines, Thinking (1.0) => 8000 lines.
      const dynamicMaxLines = Math.max(250, Math.floor(MAX_LINES * lineAmount * lineAmount));

      // Piste 3: Ephemeral synaptic connections peaking with volume
      const maxDist = (lineDistance - 1) * (1 + bass * ((speaking || demoActive) ? 1.15 : 0.4));
      const maxDistSq = maxDist * maxDist;
      const step = Math.max(1, Math.floor(N / 600));

      for (let i = 0; i < N && lineCount < dynamicMaxLines; i += step) {
        const i3 = i * 3;
        const x1 = a[i3], y1 = a[i3 + 1], z1 = a[i3 + 2];
        for (let j = i + step; j < N && lineCount < dynamicMaxLines; j += step) {
          const j3 = j * 3;
          const dx = a[j3] - x1, dy = a[j3 + 1] - y1, dz = a[j3 + 2] - z1;
          if (dx * dx + dy * dy + dz * dz < maxDistSq) {
            const idx = lineCount * 6;
            la[idx] = x1; la[idx + 1] = y1; la[idx + 2] = z1;
            la[idx + 3] = a[j3]; la[idx + 4] = a[j3 + 1]; la[idx + 5] = a[j3 + 2];
            lineCount++;
          }
        }
      }
      lineGeo.setDrawRange(0, lineCount * 2);
      lp.needsUpdate = true;
      const peakBass = Math.max(0, bass - 0.1) * 2.2;
      lineMat.opacity = Math.max(0.06, lineAmount * 0.22) + peakBass * 0.35 + shockwave * 0.20;

      activeConnections = [];
      for (let c = 0; c < Math.min(lineCount, 500); c++) {
        const ci = c * 6;
        activeConnections.push({
          x1: la[ci], y1: la[ci + 1], z1: la[ci + 2],
          x2: la[ci + 3], y2: la[ci + 4], z2: la[ci + 5],
        });
      }
    } else {
      lineGeo.setDrawRange(0, 0);
      activeConnections = [];
    }

    const maxElec = demoActive ? 25 : speaking ? 10 : 3;
    const spawnGap = demoActive ? 0.06 : speaking ? 0.18 : 1.0;
    const eSpeed = demoActive
      ? 0.014 + Math.random() * 0.012
      : speaking
        ? 0.009 + Math.random() * 0.009
        : 0.003 + Math.random() * 0.003;

    if (activeConnections.length > 0 && electronSpawnRate > 0.005) {
      if (activeElectrons.length < maxElec && (t - lastElectronSpawn) > spawnGap) {
        const conn = activeConnections[Math.floor(Math.random() * activeConnections.length)];
        activeElectrons.push({
          sx: conn.x1, sy: conn.y1, sz: conn.z1,
          ex: conn.x2, ey: conn.y2, ez: conn.z2,
          t: 0,
          speed: eSpeed,
        });
        lastElectronSpawn = t;
      }
    }

    const ep = electronGeo.getAttribute("position") as THREE.BufferAttribute;
    const ea = ep.array as Float32Array;
    let aliveCount = 0;

    for (let e = activeElectrons.length - 1; e >= 0; e--) {
      const el = activeElectrons[e];
      el.t += el.speed;
      if (el.t >= 1) { activeElectrons.splice(e, 1); continue; }
      const ei = aliveCount * 3;
      ea[ei] = el.sx + (el.ex - el.sx) * el.t;
      ea[ei + 1] = el.sy + (el.ey - el.sy) * el.t;
      ea[ei + 2] = el.sz + (el.ez - el.sz) * el.t;
      aliveCount++;
    }

    electronGeo.setDrawRange(0, aliveCount);
    ep.needsUpdate = true;

    if (textMorphActive) {
      electronPoints.rotation.set(0, 0, 0);
      electronPoints.position.z = 0;
    } else {
      electronPoints.rotation.x = spinX; electronPoints.rotation.y = spinY; electronPoints.rotation.z = spinZ;
      electronPoints.position.z = cloudZ;
    }
    electronMat.size = demoActive ? 1.4 + shockwave * 1.2 : speaking ? 1.0 + shockwave * 0.8 : 0.8;
    electronMat.opacity = demoActive ? 1.0 : speaking ? 1.0 + shockwave * 0.5 : 1.0;

    if (textMorphActive) {
      mat.opacity = 0.72;
      mat.size = 0.35;
      mat.color.lerp(COL_BASE, 0.12);
      lineMat.opacity = 0.0; // Masque complètement les lignes parasites de l'orbe pendant le texte
      electronMat.opacity = 0.0;

      pinkMat.opacity = 0.82;
      pinkMat.size = 0.38;
      pinkMat.color.setHex(currentSecondaryHex);

    } else if (demoActive) {
      const hue = ((t - demoStartTime) * 0.2) % 1.0;
      _rainbowCol.setHSL(hue, 1.0, 0.6);

      if (shockwave > 0.4) {
        _rainbowCol.lerp(COL_FLASH, Math.min(1, (shockwave - 0.4) * 2.0));
      }

      mat.opacity = Math.min(1.4, currentBright + shockwave * 0.3);
      mat.size = currentSize + shockwave * 0.5;
      mat.color.lerp(_rainbowCol, 0.12);
      lineMat.color.lerp(_rainbowCol, 0.12);
      lineMat.opacity = lineAmount * 0.18 + shockwave * 0.25;
      electronMat.color.lerp(_rainbowCol, 0.15);

      pinkMat.opacity = Math.min(1.4, currentBright + shockwave * 0.3) * 1.25;
      pinkMat.size = (currentSize + shockwave * 0.5) * 1.12;
      pinkMat.color.setHex(currentSecondaryHex);

    } else if (speaking) {
      mat.opacity = Math.min(1.2, currentBright + bass * 0.18 + shockwave * 0.25);
      mat.size = currentSize + bass * 0.12 + shockwave * 0.20;

      const pulseIntensity = (bass * 0.7 + mid * 0.2 + shockwave * 0.5);
      const wave = 0.5 + 0.5 * Math.sin(t * 12.0 + bass * 8.0);
      _tmpColor.lerpColors(COL_SPEAK, COL_BRIGHT, Math.min(1, pulseIntensity * wave));

      if (shockwave > 0.18) {
        _tmpColor.lerp(COL_FLASH, (shockwave - 0.18) * 3.0);
      }
      mat.color.lerp(_tmpColor, 0.14);
      lineMat.color.lerp(_tmpColor, 0.14);
      electronMat.color.set(0xffffff);

      pinkMat.opacity = Math.min(1.2, currentBright + bass * 0.18 + shockwave * 0.25) * 1.25;
      pinkMat.size = (currentSize + bass * 0.12 + shockwave * 0.20) * 1.12;
      pinkMat.color.setHex(currentSecondaryHex);

    } else {
      mat.opacity = currentBright + bass * 0.08;
      mat.size = currentSize + bass * 0.05;

      if (state === "thinking") {
        mat.color.lerp(COL_THINK, 0.015);
        lineMat.color.lerp(COL_THINK, 0.015);
      } else {
        mat.color.lerp(COL_BASE, 0.015);
        lineMat.color.lerp(COL_BASE, 0.015);
      }
      electronMat.color.set(0xffffff);

      pinkMat.opacity = (currentBright + bass * 0.08) * 1.25;
      pinkMat.size = (currentSize + bass * 0.05) * 1.12;
      pinkMat.color.setHex(currentSecondaryHex);
    }

    if (textMorphActive) {
      camera.position.set(0, 0, 75);
      camera.lookAt(0, 0, 0);
    } else if (demoActive) {
      const demoT = demoElapsed;
      camera.position.x = Math.sin(demoT * 0.5) * 8;
      camera.position.y = Math.cos(demoT * 0.35) * 5;
      camera.position.z = 150 + Math.sin(demoT * 0.6) * 20;
      camera.lookAt(0, 0, cloudZ * 0.2);
    } else {
      camera.position.x = Math.sin(t * 0.02) * 3;
      camera.position.y = Math.cos(t * 0.03) * 2;
      camera.position.z = 75;
      camera.lookAt(0, 0, cloudZ * 0.2);
    }


    // ── Shader toggle (Anneaux / Gold) ──────────────────────────────────────
    const isAnneaux = currentThemeName === "anneaux";
    const isGold    = currentThemeName === "gold";
    const useShader = isAnneaux || isGold;
    points.visible         = !useShader;
    pinkPoints.visible     = !useShader;
    lines.visible          = !useShader;
    electronPoints.visible = !useShader;
    ringsMesh.visible      = isAnneaux;
    goldMesh.visible       = isGold;

    // ── Gold shader update ────────────────────────────────────────────────
    if (isGold) {
      goldTime += dt * (0.5 + bass * 4.0);
      goldUniforms.iTime.value = goldTime;
      goldUniforms.iResolution.value.set(
        window.innerWidth * window.devicePixelRatio,
        window.innerHeight * window.devicePixelRatio,
        window.innerWidth / window.innerHeight
      );
      goldUniforms.audioIntensity.value = bass;
      goldUniforms.hover.value = 0.0;
      goldRot += dt * 0.12; // Vitesse de rotation lente, continue et parfaitement stable
      goldUniforms.rot.value = goldRot;
    }

    if (isAnneaux) {
      const targetRingsSpeed = 0.12 + bass * 2.5;
      currentRingsSpeed += (targetRingsSpeed - currentRingsSpeed) * 0.22;
      ringsTime += dt * currentRingsSpeed;
      ringsUniforms.iTime.value = ringsTime;
      ringsUniforms.iResolution.value.set(
        window.innerWidth * window.devicePixelRatio,
        window.innerHeight * window.devicePixelRatio,
        window.innerWidth / window.innerHeight
      );
      ringsUniforms.audioIntensity.value = bass;
      ringsUniforms.hover.value = 0.0;
      currentRot += dt * 0.10; // Rotation stable continue sans à-coup
      ringsUniforms.rot.value = currentRot;
    }
    // ────────────────────────────────────────────────────────────────────────
    renderer.render(scene, camera);
  }

  function onResize() {
    const isMinimized = canvas.classList.contains("minimized");
    const width = isMinimized ? (canvas.clientWidth || 180) : window.innerWidth;
    const height = isMinimized ? (canvas.clientHeight || 180) : window.innerHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }

  window.addEventListener("resize", onResize);
  onResize();
  animate();

  return {
    setState(s: OrbState) {
      state = s;
    },
    setVolume(v: number) {
      externalVolume = v;
      if (v > 0.4) shockwave = Math.max(shockwave, v * 0.5);
    },
    setAnalyser(a: AnalyserNode | null) {
      analyser = a;
      if (a) freqData = new Uint8Array(a.frequencyBinCount);
    },
    triggerDemo() {
      demoActive = true;
      demoStartTime = clock.getElapsedTime();
      demoBurstNextAt = demoStartTime;
      shockwave = 1.0;
      transitionEnergy = 1.0;
    },
    writeWord(w: string) {
      textTargetPositions = generateTextPoints(w, N);
      if (textTargetPositions.length > 0) {
        textMorphActive = true;
        textMorphStartTime = clock.getElapsedTime();
      }
    },
    setTheme(tName: string) {
      const theme = THEME_COLORS[tName] || THEME_COLORS.cyan;
      COL_BASE.setHex(theme.primary);
      COL_THINK.setHex(theme.think);
      COL_SPEAK.setHex(theme.speak);
      COL_BRIGHT.setHex(theme.bright);
      
      // Update materials colors directly
      mat.color.setHex(theme.primary);
      pinkMat.color.setHex(theme.secondary);
      lineMat.color.setHex(theme.primary);
      
      // Save theme variables
      currentSecondaryHex = theme.secondary;
      currentThemeName = tName;
    },
    destroy() {
      destroyed = true;
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerleave", onPointerLeave);
      renderer.dispose();
    },
  };
}
