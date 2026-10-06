/* ============================================================
   domotic_map.ts — Carte Domotique 3D Immersive (Simulation)
   Modélise la vraie maison de Neyor sur 3 niveaux verticaux.
   Prend en charge l'interaction gestuelle AR & la navigation souris.
   ============================================================ */

import * as THREE from 'three';

// ── Types & Configuration ─────────────────────────────────────

interface DeviceNodeData {
  id: string;
  name: string;
  type: 'light' | 'plug' | 'sensor' | 'speaker';
  room: string;
  relPos: THREE.Vector3; // Position relative au centre de sa pièce
}

interface RoomData {
  id: string;
  name: string;
  level: number; // Y offset factor
  pos: THREE.Vector3;
  size: THREE.Vector3;
  color: number;
}

const ROOMS: RoomData[] = [
  // Level 1: Premier Étage (Y = 0)
  { id: 'salon', name: 'SÉJOUR', level: 0, pos: new THREE.Vector3(0, 0, -0.5), size: new THREE.Vector3(5.0, 0.8, 5.0), color: 0x00e5ff },
  { id: 'cuisine', name: 'CUISINE', level: 0, pos: new THREE.Vector3(-1.25, 0, -1.75), size: new THREE.Vector3(2.5, 0.8, 2.5), color: 0x00e5ff },
  { id: 'parents', name: 'CHAMBRE PARENTS', level: 0, pos: new THREE.Vector3(0.8, 0, -4.1), size: new THREE.Vector3(2.6, 0.8, 2.2), color: 0x00e5ff },
  { id: 'veranda', name: 'VÉRANDA', level: 0, pos: new THREE.Vector3(3.8, 0, 0), size: new THREE.Vector3(2.6, 0.8, 3.0), color: 0x00e5ff },

  // Level 0: RDC (Y = -2.5) - Positionné sous le 2ème étage à gauche
  { id: 'garage', name: 'GARAGE', level: -1, pos: new THREE.Vector3(-6.5, -2.5, 0.0), size: new THREE.Vector3(4.5, 0.8, 6.0), color: 0x00e5ff },

  // Level 2: Deuxième Étage (Y = 2.5) - Aligné à gauche de l'escalier montant (X = -4.5)
  { id: 'couloir', name: 'COULOIR', level: 1, pos: new THREE.Vector3(-5.8, 2.5, -0.4), size: new THREE.Vector3(1.5, 0.8, 3.2), color: 0x00e5ff },
  { id: 'chambre_1', name: 'MA CHAMBRE', level: 1, pos: new THREE.Vector3(-7.9, 2.5, -1.9), size: new THREE.Vector3(2.2, 0.8, 5.0), color: 0x00e5ff },
  { id: 'chambre_2', name: 'CHAMBRE 2', level: 1, pos: new THREE.Vector3(-7.0, 2.5, 2.4), size: new THREE.Vector3(3.8, 0.8, 2.4), color: 0x00e5ff },
  { id: 'sdb', name: 'SALLE DE BAIN', level: 1, pos: new THREE.Vector3(-5.4, 2.5, -3.2), size: new THREE.Vector3(2.2, 0.8, 2.4), color: 0x00e5ff },
  { id: 'toilettes', name: 'WC', level: 1, pos: new THREE.Vector3(-4.45, 2.5, -1.4), size: new THREE.Vector3(1.2, 0.8, 1.2), color: 0x00e5ff }
];

