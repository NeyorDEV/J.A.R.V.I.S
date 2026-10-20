import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

/**
 * JARVIS GLOBE 3D — Terre réaliste Three.js, pilotée par le backend (window.jarvisGlobe)
 * et par les mains (mode AR, événement « jarvis-hand-move »).
 *
 * Repères : la Terre, les marqueurs et les itinéraires sont dans un même groupe
 * (globeGroup), que les gestes font tourner ; la caméra orbite toujours autour du centre
 * de la Terre (controls.target reste à l'origine), si bien que la Terre reste centrée et
 * que les vols, marqueurs et itinéraires suivent la rotation.
 */

let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let renderer: THREE.WebGLRenderer;
let controls: OrbitControls;
let globeGroup: THREE.Group;
let earth: THREE.Mesh;
let clouds: THREE.Mesh | null = null;
let atmosphere: THREE.Mesh;
let markersGroup: THREE.Group;
let routesGroup: THREE.Group;
let stars: THREE.Points;
let scanLine: THREE.Mesh;

let isInitialized = false;
let animationId: number | null = null;
const overlay = document.getElementById("globe-overlay") as HTMLDivElement;
const canvas = document.getElementById("globe-canvas") as HTMLCanvasElement;
const mapOverlay = document.getElementById("map-overlay") as HTMLDivElement | null;
const tLabel = document.getElementById("globe-target-label");
const cLabel = document.getElementById("globe-coords");
const orbCanvas = document.getElementById("orb-canvas") as HTMLCanvasElement;

// Vol en cours : direction (dans le repère de la Terre, suit sa rotation) et distance au
// centre. distanceOnly : zoom / recul sur place (la direction suit la caméra, ce qui laisse
// tourner la rotation automatique pendant le mouvement).
let flightTarget: { localDir: THREE.Vector3; distance: number; distanceOnly?: boolean } | null = null;

// Configuration
const EARTH_RADIUS = 100;
const DEFAULT_DISTANCE = 400;
const MIN_DISTANCE = 160;
const MAX_DISTANCE = 600;
const MAP_SWITCH_DISTANCE = 175; // en dessous : bascule sur la carte 2D détaillée
const TEXTURES = {
  day: "/assets/textures/earth-blue-marble.jpg",
  night: "/assets/textures/earth-night.jpg",
  bump: "/assets/textures/earth-topology.png",
  clouds: null as string | null, // Texture non disponible dans la version actuelle de three-globe
};

