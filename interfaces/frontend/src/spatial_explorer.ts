/* ============================================================
   spatial_explorer.ts — Explorateur de Fichiers Spatial 3D
   Module autonome pour naviguer dans les fichiers en 3D.
   Utilise la scène Three.js commune des vues 3D (vues_3d.js).
   ============================================================ */

import * as THREE from 'three';

// ── Types ─────────────────────────────────────────────────────

interface SpatialItem {
  name: string;
  type: 'file' | 'folder';
  path: string;
  icon?: string;     // image, video, audio, document, code, archive, exe, other
  size?: string;     // "2.3 Mo"
  children?: number; // nombre d'enfants (dossiers)
}

interface SpatialListResult {
  type: 'spatial_result';
  action: 'list';
  success: boolean;
  path: string;
  parent: string;
  folder_name: string;
  items: SpatialItem[];
  error?: string;
}

// ── Constantes couleurs ───────────────────────────────────────

const COLORS = {
  folder:   0x00e5ff,  // Cyan
  back:     0xffcc00,  // Jaune doré
  trash:    0xff2e4d,  // Rouge
  hover:    0xff8a1a,  // Orange chaud (hover magnétique)
  label_bg: 'rgba(0, 20, 40, 0.75)',
  // Fichiers par type d'icône
  file: {
    image:    0xe040fb,  // Violet
    video:    0xff4081,  // Rose vif
    audio:    0x7c4dff,  // Violet foncé
    document: 0x448aff,  // Bleu
    code:     0x69f0ae,  // Vert menthe
    archive:  0xffab40,  // Orange
    exe:      0xff6e40,  // Orange foncé
    other:    0x80deea,  // Cyan pâle
  } as Record<string, number>,
};

// ── Générateur de texture de lueur circulaire ────────────────
function createRadialGlowTexture(): THREE.Texture {
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext('2d')!;

  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
  grad.addColorStop(0.2, 'rgba(255, 255, 255, 0.85)');
  grad.addColorStop(1, 'rgba(255, 255, 255, 0)');

  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 64, 64);

  const texture = new THREE.CanvasTexture(canvas);
  return texture;
}