const DEVICES: DeviceNodeData[] = [
  // Salon
  { id: 'light.salon', name: 'Salon Principal', type: 'light', room: 'salon', relPos: new THREE.Vector3(0, 0.3, 0) },
  { id: 'light.plafond', name: 'Plafond Salon', type: 'light', room: 'salon', relPos: new THREE.Vector3(-1.2, 0.3, -1.0) },
  { id: 'light.canapes', name: 'Lumière Canapés', type: 'light', room: 'salon', relPos: new THREE.Vector3(1.2, 0.3, 1.0) },
  { id: 'light.lampadaire', name: 'Lampadaire', type: 'light', room: 'salon', relPos: new THREE.Vector3(-1.8, 0.2, 1.2) },
  { id: 'switch.prise_salon', name: 'Prise TV', type: 'plug', room: 'salon', relPos: new THREE.Vector3(1.8, -0.2, -1.2) },
  { id: 'temp.salon', name: 'Temp Salon', type: 'sensor', room: 'salon', relPos: new THREE.Vector3(0, -0.2, 1.2) },

  // Cuisine
  { id: 'light.lsc_smart_led_strip_rgbic_cctic_5m', name: 'LED Strip Cuisine', type: 'light', room: 'cuisine', relPos: new THREE.Vector3(0, 0.3, 0) },
  { id: 'light.cuisine_2', name: 'Cuisine Secondaire', type: 'light', room: 'cuisine', relPos: new THREE.Vector3(-0.6, 0.3, -0.6) },
  { id: 'switch.prise_cuisine', name: 'Cafetière', type: 'plug', room: 'cuisine', relPos: new THREE.Vector3(0.6, -0.2, 0.6) },
  { id: 'temp.cuisine', name: 'Temp Cuisine', type: 'sensor', room: 'cuisine', relPos: new THREE.Vector3(0.6, -0.2, -0.6) },

  // Chambre Parents
  { id: 'light.chambre_parentale', name: 'Chambre Parents', type: 'light', room: 'parents', relPos: new THREE.Vector3(0, 0.3, 0) },
  { id: 'light.plafond_2', name: 'Liseuse Parents', type: 'light', room: 'parents', relPos: new THREE.Vector3(-0.7, 0.3, 0.7) },
  { id: 'temp.parents', name: 'Temp Parents', type: 'sensor', room: 'parents', relPos: new THREE.Vector3(0.7, -0.2, -0.7) },

  // Véranda
  { id: 'light.veranda', name: 'Véranda', type: 'light', room: 'veranda', relPos: new THREE.Vector3(0, 0.3, 0) },
  { id: 'temp.veranda', name: 'Temp Véranda', type: 'sensor', room: 'veranda', relPos: new THREE.Vector3(0, -0.2, 0.8) },

  // Garage
  { id: 'light.garage', name: 'Garage', type: 'light', room: 'garage', relPos: new THREE.Vector3(0, 0.3, 0) },
  { id: 'temp.garage', name: 'Temp Garage', type: 'sensor', room: 'garage', relPos: new THREE.Vector3(0, -0.2, 1.5) },

  // Couloir
  { id: 'light.couloir', name: 'Couloir', type: 'light', room: 'couloir', relPos: new THREE.Vector3(0, 0.3, 0) },
  { id: 'temp.couloir', name: 'Temp Couloir', type: 'sensor', room: 'couloir', relPos: new THREE.Vector3(0, -0.2, 1.0) },

  // Ma chambre
  { id: 'light.chambre_1', name: 'Ma Chambre', type: 'light', room: 'chambre_1', relPos: new THREE.Vector3(0, 0.3, 0) },
  { id: 'temp.chambre_1', name: 'Temp Ma Chambre', type: 'sensor', room: 'chambre_1', relPos: new THREE.Vector3(0.5, -0.2, -0.5) },

  // Chambre 2
  { id: 'light.chambre_2', name: 'Chambre 2', type: 'light', room: 'chambre_2', relPos: new THREE.Vector3(0, 0.3, 0) },
  { id: 'temp.chambre_2', name: 'Temp Chambre 2', type: 'sensor', room: 'chambre_2', relPos: new THREE.Vector3(0.5, -0.2, -0.5) },

  // SdB & WC
  { id: 'light.sdb', name: 'SdB Étage', type: 'light', room: 'sdb', relPos: new THREE.Vector3(0, 0.3, 0) },
  { id: 'temp.sdb', name: 'Temp SdB Étage', type: 'sensor', room: 'sdb', relPos: new THREE.Vector3(0.5, -0.2, -0.5) },
  { id: 'light.toilettes', name: 'WC Étage', type: 'light', room: 'toilettes', relPos: new THREE.Vector3(0, 0.3, 0) },

  // HomePods (Haut-Parleurs)
  { id: 'media_player.homepod_salon', name: 'HomePod Séjour', type: 'speaker', room: 'salon', relPos: new THREE.Vector3(1.5, -0.1, -1.2) },
  { id: 'media_player.homepod_chambre', name: 'HomePod Ma Chambre', type: 'speaker', room: 'chambre_1', relPos: new THREE.Vector3(-0.6, -0.1, 0.8) }
];

const COLORS = {
  wireframe: 0x00e5ff,
  stairs:    0xffb454,
  glowOn:    0xffcc00,
  glowOff:   0x3a4b5c,
  plugOn:    0x22c55e,
  hover:     0xff8a1a,
  thermalComfort: {
    cold: 0x1e3a8a, // Bleu sombre (<18)
    comfort: 0x00e5ff, // Cyan (19-22)
    hot: 0xef4444 // Rouge (>23)
  }
};

// ── Textures helpers ──────────────────────────────────────────

function createRadialTexture(): THREE.Texture {
  const canvas = document.createElement('canvas');
  canvas.width = 64; canvas.height = 64;
  const ctx = canvas.getContext('2d')!;
  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
  grad.addColorStop(0.2, 'rgba(255, 255, 255, 0.85)');
  grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(canvas);
}

// ── Classes de rendu 3D de noeud domotique ──────────────────

class DomoticDeviceNode {
  data: DeviceNodeData;
  group: THREE.Group;
  mesh: THREE.Mesh;
  label: THREE.Sprite;
  glow: THREE.Sprite | null = null;
  baseScale: number;
  hovered = false;
  state = 'off';