export function initJarvisGlobe() {
  if (isInitialized) return;

  // ── Scene Setup ─────────────────────────────────────────────────────────────
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);

  camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 2000);
  camera.position.z = DEFAULT_DISTANCE;

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);

  // ── Lights ──────────────────────────────────────────────────────────────────
  scene.add(new THREE.AmbientLight(0xffffff, 0.4));
  const sunLight = new THREE.DirectionalLight(0xffffff, 1.2);
  sunLight.position.set(5, 3, 5);
  scene.add(sunLight);

  // ── Stars (une seule fois : elles étaient créées deux fois, dont la moitié immobiles) ──
  createStarfield();

  // ── Terre, marqueurs et itinéraires dans un même groupe ──────────────────────
  globeGroup = new THREE.Group();
  scene.add(globeGroup);

  const loader = new THREE.TextureLoader();
  const earthGeo = new THREE.SphereGeometry(EARTH_RADIUS, 64, 64);
  const earthMat = new THREE.MeshStandardMaterial({
    map: loader.load(TEXTURES.day),
    bumpMap: loader.load(TEXTURES.bump),
    bumpScale: 2,
    metalness: 0.1,
    roughness: 0.8,
  });
  earth = new THREE.Mesh(earthGeo, earthMat);
  globeGroup.add(earth);

  // ── Clouds ──────────────────────────────────────────────────────────────────
  if (TEXTURES.clouds) {
    const cloudGeo = new THREE.SphereGeometry(EARTH_RADIUS + 2, 64, 64);
    const cloudMat = new THREE.MeshStandardMaterial({
      map: loader.load(TEXTURES.clouds),
      transparent: true,
      opacity: 0.4,
      depthWrite: false,
    });
    clouds = new THREE.Mesh(cloudGeo, cloudMat);
    globeGroup.add(clouds);
  }

  // ── Atmosphere Glow ────────────────────────────────────────────────────────
  const atmosphereGeo = new THREE.SphereGeometry(EARTH_RADIUS * 1.15, 64, 64);
  const atmosphereMat = new THREE.ShaderMaterial({
    vertexShader: `
      varying vec3 vNormal;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      varying vec3 vNormal;
      void main() {
        float intensity = pow(0.7 - dot(vNormal, vec3(0, 0, 1.0)), 3.0);
        gl_FragColor = vec4(0.0, 0.9, 1.0, 1.0) * intensity;
      }
    `,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    transparent: true,
  });
  atmosphere = new THREE.Mesh(atmosphereGeo, atmosphereMat);
  scene.add(atmosphere);

  // ── Holographic Scan Line ──────────────────────────────────────────────────
  const scanGeo = new THREE.RingGeometry(EARTH_RADIUS * 1.02, EARTH_RADIUS * 1.03, 64);
  const scanMat = new THREE.MeshBasicMaterial({
    color: 0x00e5ff,
    transparent: true,
    opacity: 0.3,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
  });
  scanLine = new THREE.Mesh(scanGeo, scanMat);
  scanLine.rotation.x = Math.PI / 2;
  scene.add(scanLine);

  // ── Interaction ─────────────────────────────────────────────────────────────
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.rotateSpeed = 0.5;
  controls.zoomSpeed = 0.5; // Slower zoom for more control
  controls.enablePan = false; // le pivot doit rester au centre de la Terre
  controls.minDistance = MIN_DISTANCE;
  controls.maxDistance = MAX_DISTANCE;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.5;

  markersGroup = new THREE.Group();
  globeGroup.add(markersGroup);
  routesGroup = new THREE.Group();
  globeGroup.add(routesGroup);

  window.addEventListener("resize", onResize);

  const closeBtn = document.getElementById("globe-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      hide();
    });
  }

  isInitialized = true;
  // La boucle de rendu ne tourne que globe affiché (voir show / hide) : avant, elle
  // tournait en permanence dès le démarrage de JARVIS, même globe fermé.
}

function createStarfield() {
  const vertices = [];
  for (let i = 0; i < 5000; i++) {
    vertices.push(THREE.MathUtils.randFloatSpread(2000), THREE.MathUtils.randFloatSpread(2000),
                  THREE.MathUtils.randFloatSpread(2000));
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  const mat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.7, transparent: true, opacity: 0.8 });
  stars = new THREE.Points(geo, mat);
  scene.add(stars);
}

// ── Carte 2D détaillée (Leaflet, définie dans index.html) ─────────────────────
let isTransitioning = false;

function mapVisible(): boolean {
  return !!mapOverlay && mapOverlay.style.display === "block";
}

function closeDetailedMap() {
  if (mapOverlay) {
    mapOverlay.style.opacity = "0";
    mapOverlay.style.display = "none";
  }
  isTransitioning = false;
}

function checkZoomLevel() {
  if (isTransitioning || flightTarget || mapVisible()) return;
  if (camera.position.length() < MAP_SWITCH_DISTANCE && overlay.style.opacity === "1") {
    switchToDetailedMap();
  }
}

