/* ============================================================
   cortex_map.ts — Le Cortex Neuronal 3D (Interactive Memory Mesh)
   Modélise la mémoire à long terme de JARVIS (souvenirs vectoriels
   ChromaDB et clés locales jarvis_memoire.json) sous la forme
   d'une constellation 3D animée et interactive.
   ============================================================ */

import * as THREE from 'three';

// ── Types & Configuration ─────────────────────────────────────

interface CortexNodeData {
  id: string;
  type: 'vector' | 'key_value';
  user: string;
  assistant: string;
  timestamp: string;
}

const COLORS = {
  vectorLobe: 0x00e5ff,      // Cyan brillant
  keyValueLobe: 0xff00a0,    // Magenta/Rose néon
  synapse: 0x00e5ff,         // Couleur de base pour fils synaptiques
  spark: 0xffaa00,           // Impulsion électrique (Orange/Jaune)
  ripple: 0xff8a1a,          // Onde de sélection/nouveau souvenir
  hover: 0xff8a1a
};

// Texture radial pour l'effet de glow (particule floue)
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

// ── Classe de rendu 3D d'un neurone (CortexNode) ─────────────

class CortexNode {
  data: CortexNodeData;
  group: THREE.Group;
  mesh: THREE.Mesh;
  glow: THREE.Sprite;
  basePos: THREE.Vector3; // Position d'ancrage fixe
  currentPos: THREE.Vector3; // Position animée avec drift
  driftSeed: THREE.Vector3; // Graine aléatoire pour l'animation
  baseScale: number;
  hovered = false;
  colorHex: number;
  opacity = 1.0;
  targetOpacity = 1.0;
  isDisintegrating = false;
  disintegrationAge = 0;