  constructor(data: DeviceNodeData, worldPos: THREE.Vector3) {
    this.data = data;
    this.group = new THREE.Group();
    this.group.position.copy(worldPos);
    this.baseScale = 1.0;

    // 1. Géométrie selon type de device
    let geo: THREE.BufferGeometry;
    let matColor = COLORS.glowOff;

    if (data.type === 'light') {
      geo = new THREE.SphereGeometry(0.14, 12, 10);
      this.baseScale = 1.0;
    } else if (data.type === 'plug') {
      geo = new THREE.BoxGeometry(0.18, 0.18, 0.18);
      this.baseScale = 0.9;
    } else if (data.type === 'speaker') {
      geo = new THREE.CylinderGeometry(0.13, 0.13, 0.16, 16);
      this.baseScale = 1.1;
      matColor = 0xff00ff; // Neon magenta pour les haut-parleurs
    } else { // sensor
      geo = new THREE.CylinderGeometry(0.12, 0.12, 0.08, 12);
      this.baseScale = 0.85;
      matColor = 0x00e5ff;
    }

    const mat = new THREE.MeshBasicMaterial({
      color: matColor,
      transparent: true,
      opacity: 0.8,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.scale.setScalar(this.baseScale);
    this.group.add(this.mesh);

    // 2. Glow sprite pour les lumières et prises
    if (data.type !== 'sensor') {
      const glowMat = new THREE.SpriteMaterial({
        map: createRadialTexture(),
        color: matColor,
        transparent: true,
        opacity: 0.1,
        depthWrite: false,
        blending: THREE.AdditiveBlending
      });
      this.glow = new THREE.Sprite(glowMat);
      this.glow.scale.set(0.6, 0.6, 1);
      this.group.add(this.glow);
    }

    // 3. Label de nom flottant
    this.label = this._buildLabel();
    this.group.add(this.label);
  }

  private _buildLabel(valueText = ''): THREE.Sprite {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    
    let labelText = this.data.name.toUpperCase();
    if (valueText !== '') {
      labelText += `: ${valueText}`;
    } else if (this.data.type !== 'sensor') {
      if (this.data.type === 'speaker' && this.state !== 'paused' && this.state !== 'off') {
        labelText += `: ${this.state}`;
      } else {
        labelText += `: ${this.state.toUpperCase()}`;
      }
    }

    ctx.font = 'bold 16px Courier New';
    const textWidth = ctx.measureText(labelText).width;
    canvas.width = Math.max(256, Math.ceil(textWidth + 24));
    canvas.height = 40;

    // Rétablir la police après le changement de taille du canvas
    ctx.font = 'bold 16px Courier New';

    // Fond
    ctx.fillStyle = 'rgba(0, 10, 20, 0.7)';
    ctx.beginPath();
    ctx.roundRect(2, 2, canvas.width - 4, canvas.height - 4, 8);
    ctx.fill();

    // Texte
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(labelText, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMat = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthWrite: false
    });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(1.1 * (canvas.width / 256), 0.17, 1);
    sprite.position.y = 0.32;
    return sprite;
  }

  updateState(stateVal: string | number) {
    if (this.data.type === 'sensor') {
      // Pour les capteurs, stateVal est une température/humidité (ex: 21.4)
      const valStr = `${stateVal}°C`;
      this.group.remove(this.label);
      (this.label.material as THREE.SpriteMaterial).map?.dispose();
      (this.label.material as THREE.Material).dispose();
      this.label = this._buildLabel(valStr);
      this.group.add(this.label);
      return;
    }

    this.state = String(stateVal);
    
    // Mettre à jour la couleur et l'opacité
    let targetColor = COLORS.glowOff;
    const isActive = this.state === 'on' || this.state === 'playing';
    if (isActive) {
      if (this.data.type === 'light') targetColor = COLORS.glowOn;
      else if (this.data.type === 'plug') targetColor = COLORS.plugOn;
      else if (this.data.type === 'speaker') targetColor = 0xff00ff; // Magenta
    }

    (this.mesh.material as THREE.MeshBasicMaterial).color.setHex(targetColor);

    if (this.glow) {
      (this.glow.material as THREE.SpriteMaterial).color.setHex(targetColor);
      (this.glow.material as THREE.SpriteMaterial).opacity = isActive ? 0.8 : 0.15;
      this.glow.scale.setScalar(isActive ? 0.9 : 0.4);
    }

    // Recréer le label
    this.group.remove(this.label);
    (this.label.material as THREE.SpriteMaterial).map?.dispose();
    (this.label.material as THREE.Material).dispose();
    this.label = this._buildLabel();
    this.group.add(this.label);
  }

  update(dt: number, time: number) {
    // Rotation continue
    if (this.data.type === 'light') {
      this.mesh.rotation.y += dt * 0.5;
    } else if (this.data.type === 'plug') {
      this.mesh.rotation.y += dt * 0.4;
      this.mesh.rotation.x += dt * 0.2;
    } else if (this.data.type === 'speaker') {
      this.mesh.rotation.y += dt * 0.2;
    } else { // sensor
      this.mesh.position.y = Math.sin(time * 2.0 + this.data.relPos.x) * 0.02;
    }

    // Effet hover / pulsation
    let targetScale = this.baseScale;
    const isActive = this.state === 'on' || this.state === 'playing';
    if (this.hovered) {
      targetScale = this.baseScale * 1.35;
    } else if (isActive) {
      const amp = this.data.type === 'speaker' ? 0.15 : 0.05;
      const freq = this.data.type === 'speaker' ? 8.0 : 3.0;
      targetScale = this.baseScale * (1.0 + Math.sin(time * freq) * amp);
    }

    const currScale = this.mesh.scale.x;
    const newScale = currScale + (targetScale - currScale) * dt * 10;
    this.mesh.scale.setScalar(newScale);

    if (this.glow && isActive) {
      const freqGlow = this.data.type === 'speaker' ? 12.0 : 5.0;
      const ampGlow = this.data.type === 'speaker' ? 0.15 : 0.08;
      this.glow.scale.setScalar((0.85 + Math.sin(time * freqGlow) * ampGlow) * (this.hovered ? 1.3 : 1.0));
    }
  }

  dispose() {
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    if (this.glow) {
      (this.glow.material as THREE.SpriteMaterial).map?.dispose();
      (this.glow.material as THREE.SpriteMaterial).dispose();
    }
    (this.label.material as THREE.SpriteMaterial).map?.dispose();
    (this.label.material as THREE.Material).dispose();
  }
}

// ── Classe Principale — DomoticMap ────────────────────────────

export class DomoticMap {
  private scene: THREE.Scene;
  private camera: THREE.Camera;
  private ws: WebSocket;

  group: THREE.Group;
  private roomGroups: Map<string, THREE.Group> = new Map();
  private roomFloors: Map<string, THREE.Mesh> = new Map();
  private roomWalls: Map<string, THREE.LineSegments> = new Map();
  private deviceNodes: DomoticDeviceNode[] = [];
  