// ── Générateur d'anneau orbital holographique ─────────────────
function createLevelRing(radiusX: number, radiusZ: number, colorHex: number): THREE.LineLoop {
  const points: THREE.Vector3[] = [];
  const segments = 64;
  for (let i = 0; i <= segments; i++) {
    const theta = (i / segments) * Math.PI * 2;
    points.push(new THREE.Vector3(
      Math.cos(theta) * radiusX,
      0,
      Math.sin(theta) * radiusZ
    ));
  }
  const geo = new THREE.BufferGeometry().setFromPoints(points);
  const mat = new THREE.LineBasicMaterial({
    color: colorHex,
    transparent: true,
    opacity: 0.0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  return new THREE.LineLoop(geo, mat);
}

// ── Classe SpatialNode — un élément 3D dans la scène ──────────

class SpatialNode {
  item: SpatialItem;
  mesh!: THREE.Mesh;
  group: THREE.Group;
  label: THREE.Sprite;
  wireframe: THREE.LineSegments | null = null;
  baseScale: number;
  hovered = false;
  dragging = false;
  originalPosition: THREE.Vector3;

  constructor(item: SpatialItem, position: THREE.Vector3) {
    this.item = item;
    this.group = new THREE.Group();
    this.group.position.copy(position);
    this.originalPosition = position.clone();
    this.baseScale = 1.0;

    if (item.type === 'folder') {
      this._buildFolder();
    } else {
      this._buildFile();
    }

    this.label = this._buildLabel();
    this.group.add(this.label);
  }

  private _buildFolder() {
    const geo = new THREE.BoxGeometry(0.55, 0.55, 0.55);
    const mat = new THREE.MeshBasicMaterial({
      color: COLORS.folder,
      transparent: true,
      opacity: 0.12,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.group.add(this.mesh);

    // Wireframe overlay
    const edges = new THREE.EdgesGeometry(geo);
    const lineMat = new THREE.LineBasicMaterial({
      color: COLORS.folder,
      transparent: true,
      opacity: 0.7,
    });
    this.wireframe = new THREE.LineSegments(edges, lineMat);
    this.group.add(this.wireframe);
    this.baseScale = 0.9;
    this.mesh.scale.setScalar(this.baseScale);
    this.wireframe.scale.setScalar(this.baseScale);
  }

  private _buildFile() {
    const iconColor = COLORS.file[this.item.icon || 'other'] || COLORS.file.other;
    const geo = new THREE.SphereGeometry(0.22, 16, 12);
    const mat = new THREE.MeshBasicMaterial({
      color: iconColor,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.group.add(this.mesh);

    // Glow sprite (utilise une lueur radiale circulaire au lieu d'un carré brut)
    const glowTex = createRadialGlowTexture();
    const spriteMat = new THREE.SpriteMaterial({
      map: glowTex,
      color: iconColor,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const glow = new THREE.Sprite(spriteMat);
    glow.scale.set(0.75, 0.75, 1);
    this.group.add(glow);

    this.baseScale = 1.0;
  }

  private _buildLabel(): THREE.Sprite {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    canvas.width = 512;
    canvas.height = 64;

    // Fond glassmorphique
    ctx.fillStyle = COLORS.label_bg;
    const radius = 12;
    ctx.beginPath();
    ctx.roundRect(4, 4, canvas.width - 8, canvas.height - 8, radius);
    ctx.fill();

    // Texte
    ctx.font = 'bold 28px "Segoe UI", system-ui, sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    let displayName = this.item.name;
    if (displayName.length > 22) {
      displayName = displayName.slice(0, 20) + '…';
    }
    ctx.fillText(displayName, canvas.width / 2, canvas.height / 2);

    // Icône de type à gauche
    if (this.item.type === 'folder') {
      ctx.font = '26px "Segoe UI Emoji"';
      ctx.fillText('📁', 30, canvas.height / 2);
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    const mat = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthWrite: false,
    });
    const sprite = new THREE.Sprite(mat);
    sprite.scale.set(1.6, 0.2, 1);
    sprite.position.y = this.item.type === 'folder' ? -0.55 : -0.38;
    return sprite;
  }

  setHover(state: boolean) {
    if (this.hovered === state) return;
    this.hovered = state;
  }

  update(dt: number, time: number) {
    // Rotation lente pour les dossiers
    if (this.item.type === 'folder' && !this.dragging) {
      this.mesh.rotation.y += dt * 0.4;
      if (this.wireframe) this.wireframe.rotation.y = this.mesh.rotation.y;
    }

    // Flottement léger pour les fichiers
    if (this.item.type === 'file' && !this.dragging) {
      this.mesh.position.y = Math.sin(time * 1.5 + this.originalPosition.x * 3) * 0.04;
    }

    // Effet hover ou drag sélectionné (agrandissement modéré lors du drag)
    let targetScale = this.baseScale;
    if (this.dragging) {
      targetScale = this.baseScale * 1.15;
    } else if (this.hovered) {
      targetScale = this.baseScale * 1.1;
    }

    const currentScale = this.mesh.scale.x;
    const newScale = currentScale + (targetScale - currentScale) * dt * 8;
    this.mesh.scale.setScalar(newScale);
    if (this.wireframe) this.wireframe.scale.setScalar(newScale);

    // Changement de couleur et morphing lors du survol ou déplacement (drag)
    if (this.item.type === 'folder') {
      const targetColor = this.hovered ? COLORS.hover : COLORS.folder;
      (this.mesh.material as THREE.MeshBasicMaterial).color.lerp(
        new THREE.Color(targetColor), dt * 6
      );
      if (this.wireframe) {
        (this.wireframe.material as THREE.LineBasicMaterial).color.lerp(
          new THREE.Color(targetColor), dt * 6
        );
      }
    } else if (this.item.type === 'file') {
      const iconColor = COLORS.file[this.item.icon || 'other'] || COLORS.file.other;
      const targetColor = iconColor; // Conserver la couleur d'origine en toutes circonstances !
      
      // Lerp couleur du mesh
      (this.mesh.material as THREE.MeshBasicMaterial).color.lerp(
        new THREE.Color(targetColor), dt * 8
      );

      // Lerp couleur de la lueur glow sprite
      for (const child of this.group.children) {
        if (child instanceof THREE.Sprite && child !== this.label) {
          (child.material as THREE.SpriteMaterial).color.lerp(
            new THREE.Color(targetColor), dt * 8
          );
        }
      }
    }

    // Label opacity
    (this.label.material as THREE.SpriteMaterial).opacity = (this.hovered || this.dragging) ? 1.0 : 0.7;
  }

  dispose() {
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    if (this.wireframe) {
      this.wireframe.geometry.dispose();
      (this.wireframe.material as THREE.Material).dispose();
    }
    (this.label.material as THREE.SpriteMaterial).map?.dispose();
    (this.label.material as THREE.Material).dispose();
    // Dispose glow sprites
    for (const child of this.group.children) {
      if (child instanceof THREE.Sprite && child !== this.label) {
        (child.material as THREE.SpriteMaterial).map?.dispose();
        (child.material as THREE.Material).dispose();
      }
    }
  }
}

// ── Classe BackNode — Pyramide de retour en arrière ───────────

class BackNode {
  mesh: THREE.Mesh;
  group: THREE.Group;
  label: THREE.Sprite;
  hovered = false;

  constructor(position: THREE.Vector3) {
    this.group = new THREE.Group();
    this.group.position.copy(position);

    // Pyramide inversée
    const geo = new THREE.ConeGeometry(0.3, 0.45, 4);
    const mat = new THREE.MeshBasicMaterial({
      color: COLORS.back,
      wireframe: true,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending,
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.rotation.x = Math.PI; // Inversée
    this.group.add(this.mesh);

    // Label "RETOUR"
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    canvas.width = 256;
    canvas.height = 48;
    ctx.fillStyle = COLORS.label_bg;
    ctx.beginPath();
    ctx.roundRect(2, 2, 252, 44, 10);
    ctx.fill();
    ctx.font = 'bold 24px "Segoe UI", system-ui';
    ctx.fillStyle = '#ffcc00';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('⬅ RETOUR', 128, 24);
    const tex = new THREE.CanvasTexture(canvas);
    this.label = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex, transparent: true, depthWrite: false,
    }));
    this.label.scale.set(1.0, 0.18, 1);
    this.label.position.y = 0.5;
    this.group.add(this.label);
  }

  update(dt: number, _time: number) {
    this.mesh.rotation.y += dt * 0.8;
    const targetScale = this.hovered ? 1.3 : 1.0;
    const s = this.mesh.scale.x + (targetScale - this.mesh.scale.x) * dt * 8;
    this.mesh.scale.setScalar(s);
  }

  dispose() {
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    (this.label.material as THREE.SpriteMaterial).map?.dispose();
    (this.label.material as THREE.Material).dispose();
  }
}

// ── Classe TrashZone — Zone corbeille 3D ──────────────────────

class TrashZone {
  mesh: THREE.Mesh;
  group: THREE.Group;
  label: THREE.Sprite;
  hitMesh: THREE.Mesh; // Zone d'impact invisible pour faciliter grandement le clic
  hovered = false;

  constructor(position: THREE.Vector3) {
    this.group = new THREE.Group();
    this.group.position.copy(position);

    const geo = new THREE.TorusGeometry(0.35, 0.06, 8, 24);
    const mat = new THREE.MeshBasicMaterial({
      color: COLORS.trash,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.rotation.x = Math.PI / 2;
    this.group.add(this.mesh);

    // Hit box invisible (boîte englobante transparente) pour un raycast extrêmement réactif
    const hitGeo = new THREE.BoxGeometry(1.0, 1.0, 1.0);
    const hitMat = new THREE.MeshBasicMaterial({
      transparent: true,
      opacity: 0.0,
      depthWrite: false,
    });
    this.hitMesh = new THREE.Mesh(hitGeo, hitMat);
    this.group.add(this.hitMesh);

    // Label
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    canvas.width = 256;
    canvas.height = 48;
    ctx.fillStyle = 'rgba(60, 0, 0, 0.7)';
    ctx.beginPath();
    ctx.roundRect(2, 2, 252, 44, 10);
    ctx.fill();
    ctx.font = 'bold 22px "Segoe UI", system-ui';
    ctx.fillStyle = '#ff2e4d';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('🗑 CORBEILLE', 128, 24);
    const tex = new THREE.CanvasTexture(canvas);
    this.label = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex, transparent: true, depthWrite: false,
    }));
    this.label.scale.set(1.0, 0.18, 1);
    this.label.position.y = -0.45;
    this.group.add(this.label);
  }

  update(dt: number, _time: number) {
    this.mesh.rotation.z += dt * 0.5;
    const targetScale = this.hovered ? 1.5 : 1.0;
    const s = this.mesh.scale.x + (targetScale - this.mesh.scale.x) * dt * 8;
    this.mesh.scale.setScalar(s);
    this.hitMesh.scale.setScalar(s); // Agrandir aussi la hitbox de raycast
    (this.mesh.material as THREE.MeshBasicMaterial).opacity = this.hovered ? 0.7 : 0.35;
  }

  dispose() {
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    this.hitMesh.geometry.dispose();
    (this.hitMesh.material as THREE.Material).dispose();
    (this.label.material as THREE.SpriteMaterial).map?.dispose();
    (this.label.material as THREE.Material).dispose();
  }
}

// ── Classe Principale — SpatialFileExplorer ───────────────────

interface ExplorerLevel {
  path: string;
  parentPath?: string;
  folderName: string;
  nodes: SpatialNode[];
  parentNode: SpatialNode | null; // Dossier parent cliqué qui a engendré ce niveau
  lines: THREE.Line[];            // Lignes de flux reliant ce niveau à son parent
  ring?: THREE.LineLoop;          // Anneau orbital holographique
  baseRadius: number;             // Rayon de base du niveau
  
  // États d'animation
  currentRadiusFactor: number;   // Rayon actuel (glissement lerp)
  targetRadiusFactor: number;    // Rayon cible (1.0 au centre, 2.2 si parent périphérique, 4.0 si grand-parent)
  currentOpacity: number;        // Opacité actuelle (fade lerp)
  targetOpacity: number;         // Opacité cible (1.0 au centre, 0.25 si parent périphérique, 0.05 si grand-parent)
}

export class SpatialFileExplorer {
  private scene: THREE.Scene;
  private camera: THREE.Camera;
  private ws: WebSocket;
  private explorerGroup: THREE.Group;

  // Pile des niveaux d'arborescence actifs (cercles concentriques)
  private activeLevels: ExplorerLevel[] = [];

  private backNode: BackNode | null = null;
  private trashZone: TrashZone | null = null;

  private currentPath = '';
  private parentPath = '';
  private _active = false;

  // État de glisser-déplacer (drag & drop)
  private dragNode: SpatialNode | null = null;
  private dragStartPos: THREE.Vector3 | null = null;

  // Raycaster de détection de clics (souris / gestes)
  private raycaster = new THREE.Raycaster();

  // Étiquette du chemin de dossiers actuel (Breadcrumb)
  private breadcrumbSprite: THREE.Sprite | null = null;

  // États de souris pour le déplacement (glisser) et la rotation
  private dragStartScreenX = 0;
  private dragStartScreenY = 0;
  private hasDraggedSignificantly = false;
  private isLeftDown = false;
  private isRightDown = false;
  private lastMouseX = 0;
  private lastMouseY = 0;

  // États de gestes à deux mains pour la rotation/zoom de la scène
  private lastTwoPos0: THREE.Vector3 | null = null;
  private lastTwoPos1: THREE.Vector3 | null = null;
  private lastTwoDist: number | null = null;
  private wasHandActive = false;

  constructor(scene: THREE.Scene, camera: THREE.Camera, ws: WebSocket) {
    this.scene = scene;
    this.camera = camera;
    this.ws = ws;
    this.explorerGroup = new THREE.Group();
    this.scene.add(this.explorerGroup);

    // Enregistrement des écouteurs de clics et mouvements de souris
    window.addEventListener('click', this._onMouseClick);
    window.addEventListener('mousedown', this._onMouseDown);
    window.addEventListener('mousemove', this._onMouseMove);
    window.addEventListener('mouseup', this._onMouseUp);
    window.addEventListener('contextmenu', this._onContextMenu);
  }

  get active() { return this._active; }

  // Retourne une liste plate de tous les noeuds de tous les niveaux pour l'update global
  get nodes(): SpatialNode[] {
    const list: SpatialNode[] = [];
    for (const lvl of this.activeLevels) {
      list.push(...lvl.nodes);
    }
    return list;
  }

  // ── Activation / Désactivation ────────────────────────────

  activate(startPath?: string) {
    if (this._active) return;
    this._active = true;
    this.loadDirectory(startPath || 'telechargements');
  }

  deactivate() {
    this._active = false;
    this._clearScene();
    this.scene.remove(this.explorerGroup);
  }

  // ── Communication WebSocket ───────────────────────────────

  private _send(action: string, data: Record<string, any> = {}) {
    if (this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({
      type: 'spatial_action',
      action,
      ...data,
    }));
  }

  loadDirectory(path: string) {
    this._send('list', { path });
  }

  handleServerResponse(data: any) {
    if (!this._active) return;

    switch (data.action) {
      case 'list':
        if (data.success) {
          this._onDirectoryLoaded(data as SpatialListResult);
        } else {
          console.warn('[SPATIAL] Erreur listing:', data.error);
        }
        break;
      case 'open':
        if (data.success) {
          console.log('[SPATIAL] Fichier ouvert:', data.message);
        }
        break;
      case 'move':
        if (data.success) {
          // Recharger le niveau actif après un déplacement réussi
          this.loadDirectory(this.currentPath);
        }
        break;
      case 'delete':
        if (data.success) {
          // Recharger le niveau actif après une suppression
          this.loadDirectory(this.currentPath);
        }
        break;
    }
  }

  // ── Construction de la scène 3D concentrique ───────────────

  private _clearScene() {
    for (const lvl of this.activeLevels) {
      for (const node of lvl.nodes) {
        this.explorerGroup.remove(node.group);
        node.dispose();
      }
      for (const line of lvl.lines) {
        this.explorerGroup.remove(line);
        line.geometry.dispose();
        (line.material as THREE.Material).dispose();
      }
      if (lvl.ring) {
        this.explorerGroup.remove(lvl.ring);
        lvl.ring.geometry.dispose();
        (lvl.ring.material as THREE.Material).dispose();
      }
    }
    this.activeLevels = [];

    if (this.backNode) {
      this.explorerGroup.remove(this.backNode.group);
      this.backNode.dispose();
      this.backNode = null;
    }
    if (this.trashZone) {
      this.explorerGroup.remove(this.trashZone.group);
      this.trashZone.dispose();
      this.trashZone = null;
    }
    if (this.breadcrumbSprite) {
      this.explorerGroup.remove(this.breadcrumbSprite);
      (this.breadcrumbSprite.material as THREE.SpriteMaterial).map?.dispose();
      (this.breadcrumbSprite.material as THREE.Material).dispose();
      this.breadcrumbSprite = null;
    }
  }

  private _onDirectoryLoaded(result: SpatialListResult) {
    // A. Si c'est un rechargement / rafraîchissement du niveau actif actuel
    if (this.activeLevels.length > 0 && result.path === this.currentPath) {
      const activeLvl = this.activeLevels[this.activeLevels.length - 1];
      
      // 1. Supprimer et dispose des anciens noeuds du niveau actif
      for (const node of activeLvl.nodes) {
        this.explorerGroup.remove(node.group);
        node.dispose();
      }
      activeLvl.nodes = [];

      // 2. Recréer les noeuds avec les nouveaux items
      const items = result.items;
      const total = items.length;
      const radius = activeLvl.baseRadius; // Conserver le rayon d'origine
      const angleStep = (Math.PI * 2) / Math.max(total, 1);

      for (let i = 0; i < total; i++) {
        const angle = angleStep * i - Math.PI / 2;
        const x = Math.cos(angle) * radius;
        const z = Math.sin(angle) * radius * 0.7;
        const y = (items[i].type === 'folder' ? 0.1 : -0.1) + Math.sin(i * 0.7) * 0.1;
        const pos = new THREE.Vector3(x, y, z);
        const node = new SpatialNode(items[i], pos);
        
        // Conserver les positions pour éviter un effet de zoom initial
        node.group.position.copy(pos);
        activeLvl.nodes.push(node);
        this.explorerGroup.add(node.group);
      }

      // 3. Mettre à jour les lignes de flux si un parentNode existe
      for (const line of activeLvl.lines) {
        this.explorerGroup.remove(line);
        line.geometry.dispose();
        (line.material as THREE.Material).dispose();
      }
      activeLvl.lines = [];

      if (activeLvl.parentNode) {
        const lineMat = new THREE.LineBasicMaterial({
          color: 0x00e5ff,
          transparent: true,
          opacity: 0.25 * activeLvl.currentOpacity,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        });

        for (const node of activeLvl.nodes) {
          const points = [node.group.position.clone(), activeLvl.parentNode.group.position.clone()];
          const geo = new THREE.BufferGeometry().setFromPoints(points);
          const line = new THREE.Line(geo, lineMat);
          this.explorerGroup.add(line);
          activeLvl.lines.push(line);
        }
      }

      // 4. Recréer la zone corbeille et le breadcrumb
      this._rebuildGeneralUI(result.folder_name, result.path);
      return;
    }

    // 1. Identifier quel noeud du niveau précédent a été pinch/cliqué
    let foundParentNode: SpatialNode | null = null;
    const previousActiveLevel = this.activeLevels[this.activeLevels.length - 1];

    if (previousActiveLevel) {
      for (const node of previousActiveLevel.nodes) {
        if (node.item.path === result.path) {
          foundParentNode = node;
          break;
        }
      }
    }

    // 2. Si on rentre dans un dossier parent connu, on écarte les anciens niveaux
    if (foundParentNode && previousActiveLevel) {
      for (let i = 0; i < this.activeLevels.length; i++) {
        const lvl = this.activeLevels[i];
        const depthFromActive = this.activeLevels.length - i; // 1 pour le parent direct, etc.
        
        if (depthFromActive === 1) {
          lvl.targetRadiusFactor = 2.4; 
          lvl.targetOpacity = 0.40;     
        } else {
          lvl.targetRadiusFactor = 3.8; 
          lvl.targetOpacity = 0.15;     
        }
      }
    } else {
      // Si c'est un chargement racine ou externe, on vide tout d'abord
      this._clearScene();
    }

    // 3. Créer le nouveau niveau
    this.currentPath = result.path;
    this.parentPath = result.parent;

    const items = result.items;
    const total = items.length;
    const newNodes: SpatialNode[] = [];

    // Rayon resserré pour le centre (pour mieux le différencier de l'extérieur)
    const radius = Math.max(1.1, total * 0.12);
    const angleStep = (Math.PI * 2) / Math.max(total, 1);

    for (let i = 0; i < total; i++) {
      const angle = angleStep * i - Math.PI / 2;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius * 0.7;
      const y = (items[i].type === 'folder' ? 0.1 : -0.1) + Math.sin(i * 0.7) * 0.1;
      const pos = new THREE.Vector3(x, y, z);
      const node = new SpatialNode(items[i], pos);
      
      // Part de (0,0,0) pour un effet de pop/zoom initial magnifique
      node.group.position.set(0, 0, 0);
      newNodes.push(node);
      this.explorerGroup.add(node.group);
    }

    // Création de l'anneau orbital holographique
    const ring = createLevelRing(radius, radius * 0.7, 0x00e5ff);
    this.explorerGroup.add(ring);

    // 4. Générer les lignes holographiques reliant ce niveau au dossier parent cliqué
    const lines: THREE.Line[] = [];
    if (foundParentNode) {
      const lineMat = new THREE.LineBasicMaterial({
        color: 0x00e5ff,
        transparent: true,
        opacity: 0.0, // sera animé vers 0.3 via currentOpacity
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });

      for (const node of newNodes) {
        const points = [node.group.position.clone(), foundParentNode.group.position.clone()];
        const geo = new THREE.BufferGeometry().setFromPoints(points);
        const line = new THREE.Line(geo, lineMat);
        this.explorerGroup.add(line);
        lines.push(line);
      }
    }

    // 5. Enregistrer ce niveau dans la pile
    const newLevel: ExplorerLevel = {
      path: result.path,
      parentPath: result.parent || '',
      folderName: result.folder_name,
      nodes: newNodes,
      parentNode: foundParentNode,
      lines,
      ring,
      baseRadius: radius,
      currentRadiusFactor: foundParentNode ? 0.01 : 1.0,
      targetRadiusFactor: 1.0,
      currentOpacity: foundParentNode ? 0.0 : 1.0,
      targetOpacity: 1.0,
    };

    this.activeLevels.push(newLevel);

    // 6. Recréer l'interface générale d'arrière-plan (corbeille, retour, breadcrumb)
    this._rebuildGeneralUI(result.folder_name, result.path);
  }

  private _rebuildGeneralUI(folderName: string, path: string) {
    if (this.backNode) {
      this.explorerGroup.remove(this.backNode.group);
      this.backNode.dispose();
      this.backNode = null;
    }
    if (this.trashZone) {
      this.explorerGroup.remove(this.trashZone.group);
      this.trashZone.dispose();
      this.trashZone = null;
    }
    if (this.breadcrumbSprite) {
      this.explorerGroup.remove(this.breadcrumbSprite);
      (this.breadcrumbSprite.material as THREE.SpriteMaterial).map?.dispose();
      (this.breadcrumbSprite.material as THREE.Material).dispose();
      this.breadcrumbSprite = null;
    }

    // Bouton de retour apparaît s'il y a des niveaux empilés OU s'il existe un dossier parent physique
    if (this.activeLevels.length > 1 || (this.parentPath && this.parentPath !== this.currentPath)) {
      this.backNode = new BackNode(new THREE.Vector3(0, 1.8, 0));
      this.explorerGroup.add(this.backNode.group);
    }

    // Zone corbeille active
    this.trashZone = new TrashZone(new THREE.Vector3(0, -2.0, 0));
    this.explorerGroup.add(this.trashZone.group);

    // Fil d'Ariane (breadcrumb)
    this._buildBreadcrumb(folderName, path);
  }

  private _buildBreadcrumb(folderName: string, fullPath: string) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    canvas.width = 768;
    canvas.height = 56;

    ctx.fillStyle = 'rgba(0, 15, 30, 0.6)';
    ctx.beginPath();
    ctx.roundRect(4, 4, canvas.width - 8, canvas.height - 8, 14);
    ctx.fill();

    ctx.strokeStyle = 'rgba(0, 229, 255, 0.4)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.font = 'bold 26px "Segoe UI", system-ui';
    ctx.fillStyle = '#00e5ff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    let display = fullPath;
    if (display.length > 50) {
      display = '…' + display.slice(-48);
    }
    ctx.fillText(`📂 ${display}`, canvas.width / 2, canvas.height / 2);

    const tex = new THREE.CanvasTexture(canvas);
    this.breadcrumbSprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex, transparent: true, depthWrite: false,
    }));
    this.breadcrumbSprite.scale.set(3.5, 0.25, 1);
    this.breadcrumbSprite.position.set(0, 2.6, 0);
    this.explorerGroup.add(this.breadcrumbSprite);
  }

  // ── Revenir en arrière (Stack Back) ───────────────────────

  navigateBack() {
    if (this.activeLevels.length > 1) {
      // 1. Dépiler le dernier niveau central
      const obsoleteLevel = this.activeLevels.pop();
      if (obsoleteLevel) {
        for (const node of obsoleteLevel.nodes) {
          this.explorerGroup.remove(node.group);
          node.dispose();
        }
        for (const line of obsoleteLevel.lines) {
          this.explorerGroup.remove(line);
          line.geometry.dispose();
          (line.material as THREE.Material).dispose();
        }
        if (obsoleteLevel.ring) {
          this.explorerGroup.remove(obsoleteLevel.ring);
          obsoleteLevel.ring.geometry.dispose();
          (obsoleteLevel.ring.material as THREE.Material).dispose();
        }
      }

      // 2. Ré-activer le niveau parent au centre
      const activeLevel = this.activeLevels[this.activeLevels.length - 1];
      if (activeLevel) {
        this.currentPath = activeLevel.path;
        const parentLevel = this.activeLevels[this.activeLevels.length - 2];
        this.parentPath = parentLevel ? parentLevel.path : (activeLevel.parentPath || '');

        // Animer de retour au centre
        activeLevel.targetRadiusFactor = 1.0;
        activeLevel.targetOpacity = 1.0;

        // Rétrécir les parents plus haut
        for (let i = 0; i < this.activeLevels.length - 1; i++) {
          const lvl = this.activeLevels[i];
          const depth = this.activeLevels.length - 1 - i;
          if (depth === 1) {
            lvl.targetRadiusFactor = 2.4;
            lvl.targetOpacity = 0.40;
          } else {
            lvl.targetRadiusFactor = 3.8;
            lvl.targetOpacity = 0.15;
          }
        }

        // Reconstruire les éléments généraux
        this._rebuildGeneralUI(activeLevel.folderName, activeLevel.path);

        // Forcer le rechargement du répertoire parent réactivé pour actualiser son contenu
        this.loadDirectory(this.currentPath);
      }
    } else if (this.parentPath && this.parentPath !== this.currentPath) {
      // Si on est à la racine locale mais qu'il y a un parent physique sur le disque, on le charge
      this.loadDirectory(this.parentPath);
    }
  }

  // ── Raycasting Clics Souris ───────────────────────────────

  private _onMouseClick = (e: MouseEvent) => {
    if (!this._active) return;

    // Si l'utilisateur a glissé significativement pour déplacer ou tourner, on ignore le clic
    if (this.hasDraggedSignificantly) {
      this.hasDraggedSignificantly = false;
      return;
    }

    // Cible spécifiquement le canvas Three.js de l'hologramme
    const canvas = document.getElementById('holo-three-canvas');
    if (!canvas || e.target !== canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(new THREE.Vector2(x, y), this.camera);

    const activeLevel = this.activeLevels[this.activeLevels.length - 1];
    if (!activeLevel) return;

    // Réunir meshes + sprites d'étiquettes du niveau actif
    const targets: THREE.Object3D[] = [];
    for (const n of activeLevel.nodes) {
      targets.push(n.mesh);
      targets.push(n.label);
    }

    const intersects = this.raycaster.intersectObjects(targets);
    if (intersects.length > 0) {
      const hitObj = intersects[0].object;
      const hitNode = activeLevel.nodes.find(n => n.mesh === hitObj || n.label === hitObj);
      if (hitNode) {
        if (hitNode.item.type === 'folder') {
          this.loadDirectory(hitNode.item.path);
        } else {
          this._send('open', { path: hitNode.item.path });
        }
        return;
      }
    }

    // Vérifier clic sur la pyramide retour (mesh ou texte)
    if (this.backNode) {
      const backIntersects = this.raycaster.intersectObjects([this.backNode.mesh, this.backNode.label]);
      if (backIntersects.length > 0) {
        this.navigateBack();
        return;
      }
    }

    // Vérifier clic sur la corbeille (mesh, label ou hitbox invisible)
    if (this.trashZone) {
      const trashIntersects = this.raycaster.intersectObjects([
        this.trashZone.mesh, 
        this.trashZone.label, 
        this.trashZone.hitMesh
      ]);
      if (trashIntersects.length > 0) {
        this.loadDirectory('corbeille');
        return;
      }
    }
  };

  private _onMouseDown = (e: MouseEvent) => {
    if (!this._active) return;

    const canvas = document.getElementById('holo-three-canvas');
    if (!canvas || e.target !== canvas) return;

    this.lastMouseX = e.clientX;
    this.lastMouseY = e.clientY;

    if (e.button === 0) { // Clic gauche
      this.isLeftDown = true;
      this.dragStartScreenX = e.clientX;
      this.dragStartScreenY = e.clientY;
      this.hasDraggedSignificantly = false;

      // Raycast pour vérifier si on a cliqué sur un fichier à déplacer (drag & drop)
      const rect = canvas.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      this.raycaster.setFromCamera(new THREE.Vector2(x, y), this.camera);

      const activeLevel = this.activeLevels[this.activeLevels.length - 1];
      if (activeLevel) {
        const targets: THREE.Object3D[] = [];
        for (const n of activeLevel.nodes) {
          targets.push(n.mesh);
        }

        const intersects = this.raycaster.intersectObjects(targets);
        if (intersects.length > 0) {
          const hitMesh = intersects[0].object;
          const hitNode = activeLevel.nodes.find(n => n.mesh === hitMesh);
          if (hitNode) {
            this.dragNode = hitNode;
            this.dragNode.dragging = true;
            this.dragStartPos = hitNode.group.position.clone();
          }
        }
      }
    } else if (e.button === 2) { // Clic droit
      this.isRightDown = true;
    }
  };

  private _onMouseMove = (e: MouseEvent) => {
    if (!this._active) return;

    const dx = e.clientX - this.lastMouseX;
    const dy = e.clientY - this.lastMouseY;

    this.lastMouseX = e.clientX;
    this.lastMouseY = e.clientY;

    if (this.isLeftDown) {
      const dist = Math.hypot(e.clientX - this.dragStartScreenX, e.clientY - this.dragStartScreenY);
      if (dist > 15) {
        this.hasDraggedSignificantly = true;
      }

      if (this.dragNode && this.dragStartPos) {
        // Déplacer l'icône de fichier en projetant la souris dans l'espace 3D
        const canvas = document.getElementById('holo-three-canvas');
        if (canvas) {
          const rect = canvas.getBoundingClientRect();
          const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
          const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

          this.raycaster.setFromCamera(new THREE.Vector2(x, y), this.camera);

          // Plan 3D parallèle à l'écran passant par le noeud
          const planeZ = new THREE.Plane(new THREE.Vector3(0, 0, 1), -this.dragStartPos.z);
          const target = new THREE.Vector3();
          this.raycaster.ray.intersectPlane(planeZ, target);

          this.dragNode.group.position.lerp(target, 0.35);

          // Highlights : Raycast précis sur TOUS les dossiers visibles (de tous les niveaux actifs) (sauf celui qu'on déplace !)
          const allFolders = this.nodes.filter(n => n.item.type === 'folder' && n !== this.dragNode);
          const folderTargets: THREE.Object3D[] = [];
          for (const f of allFolders) {
            folderTargets.push(f.mesh);
            folderTargets.push(f.label);
          }

          const intersects = this.raycaster.intersectObjects(folderTargets);
          
          // Réinitialiser le survol sur tous les dossiers
          for (const f of allFolders) {
            f.setHover(false);
          }

          if (intersects.length > 0) {
            const hitObj = intersects[0].object;
            const hitNode = allFolders.find(f => f.mesh === hitObj || f.label === hitObj);
            if (hitNode) {
              hitNode.setHover(true);
            }
          }

          // Détection de survol sur le bouton RETOUR (pour remonter le fichier)
          if (this.backNode) {
            const backIntersects = this.raycaster.intersectObjects([this.backNode.mesh, this.backNode.label]);
            this.backNode.hovered = backIntersects.length > 0;
          }

          // Détection de survol sur la corbeille par Raycast (hitbox incluse)
          if (this.trashZone) {
            const trashIntersects = this.raycaster.intersectObjects([
              this.trashZone.mesh,
              this.trashZone.label,
              this.trashZone.hitMesh
            ]);
            this.trashZone.hovered = trashIntersects.length > 0;
          }
        }
      } else {
        // Déplacement/Translation de toute la scène
        this.explorerGroup.position.x += dx * 0.006;
        this.explorerGroup.position.y -= dy * 0.006;
      }
    } else if (this.isRightDown) {
      // Rotation de toute la scène
      this.explorerGroup.rotation.y += dx * 0.006;
      this.explorerGroup.rotation.x += dy * 0.006;

      // Limiter la rotation X pour éviter de retourner la scène
      this.explorerGroup.rotation.x = Math.max(-Math.PI / 3, Math.min(Math.PI / 3, this.explorerGroup.rotation.x));
    } else {
      // Survol général souris sans clic ni drag (Hover)
      const canvas = document.getElementById('holo-three-canvas');
      if (canvas && e.target === canvas) {
        const rect = canvas.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(new THREE.Vector2(x, y), this.camera);

        const activeLevel = this.activeLevels[this.activeLevels.length - 1];
        if (activeLevel) {
          // 1. Survol sur les fichiers/dossiers
          const targets: THREE.Object3D[] = [];
          for (const n of activeLevel.nodes) {
            targets.push(n.mesh);
            targets.push(n.label);
          }

          const intersects = this.raycaster.intersectObjects(targets);
          for (const n of activeLevel.nodes) {
            n.setHover(false);
          }

          if (intersects.length > 0) {
            const hitObj = intersects[0].object;
            const hitNode = activeLevel.nodes.find(n => n.mesh === hitObj || n.label === hitObj);
            if (hitNode) {
              hitNode.setHover(true);
            }
          }

          // 2. Survol sur le bouton RETOUR
          if (this.backNode) {
            const backIntersects = this.raycaster.intersectObjects([this.backNode.mesh, this.backNode.label]);
            this.backNode.hovered = backIntersects.length > 0;
          }

          // 3. Survol sur la corbeille (hitbox incluse)
          if (this.trashZone) {
            const trashIntersects = this.raycaster.intersectObjects([
              this.trashZone.mesh,
              this.trashZone.label,
              this.trashZone.hitMesh
            ]);
            this.trashZone.hovered = trashIntersects.length > 0;
          }
        }
      } else {
        // Reset des états de survol en dehors du canvas
        const activeLevel = this.activeLevels[this.activeLevels.length - 1];
        if (activeLevel) {
          for (const n of activeLevel.nodes) {
            n.setHover(false);
          }
        }
        if (this.backNode) this.backNode.hovered = false;
        if (this.trashZone) this.trashZone.hovered = false;
      }
    }
  };

  private _onMouseUp = (e: MouseEvent) => {
    if (!this._active) return;

    if (e.button === 0) { // Relâchement clic gauche
      this.isLeftDown = false;
      if (this.dragNode) {
        this._handleDrop(this.dragNode.group.position);
      }
    } else if (e.button === 2) { // Relâchement clic droit
      this.isRightDown = false;
    }
  };

  private _onContextMenu = (e: MouseEvent) => {
    const canvas = document.getElementById('holo-three-canvas');
    if (canvas && e.target === canvas) {
      e.preventDefault();
    }
  };

  // ── Interaction par gestes 3D ─────────────────────────────

  updateHandsInteraction(
    p0: THREE.Vector3 | null,
    pinched0: boolean,
    p1: THREE.Vector3 | null,
    pinched1: boolean
  ) {
    if (!this._active) {
      for (const n of this.nodes) n.setHover(false);
      if (this.backNode) this.backNode.hovered = false;
      if (this.trashZone) this.trashZone.hovered = false;
      this.lastTwoPos0 = null;
      this.lastTwoPos1 = null;
      this.lastTwoDist = null;
      this.wasHandActive = false;
      return;
    }

    // ── GESTE DE ROTATION / SCALE À 2 MAINS ────────────────────
    if (p0 && p1 && pinched0 && pinched1) {
      this.wasHandActive = true;
      // Les deux mains sont présentes et pincées -> 2-HANDS ORBIT
      const dist = p0.distanceTo(p1);
      
      if (this.lastTwoPos0 && this.lastTwoPos1) {
        // Translation de toute la scène avec le déplacement du point central
        const prevCenter = this.lastTwoPos0.clone().add(this.lastTwoPos1).multiplyScalar(0.5);
        const currentCenter = p0.clone().add(p1).multiplyScalar(0.5);
        const translation = currentCenter.clone().sub(prevCenter);
        this.explorerGroup.position.add(translation);

        // Zoom / Mise à l'échelle via la distance entre les mains
        if (this.lastTwoDist && this.lastTwoDist > 0.001) {
          const ratio = dist / this.lastTwoDist;
          this.explorerGroup.scale.multiplyScalar(ratio);
          const s = THREE.MathUtils.clamp(this.explorerGroup.scale.x, 0.3, 3.0);
          this.explorerGroup.scale.set(s, s, s);
        }

        // Rotation horizontale (autour de Y) et verticale (autour de X)
        const prevVector = this.lastTwoPos1.clone().sub(this.lastTwoPos0);
        const currVector = p1.clone().sub(p0);

        // Rotation autour de Y (panoramique horizontal) basé sur l'angle XZ
        const prevAngleY = Math.atan2(prevVector.z, prevVector.x);
        const currAngleY = Math.atan2(currVector.z, currVector.x);
        let dThetaY = currAngleY - prevAngleY;
        if (dThetaY > Math.PI) dThetaY -= Math.PI * 2;
        if (dThetaY < -Math.PI) dThetaY += Math.PI * 2;
        this.explorerGroup.rotation.y += dThetaY * 1.5;

        // Rotation autour de X (pitch vertical) basé sur l'angle XY
        const prevAngleX = Math.atan2(prevVector.y, prevVector.x);
        const currAngleX = Math.atan2(currVector.y, currVector.x);
        let dThetaX = currAngleX - prevAngleX;
        if (dThetaX > Math.PI) dThetaX -= Math.PI * 2;
        if (dThetaX < -Math.PI) dThetaX += Math.PI * 2;
        this.explorerGroup.rotation.x -= dThetaX * 1.2;
        this.explorerGroup.rotation.x = THREE.MathUtils.clamp(this.explorerGroup.rotation.x, -Math.PI / 3, Math.PI / 3);
      }

      this.lastTwoPos0 = p0.clone();
      this.lastTwoPos1 = p1.clone();
      this.lastTwoDist = dist;

      // Réinitialiser le drag monopoint
      if (this.dragNode) {
        this.dragNode.dragging = false;
        this.dragNode = null;
      }
      this.dragStartPos = null;

      for (const n of this.nodes) n.setHover(false);
      if (this.backNode) this.backNode.hovered = false;
      if (this.trashZone) this.trashZone.hovered = false;
      return;
    }

    // Réinitialiser les états 2 mains si non pincés simultanément
    this.lastTwoPos0 = null;
    this.lastTwoPos1 = null;
    this.lastTwoDist = null;

    // ── INTERACTION MONO-MAIN (SÉLECTION / GLISSER) ──
    const handWorldPos = p0 || p1;
    const isPinched = p0 ? pinched0 : pinched1;

    if (!handWorldPos) {
      if (this.wasHandActive) {
        for (const n of this.nodes) n.setHover(false);
        if (this.backNode) this.backNode.hovered = false;
        if (this.trashZone) this.trashZone.hovered = false;
        this.wasHandActive = false;
      }
      return;
    }

    this.wasHandActive = true;

    const activeLevel = this.activeLevels[this.activeLevels.length - 1];
    if (!activeLevel) return;

    // Projection de la position 3D de la main pour faire du Raycasting 2D/3D précis
    const ndc = handWorldPos.clone().project(this.camera);
    const ndc2d = new THREE.Vector2(ndc.x, ndc.y);
    this.raycaster.setFromCamera(ndc2d, this.camera);

    // 1. Détecter l'élément sous la main
    let closestNode: SpatialNode | null = null;
    const targets: THREE.Object3D[] = [];
    for (const n of activeLevel.nodes) {
      targets.push(n.mesh);
      targets.push(n.label);
    }
    const intersects = this.raycaster.intersectObjects(targets);
    if (intersects.length > 0) {
      const hitObj = intersects[0].object;
      closestNode = activeLevel.nodes.find(n => n.mesh === hitObj || n.label === hitObj) || null;
    }

    // 2. Détecter le bouton RETOUR sous la main
    let backHovered = false;
    if (this.backNode) {
      const backIntersects = this.raycaster.intersectObjects([this.backNode.mesh, this.backNode.label]);
      backHovered = backIntersects.length > 0;
      this.backNode.hovered = backHovered;
    }

    // 3. Détecter la corbeille sous la main
    let trashHovered = false;
    if (this.trashZone) {
      const trashIntersects = this.raycaster.intersectObjects([
        this.trashZone.mesh,
        this.trashZone.label,
        this.trashZone.hitMesh
      ]);
      trashHovered = trashIntersects.length > 0;
      this.trashZone.hovered = trashHovered;
    }

    for (const n of this.nodes) n.setHover(false);

    if (this.dragNode && isPinched) {
      this.dragNode.group.position.lerp(handWorldPos, 0.3);

      // Pour le survol des dossiers pendant le drag
      const folderTargets: THREE.Object3D[] = [];
      const foldersList = activeLevel.nodes.filter(n => n.item.type === 'folder' && n !== this.dragNode);
      for (const n of foldersList) {
        targets.push(n.mesh);
        targets.push(n.label);
      }
      const dragIntersects = this.raycaster.intersectObjects(folderTargets);
      if (dragIntersects.length > 0) {
        const hitObj = dragIntersects[0].object;
        const hitNode = foldersList.find(n => n.mesh === hitObj || n.label === hitObj);
        if (hitNode) hitNode.setHover(true);
      }
      return;
    }

    if (this.dragNode && !isPinched) {
      this._handleDrop(handWorldPos);
      return;
    }

    if (closestNode && !backHovered && !trashHovered) {
      closestNode.setHover(true);
    }

    if (isPinched && !this.dragNode) {
      if (backHovered && this.backNode) {
        this.navigateBack();
        return;
      }

      if (trashHovered && this.trashZone) {
        this.loadDirectory('corbeille');
        return;
      }

      if (closestNode) {
        if (closestNode.item.type === 'folder') {
          this.loadDirectory(closestNode.item.path);
        } else {
          this.dragNode = closestNode;
          this.dragNode.dragging = true;
          this.dragStartPos = closestNode.group.position.clone();
        }
      }
    }
  }

  private _handleDrop(_dropPos: THREE.Vector3) {
    if (!this.dragNode) return;
    const draggedItem = this.dragNode.item;

    // 1. Déplacer dans la pyramide de retour (RETOUR) pour remonter au dossier parent
    if (this.backNode && this.backNode.hovered) {
      if (this.parentPath && this.parentPath !== this.currentPath) {
        this._send('move', {
          source_path: draggedItem.path,
          dest_path: this.parentPath,
        });
        this._resetDrag();
        return;
      }
    }

    // 2. Déplacer dans n'importe quel dossier visible actuellement survolé (actif ou parent)
    const hoveredFolder = this.nodes.find(node => node.item.type === 'folder' && node.hovered);
    if (hoveredFolder) {
      let destPath = hoveredFolder.item.path;
      
      // Si on dépose sur le dossier parent qui représente notre niveau actif actuel (ex: "Perso" alors qu'on est dedans),
      // cela signifie qu'on souhaite l'éjecter vers son dossier parent physique du dessus (parentPath).
      if (destPath === this.currentPath && this.parentPath) {
        destPath = this.parentPath;
      }

      this._send('move', {
        source_path: draggedItem.path,
        dest_path: destPath,
      });
      this._resetDrag();
      return;
    }

    // 3. Déplacer dans la corbeille si survolée
    if (this.trashZone && this.trashZone.hovered) {
      this._send('delete', { path: draggedItem.path });
      this._resetDrag();
      return;
    }

    // Annulation du déplacement : retour à la position d'origine
    if (this.dragStartPos) {
      this.dragNode.group.position.copy(this.dragStartPos);
    }
    this._resetDrag();
  }

  private _resetDrag() {
    if (this.dragNode) {
      this.dragNode.dragging = false;
      this.dragNode = null;
    }
    this.dragStartPos = null;
    if (this.trashZone) this.trashZone.hovered = false;

    // Réinitialiser le survol sur tous les dossiers visibles
    for (const n of this.nodes) {
      n.setHover(false);
    }
  }

  handleQuickPinch(handWorldPos: THREE.Vector3) {
    if (!this._active) return;
    
    const activeLevel = this.activeLevels[this.activeLevels.length - 1];
    if (!activeLevel) return;

    for (const node of activeLevel.nodes) {
      const d = handWorldPos.distanceTo(node.group.position);
      if (d < 0.8 && node.item.type === 'file') {
        this._send('open', { path: node.item.path });
        return;
      }
    }
  }

  // ── Frame Update Loop ─────────────────────────────────────

  update(dt: number) {
    if (!this._active) return;
    const time = performance.now() / 1000;

    // 1. Mettre à jour et glisser-animer tous les niveaux empilés
    const activeLevel = this.activeLevels[this.activeLevels.length - 1];
    const activeBaseRadius = activeLevel ? activeLevel.baseRadius : 1.1;

    for (let lIdx = 0; lIdx < this.activeLevels.length; lIdx++) {
      const lvl = this.activeLevels[lIdx];

      // Calculer dynamiquement la profondeur par rapport au niveau actif
      const depth = this.activeLevels.length - 1 - lIdx;
      
      let targetRadius = activeBaseRadius;
      let targetOpacity = 1.0;

      if (depth === 0) {
        targetRadius = lvl.baseRadius;
        targetOpacity = 1.0;
      } else if (depth === 1) {
        // Cercle parent extérieur avec un espacement radial garanti de 2.2 unités (taille demandée)
        targetRadius = activeBaseRadius + 2.2;
        targetOpacity = 0.40;
      } else {
        // Cercle grand-parent encore plus extérieur
        targetRadius = activeBaseRadius + 4.2;
        targetOpacity = 0.15;
      }

      // Convertir le rayon cible en facteur multiplicateur pour le lerp
      lvl.targetRadiusFactor = targetRadius / lvl.baseRadius;
      lvl.targetOpacity = targetOpacity;

      // Lerp smooth sur le rayon et l'opacité
      lvl.currentRadiusFactor += (lvl.targetRadiusFactor - lvl.currentRadiusFactor) * dt * 4;
      lvl.currentOpacity += (lvl.targetOpacity - lvl.currentOpacity) * dt * 4;

      // Décalage de profondeur 3D (Z) extrêmement léger pour maintenir la concentricité parfaite
      const depthOffset = (lvl.currentRadiusFactor - 1.0) * -0.08; 
      const scaleFactor = Math.max(0.70, 1.0 / Math.pow(lvl.currentRadiusFactor, 0.15)); // Échelle très lisible

      // Décalage de hauteur (Y) pour créer un effet étagé / tiered hologram
      const yOffset = (lvl.currentRadiusFactor - 1.0) * -0.40;

      for (const node of lvl.nodes) {
        // Dilatation spatiale avec effet de recul dans la profondeur
        node.group.position.x = node.originalPosition.x * lvl.currentRadiusFactor;
        node.group.position.y = node.originalPosition.y * lvl.currentRadiusFactor + yOffset;
        node.group.position.z = node.originalPosition.z * lvl.currentRadiusFactor + depthOffset;

        // Réduction d'échelle physique pour les niveaux parents périphérique pour libérer l'espace
        node.group.scale.setScalar(scaleFactor);

        node.update(dt, time);

        // Opacités dynamiques selon le niveau (fade-out contextuel)
        if (node.mesh && node.mesh.material) {
          const baseOpacity = node.item.type === 'folder' ? 0.12 : 0.35;
          (node.mesh.material as THREE.MeshBasicMaterial).opacity = baseOpacity * lvl.currentOpacity;
        }
        if (node.wireframe && node.wireframe.material) {
          (node.wireframe.material as THREE.LineBasicMaterial).opacity = 0.7 * lvl.currentOpacity;
        }
        if (node.label && node.label.material) {
          const baseLabelOpacity = node.hovered ? 1.0 : 0.7;
          (node.label.material as THREE.SpriteMaterial).opacity = baseLabelOpacity * lvl.currentOpacity;
        }

        // Lueur
        for (const child of node.group.children) {
          if (child instanceof THREE.Sprite && child !== node.label) {
            (child.material as THREE.SpriteMaterial).opacity = 0.6 * lvl.currentOpacity;
          }
        }
      }

      // Mettre à jour l'anneau orbital holographique
      if (lvl.ring) {
        lvl.ring.scale.setScalar(lvl.currentRadiusFactor);
        lvl.ring.position.set(0, yOffset, depthOffset);
        
        const isParent = lvl.targetRadiusFactor > 1.0;
        const ringOpacity = isParent ? 0.12 : 0.3;
        (lvl.ring.material as THREE.LineBasicMaterial).opacity = ringOpacity * lvl.currentOpacity;

        const ringColor = isParent ? 0x0088cc : 0x00e5ff;
        (lvl.ring.material as THREE.LineBasicMaterial).color.setHex(ringColor);
      }

      // 2. Animer les traits de flux reliant ce niveau à son parent
      if (lvl.parentNode && lvl.lines.length > 0) {
        const parentPos = lvl.parentNode.group.position;

        for (let i = 0; i < lvl.nodes.length; i++) {
          const childNode = lvl.nodes[i];
          const line = lvl.lines[i];

          if (line) {
            (line.material as THREE.LineBasicMaterial).opacity = 0.25 * lvl.currentOpacity;

            const posAttr = line.geometry.getAttribute('position') as THREE.BufferAttribute;
            posAttr.setXYZ(0, childNode.group.position.x, childNode.group.position.y, childNode.group.position.z);
            posAttr.setXYZ(1, parentPos.x, parentPos.y, parentPos.z);
            posAttr.needsUpdate = true;
          }
        }
      }
    }

    if (this.backNode) this.backNode.update(dt, time);
    if (this.trashZone) this.trashZone.update(dt, time);
  }

  destroy() {
    this.deactivate();
    window.removeEventListener('click', this._onMouseClick);
    window.removeEventListener('mousedown', this._onMouseDown);
    window.removeEventListener('mousemove', this._onMouseMove);
    window.removeEventListener('mouseup', this._onMouseUp);
    window.removeEventListener('contextmenu', this._onContextMenu);
  }
}