function switchToDetailedMap() {
  isTransitioning = true;
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(new THREE.Vector2(0, 0), camera);
  const intersects = raycaster.intersectObject(earth);

  if (intersects.length > 0) {
    // Coordonnées dans le repère de la Terre (robuste à sa rotation par les gestes)
    const localPoint = earth.worldToLocal(intersects[0].point.clone());
    const { lat, lon } = vector3ToLatLon(localPoint);
    (window as any).showDetailedMap(lat, lon);
  } else {
    isTransitioning = false;
  }
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

// Retour de la carte 2D vers l'espace (bouton « RETOUR À L'ESPACE » / « FERMER »)
(window as any).resetGlobeTransition = () => {
  isTransitioning = false;
  if (!camera) return;
  // On garde le lieu face à la caméra, en reprenant de l'altitude, Terre centrée
  controls.target.set(0, 0, 0);
  camera.position.setLength(350);
  controls.update();
};

function animate() {
  animationId = requestAnimationFrame(animate);

  // Vol : rotation de la caméra autour du centre (interpolation sphérique, pour ne jamais
  // traverser la Terre) et ajustement de la distance
  if (flightTarget) {
    const curDir = camera.position.clone().normalize();
    const targetDir = flightTarget.distanceOnly ? curDir.clone()
      : flightTarget.localDir.clone().applyQuaternion(globeGroup.quaternion).normalize();
    const curDist = camera.position.length();
    const step = new THREE.Quaternion().setFromUnitVectors(curDir, targetDir);
    const partial = new THREE.Quaternion().slerp(step, 0.06);
    const newDir = curDir.applyQuaternion(partial);
    const newDist = THREE.MathUtils.lerp(curDist, flightTarget.distance, 0.06);
    camera.position.copy(newDir.multiplyScalar(newDist));
    if (camera.position.clone().normalize().angleTo(targetDir) < 0.002 && Math.abs(newDist - flightTarget.distance) < 0.5) {
      flightTarget = null;
    }
  }

  controls.update();

  if (clouds) clouds.rotation.y += 0.0002;
  if (stars) stars.rotation.y += 0.0001;

  if (scanLine) {
    const time = Date.now() * 0.001;
    scanLine.position.y = Math.sin(time * 0.5) * (EARTH_RADIUS * 0.8);
    (scanLine.material as THREE.MeshBasicMaterial).opacity = 0.2 + Math.abs(Math.sin(time)) * 0.2;
  }

  checkZoomLevel();
  renderer.render(scene, camera);
}

function startLoop() {
  if (animationId === null) animate();
}

function stopLoop() {
  if (animationId !== null) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }
}

// ── API for J.A.R.V.I.S ──────────────────────────────────────────────────────

/** Coordonnées dans le repère de la Terre (globeGroup). */
function latLonToVector3(lat: number, lon: number, radius: number) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  const x = -(radius * Math.sin(phi) * Math.cos(theta));
  const z = radius * Math.sin(phi) * Math.sin(theta);
  const y = radius * Math.cos(phi);
  return new THREE.Vector3(x, y, z);
}

function vector3ToLatLon(v: THREE.Vector3) {
  const r = v.length();
  const lat = Math.asin(v.y / r) * (180 / Math.PI);
  let lon = Math.atan2(v.z, -v.x) * (180 / Math.PI) - 180;
  if (lon < -180) lon += 360;
  if (lon > 180) lon -= 360;
  return { lat, lon };
}

function isNum(v: any): v is number {
  return typeof v === "number" && !isNaN(v);
}

function clearGroups() {
  while (markersGroup.children.length > 0) markersGroup.remove(markersGroup.children[0]);
  while (routesGroup.children.length > 0) routesGroup.remove(routesGroup.children[0]);
}

function addMarker(lat: number, lon: number, color: string = "#00e5ff") {
  const pos = latLonToVector3(lat, lon, EARTH_RADIUS);

  // Outer glow
  const ringGeo = new THREE.RingGeometry(2, 3, 32);
  const ringMat = new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide, transparent: true, opacity: 0.6 });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.position.copy(pos);
  ring.lookAt(new THREE.Vector3(0, 0, 0));
  markersGroup.add(ring);

  // Inner dot
  const dotGeo = new THREE.SphereGeometry(1, 16, 16);
  const dotMat = new THREE.MeshBasicMaterial({ color });
  const dot = new THREE.Mesh(dotGeo, dotMat);
  dot.position.copy(pos);
  markersGroup.add(dot);
}