  private active = false;
  private raycaster = new THREE.Raycaster();
  private mouse = new THREE.Vector2();

  // Variables de glissement/rotation souris
  private isLeftDown = false;
  private isRightDown = false;
  private lastMouseX = 0;
  private lastMouseY = 0;

  // Ondes holographiques de clics
  private activeRipples: { ring: THREE.Mesh; age: number; life: number; }[] = [];

  // Ondes acoustiques de routage de la musique
  private activeWaves: { group: THREE.Group; rings: THREE.Mesh[]; progress: number; speed: number; start: THREE.Vector3; end: THREE.Vector3; }[] = [];

  // Bannière HUD Simulation
  private hudBanner: HTMLDivElement | null = null;

  // Suivi gestuel (MediaPipe Gestures v2)
  private lastTwoPos0: THREE.Vector3 | null = null;
  private lastTwoPos1: THREE.Vector3 | null = null;
  private lastTwoDist: number | null = null;
  private wasHandActive = false;

  constructor(scene: THREE.Scene, camera: THREE.Camera, ws: WebSocket) {
    this.scene = scene;
    this.camera = camera;
    this.ws = ws;
    this.group = new THREE.Group();
    
    // Légère rotation de base pour un affichage 3D isométrique magnifique dès le début
    this.group.rotation.set(0.35, -0.45, 0);
    this.scene.add(this.group);

    // Event listeners
    window.addEventListener('mousedown', this._onMouseDown);
    window.addEventListener('mousemove', this._onMouseMove);
    window.addEventListener('mouseup', this._onMouseUp);
    window.addEventListener('contextmenu', this._onContextMenu);
    window.addEventListener('wheel', this._onWheel, { passive: true });
    window.addEventListener('click', this._onMouseClick);
  }

  activate() {
    if (this.active) return;
    this.active = true;

    this._buildRooms();
    this._buildStaircases();
    this._buildDevices();
    this._createHudBanner();

    // Demander l'état initial des entités domotiques simulées au backend
    this._send('domotic_list');
    console.log('[DOMOTIC MAP] Module 3D activé.');
  }

  deactivate() {
    if (!this.active) return;
    this.active = false;

    this._clearScene();
    this._removeHudBanner();

    window.removeEventListener('mousedown', this._onMouseDown);
    window.removeEventListener('mousemove', this._onMouseMove);
    window.removeEventListener('mouseup', this._onMouseUp);
    window.removeEventListener('contextmenu', this._onContextMenu);
    window.removeEventListener('wheel', this._onWheel);
    window.removeEventListener('click', this._onMouseClick);
    console.log('[DOMOTIC MAP] Module 3D désactivé.');
  }

  // ── Modélisation 3D ────────────────────────────────────────

  private _buildRooms() {
    ROOMS.forEach((r) => {
      const roomGroup = new THREE.Group();
      roomGroup.position.copy(r.pos);

      // A. Structure fil de fer (murs)
      const geo = new THREE.BoxGeometry(r.size.x, r.size.y, r.size.z);
      const edges = new THREE.EdgesGeometry(geo);
      const lineMat = new THREE.LineBasicMaterial({
        color: COLORS.wireframe,
        transparent: true,
        opacity: 0.45,
        blending: THREE.AdditiveBlending
      });
      const wireframe = new THREE.LineSegments(edges, lineMat);
      roomGroup.add(wireframe);
      this.roomWalls.set(r.id, wireframe);

      // B. Sol semi-transparent (uniquement si ce n'est pas la cuisine)
      if (r.id !== 'cuisine') {
        const floorGeo = new THREE.PlaneGeometry(r.size.x, r.size.z);
        const floorMat = new THREE.MeshBasicMaterial({
          color: COLORS.wireframe,
          transparent: true,
          opacity: 0.05,
          side: THREE.DoubleSide,
          depthWrite: false,
          blending: THREE.AdditiveBlending
        });
        const floor = new THREE.Mesh(floorGeo, floorMat);
        floor.rotation.x = Math.PI / 2;
        floor.position.y = -r.size.y / 2 + 0.01;
        roomGroup.add(floor);
        this.roomFloors.set(r.id, floor);

        // C. Sprite étiquette de pièce
        const label = this._buildRoomLabel(r.name);
        label.position.y = r.size.y / 2 + 0.65;
        roomGroup.add(label);
      }

      this.group.add(roomGroup);
      this.roomGroups.set(r.id, roomGroup);
     });
  }