  constructor(data: CortexNodeData, pos: THREE.Vector3) {
    this.data = data;
    this.basePos = pos.clone();
    this.currentPos = pos.clone();
    this.group = new THREE.Group();
    this.group.position.copy(pos);
    
    // Graine de dérive aléatoire pour des mouvements asynchrones et fluides
    this.driftSeed = new THREE.Vector3(
      Math.random() * 100,
      Math.random() * 100,
      Math.random() * 100
    );
 
    this.baseScale = data.type === 'vector' ? 0.12 : 0.09;
    this.colorHex = data.type === 'vector' ? COLORS.vectorLobe : COLORS.keyValueLobe;
 
    // 1. Noyau interne (Mesh solide)
    const geo = new THREE.SphereGeometry(this.baseScale, 16, 12);
    const mat = new THREE.MeshBasicMaterial({
      color: this.colorHex,
      transparent: true,
      opacity: 0.85,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.group.add(this.mesh);
 
    // 2. Halo extérieur (Glow Sprite)
    const glowMat = new THREE.SpriteMaterial({
      map: createRadialTexture(),
      color: this.colorHex,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
    this.glow = new THREE.Sprite(glowMat);
    this.glow.scale.setScalar(this.baseScale * 4.5);
    this.group.add(this.glow);
  }
 
  update(dt: number, time: number) {
    if (this.isDisintegrating) {
      this.disintegrationAge += dt;
      const t = this.disintegrationAge / 0.8; // Vie de 0.8 seconde
      this.opacity = Math.max(0, 1.0 - t);
      this.mesh.scale.setScalar(this.baseScale * (1.0 - t));
      this.glow.scale.setScalar(this.baseScale * 4.5 * (1.0 + t * 2.0));
      (this.mesh.material as THREE.MeshBasicMaterial).opacity = this.opacity * 0.85;
      (this.glow.material as THREE.SpriteMaterial).opacity = this.opacity * 0.5;
      return;
    }

    // Estompage fluide (Lerp vers targetOpacity)
    this.opacity += (this.targetOpacity - this.opacity) * dt * 5.0;
 
    // A. Breathe & Drift (Dérive lente tridimensionnelle organique et complexe style essaim)
    const tX = time * 0.35 + this.driftSeed.x;
    const tY = time * 0.30 + this.driftSeed.y;
    const tZ = time * 0.40 + this.driftSeed.z;
    
    // Superposition de vagues de fréquences différentes pour un mouvement d'essaim fluide
    const dx = Math.sin(tX) * 0.22 + Math.cos(tX * 2.2) * 0.08;
    const dy = Math.cos(tY) * 0.22 + Math.sin(tY * 1.8) * 0.08;
    const dz = Math.sin(tZ) * 0.16 + Math.cos(tZ * 2.5) * 0.06;
    
    this.currentPos.x = this.basePos.x + dx;
    this.currentPos.y = this.basePos.y + dy;
    this.currentPos.z = this.basePos.z + dz;

    this.group.position.copy(this.currentPos);

    // B. Pulsation d'Orbe
    let targetScale = 1.0;
    if (this.hovered) {
      targetScale = 1.6;
    } else {
      // Légère respiration continue
      targetScale = 1.0 + Math.sin(time * 2.5 + this.driftSeed.x) * 0.08;
    }

    const currentScale = this.mesh.scale.x;
    const nextScale = currentScale + (targetScale - currentScale) * dt * 8;
    this.mesh.scale.setScalar(nextScale);
    this.glow.scale.setScalar(this.baseScale * nextScale * 4.0 * (1.0 + Math.sin(time * 4 + this.driftSeed.y) * 0.05));

    // C. Ajustement de couleur si survolé
    const targetColor = this.hovered ? COLORS.hover : this.colorHex;
    (this.mesh.material as THREE.MeshBasicMaterial).color.setHex(targetColor);
    (this.glow.material as THREE.SpriteMaterial).color.setHex(targetColor);

    // D. Appliquer opacités de base
    (this.mesh.material as THREE.MeshBasicMaterial).opacity = this.opacity * 0.85;
    (this.glow.material as THREE.SpriteMaterial).opacity = this.opacity * 0.5;
  }

  disintegrate() {
    this.isDisintegrating = true;
  }

  dispose() {
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    (this.glow.material as THREE.SpriteMaterial).map?.dispose();
    (this.glow.material as THREE.SpriteMaterial).dispose();
  }
}

// ── Structure d'une liaison synaptique (Synapse) ─────────────

interface SynapseData {
  fromNode: CortexNode;
  toNode: CortexNode;
  line: THREE.Line;
}

// Spark électrique voyageant le long des synapses
class SynapticSpark {
  fromNode: CortexNode;
  toNode: CortexNode;
  mesh: THREE.Mesh;
  glow: THREE.Sprite;
  progress = 0.0;
  speed = 1.0;

  constructor(from: CortexNode, to: CortexNode) {
    this.fromNode = from;
    this.toNode = to;
    this.speed = 0.45 + Math.random() * 0.5;

    const geo = new THREE.SphereGeometry(0.035, 8, 6);
    const mat = new THREE.MeshBasicMaterial({
      color: COLORS.spark,
      transparent: true,
      opacity: 0.95,
      depthWrite: false
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.position.copy(from.currentPos);

    const glowMat = new THREE.SpriteMaterial({
      map: createRadialTexture(),
      color: COLORS.spark,
      transparent: true,
      opacity: 0.7,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
    this.glow = new THREE.Sprite(glowMat);
    this.glow.scale.setScalar(0.25);
    this.mesh.add(this.glow);
  }

  update(dt: number, parentGroup: THREE.Group) {
    this.progress += dt * this.speed;
    if (this.progress > 1.0) {
      this.progress = 1.0;
    }

    // Interpolation linéaire 3D entre les nœuds actuels
    const p1 = this.fromNode.currentPos;
    const p2 = this.toNode.currentPos;
    this.mesh.position.lerpVectors(p1, p2, this.progress);

    // Ajustement visuel (pulsation)
    const factor = Math.sin(this.progress * Math.PI);
    this.mesh.scale.setScalar(0.7 + factor * 0.6);
  }

  dispose(parentGroup: THREE.Group) {
    parentGroup.remove(this.mesh);
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    this.glow.geometry.dispose();
    (this.glow.material as THREE.SpriteMaterial).map?.dispose();
    (this.glow.material as THREE.SpriteMaterial).dispose();
  }
}

// ── Classe Principale — CortexMap ────────────────────────────

export class CortexMap {
  private scene: THREE.Scene;
  private camera: THREE.Camera;
  private ws: WebSocket;

  group: THREE.Group;
  private nodes: CortexNode[] = [];
  private synapses: SynapseData[] = [];
  private sparks: SynapticSpark[] = [];
  private activeRipples: { ring: THREE.Mesh; age: number; life: number; }[] = [];

  private active = false;
  private raycaster = new THREE.Raycaster();
  private mouse = new THREE.Vector2();

  // Contrôles souris
  private isLeftDown = false;
  private isRightDown = false;
  private lastMouseX = 0;
  private lastMouseY = 0;

  // Tooltip HUD dynamic
  private tooltip: HTMLDivElement | null = null;
  private hoveredNode: CortexNode | null = null;
  private selectedNode: CortexNode | null = null;

  // Extensions Cognitives & Interactives
  private customLinks: { from: string; to: string; }[] = [];
  private targetGroupPos = new THREE.Vector3(0, 0, 0);
  private searchResetTimer = 0;
  private draggedNode: CortexNode | null = null;
  private dragLine: THREE.Line | null = null;

  // Suivi gestuel (MediaPipe Gestures v2)
  private lastTwoPos0: THREE.Vector3 | null = null;
  private lastTwoPos1: THREE.Vector3 | null = null;
  private lastTwoDist: number | null = null;
  private wasHandActive = false;
  private gestHandGrabbedNode: CortexNode | null = null;
  private isGestDragging = false;
  private wasGestPinched = false;

  // Lissage adaptatif chirurgical
  private smoothedHandPos0 = new THREE.Vector3();
  private smoothedHandPos1 = new THREE.Vector3();
  private isHand0Smoothed = false;
  private isHand1Smoothed = false;


  constructor(scene: THREE.Scene, camera: THREE.Camera, ws: WebSocket) {
    this.scene = scene;
    this.camera = camera;
    this.ws = ws;
    this.group = new THREE.Group();
    
    // Position initiale et angle isométrique
    this.group.rotation.set(0.2, -0.3, 0);
    this.scene.add(this.group);
  }

  activate() {
    if (this.active) return;
    this.active = true;

    // Créer le tooltip HUD
    this._createTooltip();

    // Enregistrer les écouteurs d'événements
    window.addEventListener('mousedown', this._onMouseDown);
    window.addEventListener('mousemove', this._onMouseMove);
    window.addEventListener('mouseup', this._onMouseUp);
    window.addEventListener('contextmenu', this._onContextMenu);
    window.addEventListener('wheel', this._onWheel, { passive: true });
    window.addEventListener('click', this._onMouseClick);

    // Relier les clics sur le panel de gestion HTML
    this._wirePanelControls();

    // Masquer les autres panels d'interface potentiels
    const panel = document.getElementById('holo-cortex-panel');
    if (panel) panel.style.display = 'none';

    // Demander la liste des souvenirs
    this._send('cortex_list');
    console.log('[CORTEX] Réseau neuronal activé.');
  }

  deactivate() {
    if (!this.active) return;
    this.active = false;

    // Supprimer le tooltip et masquer le panel
    this._removeTooltip();
    const panel = document.getElementById('holo-cortex-panel');
    if (panel) panel.style.display = 'none';

    // Nettoyer les écouteurs
    window.removeEventListener('mousedown', this._onMouseDown);
    window.removeEventListener('mousemove', this._onMouseMove);
    window.removeEventListener('mouseup', this._onMouseUp);
    window.removeEventListener('contextmenu', this._onContextMenu);
    window.removeEventListener('wheel', this._onWheel);
    window.removeEventListener('click', this._onMouseClick);

    this._clearScene();
    console.log('[CORTEX] Réseau neuronal désactivé.');
  }

  // ── Modélisation 3D ────────────────────────────────────────

  private _clearScene() {
    this.sparks.forEach(s => s.dispose(this.group));
    this.sparks = [];

    this.synapses.forEach((s) => {
      this.group.remove(s.line);
      s.line.geometry.dispose();
      (s.line.material as THREE.Material).dispose();
    });
    this.synapses = [];

    this.nodes.forEach((n) => {
      this.group.remove(n.group);
      n.dispose();
    });
    this.nodes = [];

    this.activeRipples.forEach((r) => {
      this.group.remove(r.ring);
      r.ring.geometry.dispose();
      (r.ring.material as THREE.Material).dispose();
    });
    this.activeRipples = [];

    this.scene.remove(this.group);
  }

  handleServerResponse(data: any) {
    if (!this.active) return;

    if (data.action === 'cortex_list') {
      this.customLinks = data.links || [];
      this._buildMemoryMesh(data.nodes || []);
    } else if (data.action === 'cortex_update') {
      this._handleNodeDeleted(data.deleted_id);
    } else if (data.action === 'cortex_new_memory') {
      this._handleNewMemoryDynamic(data.node);
    } else if (data.action === 'cortex_link_created') {
      this._handleCustomLinkCreated(data.from, data.to);
    } else if (data.action === 'cortex_link_removed') {
      this._handleCustomLinkRemoved(data.from, data.to);
    } else if (data.action === 'cortex_edit_success') {
      this._handleNodeEdited(data.entity_id, data.user, data.assistant);
    }
  }

  private _handleNodeEdited(entityId: string, user: string, assistant: string) {
    const node = this.nodes.find(n => n.data.id === entityId);
    if (node) {
      node.data.user = user;
      node.data.assistant = assistant;
      
      // Si c'est le nœud actuellement sélectionné, on met à jour le HUD en direct
      if (this.selectedNode && this.selectedNode.data.id === entityId) {
        const userEl = document.getElementById('cp-txt-user');
        const assistantEl = document.getElementById('cp-txt-assistant');
        if (userEl) userEl.innerText = user;
        if (assistantEl) assistantEl.innerText = assistant;
      }
      
      // Ripple doré pour signaler la modification avec succès
      this.triggerRipple(node.currentPos, 0xff8a1a, 2.5);
    }
  }

  private _handleCustomLinkCreated(fromId: string, toId: string) {
    this.customLinks.push({ from: fromId, to: toId });
    this._rebuildSynapses();

    const fromNode = this.nodes.find(n => n.data.id === fromId);
    const toNode = this.nodes.find(n => n.data.id === toId);
    if (fromNode && toNode) {
      this.triggerRipple(fromNode.currentPos, COLORS.ripple, 2.5);
      this.triggerRipple(toNode.currentPos, COLORS.ripple, 2.5);

      // Arc synaptique instantané
      const newSpark = new SynapticSpark(fromNode, toNode);
      this.sparks.push(newSpark);
      this.group.add(newSpark.mesh);
    }
  }

  private _handleCustomLinkRemoved(fromId: string, toId: string) {
    this.customLinks = this.customLinks.filter(l => 
      !((l.from === fromId && l.to === toId) || (l.from === toId && l.to === fromId))
    );
    this._rebuildSynapses();

    const fromNode = this.nodes.find(n => n.data.id === fromId);
    const toNode = this.nodes.find(n => n.data.id === toId);
    if (fromNode && toNode) {
      // Onde de déconnexion de couleur Magenta/Rose
      this.triggerRipple(fromNode.currentPos, 0xff00a0, 2.5);
      this.triggerRipple(toNode.currentPos, 0xff00a0, 2.5);
    }
  }

  private _buildMemoryMesh(nodeList: CortexNodeData[]) {
    // 1. Vider l'ancienne scène (conserver la position et rotation globale)
    this.sparks.forEach(s => s.dispose(this.group));
    this.sparks = [];
    this.synapses.forEach(s => {
      this.group.remove(s.line);
      s.line.geometry.dispose();
      (s.line.material as THREE.Material).dispose();
    });
    this.synapses = [];
    this.nodes.forEach(n => {
      this.group.remove(n.group);
      n.dispose();
    });
    this.nodes = [];

    // 2. Instancier les nœuds
    nodeList.forEach((nData, index) => {
      // Déterminer la position en lobes du cerveau
      // Lobe gauche (Vectoriel - Bleu/Cyan) : X < 0
      // Lobe droit (Factuel - Magenta/Rose) : X > 0
      const center = new THREE.Vector3(
        nData.type === 'vector' ? -2.0 : 2.0,
        0,
        0
      );

      // Répartition sphérique organique
      const r = 0.5 + Math.random() * 0.95;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos((Math.random() * 2) - 1);

      const offset = new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta) * 0.75, // Lobe légèrement allongé en X/Z
        r * Math.cos(phi) * 0.65
      );

      const nodePos = center.clone().add(offset);
      const node = new CortexNode(nData, nodePos);
      this.nodes.push(node);
      this.group.add(node.group);
    });

    // 3. Dessiner les synapses & connexions
    this._rebuildSynapses();

    // 4. Lancer quelques étincelles synaptiques initiales
    this._launchSparks(7);
  }

  private _rebuildSynapses() {
    // Retirer les anciennes lignes synaptiques
    this.synapses.forEach(s => {
      this.group.remove(s.line);
      s.line.geometry.dispose();
      (s.line.material as THREE.Material).dispose();
    });
    this.synapses = [];

    if (this.nodes.length < 2) return;

    // Connecter chronologiquement (dans chaque type) pour former des flux séquentiels
    ['vector', 'key_value'].forEach((t) => {
      const typeNodes = this.nodes.filter(n => n.data.type === t && !n.isDisintegrating);
      for (let i = 0; i < typeNodes.length - 1; i++) {
        this._createSynapseLine(typeNodes[i], typeNodes[i + 1]);
      }
    });

    // Connecter par proximité sémantique/3D globale (effet toile de neurones connectée)
    this.nodes.forEach((n) => {
      if (n.isDisintegrating) return;
      
      // Chercher des voisins dans toute la constellation (liaisons croisées inter-lobes pour effet toile)
      const peers = this.nodes.filter(p => p !== n && !p.isDisintegrating);
      
      // Trier par distance 3D
      peers.sort((a, b) => {
        const d1 = n.basePos.distanceTo(a.basePos);
        const d2 = n.basePos.distanceTo(b.basePos);
        return d1 - d2;
      });

      const limit = Math.min(4, peers.length); // Plus de liaisons pour démultiplier l'effet toile
      for (let i = 0; i < limit; i++) {
        const target = peers[i];
        // Éviter de dupliquer la liaison exacte
        const alreadyLinked = this.synapses.some(s => 
          (s.fromNode === n && s.toNode === target) || 
          (s.fromNode === target && s.toNode === n)
        );
        if (!alreadyLinked && n.basePos.distanceTo(target.basePos) < 2.5) { // Attraction à plus longue portée
          this._createSynapseLine(n, target);
        }
      }
    });

    // Dessiner les synapses personnalisées créées par Drag-and-Link
    if (this.customLinks) {
      this.customLinks.forEach((link: any) => {
        const fromNode = this.nodes.find(n => n.data.id === link.from);
        const toNode = this.nodes.find(n => n.data.id === link.to);
        if (fromNode && toNode && !fromNode.isDisintegrating && !toNode.isDisintegrating) {
          // Éviter les doublons
          const alreadyLinked = this.synapses.some(s => 
            (s.fromNode === fromNode && s.toNode === toNode) || 
            (s.fromNode === toNode && s.toNode === fromNode)
          );
          if (!alreadyLinked) {
            this._createSynapseLine(fromNode, toNode);
          }
        }
      });
    }
  }

  private _createSynapseLine(from: CortexNode, to: CortexNode) {
    const points = [from.currentPos, to.currentPos];
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineBasicMaterial({
      color: from.data.type === 'vector' ? COLORS.vectorLobe : COLORS.keyValueLobe,
      transparent: true,
      opacity: 0.15,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const line = new THREE.Line(geo, mat);
    this.group.add(line);

    this.synapses.push({ fromNode: from, toNode: to, line });
  }

  private _launchSparks(count: number) {
    if (this.synapses.length === 0) return;
    for (let i = 0; i < count; i++) {
      const syn = this.synapses[Math.floor(Math.random() * this.synapses.length)];
      // Direction aléatoire
      const reverse = Math.random() > 0.5;
      const spark = new SynapticSpark(
        reverse ? syn.toNode : syn.fromNode,
        reverse ? syn.fromNode : syn.toNode
      );
      this.sparks.push(spark);
      this.group.add(spark.mesh);
    }
  }

  // ── Ondes holographiques de sélection ────────────────────────

  triggerRipple(pos: THREE.Vector3, colorHex = COLORS.ripple, sizeFactor = 1.0) {
    const g = new THREE.RingGeometry(0.01, 0.08 * sizeFactor, 32);
    const m = new THREE.MeshBasicMaterial({
      color: colorHex,
      transparent: true,
      opacity: 1.0,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
    const ring = new THREE.Mesh(g, m);
    ring.position.copy(pos);
    ring.lookAt(this.camera.position);

    this.group.add(ring);
    this.activeRipples.push({ ring, age: 0, life: 0.7 });
  }

  // ── Gestion de suppression & apprentissage en direct ─────────

  private _handleNodeDeleted(deletedId: string) {
    const node = this.nodes.find(n => n.data.id === deletedId);
    if (!node) return;

    // Déclencher la désintégration
    node.disintegrate();
    this.triggerRipple(node.currentPos, 0xff2e4d, 2.5); // Shockwave rouge

    // Masquer le panel de gestion s'il affichait ce nœud
    if (this.selectedNode === node) {
      this.selectedNode = null;
      const panel = document.getElementById('holo-cortex-panel');
      if (panel) panel.style.display = 'none';
    }

    // Après 0.8 seconde, retirer définitivement le nœud de la scène
    setTimeout(() => {
      this._removeNodeCompletely(deletedId);
    }, 850);
  }

  private _removeNodeCompletely(id: string) {
    const index = this.nodes.findIndex(n => n.data.id === id);
    if (index === -1) return;

    const node = this.nodes[index];
    this.group.remove(node.group);
    node.dispose();
    this.nodes.splice(index, 1);

    // Supprimer les étincelles associées
    this.sparks = this.sparks.filter(s => {
      const hit = s.fromNode === node || s.toNode === node;
      if (hit) s.dispose(this.group);
      return !hit;
    });

    // Reconstruire les synapses et rafraîchir
    this._rebuildSynapses();
  }

  private _handleNewMemoryDynamic(nodeData: CortexNodeData) {
    // 1. S'assurer que le nœud n'existe pas déjà
    if (this.nodes.some(n => n.data.id === nodeData.id)) return;

    // 2. Positionner le nouveau nœud au centre de son lobe respectif
    const lobeCenter = new THREE.Vector3(
      nodeData.type === 'vector' ? -2.0 : 2.0,
      0,
      0
    );

    // Décalage léger
    const offset = new THREE.Vector3(
      (Math.random() - 0.5) * 0.4,
      (Math.random() - 0.5) * 0.4,
      (Math.random() - 0.5) * 0.3
    );

    const nodePos = lobeCenter.clone().add(offset);
    const node = new CortexNode(nodeData, nodePos);
    this.nodes.push(node);
    this.group.add(node.group);

    // 3. Onde lumineuse spectaculaire ORANGE (appris)
    this.triggerRipple(node.currentPos, 0xff8a1a, 4.0);

    // 4. Reconstruire les liaisons synaptiques
    this._rebuildSynapses();

    // 5. Envoyer une pluie d'impulsions électriques synaptiques vers ce nouveau nœud !
    const neighbors = this.nodes.filter(n => n !== node && n.data.type === node.data.type && !n.isDisintegrating);
    const count = Math.min(4, neighbors.length);
    for (let i = 0; i < count; i++) {
      const spark = new SynapticSpark(neighbors[i], node);
      this.sparks.push(spark);
      this.group.add(spark.mesh);
    }
  }

  // ── Envoi de messages WebSocket ──────────────────────────────

  private _send(action: string, data: Record<string, any> = {}) {
    if (this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({
      type: 'spatial_action',
      action,
      ...data
    }));
  }

  // ── Tooltip HUD dynamic HTML ─────────────────────────────────

  private _createTooltip() {
    this._removeTooltip();
    this.tooltip = document.createElement('div');
    this.tooltip.id = 'holo-cortex-tooltip';
    this.tooltip.style.position = 'fixed';
    this.tooltip.style.background = 'rgba(6, 12, 22, 0.96)';
    this.tooltip.style.borderRadius = '8px';
    this.tooltip.style.padding = '16px 22px';
    this.tooltip.style.fontFamily = 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, sans-serif';
    this.tooltip.style.zIndex = '99999';
    this.tooltip.style.pointerEvents = 'none';
    this.tooltip.style.display = 'none';
    this.tooltip.style.backdropFilter = 'blur(16px)';
    this.tooltip.style.maxWidth = '500px'; // Plus large pour contenir de longs paragraphes
    this.tooltip.style.transition = 'opacity 0.15s ease, transform 0.15s ease';
    
    // Attacher à #holo-overlay pour faire partie de son contexte d'empilement
    const container = document.getElementById('holo-overlay') || document.body;
    container.appendChild(this.tooltip);
  }

  private _removeTooltip() {
    if (this.tooltip && this.tooltip.parentNode) {
      this.tooltip.parentNode.removeChild(this.tooltip);
    }
    this.tooltip = null;
  }

  // ── Raycasting & Mouse Controls ─────────────────────────────

  private _onMouseDown = (e: MouseEvent) => {
    if (!this.active) return;
    const canvas = document.getElementById('holo-three-canvas');
    if (!canvas || e.target !== canvas) return;

    this.lastMouseX = e.clientX;
    this.lastMouseY = e.clientY;

    // Drag-and-Link : Shift + Click gauche sur un nœud
    if (e.shiftKey && this.hoveredNode && e.button === 0) {
      this.draggedNode = this.hoveredNode;
      this.isLeftDown = false;

      // Créer la ligne de drag temporaire
      const points = [this.draggedNode.currentPos, this.draggedNode.currentPos];
      const geo = new THREE.BufferGeometry().setFromPoints(points);
      const mat = new THREE.LineBasicMaterial({
        color: 0xffaa00,
        transparent: true,
        opacity: 0.8,
        depthWrite: false
      });
      this.dragLine = new THREE.Line(geo, mat);
      this.group.add(this.dragLine);
      return;
    }

    if (e.button === 0) { // Click gauche -> Pan
      this.isLeftDown = true;
      this.targetGroupPos.copy(this.group.position);
      this.searchResetTimer = 0;
    } else if (e.button === 2) { // Click droit -> Orbit
      this.isRightDown = true;
      this.targetGroupPos.copy(this.group.position);
      this.searchResetTimer = 0;
    }
  };

  private _onMouseMove = (e: MouseEvent) => {
    if (!this.active) return;

    const dx = e.clientX - this.lastMouseX;
    const dy = e.clientY - this.lastMouseY;

    this.lastMouseX = e.clientX;
    this.lastMouseY = e.clientY;

    // Calculer coordonnées standardisées de la souris dans le canvas
    const canvas = document.getElementById('holo-three-canvas');
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);

    // Détection de survol (hover)
    const activeNodes = this.nodes.filter(n => !n.isDisintegrating);
    const meshes = activeNodes.map(n => n.mesh);
    const intersects = this.raycaster.intersectObjects(meshes);

    this.nodes.forEach(n => n.hovered = false);
    this.hoveredNode = null;

    if (intersects.length > 0) {
      const mesh = intersects[0].object as THREE.Mesh;
      const node = this.nodes.find(n => n.mesh === mesh);
      if (node) {
        node.hovered = true;
        this.hoveredNode = node;

        // Positionner et remplir le tooltip au-dessus de la sphère (projection 3D → 2D)
        if (this.tooltip) {
          const typeStr = node.data.type === 'vector' ? 'CONVERSATION' : 'FAIT';
          const accentColor = node.data.type === 'vector' ? '#00e5ff' : '#ff00a0';
          const shadowColor = node.data.type === 'vector' ? 'rgba(0, 229, 255, 0.3)' : 'rgba(255, 0, 160, 0.3)';

          // Mettre à jour dynamiquement la bordure et l'ombre en fonction du type de nœud
          this.tooltip.style.border = `1.5px solid ${accentColor}`;
          this.tooltip.style.boxShadow = `0 12px 40px rgba(0, 0, 0, 0.6), 0 0 20px ${shadowColor}`;

          // Formater le titre pour qu'il soit plus propre et esthétique
          let titre = node.data.id;
          if (titre.startsWith('kv_')) {
            const cleanKey = titre.substring(3).replace(/[_-]/g, ' ');
            titre = cleanKey.charAt(0).toUpperCase() + cleanKey.slice(1);
          } else if (titre.startsWith('msg_')) {
            const num = titre.substring(4);
            titre = `Discussion n° ${num}`;
          }

          // Plus de troncature du tout ! On affiche l'intégralité du texte
          const userPreview = node.data.user;
          const assistantPreview = node.data.assistant || '';

          this.tooltip.innerHTML = `
            <div style="font-family: 'Courier New', monospace; font-size: 11.5px; font-weight: bold; letter-spacing: 2px; opacity: 0.7; margin-bottom: 8px; color: ${accentColor}; text-transform: uppercase;">
              ▣ ${typeStr} &nbsp;·&nbsp; ${node.data.timestamp}
            </div>
            <div style="font-family: 'Courier New', monospace; font-weight: bold; font-size: 15px; color: #ffffff; margin-bottom: 12px; letter-spacing: 0.5px; border-bottom: 1.5px solid rgba(255, 255, 255, 0.15); padding-bottom: 8px; word-break: break-all;">
              ${titre}
            </div>
            <div style="font-size: 14.5px; font-weight: 500; color: #e0faff; line-height: 1.6; margin-bottom: 8px; word-break: break-word;">
              ${userPreview}
            </div>
            ${assistantPreview ? `
              <div style="font-size: 14px; font-weight: 400; color: #ffe8d4; line-height: 1.6; margin-top: 10px; padding-top: 10px; border-top: 1px dashed rgba(255,255,255,0.12); word-break: break-word; display: flex; gap: 8px;">
                <span style="color: #ff8a1a; flex-shrink: 0; font-weight: bold; font-size: 15px;">→</span>
                <span>${assistantPreview}</span>
              </div>
            ` : ''}
          `;

          // Projeter la position 3D de la sphère en coordonnées écran de manière synchrone et ultra-robuste
          this.group.updateMatrixWorld(true);
          const worldPos = new THREE.Vector3();
          node.mesh.getWorldPosition(worldPos);
          
          const projected = worldPos.project(this.camera);

          // Masquer si derrière la caméra
          if (projected.z > 1 || projected.z < -1) {
            this.tooltip.style.display = 'none';
          } else {
            const screenX = (projected.x + 1) / 2 * rect.width + rect.left;
            const screenY = -(projected.y - 1) / 2 * rect.height + rect.top;

            this.tooltip.style.display = 'block';
            
            // Calcul immédiat pour éviter tout flickering ou race conditions asynchrones
            const tw = this.tooltip.offsetWidth;
            const th = this.tooltip.offsetHeight;
            
            this.tooltip.style.left = `${Math.max(8, Math.min(window.innerWidth - tw - 8, screenX - tw / 2))}px`;
            this.tooltip.style.top  = `${Math.max(8, screenY - th - 22)}px`;
          }
        }
      }
    } else {
      if (this.tooltip) this.tooltip.style.display = 'none';
    }

    // Mise à jour de la ligne Drag-and-Link
    if (this.draggedNode && this.dragLine) {
      const planeNormal = new THREE.Vector3();
      this.camera.getWorldDirection(planeNormal);
      planeNormal.negate();
      const worldNodePos = this.draggedNode.currentPos.clone().applyMatrix4(this.group.matrixWorld);
      const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(planeNormal, worldNodePos);
      const target = new THREE.Vector3();
      this.raycaster.ray.intersectPlane(plane, target);
      
      const localTarget = target.clone().applyMatrix4(this.group.matrixWorld.clone().invert());
      
      const posAttr = this.dragLine.geometry.attributes.position;
      const pArr = posAttr.array as Float32Array;
      pArr[0] = this.draggedNode.currentPos.x;
      pArr[1] = this.draggedNode.currentPos.y;
      pArr[2] = this.draggedNode.currentPos.z;
      pArr[3] = localTarget.x;
      pArr[4] = localTarget.y;
      pArr[5] = localTarget.z;
      posAttr.needsUpdate = true;
      return; // Empêcher la translation caméra pendant le drag!
    }

    // Translation (Pan)
    if (this.isLeftDown) {
      this.group.position.x += dx * 0.005;
      this.group.position.y -= dy * 0.005;
    } 
    // Rotation (Orbit)
    else if (this.isRightDown) {
      this.group.rotation.y += dx * 0.004;
      this.group.rotation.x += dy * 0.004;
      // Empêcher les rotations trop brutales verticalement
      this.group.rotation.x = Math.max(-0.6, Math.min(Math.PI / 2.5, this.group.rotation.x));
    }
  };

  private _onMouseUp = (e: MouseEvent) => {
    if (e.button === 0) this.isLeftDown = false;
    else if (e.button === 2) this.isRightDown = false;

    if (this.draggedNode) {
      if (this.dragLine) {
        this.group.remove(this.dragLine);
        this.dragLine.geometry.dispose();
        (this.dragLine.material as THREE.Material).dispose();
        this.dragLine = null;
      }

      if (this.hoveredNode && this.hoveredNode !== this.draggedNode) {
        // Envoyer la création de synapse au serveur
        this._send('cortex_link', {
          from_id: this.draggedNode.data.id,
          to_id: this.hoveredNode.data.id
        });
      }
      this.draggedNode = null;
    }
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
    const factor = e.deltaY > 0 ? 0.92 : 1.08;
    this.group.scale.multiplyScalar(factor);
    this.group.scale.setScalar(Math.max(0.4, Math.min(2.5, this.group.scale.x)));
    this.targetGroupPos.copy(this.group.position);
    this.searchResetTimer = 0;
  };

  private _onMouseClick = (e: MouseEvent) => {
    if (!this.active || e.button !== 0) return;
    const canvas = document.getElementById('holo-three-canvas');
    if (!canvas || e.target !== canvas) return;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const activeNodes = this.nodes.filter(n => !n.isDisintegrating);
    const meshes = activeNodes.map(n => n.mesh);
    const intersects = this.raycaster.intersectObjects(meshes);

    if (intersects.length > 0) {
      const mesh = intersects[0].object as THREE.Mesh;
      const node = this.nodes.find(n => n.mesh === mesh);
      if (node) {
        this._selectNode(node);
      }
    } else {
      // Clic dans le vide -> Réinitialiser la recherche / l'estompement
      this.nodes.forEach(n => n.targetOpacity = 1.0);
      this.targetGroupPos.set(0, 0, 0);
      this.searchResetTimer = 0;
    }
  };

  private _selectNode(node: CortexNode) {
    this.selectedNode = node;

    // Déclencher l'onde holographique
    this.triggerRipple(node.currentPos, node.colorHex, 2.0);

    // Remplir et afficher le panel de détails HTML
    const panel = document.getElementById('holo-cortex-panel');
    const idEl = document.getElementById('cp-meta-id');
    const timeEl = document.getElementById('cp-meta-time');
    const typeEl = document.getElementById('cp-meta-type');
    const userEl = document.getElementById('cp-txt-user');
    const assistantEl = document.getElementById('cp-txt-assistant');
    const assistantTitleEl = document.getElementById('cp-assistant-title');

    if (panel && idEl && timeEl && typeEl && userEl && assistantEl && assistantTitleEl) {
      let cleanId = node.data.id;
      if (cleanId.startsWith('kv_')) {
        const cleanKey = cleanId.substring(3).replace(/[_-]/g, ' ');
        cleanId = cleanKey.charAt(0).toUpperCase() + cleanKey.slice(1);
      } else if (cleanId.startsWith('msg_')) {
        cleanId = `Discussion n° ${cleanId.substring(4)}`;
      }
      idEl.innerText = cleanId;
      timeEl.innerText = node.data.timestamp;
      typeEl.innerText = node.data.type === 'vector' ? 'VECTOR_MEMORY (ChromaDB)' : 'FACTUAL_MEMORY (jarvis_memoire.json)';
      
      // Personnalisation des titres et bulles selon le type
      if (node.data.type === 'vector') {
        userEl.innerText = node.data.user;
        userEl.className = 'cp-bubble cp-user';
        assistantEl.innerText = node.data.assistant || 'Aucune réponse parlée mémorisée.';
        assistantEl.style.display = 'block';
        assistantTitleEl.style.display = 'block';
      } else {
        // Clé-valeur locale
        userEl.innerText = node.data.user;
        userEl.className = 'cp-bubble cp-user';
        assistantEl.innerText = node.data.assistant;
        assistantEl.style.display = 'block';
        assistantTitleEl.style.display = 'block';
      }

      panel.style.display = 'flex';
    }
  }

  // ── Recherche sémantique visuelle & Narration vocale ──────────

  searchCortex(query: string) {
    if (!this.active) return;
    const stripAccents = (str: string) => str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const q = stripAccents(query.toLowerCase().trim());
    if (!q) return;

    const matches = this.nodes.filter(n => 
      stripAccents(n.data.user.toLowerCase()).includes(q) || 
      stripAccents(n.data.assistant.toLowerCase()).includes(q)
    );

    if (matches.length > 0) {
      console.log(`[CORTEX] ${matches.length} souvenir(s) correspondant à "${q}"`);
      const bestNode = matches[0];

      // Centrer cinématiquement sur ce nœud (lerp vers -basePos)
      this.targetGroupPos.copy(bestNode.basePos).multiplyScalar(-1.0);

      // Estomper les autres (dimming) et garder les matchs allumés
      this.nodes.forEach(n => {
        if (matches.includes(n)) {
          n.targetOpacity = 1.0;
        } else {
          n.targetOpacity = 0.1;
        }
      });

      // Onde dorée néon sur tous les matchs
      matches.forEach(m => {
        this.triggerRipple(m.currentPos, 0xffaa00, 3.0);
      });

      // Sélectionner automatiquement le meilleur match
      this._selectNode(bestNode);

      // Lancer le timer de réinitialisation automatique (10 secondes)
      this.searchResetTimer = 10.0;
    } else {
      console.log(`[CORTEX] Aucun souvenir correspondant à "${q}"`);
      // Réinitialiser la recherche si aucun résultat
      this.nodes.forEach(n => n.targetOpacity = 1.0);
      this.targetGroupPos.set(0, 0, 0);
      this.searchResetTimer = 0;
    }
  }

  handleVocalSpeakRequest() {
    if (this.selectedNode) {
      this._send('cortex_speak', { entity_id: this.selectedNode.data.id });
    } else {
      this._send('cortex_speak_error', { message: "Aucun souvenir sélectionné dans votre cortex. Veuillez en sélectionner un en cliquant sur un nœud." });
    }
  }

  // ── Logique de suppression via le panel HTML ─────────────────

  private _wirePanelControls() {
    const closeBtn = document.getElementById('cp-close-btn');
    if (closeBtn) {
      closeBtn.onclick = () => {
        const panel = document.getElementById('holo-cortex-panel');
        if (panel) panel.style.display = 'none';
        this.selectedNode = null;
        
        // Reset de l'état d'édition si fermeture
        const editBtn = document.getElementById('cp-edit-btn');
        if (editBtn) {
          editBtn.textContent = "MODIFIER";
          editBtn.style.background = "rgba(255, 140, 0, 0.12)";
          editBtn.style.borderColor = "rgba(255, 140, 0, 0.35)";
          editBtn.style.color = "#ff8a1a";
        }
        const userEl = document.getElementById('cp-txt-user');
        const assistantEl = document.getElementById('cp-txt-assistant');
        if (userEl) { userEl.contentEditable = "false"; userEl.style.border = "none"; userEl.style.padding = ""; }
        if (assistantEl) { assistantEl.contentEditable = "false"; assistantEl.style.border = "none"; assistantEl.style.padding = ""; }
      };
    }

    const deleteBtn = document.getElementById('cp-delete-btn');
    if (deleteBtn) {
      deleteBtn.onclick = () => {
        if (!this.selectedNode) return;
        
        const deleteConfirm = confirm("Voulez-vous supprimer définitivement ce souvenir ? Cette action est irréversible.");
        if (deleteConfirm) {
          // Envoyer la demande au serveur Python
          this._send('cortex_delete', { entity_id: this.selectedNode.data.id });
        }
      };
    }

    const listenBtn = document.getElementById('cp-listen-btn');
    if (listenBtn) {
      listenBtn.onclick = () => {
        if (!this.selectedNode) return;
        this._send('cortex_speak', { entity_id: this.selectedNode.data.id });
      };
    }

    const editBtn = document.getElementById('cp-edit-btn') as HTMLButtonElement;
    if (editBtn) {
      editBtn.onclick = () => {
        if (!this.selectedNode) return;
        
        const userEl = document.getElementById('cp-txt-user');
        const assistantEl = document.getElementById('cp-txt-assistant');
        if (!userEl || !assistantEl) return;
        
        const isEditing = editBtn.textContent === "ENREGISTRER";
        
        if (!isEditing) {
          // Entrée en mode édition
          editBtn.textContent = "ENREGISTRER";
          editBtn.style.background = "rgba(0, 229, 255, 0.12)";
          editBtn.style.borderColor = "rgba(0, 229, 255, 0.5)";
          editBtn.style.color = "#00e5ff";
          
          userEl.contentEditable = "true";
          userEl.style.border = "1px dashed #ff8a1a";
          userEl.style.padding = "10px";
          userEl.style.outline = "none";
          
          assistantEl.contentEditable = "true";
          assistantEl.style.border = "1px dashed #ff8a1a";
          assistantEl.style.padding = "10px";
          assistantEl.style.outline = "none";
          
          userEl.focus();
        } else {
          // Sortie du mode édition - Enregistrement
          const newUserText = userEl.innerText.trim();
          const newAssistantText = assistantEl.innerText.trim();
          
          if (!newUserText) {
            alert("Le texte ne peut pas être vide.");
            return;
          }
          
          // Envoyer au serveur
          this._send('cortex_edit_memory', {
            entity_id: this.selectedNode.data.id,
            user: newUserText,
            assistant: newAssistantText
          });
          
          // Sortir visuellement du mode édition
          editBtn.textContent = "MODIFIER";
          editBtn.style.background = "rgba(255, 140, 0, 0.12)";
          editBtn.style.borderColor = "rgba(255, 140, 0, 0.35)";
          editBtn.style.color = "#ff8a1a";
          
          userEl.contentEditable = "false";
          userEl.style.border = "none";
          userEl.style.padding = "";
          
          assistantEl.contentEditable = "false";
          assistantEl.style.border = "none";
          assistantEl.style.padding = "";
        }
      };
    }
  }

  // ── AR Hand tracking coordinates handler ────────────────────

  updateHandsInteraction(pos0: THREE.Vector3 | null, pinched0: boolean, pos1: THREE.Vector3 | null, pinched1: boolean) {
    if (!this.active) {
      this.lastTwoPos0 = null;
      this.lastTwoPos1 = null;
      this.lastTwoDist = null;
      this.wasHandActive = false;
      this.gestHandGrabbedNode = null;
      this.isGestDragging = false;
      this.wasGestPinched = false;
      this.isHand0Smoothed = false;
      this.isHand1Smoothed = false;
      return;
    }

    // Appliquer un lissage adaptatif 3D chirurgical par Lerp dynamique (élimine le tremblement mais réagit vite)
    if (pos0) {
      if (!this.isHand0Smoothed) {
        this.smoothedHandPos0.copy(pos0);
        this.isHand0Smoothed = true;
      } else {
        const d = this.smoothedHandPos0.distanceTo(pos0);
        const factor = THREE.MathUtils.clamp(d * 3.5, 0.02, 0.38); // Amortissement adaptatif
        this.smoothedHandPos0.lerp(pos0, factor);
      }
      pos0 = this.smoothedHandPos0;
    } else {
      this.isHand0Smoothed = false;
    }

    if (pos1) {
      if (!this.isHand1Smoothed) {
        this.smoothedHandPos1.copy(pos1);
        this.isHand1Smoothed = true;
      } else {
        const d = this.smoothedHandPos1.distanceTo(pos1);
        const factor = THREE.MathUtils.clamp(d * 3.5, 0.02, 0.38);
        this.smoothedHandPos1.lerp(pos1, factor);
      }
      pos1 = this.smoothedHandPos1;
    } else {
      this.isHand1Smoothed = false;
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
          const s = THREE.MathUtils.clamp(this.group.scale.x, 0.4, 2.5);
          this.group.scale.set(s, s, s);
          // Mettre à jour la cible de position souris pour rester synchronisés
          this.targetGroupPos.copy(this.group.position);
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
        this.group.rotation.x = THREE.MathUtils.clamp(this.group.rotation.x, -0.6, Math.PI / 2.5);
      }

      this.lastTwoPos0 = pos0.clone();
      this.lastTwoPos1 = pos1.clone();
      this.lastTwoDist = dist;

      // Réinitialiser le survol en mode zoom/orbite
      this.nodes.forEach(n => n.hovered = false);
      this.hoveredNode = null;
      return;
    }

    // Réinitialiser les états 2 mains si non pincés simultanément
    this.lastTwoPos0 = null;
    this.lastTwoPos1 = null;
    this.lastTwoDist = null;

    // ── GESTE DE DÉPLACEMENT MONO-MAIN / SÉLECTION ──
    const handWorldPos = pos0 || pos1;
    const isPinched = pos0 ? pinched0 : pinched1;

    if (!handWorldPos) {
      if (this.wasHandActive) {
        this.nodes.forEach(n => n.hovered = false);
        this.hoveredNode = null;
        this.wasHandActive = false;
      }
      return;
    }

    this.wasHandActive = true;

    // Détection de survol par MediaPipe
    this.nodes.forEach(n => { if (!n.isDisintegrating) n.hovered = false; });
    this.hoveredNode = null;

    // Recherche du nœud le plus proche du pointeur index
    let bestNode: CortexNode | null = null;
    let minDist = 0.35; // Seuil d'attraction 3D

    const activeNodes = this.nodes.filter(n => !n.isDisintegrating);
    activeNodes.forEach((node) => {
      const d = node.currentPos.distanceTo(handWorldPos);
      if (d < minDist) {
        minDist = d;
        bestNode = node;
      }
    });

    if (bestNode) {
      (bestNode as CortexNode).hovered = true;
      this.hoveredNode = bestNode;
    }

    // --- MACHINE À ÉTATS DE GESTION DU PINCH (SÉLECTION OU DRAG-AND-LINK) ---
    if (isPinched && !this.wasGestPinched) {
      // PINCH START
      if (bestNode) {
        this.gestHandGrabbedNode = bestNode;
        this.isGestDragging = false;
      } else {
        this.gestHandGrabbedNode = null;
      }
    }

    if (isPinched) {
      // PINCH HOLDING
      if (this.gestHandGrabbedNode) {
        const dist = handWorldPos.distanceTo(this.gestHandGrabbedNode.currentPos);
        // Si la main s'écarte du nœud initial, on active le mode drag
        if (!this.isGestDragging && dist > 0.4) {
          this.isGestDragging = true;
          // Initialisation de la ligne de drag
          if (!this.dragLine) {
            const points = [this.gestHandGrabbedNode.currentPos, this.gestHandGrabbedNode.currentPos];
            const geo = new THREE.BufferGeometry().setFromPoints(points);
            const mat = new THREE.LineBasicMaterial({
              color: 0xffaa00,
              transparent: true,
              opacity: 0.8,
              depthWrite: false
            });
            this.dragLine = new THREE.Line(geo, mat);
            this.group.add(this.dragLine);
          }
        }

        if (this.isGestDragging && this.dragLine) {
          // Mise à jour des points de la ligne dans l'espace local du groupe
          const localHandPos = handWorldPos.clone().applyMatrix4(this.group.matrixWorld.clone().invert());
          const posAttr = this.dragLine.geometry.attributes.position;
          const pArr = posAttr.array as Float32Array;
          pArr[0] = this.gestHandGrabbedNode.currentPos.x;
          pArr[1] = this.gestHandGrabbedNode.currentPos.y;
          pArr[2] = this.gestHandGrabbedNode.currentPos.z;
          pArr[3] = localHandPos.x;
          pArr[4] = localHandPos.y;
          pArr[5] = localHandPos.z;
          posAttr.needsUpdate = true;
        }
      } else {
        // Pincement dans le vide -> translation globale (drag) de la constellation
        const hIdx = pos0 ? 0 : 1;
        const prevHandPos = (window as any)._prevCortexHandPos?.[hIdx] as THREE.Vector3 | undefined;
        if (prevHandPos) {
          const translation = handWorldPos.clone().sub(prevHandPos);
          this.group.position.add(translation.multiplyScalar(1.2)); // Facteur de sensibilité
          this.targetGroupPos.copy(this.group.position);
        }
        if (!(window as any)._prevCortexHandPos) (window as any)._prevCortexHandPos = [null, null];
        (window as any)._prevCortexHandPos[hIdx] = handWorldPos.clone();
      }
    } else if (!isPinched && this.wasGestPinched) {
      // PINCH RELEASE
      if (this.gestHandGrabbedNode) {
        if (this.isGestDragging) {
          // Fin du Drag-and-Link : retirer la ligne et lier si survol d'un autre nœud
          if (this.dragLine) {
            this.group.remove(this.dragLine);
            this.dragLine.geometry.dispose();
            (this.dragLine.material as THREE.Material).dispose();
            this.dragLine = null;
          }

          if (bestNode && bestNode !== this.gestHandGrabbedNode) {
            this._send('cortex_link', {
              from_id: this.gestHandGrabbedNode.data.id,
              to_id: (bestNode as CortexNode).data.id
            });
          }
          this.isGestDragging = false;
        } else {
          // Simple clic : sélection du nœud
          this._selectNode(this.gestHandGrabbedNode);
        }
        this.gestHandGrabbedNode = null;
      }

      // Nettoyer les positions de drag vide
      const hIdx = pos0 ? 0 : 1;
      if ((window as any)._prevCortexHandPos) {
        (window as any)._prevCortexHandPos[hIdx] = null;
      }
    }

    if (!isPinched) {
      const hIdx = pos0 ? 0 : 1;
      if ((window as any)._prevCortexHandPos) {
        (window as any)._prevCortexHandPos[hIdx] = null;
      }
    }

    this.wasGestPinched = isPinched;
  }

  // ── Global Loop & Update ────────────────────────────────────

  update(dt: number) {
    const time = performance.now() / 1000;

    // Cinematic focus interpolation for search queries
    this.group.position.lerp(this.targetGroupPos, dt * 3.0);

    // Search reset countdown timer
    if (this.searchResetTimer > 0) {
      this.searchResetTimer -= dt;
      if (this.searchResetTimer <= 0) {
        // Reset node opacities to full and return constellation to home position
        this.nodes.forEach(n => n.targetOpacity = 1.0);
        this.targetGroupPos.set(0, 0, 0);
      }
    }

    // A. Mettre à jour les nœuds (drift et respiration)
    this.nodes.forEach(n => n.update(dt, time));

    // B. Mettre à jour les lignes synaptiques pour suivre la dérive
    this.synapses.forEach((syn) => {
      const pos = syn.line.geometry.attributes.position;
      const pArr = pos.array as Float32Array;

      pArr[0] = syn.fromNode.currentPos.x;
      pArr[1] = syn.fromNode.currentPos.y;
      pArr[2] = syn.fromNode.currentPos.z;

      pArr[3] = syn.toNode.currentPos.x;
      pArr[4] = syn.toNode.currentPos.y;
      pArr[5] = syn.toNode.currentPos.z;

      pos.needsUpdate = true;
    });

    // C. Mettre à jour les ondes de ripple 3D
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

    // D. Mettre à jour les étincelles électriques (Synaptic Sparks)
    for (let i = this.sparks.length - 1; i >= 0; i--) {
      const s = this.sparks[i];
      s.update(dt, this.group);
      
      // Si étincelle arrivée, la relancer le long d'une autre synapse
      if (s.progress >= 1.0) {
        s.dispose(this.group);
        this.sparks.splice(i, 1);

        // Relancer une nouvelle étincelle si synapses existantes
        if (this.synapses.length > 0 && !s.toNode.isDisintegrating) {
          const nextSynapses = this.synapses.filter(syn => 
            (syn.fromNode === s.toNode || syn.toNode === s.toNode)
          );
          if (nextSynapses.length > 0) {
            const nextSyn = nextSynapses[Math.floor(Math.random() * nextSynapses.length)];
            const otherNode = nextSyn.fromNode === s.toNode ? nextSyn.toNode : nextSyn.fromNode;
            if (!otherNode.isDisintegrating) {
              const newSpark = new SynapticSpark(s.toNode, otherNode);
              this.sparks.push(newSpark);
              this.group.add(newSpark.mesh);
            }
          }
        }
      }
    }

    // Maintenir le nombre d'étincelles en circulation
    const targetSparks = Math.min(8, this.synapses.length);
    if (this.sparks.length < targetSparks && this.synapses.length > 0) {
      this._launchSparks(1);
    }
  }
}