/** Informe le backend (zoom vocal « rapproche-toi » seulement globe affiché). */
function notifyBackend(visible: boolean) {
  const ws = (window as any)._jarvisWs as WebSocket | undefined;
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "globe_state", visible }));
  }
}

let showTimer: ReturnType<typeof setTimeout> | null = null;
let hideTimer: ReturnType<typeof setTimeout> | null = null;

function show() {
  // Une fermeture en cours ne doit pas masquer le globe qu'on rouvre
  if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
  const wasHidden = overlay.style.display === "none" || overlay.style.opacity !== "1";
  overlay.style.display = "flex";
  if (orbCanvas) orbCanvas.classList.add("minimized");

  // Masquer les brackets HUD pour l'intégration
  document.querySelectorAll(".globe-bracket").forEach(b => (b as HTMLElement).style.opacity = "0");

  if (showTimer) clearTimeout(showTimer);
  showTimer = setTimeout(() => {
    overlay.style.transition = "opacity 0.8s ease";
    overlay.style.opacity = "1";
    showTimer = null;
  }, 10);
  controls.autoRotate = true;
  startLoop();
  if (wasHidden) notifyBackend(true);
}

function hide() {
  if (showTimer) { clearTimeout(showTimer); showTimer = null; }
  overlay.style.transition = "opacity 0.5s ease";
  overlay.style.opacity = "0";
  if (orbCanvas) orbCanvas.classList.remove("minimized");

  // Réafficher les brackets HUD
  document.querySelectorAll(".globe-bracket").forEach(b => (b as HTMLElement).style.opacity = "0.6");

  // La carte 2D se ferme avec le globe : sinon elle réapparaissait à la réouverture
  closeDetailedMap();
  flightTarget = null;

  if (hideTimer) clearTimeout(hideTimer);
  hideTimer = setTimeout(() => {
    overlay.style.display = "none";
    stopLoop();
    hideTimer = null;
  }, 520);
  clearGroups();
  notifyBackend(false);
}

/** Vole vers (lat, lon) ; distance = éloignement de la caméra au centre de la Terre. */
function flyTo(lat: number, lon: number, distance: number = 300) {
  controls.autoRotate = false;
  flightTarget = {
    localDir: latLonToVector3(lat, lon, 1).normalize(),
    distance: THREE.MathUtils.clamp(distance, MIN_DISTANCE, MAX_DISTANCE),
  };
}

/** Zoom / recul sur place : seule la distance au centre de la Terre change. */
function flyToDistance(distance: number) {
  flightTarget = {
    localDir: camera.position.clone().normalize(),
    distance: THREE.MathUtils.clamp(distance, MIN_DISTANCE, MAX_DISTANCE),
    distanceOnly: true,
  };
}

/** Arc de grand cercle entre deux points (repère de la Terre), légèrement surélevé. */
function greatCirclePoints(a: THREE.Vector3, b: THREE.Vector3, segments = 64) {
  const da = a.clone().normalize(), db = b.clone().normalize();
  const angle = da.angleTo(db);
  let full: THREE.Quaternion;
  if (Math.PI - angle < 1e-3) {
    // Points opposés : n'importe quel grand cercle convient, on passe par un axe perpendiculaire
    const axis = Math.abs(da.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
    full = new THREE.Quaternion().setFromAxisAngle(axis.cross(da).normalize(), Math.PI);
  } else {
    full = new THREE.Quaternion().setFromUnitVectors(da, db);
  }
  const lift = 0.04 + 0.25 * (angle / Math.PI);
  const points: THREE.Vector3[] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const q = new THREE.Quaternion().slerp(full, t);
    const r = EARTH_RADIUS * (1 + lift * Math.sin(Math.PI * t));
    points.push(da.clone().applyQuaternion(q).multiplyScalar(r));
  }
  return { points, angle };
}

function setCoords(lat: number, lon: number) {
  if (cLabel) cLabel.textContent = `LAT ${lat.toFixed(4)}°  LON ${lon.toFixed(4)}°`;
}