  private _buildRoomLabel(name: string): THREE.Sprite {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    canvas.width = 256; canvas.height = 48;
    
    // Background dégradé sci-fi subtil
    const grad = ctx.createLinearGradient(0, 0, canvas.width, 0);
    grad.addColorStop(0, 'rgba(0, 229, 255, 0.0)');
    grad.addColorStop(0.3, 'rgba(0, 229, 255, 0.12)');
    grad.addColorStop(0.7, 'rgba(0, 229, 255, 0.12)');
    grad.addColorStop(1, 'rgba(0, 229, 255, 0.0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Ligne de bordure inférieure cyan fluorescente
    ctx.strokeStyle = 'rgba(0, 229, 255, 0.6)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(30, canvas.height - 2);
    ctx.lineTo(canvas.width - 30, canvas.height - 2);
    ctx.stroke();

    // Texte avec halo lumineux
    ctx.font = '900 15px "Courier New", monospace';
    ctx.fillStyle = '#00e5ff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = '#00e5ff';
    ctx.shadowBlur = 8;
    ctx.fillText(name, canvas.width / 2, canvas.height / 2 - 2);

    const tex = new THREE.CanvasTexture(canvas);
    const spriteMat = new THREE.SpriteMaterial({
      map: tex,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
    const sprite = new THREE.Sprite(spriteMat);
    // Calcul correct de l'aspect ratio (256/48 = 5.33)
    const h = 0.32;
    sprite.scale.set(h * (canvas.width / canvas.height), h, 1);
    return sprite;
  }

  private _buildStaircases() {
    // 1. Escalier de gauche descendant : Salon Y=0 -> Garage Y=-2.5 (Placé à Z = -0.2, juste à côté de la cuisine)
    this._createStairsLine(new THREE.Vector3(-2.2, 0, -0.2), new THREE.Vector3(-4.5, -2.5, -0.2));

    // 2. Escalier de gauche montant : Salon Y=0 -> Couloir Y=2.5 (Placé à Z = 0.2, juste à côté de l'autre escalier)
    this._createStairsLine(new THREE.Vector3(-2.2, 0, 0.2), new THREE.Vector3(-4.5, 2.5, 0.2));
  }

  private _createStairsLine(start: THREE.Vector3, end: THREE.Vector3) {
    const points: THREE.Vector3[] = [];
    const steps = 14;
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      // Interpolation par paliers (marches d'escalier)
      const x = start.x + (end.x - start.x) * t;
      const z = start.z + (end.z - start.z) * t;
      // Escalier par palier de hauteur
      const prevT = Math.max(0, (i - 1) / steps);
      const y = start.y + (end.y - start.y) * prevT;
      points.push(new THREE.Vector3(x, y, z));
      points.push(new THREE.Vector3(x, start.y + (end.y - start.y) * t, z));
    }

    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const lineMat = new THREE.LineBasicMaterial({
      color: COLORS.stairs,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending
    });
    const line = new THREE.Line(geo, lineMat);
    this.group.add(line);
  }

  private _buildDevices() {
    DEVICES.forEach((d) => {
      const roomGroup = this.roomGroups.get(d.room);
      if (!roomGroup) return;

      // Calculer la position absolue dans le groupe parent de la maison
      const worldPos = d.relPos.clone().add(roomGroup.position);
      const node = new DomoticDeviceNode(d, worldPos);
      this.deviceNodes.push(node);
      this.group.add(node.group);
    });
  }

  // ── Rendu Thermique Dynamique ───────────────────────────────

  private _updateThermalComfort(roomId: string, temp: number) {
    const floor = this.roomFloors.get(roomId);
    const wireframe = this.roomWalls.get(roomId);
    if (!floor || !wireframe) return;

    let targetColor = COLORS.thermalComfort.comfort;
    let opacity = 0.05;

    if (temp < 18.5) {
      targetColor = COLORS.thermalComfort.cold;
      opacity = 0.15; // Un peu plus opaque pour mieux voir le bleu profond
    } else if (temp > 23.0) {
      targetColor = COLORS.thermalComfort.hot;
      opacity = 0.18; // Plus visible pour la sensation de chaleur
    }

    // Lerp fluide pour éviter les transitions saccadées
    const colFloor = (floor.material as THREE.MeshBasicMaterial).color;
    colFloor.lerp(new THREE.Color(targetColor), 0.05);
    (floor.material as THREE.MeshBasicMaterial).opacity = THREE.MathUtils.lerp((floor.material as THREE.MeshBasicMaterial).opacity, opacity, 0.05);

    const colWall = (wireframe.material as THREE.LineBasicMaterial).color;
    colWall.lerp(new THREE.Color(targetColor), 0.05);
  }

  // ── Ondes de clics ──────────────────────────────────────────

  triggerRipple(pos: THREE.Vector3) {
    const g = new THREE.RingGeometry(0.01, 0.12, 32);
    const m = new THREE.MeshBasicMaterial({
      color: COLORS.hover,
      transparent: true,
      opacity: 1,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
    const ring = new THREE.Mesh(g, m);
    // Face à la caméra
    ring.position.copy(pos);
    ring.lookAt(this.camera.position);

    this.group.add(ring);
    this.activeRipples.push({ ring, age: 0, life: 0.6 });
  }

  animateAudioRouting(sourceRoom: string, destRoom: string) {
    const roomMap: Record<string, string> = {
      'salon': 'salon',
      'sejour': 'salon',
      'séjour': 'salon',
      'chambre': 'chambre_1',
      'ma chambre': 'chambre_1',
      'chambre 2': 'chambre_2',
      'salle de jeux': 'chambre_2',
      'jeux': 'chambre_2',
      'chambre parentale': 'parents',
      'parents': 'parents',
      'cuisine': 'cuisine',
      'veranda': 'veranda',
      'garage': 'garage',
      'couloir': 'couloir',
      'sdb': 'sdb',
      'salle de bain': 'sdb'
    };

    const srcId = roomMap[sourceRoom.toLowerCase()] || sourceRoom;
    const destId = roomMap[destRoom.toLowerCase()] || destRoom;

    let startPos = new THREE.Vector3();
    let endPos = new THREE.Vector3();

    const srcGroup = this.roomGroups.get(srcId);
    const destGroup = this.roomGroups.get(destId);

    if (srcGroup) startPos.copy(srcGroup.position);
    if (destGroup) endPos.copy(destGroup.position);

    startPos.y += 0.3;
    endPos.y += 0.3;

    const srcNode = this.deviceNodes.find(n => n.data.room === srcId && n.data.type === 'speaker');
    const destNode = this.deviceNodes.find(n => n.data.room === destId && n.data.type === 'speaker');

    if (srcNode) startPos.copy(srcNode.group.position);
    if (destNode) endPos.copy(destNode.group.position);

    const waveGroup = new THREE.Group();
    const rings: THREE.Mesh[] = [];
    const colors = [0x8a2be2, 0xff00ff, 0x00ffff];

    for (let i = 0; i < 3; i++) {
      const g = new THREE.RingGeometry(0.05, 0.15 + i * 0.1, 32);
      const m = new THREE.MeshBasicMaterial({
        color: colors[i],
        transparent: true,
        opacity: 0.8,
        side: THREE.DoubleSide,
        depthWrite: false,
        blending: THREE.AdditiveBlending
      });
      const ring = new THREE.Mesh(g, m);
      waveGroup.add(ring);
      rings.push(ring);
    }

    waveGroup.position.copy(startPos);
    this.group.add(waveGroup);

    this.activeWaves.push({
      group: waveGroup,
      rings,
      progress: 0,
      speed: 0.8,
      start: startPos.clone(),
      end: endPos.clone()
    });
  }

  // ── Récéption et communication ──────────────────────────────

  handleServerResponse(data: any) {
    if (!this.active) return;
    
    if (data.action === 'domotic_map_update') {
      const states = data.states || {};
      this.deviceNodes.forEach((node) => {
        if (node.data.id in states) {
          const val = states[node.data.id].state;
          node.updateState(val);
        }
      });

      // Mettre à jour les couleurs de confort thermique des pièces
      ROOMS.forEach((r) => {
        const tempKey = `temp.${r.id}`;
        if (tempKey in states) {
          const tempVal = parseFloat(states[tempKey].state) || 20.0;
          this._updateThermalComfort(r.id, tempVal);
        }
      });
    } else if (data.action === 'domotic_audio_route_animation') {
      const sourceRoom = data.source || 'salon';
      const destRoom = data.destination || 'chambre';
      this.animateAudioRouting(sourceRoom, destRoom);
    }
  }

  private _send(action: string, data: Record<string, any> = {}) {
    if (this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({
      type: 'spatial_action',
      action,
      ...data
    }));
  }

  // ── Raycasting & Mouse controls ─────────────────────────────

  private _onMouseDown = (e: MouseEvent) => {
    if (!this.active) return;
    const canvas = document.getElementById('holo-three-canvas');
    if (!canvas || e.target !== canvas) return;

    this.lastMouseX = e.clientX;
    this.lastMouseY = e.clientY;

    if (e.button === 0) { // Clic gauche pour translater/paner
      this.isLeftDown = true;
    } else if (e.button === 2) { // Clic droit pour orbiter/tourner
      this.isRightDown = true;
    }
  };

  private _onMouseMove = (e: MouseEvent) => {
    if (!this.active) return;

    const dx = e.clientX - this.lastMouseX;
    const dy = e.clientY - this.lastMouseY;

    this.lastMouseX = e.clientX;
    this.lastMouseY = e.clientY;

    if (this.isLeftDown) {
      // Translation/Pan de la maison
      this.group.position.x += dx * 0.006;
      this.group.position.y -= dy * 0.006;
    } else if (this.isRightDown) {
      // Rotation isométrique
      this.group.rotation.y += dx * 0.005;
      this.group.rotation.x += dy * 0.005;
      this.group.rotation.x = Math.max(-0.2, Math.min(Math.PI / 2.2, this.group.rotation.x));
    }

    // Raycast hover detection
    const canvas = this.camera.viewport ? null : document.getElementById('holo-three-canvas');
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    
    // Collecter les meshs des noeuds
    const meshes = this.deviceNodes.map(n => n.mesh);
    const intersects = this.raycaster.intersectObjects(meshes);

    this.deviceNodes.forEach(n => n.hovered = false);

    if (intersects.length > 0) {
      const best = intersects[0].object as THREE.Mesh;
      const node = this.deviceNodes.find(n => n.mesh === best);
      if (node) {
        node.hovered = true;
      }
    }
  };

  private _onMouseUp = (e: MouseEvent) => {
    if (e.button === 0) this.isLeftDown = false;
    else if (e.button === 2) this.isRightDown = false;
  };

  private _onContextMenu = (e: MouseEvent) => {
    if (!this.active) return;
    const canvas = document.getElementById('holo-three-canvas');
    if (canvas && e.target === canvas) {
      e.preventDefault();
    }
  };

  private _onWheel = (e: WheelEvent) => {
    if (!this.active) return;
    // Zoom/Dezoom de la maison
    const factor = e.deltaY > 0 ? 0.93 : 1.07;
    this.group.scale.multiplyScalar(factor);
    this.group.scale.setScalar(Math.max(0.3, Math.min(3.0, this.group.scale.x)));
  };

  private _onMouseClick = (e: MouseEvent) => {
    if (!this.active || e.button !== 0) return;
    const canvas = document.getElementById('holo-three-canvas');
    if (!canvas || e.target !== canvas) return;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const meshes = this.deviceNodes.map(n => n.mesh);
    const intersects = this.raycaster.intersectObjects(meshes);

    if (intersects.length > 0) {
      const best = intersects[0].object as THREE.Mesh;
      const node = this.deviceNodes.find(n => n.mesh === best);
      if (node && node.data.type !== 'sensor') {
        // Déclencher l'onde et le basculement
        this.triggerRipple(node.group.position);
        
        // Basculement prédictif instantané pour un sentiment de fluidité accrue
        const nextVal = node.state === 'on' ? 'off' : 'on';
        node.updateState(nextVal);

        // Envoyer au backend Python
        this._send('domotic_toggle', { entity_id: node.data.id });
      }
    }
  };

  // ── AR Hand tracking coordinates handler ────────────────────

  updateHandsInteraction(pos0: THREE.Vector3 | null, pinched0: boolean, pos1: THREE.Vector3 | null, pinched1: boolean) {
    if (!this.active) {
      this.lastTwoPos0 = null;
      this.lastTwoPos1 = null;
      this.lastTwoDist = null;
      this.wasHandActive = false;
      return;
    }

    // ── GESTE DE ROTATION / SCALE À 2 MAINS ────────────────────
    if (pos0 && pos1 && pinched0 && pinched1) {
      this.wasHandActive = true;
      const dist = pos0.distanceTo(pos1);
      
      if (this.lastTwoPos0 && this.lastTwoPos1) {
        // Translation de toute la scène avec le déplacement du point central
        const prevCenter = this.lastTwoPos0.clone().add(this.lastTwoPos1).multiplyScalar(0.5);
        const currentCenter = pos0.clone().add(pos1).multiplyScalar(0.5);
        const translation = currentCenter.clone().sub(prevCenter);
        this.group.position.add(translation);

        // Zoom / Mise à l'échelle via la distance entre les mains
        if (this.lastTwoDist && this.lastTwoDist > 0.001) {
          const ratio = dist / this.lastTwoDist;
          this.group.scale.multiplyScalar(ratio);
          const s = THREE.MathUtils.clamp(this.group.scale.x, 0.3, 3.0);
          this.group.scale.set(s, s, s);
        }

        // Rotation horizontale (autour de Y) et verticale (autour de X)
        const prevVector = this.lastTwoPos1.clone().sub(this.lastTwoPos0);
        const currVector = pos1.clone().sub(pos0);

        // Rotation autour de Y (panoramique horizontal) basé sur l'angle XZ
        const prevAngleY = Math.atan2(prevVector.z, prevVector.x);
        const currAngleY = Math.atan2(currVector.z, currVector.x);
        let dThetaY = currAngleY - prevAngleY;
        if (dThetaY > Math.PI) dThetaY -= Math.PI * 2;
        if (dThetaY < -Math.PI) dThetaY += Math.PI * 2;
        this.group.rotation.y += dThetaY * 1.5;

        // Rotation autour de X (pitch vertical) basé sur l'angle XY
        const prevAngleX = Math.atan2(prevVector.y, prevVector.x);
        const currAngleX = Math.atan2(currVector.y, currVector.x);
        let dThetaX = currAngleX - prevAngleX;
        if (dThetaX > Math.PI) dThetaX -= Math.PI * 2;
        if (dThetaX < -Math.PI) dThetaX += Math.PI * 2;
        this.group.rotation.x -= dThetaX * 1.2;
        this.group.rotation.x = THREE.MathUtils.clamp(this.group.rotation.x, -0.2, Math.PI / 2.2);
      }

      this.lastTwoPos0 = pos0.clone();
      this.lastTwoPos1 = pos1.clone();
      this.lastTwoDist = dist;

      // Réinitialiser le survol en mode zoom/orbite
      this.deviceNodes.forEach(n => n.hovered = false);
      return;
    }

    // Réinitialiser les états 2 mains si non pincés simultanément
    this.lastTwoPos0 = null;
    this.lastTwoPos1 = null;
    this.lastTwoDist = null;

    // ── GESTE DE DÉPLACEMENT MONO-MAIN / CLIC ──
    const handWorldPos = pos0 || pos1;
    const isPinched = pos0 ? pinched0 : pinched1;

    if (!handWorldPos) {
      if (this.wasHandActive) {
        this.deviceNodes.forEach(n => n.hovered = false);
        this.wasHandActive = false;
      }
      return;
    }

    this.wasHandActive = true;

    // Détecter le survol d'un noeud par l'un des pointeurs 3D MediaPipe
    this.deviceNodes.forEach(n => n.hovered = false);

    // Chercher le noeud le plus proche du pointeur
    let bestNode: DomoticDeviceNode | null = null;
    let minDist = 0.45;

    this.deviceNodes.forEach((node) => {
      const d = node.group.position.distanceTo(handWorldPos);
      if (d < minDist) {
        minDist = d;
        bestNode = node;
      }
    });

    if (bestNode) {
      (bestNode as DomoticDeviceNode).hovered = true;

      // Si pincement sur le nœud -> clic AR virtuel
      if (isPinched && (bestNode as DomoticDeviceNode).data.type !== 'sensor') {
        const hIdx = pos0 ? 0 : 1;
        const wasPinched = (window as any)._wasSpatialPinched?.[hIdx];
        if (!wasPinched) {
          if (!(window as any)._wasSpatialPinched) (window as any)._wasSpatialPinched = [false, false];
          (window as any)._wasSpatialPinched[hIdx] = true;

          this.triggerRipple((bestNode as DomoticDeviceNode).group.position);
          
          const nextVal = (bestNode as DomoticDeviceNode).state === 'on' ? 'off' : 'on';
          (bestNode as DomoticDeviceNode).updateState(nextVal);

          this._send('domotic_toggle', { entity_id: (bestNode as DomoticDeviceNode).data.id });
        }
      } else {
        const hIdx = pos0 ? 0 : 1;
        if ((window as any)._wasSpatialPinched) {
          (window as any)._wasSpatialPinched[hIdx] = false;
        }
      }

      const hIdx = pos0 ? 0 : 1;
      if ((window as any)._prevDomoticHandPos) {
        (window as any)._prevDomoticHandPos[hIdx] = null;
      }
    } else {
      // Pincement dans le vide -> translation globale (drag) de la maison
      if (isPinched) {
        const hIdx = pos0 ? 0 : 1;
        const prevHandPos = (window as any)._prevDomoticHandPos?.[hIdx] as THREE.Vector3 | undefined;
        if (prevHandPos) {
          const translation = handWorldPos.clone().sub(prevHandPos);
          this.group.position.add(translation.multiplyScalar(1.2)); // Facteur de sensibilité
        }
        if (!(window as any)._prevDomoticHandPos) (window as any)._prevDomoticHandPos = [null, null];
        (window as any)._prevDomoticHandPos[hIdx] = handWorldPos.clone();
      } else {
        const hIdx = pos0 ? 0 : 1;
        if ((window as any)._prevDomoticHandPos) {
          (window as any)._prevDomoticHandPos[hIdx] = null;
        }
        if ((window as any)._wasSpatialPinched) {
          (window as any)._wasSpatialPinched[hIdx] = false;
        }
      }
    }
  }

  // ── Global Loop & Cleanup ───────────────────────────────────

  update(dt: number) {
    const time = performance.now() / 1000;

    // Mettre à jour les ondes de clics
    for (let i = this.activeRipples.length - 1; i >= 0; i--) {
      const r = this.activeRipples[i];
      r.age += dt;
      const t = r.age / r.life;
      r.ring.scale.setScalar(1.0 + t * 4.0);
      (r.ring.material as THREE.MeshBasicMaterial).opacity = Math.max(0, 1.0 - t);
      if (t >= 1) {
        this.group.remove(r.ring);
        r.ring.geometry.dispose();
        (r.ring.material as THREE.Material).dispose();
        this.activeRipples.splice(i, 1);
      }
    }

    // Mettre à jour les ondes de routage audio
    for (let i = this.activeWaves.length - 1; i >= 0; i--) {
      const w = this.activeWaves[i];
      w.progress += dt * w.speed;
      const t = w.progress;
      
      const currentPos = new THREE.Vector3().lerpVectors(w.start, w.end, t);
      const height = Math.sin(t * Math.PI) * 1.5;
      currentPos.y += height;
      w.group.position.copy(currentPos);
      
      const dir = new THREE.Vector3().subVectors(w.end, w.start).normalize();
      w.group.lookAt(new THREE.Vector3().addVectors(w.group.position, dir));
      
      w.rings.forEach((ring, idx) => {
        const scale = 1.0 + Math.sin(time * 10 + idx) * 0.2 + t * 2.0;
        ring.scale.setScalar(scale);
        ring.rotation.z += dt * (idx + 1) * 2;
        if (ring.material) {
          (ring.material as THREE.MeshBasicMaterial).opacity = Math.max(0, (1.0 - t) * 0.8);
        }
      });
      
      if (t >= 1) {
        this.group.remove(w.group);
        w.rings.forEach(ring => {
          ring.geometry.dispose();
          (ring.material as THREE.Material).dispose();
        });
        this.activeWaves.splice(i, 1);
      }
    }

    // Mettre à jour les noeuds
    this.deviceNodes.forEach(node => node.update(dt, time));
  }

  private _clearScene() {
    this.deviceNodes.forEach((node) => {
      this.group.remove(node.group);
      node.dispose();
    });
    this.deviceNodes = [];

    this.roomGroups.forEach((group) => {
      this.group.remove(group);
    });
    this.roomGroups.clear();

    this.roomFloors.forEach(floor => floor.geometry.dispose());
    this.roomFloors.clear();

    this.roomWalls.forEach(wall => wall.geometry.dispose());
    this.roomWalls.clear();

    this.activeRipples.forEach((r) => {
      this.group.remove(r.ring);
      r.ring.geometry.dispose();
      (r.ring.material as THREE.Material).dispose();
    });
    this.activeRipples = [];

    this.activeWaves.forEach((w) => {
      this.group.remove(w.group);
      w.rings.forEach((ring) => {
        ring.geometry.dispose();
        (ring.material as THREE.Material).dispose();
      });
    });
    this.activeWaves = [];

    this.scene.remove(this.group);
  }

  private _createHudBanner() {
    this._removeHudBanner();
    this.hudBanner = document.createElement('div');
    this.hudBanner.id = 'holo-domotic-banner';
    this.hudBanner.style.position = 'fixed';
    this.hudBanner.style.top = '120px';
    this.hudBanner.style.left = '50%';
    this.hudBanner.style.transform = 'translateX(-50%)';
    this.hudBanner.style.background = 'rgba(255, 140, 0, 0.08)';
    this.hudBanner.style.border = '1px solid rgba(255, 140, 0, 0.4)';
    this.hudBanner.style.color = '#ff8a1a';
    this.hudBanner.style.padding = '8px 18px';
    this.hudBanner.style.fontFamily = "'Courier New', monospace";
    this.hudBanner.style.fontSize = '11px';
    this.hudBanner.style.letterSpacing = '2px';
    this.hudBanner.style.zIndex = '120';
    this.hudBanner.style.borderRadius = '4px';
    this.hudBanner.style.textShadow = '0 0 10px rgba(255, 140, 0, 0.5)';
    this.hudBanner.style.backdropFilter = 'blur(10px)';
    this.hudBanner.textContent = '◈ PROTOCOLE_SIMULATION_DOMOTIQUE_ACTIF ◈';

    document.body.appendChild(this.hudBanner);
  }

  private _removeHudBanner() {
    if (this.hudBanner && this.hudBanner.parentNode) {
      this.hudBanner.parentNode.removeChild(this.hudBanner);
      this.hudBanner = null;
    }
  }
}