// Expose to window for the backend
(window as any).jarvisGlobe = function (data: any) {
  initJarvisGlobe();

  const action = data.globe_action || "";
  switch (action) {
    case "show_earth":
      show();
      closeDetailedMap();
      clearGroups();
      // Vue d'ensemble : Terre recentrée, droite, à distance par défaut
      globeGroup.rotation.set(0, 0, 0);
      controls.target.set(0, 0, 0);
      flyToDistance(DEFAULT_DISTANCE);
      controls.autoRotate = true;
      if (tLabel) tLabel.textContent = "GLOBE TERRESTRE";
      if (cLabel) cLabel.textContent = "";
      break;

    case "fly_to": {
      if (!isNum(data.lat) || !isNum(data.lon)) break; // jamais vers 0,0 par défaut
      const lt = data.lat, ln = data.lon;
      show();
      clearGroups();
      addMarker(lt, ln);
      if (mapVisible() && typeof (window as any).showDetailedMap === "function") {
        // Déjà sur la carte 2D : on y recentre le lieu
        (window as any).showDetailedMap(lt, ln);
      } else {
        flyTo(lt, ln, isNum(data.distance) ? data.distance : 300);
      }
      if (tLabel) tLabel.textContent = "⊕ " + (data.target || "").toUpperCase();
      setCoords(lt, ln);
      break;
    }

    case "route": {
      show();
      closeDetailedMap();
      clearGroups();
      const hasFrom = isNum(data.from_lat) && isNum(data.from_lon);
      const hasTo = isNum(data.to_lat) && isNum(data.to_lon);
      if (hasFrom) addMarker(data.from_lat, data.from_lon, "#00e5ff");
      if (hasTo) addMarker(data.to_lat, data.to_lon, "#ff6b35");

      if (hasFrom && hasTo) {
        const start = latLonToVector3(data.from_lat, data.from_lon, EARTH_RADIUS);
        const end = latLonToVector3(data.to_lat, data.to_lon, EARTH_RADIUS);
        const { points, angle } = greatCirclePoints(start, end);
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const material = new THREE.LineBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.6 });
        routesGroup.add(new THREE.Line(geometry, material));

        // Milieu du trajet sur le grand cercle (et non la moyenne des longitudes, fausse
        // de l'autre côté du Pacifique) ; plus le trajet est long, plus on prend de recul.
        const mid = vector3ToLatLon(points[Math.floor(points.length / 2)]);
        flyTo(mid.lat, mid.lon, 260 + 200 * (angle / Math.PI));
      }

      if (tLabel) tLabel.textContent = `ROUTE : ${(data.from_name || "?").toUpperCase()} → ${(data.to_name || "?").toUpperCase()}`;
      if (cLabel) cLabel.textContent = "";
      break;
    }

    case "my_location":
      show();
      closeDetailedMap();
      if (isNum(data.lat) && isNum(data.lon)) {
        clearGroups();
        addMarker(data.lat, data.lon, "#00ff88");
        flyTo(data.lat, data.lon, 230);
        if (tLabel) tLabel.textContent = (data.target ? String(data.target).toUpperCase() : "VOTRE POSITION");
        setCoords(data.lat, data.lon);
      } else if (navigator.geolocation) {
        if (tLabel) tLabel.textContent = "LOCALISATION...";
        if (cLabel) cLabel.textContent = "";
        navigator.geolocation.getCurrentPosition((pos) => {
          const mLat = pos.coords.latitude;
          const mLon = pos.coords.longitude;
          clearGroups();
          addMarker(mLat, mLon, "#00ff88");
          flyTo(mLat, mLon, 230);
          if (tLabel) tLabel.textContent = "VOTRE POSITION";
          setCoords(mLat, mLon);
        }, () => {
          if (tLabel) tLabel.textContent = "LOCALISATION REFUSÉE";
          if (cLabel) cLabel.textContent = "";
        });
      }
      break;

    case "zoom_in":
      if (overlay.style.display !== "none") flyToDistance(camera.position.length() * 0.7);
      break;

    case "zoom_out":
      if (overlay.style.display !== "none") {
        if (mapVisible()) (window as any).resetGlobeTransition();
        flyToDistance(camera.position.length() * 1.4);
      }
      break;

    case "hide":
      hide();
      break;
  }
};

// ── Hand Tracking Gestures Integration for 3D Globe ──────────────────────────
// Les gestes tournent le groupe Terre + marqueurs + itinéraires (et non plus le seul
// maillage de la Terre, qui laissait les marqueurs en place pendant qu'elle tournait).
let lastHandX = 0;
let lastHandY = 0;
let isHandDragging = false;
let lastTwoDist: number | null = null;
let lastAngle: number | null = null;
let lastMidX = 0;
let lastMidY = 0;

document.addEventListener("jarvis-hand-move", (e: any) => {
  // Tourner la Terre seulement si le globe est visible à l'écran
  const isGlobeVisible = overlay && overlay.style.display !== "none" && overlay.style.opacity === "1";
  if (!isInitialized || !globeGroup || !isGlobeVisible || mapVisible()) return;

  const { x, y, pinched, x1, y1, pinched1 } = e.detail;

  // ── GESTE DE ROTATION / SCALE / ROULIS À 2 MAINS ────────────────────
  if (x1 !== undefined && y1 !== undefined && pinched && pinched1) {
    if (controls) controls.autoRotate = false;
    flightTarget = null;
    isHandDragging = false; // Réinitialise l'état de glissement mono-main

    const midX = (x + x1) / 2;
    const midY = (y + y1) / 2;
    const dx_hands = x1 - x;
    const dy_hands = y1 - y;
    const dist = Math.sqrt(dx_hands * dx_hands + dy_hands * dy_hands);
    const angle = Math.atan2(dy_hands, dx_hands);

    if (lastTwoDist !== null && lastAngle !== null) {
      // 1. Rotation par glissement du point central (pan)
      globeGroup.rotation.y += (midX - lastMidX) * 0.007;
      globeGroup.rotation.x += (midY - lastMidY) * 0.007;

      // 2. Zoom par écartement / rapprochement des mains (distance au centre de la
      //    Terre, qui est aussi le pivot de la caméra)
      if (dist > 5) {
        const ratio = dist / lastTwoDist;
        const factor = 1 + (1 - ratio) * 1.8;
        camera.position.setLength(THREE.MathUtils.clamp(camera.position.length() * factor, MIN_DISTANCE, MAX_DISTANCE));
        controls.update();
      }

      // 3. Rotation angulaire (roulis) sur l'axe Z
      let dAngle = angle - lastAngle;
      while (dAngle > Math.PI) dAngle -= Math.PI * 2;
      while (dAngle < -Math.PI) dAngle += Math.PI * 2;
      globeGroup.rotation.z += dAngle;
    }

    lastTwoDist = dist;
    lastAngle = angle;
    lastMidX = midX;
    lastMidY = midY;
    return;
  }

  // Réinitialiser les états 2 mains si les deux ne sont pas pincés simultanément
  lastTwoDist = null;
  lastAngle = null;

  // ── GESTE DE DÉPLACEMENT MONO-MAIN ──────────────────────────────────
  if (pinched) {
    if (!isHandDragging) {
      isHandDragging = true;
      lastHandX = x;
      lastHandY = y;
      // Désactiver la rotation automatique pendant que l'utilisateur manipule le globe
      if (controls) controls.autoRotate = false;
      flightTarget = null;
    } else {
      globeGroup.rotation.y += (x - lastHandX) * 0.006;
      globeGroup.rotation.x += (y - lastHandY) * 0.006;
      lastHandX = x;
      lastHandY = y;
    }
  } else if (isHandDragging) {
    // Rétablir la rotation automatique douce après le relâchement
    isHandDragging = false;
    setTimeout(() => {
      if (!isHandDragging && controls && !flightTarget) {
        controls.autoRotate = true;
      }
    }, 5000);
  }
});
