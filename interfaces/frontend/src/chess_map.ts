import * as THREE from 'three';

// Interface pour suivre l'état d'un déplacement de pièce
interface PieceAnimation {
  pieceMesh: THREE.Group;
  fromPos: THREE.Vector3;
  toPos: THREE.Vector3;
  progress: number;
  duration: number; // en secondes
  isLeap: boolean; // Les Cavaliers font des sauts en cloche
  capturedMesh?: THREE.Group;
  capturedSquare?: string;
  capturingColor?: string;
}

// Interface pour les particules lors d'une capture
interface ChessParticle {
  mesh: THREE.Mesh;
  velocity: THREE.Vector3;
  life: number; // de 1.0 à 0.0
  decay: number;
}

// Interface pour l'animation de disparition d'une pièce capturée
interface CapturedPieceAnimation {
  mesh: THREE.Group;
  duration: number; // en secondes
  progress: number;
}

// Interface pour les ondes de choc lors d'une capture
interface ChessShockwave {
  mesh: THREE.Mesh;
  maxRadius: number;
  life: number; // de 1.0 à 0.0
  decay: number;
}

export class ChessMap {
  public active: boolean = false;
  private scene: THREE.Scene;
  private camera: THREE.Camera;
  private ws: WebSocket;
  private group: THREE.Group;

  // Références Three.js
  private boardGroup: THREE.Group | null = null;
  private piecesGroup: THREE.Group | null = null;
  private particlesGroup: THREE.Group | null = null;
  private boardSquares: THREE.Mesh[] = [];

  // Dictionnaire des pièces 3D indexé par nom de case (ex: "e2", "f3")
  private piecesMap: Map<string, THREE.Group> = new Map();

  // Animations actives
  private animations: PieceAnimation[] = [];
  private particles: ChessParticle[] = [];
  private dyingPieces: CapturedPieceAnimation[] = [];
  private shockwaves: ChessShockwave[] = [];
  private checkFloatingText: THREE.Mesh | null = null;
  private gameOverTextMesh: THREE.Mesh | null = null;
  private floatingTime: number = 0;

  // Mémorisation de la caméra avant activation
  private savedCameraPos: THREE.Vector3 = new THREE.Vector3();
  private savedCameraLookAt: THREE.Vector3 = new THREE.Vector3();

  // Géométries partagées (mémorisées pour éviter les recalculs)
  private geometries: Map<string, THREE.BufferGeometry> = new Map();
  // Matériaux partagés
  private materials: Map<string, THREE.Material> = new Map();

  // Indicateur visuel d'échec
  private checkHighlight: THREE.Mesh | null = null;
  private checkSquareName: string | null = null;
  private checkPulseTime: number = 0;
  private chessLight: THREE.DirectionalLight | null = null;

  // Chronomètres de jeu (Blitz 10 minutes)
  private whiteTime: number = 600;
  private blackTime: number = 600;
  private isGameTimerActive: boolean = false;

  // Setup configuration state
  private gameStarted: boolean = false;
  private useTimer: boolean = false;

  // Mouse interaction state
  private legalMoves: string[] = [];
  private currentTurn: string = "white";
  private selectedSquare: string | null = null;
  private selectionHighlight: THREE.Mesh | null = null;
  private legalMoveHighlights: THREE.Mesh[] = [];
  private raycaster: THREE.Raycaster = new THREE.Raycaster();
  private hoverHighlight: THREE.Mesh | null = null;
  private hoveredSquare: string | null = null;
  private isThinking: boolean = false;
  private thinkingPulseTime: number = 0;

  // Rotation & Hand tracking state
  private isRotating: boolean = false;
  private previousMousePosition = { x: 0, y: 0 };
  private lastTwoPos0: THREE.Vector3 | null = null;
  private lastTwoPos1: THREE.Vector3 | null = null;
  private lastTwoDist: number | null = null;
  private wasHandActive: boolean = false;
  private wasHandPinched: boolean = false;

  // Last move highlights
  private lastMoveHighlights: THREE.Group[] = [];
  private playerColor: string = "white";

  // Boutons 3D de contrôle et de suivi de main
  private uiButtonsGroup: THREE.Group | null = null;
  private startButton3d: THREE.Mesh | null = null;
  private resetButton3d: THREE.Mesh | null = null;
  private quitButton3d: THREE.Mesh | null = null;


  constructor(scene: THREE.Scene, camera: THREE.Camera, ws: WebSocket) {
    this.scene = scene;
    this.camera = camera;
    this.ws = ws;
    this.group = new THREE.Group();
    this.group.name = "chess_map_group";

    // Initialiser les géométries procédurales réalistes (Staunton style)
    this.initPieceGeometries();
    this.initMaterials();
  }

  // Activer la carte d'échecs
  public activate(): void {
    if (this.active) return;
    this.active = true;

    // Masquer les autres éléments du HUD si possible
    this.scene.traverse((child) => {
      if (child.name === "domotic_group" || child.name === "cortex_group" || child.name === "explorer_group") {
        child.visible = false;
      }
    });

    // Sauvegarder la position caméra actuelle
    this.savedCameraPos.copy(this.camera.position);

    // Ajouter le groupe principal à la scène
    this.scene.add(this.group);

    // Ajouter une lumière spécifique pour détacher les reliefs 3D des pièces
    this.chessLight = new THREE.DirectionalLight(0xffffff, 1.2);
    this.chessLight.position.set(2, 6, 3);
    this.group.add(this.chessLight);

    // Construire le plateau
    this.buildBoard();

    // Groupes pour pièces et effets
    this.piecesGroup = new THREE.Group();
    this.particlesGroup = new THREE.Group();
    this.group.add(this.piecesGroup);
    this.group.add(this.particlesGroup);

    // Ajuster la caméra pour les échecs (angle de vue optimal)
    this.animateCameraToChessView();

    // Mouse listener
    window.addEventListener('mousedown', this._onMouseDown);
    window.addEventListener('mouseup', this._onMouseUp);
    window.addEventListener('mousemove', this._onMouseMove);
    window.addEventListener('contextmenu', this._onContextMenu);

    // Afficher le panel HUD échecs et connecter les boutons
    const panel = document.getElementById('holo-chess-panel');
    if (panel) {
      panel.style.display = 'flex';
    }

    // Initialiser en état configuration
    this.gameStarted = false;
    this.useTimer = false;
    this.isGameTimerActive = false;

    const setupContainer = document.getElementById('chess-setup-container');
    if (setupContainer) {
      setupContainer.style.display = 'block';
    }

    const timerContainer = document.getElementById('chess-timer-container');
    if (timerContainer) {
      timerContainer.style.display = 'none';
    }

    const stateEl = document.getElementById('chess-meta-state');
    if (stateEl) {
      stateEl.textContent = "CONFIGURATION";
      stateEl.style.color = "#ff8c00";
    }

    const turnEl = document.getElementById('chess-meta-turn');
    if (turnEl) {
      turnEl.textContent = "EN ATTENTE // SETUP";
      turnEl.style.color = "rgba(0, 229, 255, 0.5)";
    }

    const logEl = document.getElementById('chess-log-text');
    if (logEl) {
      logEl.textContent = "Veuillez configurer et démarrer la partie pour commencer à jouer.";
    }

    // Construire les boutons 3D de contrôle interactifs (main et souris)
    this.build3dButtons();

    const startBtn = document.getElementById('chess-start-game-btn');
    const timerSelect = document.getElementById('chess-config-timer') as HTMLSelectElement | null;
    const diffSelect = document.getElementById('chess-config-difficulty') as HTMLSelectElement | null;
    const colorSelect = document.getElementById('chess-config-color') as HTMLSelectElement | null;

    if (startBtn) {
      startBtn.onclick = () => {
        const useTimerVal = timerSelect ? timerSelect.value : 'no';
        const difficulty = diffSelect ? diffSelect.value : '1000';
        const playerColor = colorSelect ? colorSelect.value : 'white';
        this.startFromConfig(difficulty, playerColor, useTimerVal === 'yes');

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          console.log("[CHESS] Commande reset envoyée");
          this.ws.send(JSON.stringify({
            type: "chess_action",
            action: "start",
            difficulty: difficulty,
            player_color: playerColor,
            use_timer: useTimerVal
          }));
        }
      };
    }

    const resetBtn = document.getElementById('chess-reset-btn');
    if (resetBtn) {
      resetBtn.onclick = () => {
        this.resetGame(false);
      };
    }

    const stopBtn = document.getElementById('chess-stop-btn');
    if (stopBtn) {
      stopBtn.onclick = () => {
        // Ferme la vue 3D (la partie est arrêtée côté backend), retour à JARVIS
        (window as any)._fermerVues3D?.();
      };
    }
  }

  // --- MÉTHODES DE CONTRÔLE 3D ET GESTUEL ---

  private build3dButtons(): void {
    if (this.uiButtonsGroup) {
      this.group.remove(this.uiButtonsGroup);
      this.uiButtonsGroup = null;
    }

    this.uiButtonsGroup = new THREE.Group();
    this.uiButtonsGroup.name = "chess_ui_buttons";
    this.group.add(this.uiButtonsGroup);

    // 1. Bouton DÉMARRER
    this.startButton3d = this.create3dButton("DEMARRER", "#00ff88");
    this.startButton3d.userData = { action: "start" };
    this.uiButtonsGroup.add(this.startButton3d);

    // 2. Bouton RECOMMENCER
    this.resetButton3d = this.create3dButton("RECOMMENCER", "#ff8a1a");
    this.resetButton3d.userData = { action: "reset" };
    this.uiButtonsGroup.add(this.resetButton3d);

    // 3. Bouton QUITTER
    this.quitButton3d = this.create3dButton("QUITTER", "#ff2e4d");
    this.quitButton3d.userData = { action: "quit" };
    this.uiButtonsGroup.add(this.quitButton3d);

    this.update3dButtonsVisibility();
    this.reposition3dButtons();
  }

  private reposition3dButtons(): void {
    if (!this.startButton3d || !this.resetButton3d || !this.quitButton3d) return;

    if (this.playerColor === 'black') {
      // Pour les noirs (le plateau est pivoté de 180° autour de Y)
      // On positionne à X = +5.1 local (qui tourne à X = -5.1 dans le monde)
      // On compense la rotation de 180° du parent en tournant de -5 * Math.PI / 6
      this.startButton3d.position.set(5.1, 0.05, -0.8);
      this.startButton3d.rotation.y = -5 * Math.PI / 6;

      this.resetButton3d.position.set(5.1, 0.05, -0.8);
      this.resetButton3d.rotation.y = -5 * Math.PI / 6;

      this.quitButton3d.position.set(5.1, 0.05, 0.8);
      this.quitButton3d.rotation.y = -5 * Math.PI / 6;
    } else {
      // Pour les blancs (le plateau est en rotation Y = 0)
      // On positionne à X = -5.1 local (qui reste X = -5.1 dans le monde)
      this.startButton3d.position.set(-5.1, 0.05, 0.8);
      this.startButton3d.rotation.y = Math.PI / 6;

      this.resetButton3d.position.set(-5.1, 0.05, 0.8);
      this.resetButton3d.rotation.y = Math.PI / 6;

      this.quitButton3d.position.set(-5.1, 0.05, -0.8);
      this.quitButton3d.rotation.y = Math.PI / 6;
    }
  }

  private update3dButtonsVisibility(): void {
    if (this.startButton3d) {
      this.startButton3d.visible = !this.gameStarted;
    }
    if (this.resetButton3d) {
      this.resetButton3d.visible = this.gameStarted;
    }
    if (this.quitButton3d) {
      this.quitButton3d.visible = true;
    }
  }

  private create3dButton(text: string, color: string): THREE.Mesh {
    const canvas = document.createElement('canvas');
    canvas.width = 384;
    canvas.height = 96;
    const ctx = canvas.getContext('2d')!;

    // Fond sombre semi-transparent
    ctx.fillStyle = 'rgba(0, 8, 20, 0.85)';
    ctx.fillRect(0, 0, 384, 96);

    // Bordure néon
    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, 380, 92);

    // Texte avec effet néon
    ctx.font = 'bold 36px monospace';
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = color;
    ctx.shadowBlur = 10;
    ctx.fillText(text, 192, 48);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;

    const geom = new THREE.PlaneGeometry(1.2, 0.3);
    const mat = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      side: THREE.DoubleSide
    });

    const mesh = new THREE.Mesh(geom, mat);
    mesh.rotation.order = 'YXZ'; // Rotation Y (orientation) d'abord, puis X (inclinaison)
    mesh.rotation.x = -Math.PI / 5; // Penché face à la caméra
    mesh.userData = { geometry: geom, material: mat, texture: texture };
    return mesh;
  }

  private check3dButtonHitFromEvent(e: MouseEvent): string | null {
    const canvas = document.getElementById('holo-three-canvas');
    if (!canvas) return null;

    const rect = canvas.getBoundingClientRect();
    const mouse = new THREE.Vector2();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    this.camera.updateMatrixWorld(true);
    this.raycaster.setFromCamera(mouse, this.camera);

    if (this.uiButtonsGroup) {
      const activeButtons = this.uiButtonsGroup.children.filter(child => child.visible);
      const intersects = this.raycaster.intersectObjects(activeButtons, true);
      if (intersects.length > 0) {
        let curr: THREE.Object3D | null = intersects[0].object;
        while (curr && curr !== this.scene) {
          if (curr.userData && curr.userData.action) {
            return curr.userData.action;
          }
          curr = curr.parent;
        }
      }
    }
    return null;
  }

  private check3dButtonHitFromWorldPos(worldPos: THREE.Vector3): string | null {
    this.camera.updateMatrixWorld(true);
    const direction = worldPos.clone().sub(this.camera.position).normalize();
    this.raycaster.set(this.camera.position, direction);

    if (this.uiButtonsGroup) {
      const activeButtons = this.uiButtonsGroup.children.filter(child => child.visible);
      const intersects = this.raycaster.intersectObjects(activeButtons, true);
      if (intersects.length > 0) {
        let curr: THREE.Object3D | null = intersects[0].object;
        while (curr && curr !== this.scene) {
          if (curr.userData && curr.userData.action) {
            return curr.userData.action;
          }
          curr = curr.parent;
        }
      }
    }
    return null;
  }

  private trigger3dButtonAction(action: string): void {
    console.log("[CHESS 3D BUTTON] Action déclenchée:", action);
    if (action === "start") {
      const startBtn = document.getElementById('chess-start-game-btn');
      if (startBtn) startBtn.click();
    } else if (action === "reset") {
      const resetBtn = document.getElementById('chess-reset-btn');
      if (resetBtn) resetBtn.click();
    } else if (action === "quit") {
      const stopBtn = document.getElementById('chess-stop-btn');
      if (stopBtn) stopBtn.click();
    }
  }

  public startFromConfig(difficulty: string, playerColor: string, useTimer: boolean): void {
    const setupContainer = document.getElementById('chess-setup-container');
    this.useTimer = useTimer;
    this.gameStarted = true;
    this.playerColor = playerColor;

    // Orienter le plateau en fonction de la couleur
    if (playerColor === 'black') {
      this.group.rotation.y = Math.PI;
    } else {
      this.group.rotation.y = 0;
    }

    if (setupContainer) {
      setupContainer.style.display = 'none';
    }

    const timerContainer = document.getElementById('chess-timer-container');
    if (timerContainer) {
      timerContainer.style.display = this.useTimer ? 'flex' : 'none';
    }

    if (this.useTimer) {
      this.whiteTime = 600;
      this.blackTime = 600;
      this.isGameTimerActive = true;
      this.updateTimerUI();
    } else {
      this.isGameTimerActive = false;
    }

    const stateEl = document.getElementById('chess-meta-state');
    if (stateEl) {
      stateEl.textContent = "ACTIVE";
      stateEl.style.color = "#00ff88";
    }

    const turnEl = document.getElementById('chess-meta-turn');
    if (turnEl) {
      if (playerColor === 'black') {
        turnEl.textContent = "TOUR DE JARVIS // BLANC";
        turnEl.style.color = "#ff3264";
      } else {
        turnEl.textContent = "VOTRE TOUR // BLANC";
        turnEl.style.color = "#00e5ff";
      }
    }

    const logEl = document.getElementById('chess-log-text');
    if (logEl) {
      if (playerColor === 'black') {
        logEl.textContent = "Partie lancée. JARVIS (Blanc) réfléchit à son premier coup...";
      } else {
        logEl.textContent = "Partie lancée. Sélectionnez une pièce blanche (cyan) et déplacez-la sur un cercle vert.";
      }
    }

    this.update3dButtonsVisibility();
    this.reposition3dButtons();
  }

  public resetGame(force: boolean = false): void {
    const setupContainer = document.getElementById('chess-setup-container');


    this.gameStarted = false;
    this.useTimer = false;
    this.isGameTimerActive = false;
    this.clearSelection();
    this.clearLastMoveHighlights();
    this.updateHistoryUI([]);
    
    // Réinitialiser les transformations de la scène
    this.group.rotation.set(0, 0, 0);
    this.group.scale.set(1, 1, 1);
    this.group.position.set(0, 0, 0);
    this.playerColor = "white";

    if (setupContainer) {
      setupContainer.style.display = 'block';
    }

    const timerContainer = document.getElementById('chess-timer-container');
    if (timerContainer) {
      timerContainer.style.display = 'none';
    }

    const stateEl = document.getElementById('chess-meta-state');
    if (stateEl) {
      stateEl.textContent = "CONFIGURATION";
      stateEl.style.color = "#ff8c00";
    }

    const turnEl = document.getElementById('chess-meta-turn');
    if (turnEl) {
      turnEl.textContent = "EN ATTENTE // SETUP";
      turnEl.style.color = "rgba(0, 229, 255, 0.5)";
    }

    const logEl = document.getElementById('chess-log-text');
    if (logEl) {
      logEl.textContent = "Veuillez configurer et démarrer la partie pour commencer à jouer.";
    }

    if (!force && this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log("[CHESS] Commande reset envoyée");
      this.ws.send(JSON.stringify({
        type: "chess_action",
        action: "reset"
      }));
    }

    // Nettoyer les animations et pièces
    this.animations.forEach((anim) => {
      if (anim.capturedMesh) {
        this.piecesGroup?.remove(anim.capturedMesh);
        anim.capturedMesh.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.geometry.dispose();
            if (Array.isArray(child.material)) {
              child.material.forEach((mat) => mat.dispose());
            } else {
              child.material.dispose();
            }
          }
        });
      }
    });
    this.animations = [];

    this.dyingPieces.forEach((anim) => {
      this.piecesGroup?.remove(anim.mesh);
      anim.mesh.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose();
          if (Array.isArray(child.material)) {
            child.material.forEach((mat) => mat.dispose());
          } else {
            child.material.dispose();
          }
        }
      });
    });
    this.dyingPieces = [];
    this.particles = [];

    this.update3dButtonsVisibility();
    this.reposition3dButtons();
  }


  // Désactiver la carte d'échecs
  public deactivate(): void {
    if (!this.active) return;
    this.active = false;

    // Restaurer les autres éléments
    this.scene.traverse((child) => {
      if (child.name === "domotic_group" || child.name === "cortex_group") {
        child.visible = true;
      }
    });

    // Nettoyer
    if (this.chessLight) {
      this.group.remove(this.chessLight);
      this.chessLight = null;
    }
    this.isGameTimerActive = false;
    this.clearAll();
    this.scene.remove(this.group);

    // Restaurer la position caméra
    this.camera.position.copy(this.savedCameraPos);
    this.camera.lookAt(0, 0, 0);

    // Mouse listener
    window.removeEventListener('mousedown', this._onMouseDown);
    window.removeEventListener('mouseup', this._onMouseUp);
    window.removeEventListener('mousemove', this._onMouseMove);
    window.removeEventListener('contextmenu', this._onContextMenu);

    // Masquer le panel HUD échecs
    const panel = document.getElementById('holo-chess-panel');
    if (panel) {
      panel.style.display = 'none';
    }
  }


  // Nettoyer le plateau
  private clearAll(): void {
    this.clearLastMoveHighlights();
    this.boardSquares = [];
    this.piecesMap.forEach((mesh) => {
      this.piecesGroup?.remove(mesh);
    });
    this.piecesMap.clear();

    // Libérer les capturedMesh en attente dans les animations actives
    this.animations.forEach((anim) => {
      if (anim.capturedMesh) {
        this.piecesGroup?.remove(anim.capturedMesh);
        anim.capturedMesh.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.geometry.dispose();
            if (Array.isArray(child.material)) {
              child.material.forEach((mat) => mat.dispose());
            } else {
              child.material.dispose();
            }
          }
        });
      }
    });
    this.animations = [];

    this.dyingPieces.forEach((anim) => {
      this.piecesGroup?.remove(anim.mesh);
      anim.mesh.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose();
          if (Array.isArray(child.material)) {
            child.material.forEach((mat) => mat.dispose());
          } else {
            child.material.dispose();
          }
        }
      });
    });
    this.dyingPieces = [];
    this.particles = [];

    if (this.boardGroup) {
      this.boardGroup.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose();
          if (child.material) {
            if (Array.isArray(child.material)) {
              child.material.forEach((mat) => {
                if ((mat as any).map) (mat as any).map.dispose();
                mat.dispose();
              });
            } else {
              if ((child.material as any).map) (child.material as any).map.dispose();
              child.material.dispose();
            }
          }
        }
      });
      this.group.remove(this.boardGroup);
    }

    if (this.uiButtonsGroup) {
      this.uiButtonsGroup.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose();
          if (child.material) {
            if (Array.isArray(child.material)) {
              child.material.forEach(mat => mat.dispose());
            } else {
              child.material.dispose();
            }
          }
          if (child.userData?.texture) {
            child.userData.texture.dispose();
          }
        }
      });
      this.group.remove(this.uiButtonsGroup);
      this.uiButtonsGroup = null;
      this.startButton3d = null;
      this.resetButton3d = null;
      this.quitButton3d = null;
    }

    if (this.piecesGroup) this.group.remove(this.piecesGroup);
    if (this.particlesGroup) this.group.remove(this.particlesGroup);
    this.boardGroup = null;
    this.piecesGroup = null;
    this.particlesGroup = null;
    this.checkHighlight = null;
    this.clearCheckHighlight();
    this.hideGameOverText();

    // Nettoyer les ondes de choc
    this.shockwaves.forEach((sw) => {
      this.group.remove(sw.mesh);
      sw.mesh.geometry.dispose();
      (sw.mesh.material as THREE.Material).dispose();
    });
    this.shockwaves = [];

    this.clearSelection();
    if (this.hoverHighlight) {
      this.group.remove(this.hoverHighlight);
      this.hoverHighlight.geometry.dispose();
      (this.hoverHighlight.material as THREE.Material).dispose();
      this.hoverHighlight = null;
    }
    this.hoveredSquare = null;
  }


  // Animer la caméra vers la vue d'échecs
  private animateCameraToChessView(): void {
    // Vue en plongée inclinée optimisée pour limiter la parallaxe et l'occlusion des pièces
    const targetPos = new THREE.Vector3(0, 8.2, 4.5);
    this.camera.position.copy(targetPos);
    this.camera.lookAt(new THREE.Vector3(0, -0.5, 0));
  }

  // Initialiser les géométries des pièces avec des contours Staunton réalistes, élancés et très typés
  private initPieceGeometries(): void {
    // 1. Pion (Pawn) - Profil classique compact
    const pawnPoints = [];
    pawnPoints.push(new THREE.Vector2(0.0, 0.0));
    pawnPoints.push(new THREE.Vector2(0.17, 0.0));
    pawnPoints.push(new THREE.Vector2(0.17, 0.04));
    pawnPoints.push(new THREE.Vector2(0.13, 0.07));
    pawnPoints.push(new THREE.Vector2(0.08, 0.22)); // Col resserré
    pawnPoints.push(new THREE.Vector2(0.12, 0.26)); // Collerette
    pawnPoints.push(new THREE.Vector2(0.10, 0.30));
    for (let i = 0; i <= 8; i++) {
      const angle = (i / 8) * Math.PI;
      const r = 0.09;
      const cx = 0.0;
      const cy = 0.39;
      pawnPoints.push(new THREE.Vector2(cx + r * Math.sin(angle), cy - r * Math.cos(angle)));
    }
    pawnPoints.push(new THREE.Vector2(0.0, 0.48));
    this.geometries.set('pawn', new THREE.LatheGeometry(pawnPoints, 24));

    // 2. Tour (Rook) - Créneaux massifs
    const rookPoints = [];
    rookPoints.push(new THREE.Vector2(0.0, 0.0));
    rookPoints.push(new THREE.Vector2(0.21, 0.0));
    rookPoints.push(new THREE.Vector2(0.21, 0.06));
    rookPoints.push(new THREE.Vector2(0.17, 0.10));
    rookPoints.push(new THREE.Vector2(0.14, 0.42)); // Corps robuste
    rookPoints.push(new THREE.Vector2(0.19, 0.48)); // Évasement créneaux
    rookPoints.push(new THREE.Vector2(0.19, 0.60)); // Créneaux
    rookPoints.push(new THREE.Vector2(0.14, 0.60));
    rookPoints.push(new THREE.Vector2(0.14, 0.52)); // Creux intérieur
    rookPoints.push(new THREE.Vector2(0.0, 0.52));
    this.geometries.set('rook', new THREE.LatheGeometry(rookPoints, 24));

    // 3. Cavalier (Knight) - Socle et Tête extrudée séparée (profil Staunton élancé)
    const knightBasePoints = [];
    knightBasePoints.push(new THREE.Vector2(0.0, 0.0));
    knightBasePoints.push(new THREE.Vector2(0.20, 0.0));
    knightBasePoints.push(new THREE.Vector2(0.20, 0.05));
    knightBasePoints.push(new THREE.Vector2(0.16, 0.10));
    knightBasePoints.push(new THREE.Vector2(0.12, 0.20));
    knightBasePoints.push(new THREE.Vector2(0.14, 0.22));
    knightBasePoints.push(new THREE.Vector2(0.0, 0.22));
    this.geometries.set('knight_base', new THREE.LatheGeometry(knightBasePoints, 24));

    const knightShape = new THREE.Shape();
    knightShape.moveTo(-0.02, 0.0);
    knightShape.lineTo(0.14, 0.0);
    knightShape.quadraticCurveTo(0.18, 0.14, 0.23, 0.25); // poitrine
    knightShape.lineTo(0.27, 0.30); // museau bas
    knightShape.lineTo(0.25, 0.35); // museau pointe
    knightShape.lineTo(0.18, 0.37); // nez
    knightShape.lineTo(0.08, 0.48); // front
    knightShape.lineTo(0.07, 0.55); // oreille 1
    knightShape.lineTo(0.04, 0.50);
    knightShape.lineTo(0.02, 0.55); // oreille 2
    knightShape.lineTo(0.0, 0.48);
    knightShape.quadraticCurveTo(-0.08, 0.25, -0.02, 0.0); // crinière

    const extrudeSettings = {
      depth: 0.08, // Épaisseur fine réaliste (Staunton) pour un profil élancé
      bevelEnabled: true,
      bevelSegments: 2,
      steps: 1,
      bevelSize: 0.01,
      bevelThickness: 0.01
    };
    const knightHeadGeom = new THREE.ExtrudeGeometry(knightShape, extrudeSettings);
    knightHeadGeom.center();
    this.geometries.set('knight_head', knightHeadGeom);

    // 4. Fou (Bishop) - Silhouette de mitre pointue à pompon
    const bishopPoints = [];
    bishopPoints.push(new THREE.Vector2(0.0, 0.0));
    bishopPoints.push(new THREE.Vector2(0.20, 0.0));
    bishopPoints.push(new THREE.Vector2(0.20, 0.05));
    bishopPoints.push(new THREE.Vector2(0.16, 0.10));
    bishopPoints.push(new THREE.Vector2(0.06, 0.40)); // Col resserré
    bishopPoints.push(new THREE.Vector2(0.13, 0.48)); // Base mitre
    bishopPoints.push(new THREE.Vector2(0.12, 0.68)); // Mitre
    bishopPoints.push(new THREE.Vector2(0.05, 0.74)); // Tête pointue
    for (let i = 0; i <= 6; i++) {
      const angle = (i / 6) * Math.PI;
      const r = 0.025; // Petit pompon supérieur
      const cx = 0.0;
      const cy = 0.765;
      bishopPoints.push(new THREE.Vector2(cx + r * Math.sin(angle), cy - r * Math.cos(angle)));
    }
    bishopPoints.push(new THREE.Vector2(0.0, 0.79));
    this.geometries.set('bishop', new THREE.LatheGeometry(bishopPoints, 24));

    // 5. Reine (Queen) - Base élancée, hauteur 0.95, couronne évasée
    const queenPoints = [];
    queenPoints.push(new THREE.Vector2(0.0, 0.0));
    queenPoints.push(new THREE.Vector2(0.22, 0.0));
    queenPoints.push(new THREE.Vector2(0.22, 0.06));
    queenPoints.push(new THREE.Vector2(0.18, 0.12));
    queenPoints.push(new THREE.Vector2(0.07, 0.58)); // Col élancé
    queenPoints.push(new THREE.Vector2(0.19, 0.80)); // Col évasé de la couronne
    queenPoints.push(new THREE.Vector2(0.13, 0.86)); // Sommet rentrant
    for (let i = 0; i <= 6; i++) {
      const angle = (i / 6) * Math.PI;
      const r = 0.045; // Finial sphérique supérieur
      const cx = 0.0;
      const cy = 0.905;
      queenPoints.push(new THREE.Vector2(cx + r * Math.sin(angle), cy - r * Math.cos(angle)));
    }
    queenPoints.push(new THREE.Vector2(0.0, 0.95));
    this.geometries.set('queen', new THREE.LatheGeometry(queenPoints, 24));

    // 6. Roi (King) - Le plus grand, hauteur 1.20, dôme élancé et croix massive
    const kingPoints = [];
    kingPoints.push(new THREE.Vector2(0.0, 0.0));
    kingPoints.push(new THREE.Vector2(0.24, 0.0));
    kingPoints.push(new THREE.Vector2(0.24, 0.07));
    kingPoints.push(new THREE.Vector2(0.19, 0.14));
    kingPoints.push(new THREE.Vector2(0.08, 0.65)); // Col élancé
    kingPoints.push(new THREE.Vector2(0.21, 0.95)); // Tête large en dôme
    kingPoints.push(new THREE.Vector2(0.12, 1.02)); // Sommet du dôme
    kingPoints.push(new THREE.Vector2(0.0, 1.02));
    this.geometries.set('king_body', new THREE.LatheGeometry(kingPoints, 24));
  }

  // Créer les matériaux holographiques néon optimisés avec ombrage diffus
  private initMaterials(): void {
    // Matériau pour les pièces blanches (Player) - Blanc porcelaine opaque avec fine lueur
    this.materials.set('white_piece', new THREE.MeshStandardMaterial({
      color: 0xffffff,
      emissive: 0x00e5ff,
      emissiveIntensity: 0.08, // Émission réduite pour révéler les ombres et reliefs 3D
      roughness: 0.22, // Plus mat pour de plus doux gradients de lumière
      metalness: 0.15, // Porcelaine solide, non-métal
      transparent: false
    }));

    // Matériau pour les pièces noires (JARVIS) - Noir obsidienne brillant avec fine lueur
    this.materials.set('black_piece', new THREE.MeshStandardMaterial({
      color: 0x151c24, // Légèrement plus clair pour détacher les ombres propres
      emissive: 0xff2e4d,
      emissiveIntensity: 0.08, // Émission réduite pour révéler les ombres et reliefs 3D
      roughness: 0.18,
      metalness: 0.25, // Réflectivité obsidienne naturelle
      transparent: false
    }));

    // Matériaux plats (flatShading) pour les pièces extrudées comme le Cavalier
    this.materials.set('white_piece_flat', new THREE.MeshStandardMaterial({
      color: 0xffffff,
      emissive: 0x00e5ff,
      emissiveIntensity: 0.08,
      roughness: 0.22,
      metalness: 0.15,
      flatShading: true,
      transparent: false
    }));

    this.materials.set('black_piece_flat', new THREE.MeshStandardMaterial({
      color: 0x151c24,
      emissive: 0xff2e4d,
      emissiveIntensity: 0.08,
      roughness: 0.18,
      metalness: 0.25,
      flatShading: true,
      transparent: false
    }));

    // Matériaux pour le plateau
    this.materials.set('square_light', new THREE.MeshBasicMaterial({
      color: 0x06254c,
      transparent: true,
      opacity: 0.55,
      side: THREE.DoubleSide
    }));

    this.materials.set('square_dark', new THREE.MeshBasicMaterial({
      color: 0x010b1a,
      transparent: true,
      opacity: 0.85,
      side: THREE.DoubleSide
    }));
  }

  // Dessine le plateau d'échecs 3D
  private buildBoard(): void {
    this.boardGroup = new THREE.Group();
    this.boardGroup.name = "chess_board";
    this.group.add(this.boardGroup);

    const size = 0.85; // Taille de chaque case
    const thickness = 0.04;

    const boxGeom = new THREE.BoxGeometry(size, thickness, size);
    const matLight = this.materials.get('square_light')!;
    const matDark = this.materials.get('square_dark')!;

    // Bords néon du plateau
    const borderMat = new THREE.LineBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.8 });

    const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
    this.boardSquares = []; // Réinitialiser le tableau des cases raycastables
    for (let r = 0; r < 8; r++) {
      for (let f = 0; f < 8; f++) {
        const isDark = (r + f) % 2 === 0;
        const squareMesh = new THREE.Mesh(boxGeom, isDark ? matDark : matLight);

        // Attacher les coordonnées de la case
        const sqName = files[f] + (r + 1);
        squareMesh.userData = { squareName: sqName };

        // Positionnement (centré autour de 0,0)
        const x = (f - 3.5) * size;
        const z = (3.5 - r) * size;
        squareMesh.position.set(x, -thickness / 2, z);


        // Lignes de contour néon
        const edges = new THREE.EdgesGeometry(boxGeom);
        const line = new THREE.LineSegments(edges, borderMat);
        line.raycast = () => {}; // Ne pas intersecter les contours filaires
        squareMesh.add(line);

        this.boardGroup.add(squareMesh);
        this.boardSquares.push(squareMesh); // Enregistrer la case pour le raycasting exclusif
      }
    }

    const boardSize = size * 8;

    // Contour solide (cadre) autour des cases pour plus de lisibilité des coordonnées
    const borderWidth = 0.65;
    const borderThickness = thickness;
    const frameMat = new THREE.MeshStandardMaterial({
      color: 0x12141a,      // Sleek dark graphite
      roughness: 0.45,
      metalness: 0.75,
      flatShading: true
    });

    // 1. Bordure bas (côté Blancs, Z positif)
    const bottomBorderGeom = new THREE.BoxGeometry(boardSize + borderWidth * 2, borderThickness, borderWidth);
    const bottomBorder = new THREE.Mesh(bottomBorderGeom, frameMat);
    bottomBorder.position.set(0, -thickness / 2, 4 * size + borderWidth / 2);
    bottomBorder.receiveShadow = true;
    bottomBorder.castShadow = true;
    bottomBorder.raycast = () => {};
    this.boardGroup.add(bottomBorder);

    // 2. Bordure haut (côté Noirs, Z négatif)
    const topBorderGeom = new THREE.BoxGeometry(boardSize + borderWidth * 2, borderThickness, borderWidth);
    const topBorder = new THREE.Mesh(topBorderGeom, frameMat);
    topBorder.position.set(0, -thickness / 2, -(4 * size + borderWidth / 2));
    topBorder.receiveShadow = true;
    topBorder.castShadow = true;
    topBorder.raycast = () => {};
    this.boardGroup.add(topBorder);

    // 3. Bordure gauche (X négatif)
    const leftBorderGeom = new THREE.BoxGeometry(borderWidth, borderThickness, boardSize);
    const leftBorder = new THREE.Mesh(leftBorderGeom, frameMat);
    leftBorder.position.set(-(4 * size + borderWidth / 2), -thickness / 2, 0);
    leftBorder.receiveShadow = true;
    leftBorder.castShadow = true;
    leftBorder.raycast = () => {};
    this.boardGroup.add(leftBorder);

    // 4. Bordure droite (X positif)
    const rightBorderGeom = new THREE.BoxGeometry(borderWidth, borderThickness, boardSize);
    const rightBorder = new THREE.Mesh(rightBorderGeom, frameMat);
    rightBorder.position.set(4 * size + borderWidth / 2, -thickness / 2, 0);
    rightBorder.receiveShadow = true;
    rightBorder.castShadow = true;
    rightBorder.raycast = () => {};
    this.boardGroup.add(rightBorder);

    // Contour néon intérieur (autour des cases actives)
    const innerGeom = new THREE.BoxGeometry(boardSize, thickness + 0.005, boardSize);
    const innerEdges = new THREE.EdgesGeometry(innerGeom);
    const innerLineMat = new THREE.LineBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.8 });
    const innerLine = new THREE.LineSegments(innerEdges, innerLineMat);
    innerLine.position.set(0, -thickness / 2, 0);
    innerLine.raycast = () => {};
    this.boardGroup.add(innerLine);

    // Contour néon extérieur complet (autour du cadre)
    const totalOuterSize = boardSize + borderWidth * 2;
    const outerFrameGeom = new THREE.BoxGeometry(totalOuterSize, thickness + 0.005, totalOuterSize);
    const outerFrameEdges = new THREE.EdgesGeometry(outerFrameGeom);
    const outerLineMat = new THREE.LineBasicMaterial({ color: 0x00aaff, transparent: true, opacity: 0.9 });
    const outerFrameLine = new THREE.LineSegments(outerFrameEdges, outerLineMat);
    outerFrameLine.position.set(0, -thickness / 2, 0);
    outerFrameLine.raycast = () => {};
    this.boardGroup.add(outerFrameLine);

    // Ajout de lettres/chiffres holographiques centrés sur la bordure extérieure
    const labelGeom = new THREE.PlaneGeometry(0.32, 0.32);
    const labelZ = 4 * size + borderWidth / 2; // Distance centrale de la bordure
    const labelX = 4 * size + borderWidth / 2;

    // Files: A-H
    for (let f = 0; f < 8; f++) {
      const fileChar = files[f].toUpperCase();
      const x = (f - 3.5) * size;

      // Bas (côté Blancs)
      const textureBottom = this.createTextTexture(fileChar);
      const matBottom = new THREE.MeshBasicMaterial({
        map: textureBottom,
        transparent: true,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending
      });
      const meshBottom = new THREE.Mesh(labelGeom, matBottom);
      meshBottom.rotation.x = -Math.PI / 2;
      meshBottom.position.set(x, 0.01, labelZ); // Légère élévation pour éviter le z-fighting
      this.boardGroup.add(meshBottom);

      // Haut (côté Noirs)
      const textureTop = this.createTextTexture(fileChar);
      const matTop = new THREE.MeshBasicMaterial({
        map: textureTop,
        transparent: true,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending
      });
      const meshTop = new THREE.Mesh(labelGeom, matTop);
      meshTop.rotation.x = -Math.PI / 2;
      meshTop.rotation.z = Math.PI;
      meshTop.position.set(x, 0.01, -labelZ);
      this.boardGroup.add(meshTop);
    }

    // Ranks: 1-8
    for (let r = 0; r < 8; r++) {
      const rankChar = (r + 1).toString();
      const z = (3.5 - r) * size;

      // Gauche
      const textureLeft = this.createTextTexture(rankChar);
      const matLeft = new THREE.MeshBasicMaterial({
        map: textureLeft,
        transparent: true,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending
      });
      const meshLeft = new THREE.Mesh(labelGeom, matLeft);
      meshLeft.rotation.x = -Math.PI / 2;
      meshLeft.rotation.z = -Math.PI / 2;
      meshLeft.position.set(-labelX, 0.01, z);
      this.boardGroup.add(meshLeft);

      // Droite
      const textureRight = this.createTextTexture(rankChar);
      const matRight = new THREE.MeshBasicMaterial({
        map: textureRight,
        transparent: true,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending
      });
      const meshRight = new THREE.Mesh(labelGeom, matRight);
      meshRight.rotation.x = -Math.PI / 2;
      meshRight.rotation.z = Math.PI / 2;
      meshRight.position.set(labelX, 0.01, z);
      this.boardGroup.add(meshRight);
    }
  }

  // Convertit les coordonnées d'une case (ex: "e4") en coordonnées Vector3 3D
  private squareToVector3(sqName: string, pieceHeightOffset: number = 0): THREE.Vector3 {
    const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
    const file = sqName[0];
    const rank = parseInt(sqName[1], 10);

    const fileIdx = files.indexOf(file);
    const rankIdx = rank - 1;

    const size = 0.85;
    const x = (fileIdx - 3.5) * size;
    const z = (3.5 - rankIdx) * size;

    return new THREE.Vector3(x, pieceHeightOffset, z);
  }

  private createTextTexture(char: string): THREE.Texture {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 256;
    const ctx = canvas.getContext('2d')!;

    ctx.clearRect(0, 0, 256, 256);
    ctx.font = 'bold 180px monospace';
    ctx.fillStyle = '#00e5ff'; // cyan
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // Effet de halo néon à l'échelle
    ctx.shadowColor = '#00e5ff';
    ctx.shadowBlur = 30;

    ctx.fillText(char, 128, 128);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.generateMipmaps = true;
    
    return texture;
  }

  // Création d'une pièce 3D avec contours néon
  private createPieceMesh(symbol: string): THREE.Group {
    const group = new THREE.Group();
    const isWhite = symbol === symbol.toUpperCase();
    const type = symbol.toLowerCase();
    const material = isWhite ? this.materials.get('white_piece')! : this.materials.get('black_piece')!;

    // Matériau de contour néon pour détacher la pièce des autres et du fond
    const outlineColor = isWhite ? 0x00e5ff : 0xff2e4d;
    const outlineMat = new THREE.LineBasicMaterial({
      color: outlineColor,
      transparent: true,
      opacity: 0.75, // Bonne visibilité
    });

    // Dessine le contour filaire des arrêtes significatives
    const addOutline = (mesh: THREE.Mesh, thresholdAngle: number = 24) => {
      const edges = new THREE.EdgesGeometry(mesh.geometry, thresholdAngle);
      const lines = new THREE.LineSegments(edges, outlineMat);
      lines.raycast = () => {}; // Ne pas intersecter les contours filaires
      mesh.add(lines);
    };

    let geom: THREE.BufferGeometry | undefined;

    if (type === 'k') {
      // Roi : Corps + Socle d'ornement + Croix massive bien distinctive
      const bodyGeom = this.geometries.get('king_body')!;
      const body = new THREE.Mesh(bodyGeom, material);
      addOutline(body, 22);
      group.add(body);

      const crossMat = material;
      const crossGroup = new THREE.Group();
      crossGroup.position.set(0, 1.02, 0); // Posée pile sur le sommet (1.02)

      // Socle cylindrique de la croix
      const base = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.03, 8), crossMat);
      base.position.set(0, 0.015, 0);
      addOutline(base, 25);
      crossGroup.add(base);

      // Branche verticale de la croix
      const vert = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.16, 0.04), crossMat);
      vert.position.set(0, 0.11, 0);
      addOutline(vert, 25);
      crossGroup.add(vert);

      // Branche horizontale de la croix
      const horiz = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.04, 0.04), crossMat);
      horiz.position.set(0, 0.13, 0);
      addOutline(horiz, 25);
      crossGroup.add(horiz);

      group.add(crossGroup);
    } else if (type === 'q') {
      // Reine : Corps + 7 sphères créant une couronne à pointes caractéristique
      const bodyGeom = this.geometries.get('queen')!;
      const body = new THREE.Mesh(bodyGeom, material);
      addOutline(body, 22);
      group.add(body);

      const crownPointsCount = 7;
      const crownRadius = 0.18;
      const crownY = 0.80; // Niveau du col de la Reine
      const sphereGeom = new THREE.SphereGeometry(0.025, 8, 8);
      for (let i = 0; i < crownPointsCount; i++) {
        const angle = (i / crownPointsCount) * Math.PI * 2;
        const pMesh = new THREE.Mesh(sphereGeom, material);
        pMesh.position.set(
          Math.cos(angle) * crownRadius,
          crownY,
          Math.sin(angle) * crownRadius
        );
        addOutline(pMesh, 25);
        group.add(pMesh);
      }
    } else if (type === 'n') {
      // Cavalier : Socle tourné + Tête extrudée posée dessus avec matériau plat (flatShading)
      const baseGeom = this.geometries.get('knight_base')!;
      const baseMesh = new THREE.Mesh(baseGeom, material);
      addOutline(baseMesh, 22);
      group.add(baseMesh);

      const headGeom = this.geometries.get('knight_head')!;
      const flatMaterial = isWhite ? this.materials.get('white_piece_flat')! : this.materials.get('black_piece_flat')!;
      const headMesh = new THREE.Mesh(headGeom, flatMaterial);
      headMesh.position.set(0, 0.495, 0); // Repositionné pour le profil élancé (0.22 + 0.275)
      headMesh.rotation.y = isWhite ? 0 : Math.PI;
      addOutline(headMesh, 15); // Seuil de 15° pour dessiner les arêtes des facettes de la tête
      group.add(headMesh);
    } else {
      // Autres pièces de révolution (Pion, Tour, Fou)
      const geomName = type === 'p' ? 'pawn' :
                       type === 'r' ? 'rook' : 'bishop';
      geom = this.geometries.get(geomName)!;
      const mesh = new THREE.Mesh(geom, material);
      addOutline(mesh, 22); // Contour à 22° pour marquer les collerettes et socles
      group.add(mesh);
    }

    // Orientations et ombres
    group.castShadow = true;
    group.receiveShadow = true;
    return group;
  }

  public handleGameState(state: any, lastMove: any = null): void {
    if (!this.active) this.activate();
    this.handleThinking(false);

    if (state.player_color) {
      this.playerColor = state.player_color;
    }

    // Reset du chronomètre si c'est le début de la partie
    if (state.fen && (state.fen.startsWith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR") || state.fen.startsWith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"))) {
      this.whiteTime = 600;
      this.blackTime = 600;
      this.isGameTimerActive = this.gameStarted && this.useTimer;
      this.updateTimerUI();
    }

    if (state.is_game_over) {
      this.isGameTimerActive = false;

      // Affichage du texte géant holographique de fin de partie
      let resultText = "FIN DE PARTIE";
      let color = "#ff8a1a"; // orange néon par défaut
      if (state.result === "1-0") {
        resultText = this.playerColor === 'white' ? "VICTOIRE" : "DÉFAITE";
        color = this.playerColor === 'white' ? "#00ff88" : "#ff3264";
      } else if (state.result === "0-1") {
        resultText = this.playerColor === 'black' ? "VICTOIRE" : "DÉFAITE";
        color = this.playerColor === 'black' ? "#00ff88" : "#ff3264";
      } else if (state.result === "1/2-1/2") {
        resultText = "MATCH NUL";
        color = "#ffdd00"; // jaune
      }
      this.showGameOverText(resultText, color);
    } else {
      this.hideGameOverText();
    }

    // Mettre à jour l'état du tour et des coups légaux
    this.currentTurn = state.turn || "white";
    this.legalMoves = this.gameStarted ? (state.legal_moves || []) : [];
    this.clearSelection();

    // Mettre à jour l'historique de coups
    this.updateHistoryUI(state.history || []);

    // Mettre à jour les surlignages de dernier coup
    this.clearLastMoveHighlights();
    if (lastMove && lastMove.from && lastMove.to) {
      const isPlayerMove = lastMove.color === this.playerColor;
      const color = isPlayerMove ? 0xbd00ff : 0xffdd00; // violet ou jaune néon
      const fromH = this.createNeonOutline(lastMove.from, color);
      const toH = this.createNeonOutline(lastMove.to, color);
      this.group.add(fromH);
      this.group.add(toH);
      this.lastMoveHighlights.push(fromH, toH);
    }

    // Mettre à jour le panel HUD
    if (this.gameStarted) {
      const turnEl = document.getElementById('chess-meta-turn');
      if (turnEl) {
        if (state.is_game_over) {
          turnEl.textContent = "PARTIE TERMINÉE";
          turnEl.style.color = "#ff8a1a";
        } else {
          const isPlayerTurn = this.currentTurn === this.playerColor;
          const turnColorName = this.currentTurn === "white" ? "BLANC" : "NOIR";
          if (isPlayerTurn) {
            turnEl.textContent = `VOTRE TOUR // ${turnColorName}`;
            turnEl.style.color = "#00e5ff";
          } else {
            turnEl.textContent = `TOUR DE JARVIS // ${turnColorName}`;
            turnEl.style.color = "#ff3264";
          }
        }
      }

      const logEl = document.getElementById('chess-log-text');
      if (logEl) {
        if (state.is_game_over) {
          logEl.textContent = `Partie terminée. Résultat : ${state.result || "Fin de partie"}`;
        } else if (lastMove) {
          const moveName = lastMove.color === this.playerColor ? "Vous" : "JARVIS";
          logEl.textContent = `${moveName} : ${lastMove.from} → ${lastMove.to}\nÀ ${this.currentTurn === this.playerColor ? 'vous' : 'JARVIS'} de jouer.`;
        } else {
          logEl.textContent = this.currentTurn === this.playerColor ? "À vous de jouer, monsieur." : "JARVIS réfléchit...";
        }
      }
    } else {
      const stateEl = document.getElementById('chess-meta-state');
      if (stateEl) {
        stateEl.textContent = "CONFIGURATION";
        stateEl.style.color = "#ff8c00";
      }
      const turnEl = document.getElementById('chess-meta-turn');
      if (turnEl) {
        turnEl.textContent = "EN ATTENTE // SETUP";
        turnEl.style.color = "rgba(0, 229, 255, 0.5)";
      }
      const logEl = document.getElementById('chess-log-text');
      if (logEl) {
        logEl.textContent = "Veuillez configurer et démarrer la partie pour commencer à jouer.";
      }
    }

    const newPieces = state.pieces || [];

    // Mettre à jour les pièces capturées (graveyard)
    const initialCounts: { [key: string]: number } = {
      'P': 8, 'N': 2, 'B': 2, 'R': 2, 'Q': 1,
      'p': 8, 'n': 2, 'b': 2, 'r': 2, 'q': 1
    };
    const activeCounts: { [key: string]: number } = {
      'P': 0, 'N': 0, 'B': 0, 'R': 0, 'Q': 0,
      'p': 0, 'n': 0, 'b': 0, 'r': 0, 'q': 0
    };
    newPieces.forEach((p: any) => {
      const type = p.type;
      if (type in activeCounts) {
        activeCounts[type]++;
      }
    });
    const unicodeSymbols: { [key: string]: string } = {
      'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕',
      'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛'
    };
    const capturedWhite: string[] = [];
    const whiteOrder = ['P', 'N', 'B', 'R', 'Q'];
    whiteOrder.forEach(type => {
      const diff = initialCounts[type] - activeCounts[type];
      for (let i = 0; i < diff; i++) {
        capturedWhite.push(unicodeSymbols[type]);
      }
    });
    const capturedBlack: string[] = [];
    const blackOrder = ['p', 'n', 'b', 'r', 'q'];
    blackOrder.forEach(type => {
      const diff = initialCounts[type] - activeCounts[type];
      for (let i = 0; i < diff; i++) {
        capturedBlack.push(unicodeSymbols[type]);
      }
    });

    const playerLost = this.playerColor === 'white' ? capturedWhite : capturedBlack;
    const jarvisLost = this.playerColor === 'white' ? capturedBlack : capturedWhite;

    const whiteEl = document.getElementById('chess-captured-white');
    if (whiteEl) {
      whiteEl.textContent = playerLost.length > 0 ? playerLost.join(' ') : '—';
    }
    const blackEl = document.getElementById('chess-captured-black');
    if (blackEl) {
      blackEl.textContent = jarvisLost.length > 0 ? jarvisLost.join(' ') : '—';
    }

    const newPiecesMap: Map<string, string> = new Map();

    newPieces.forEach((p: any) => {
      newPiecesMap.set(p.square, p.type);
    });

    // 1. Gérer les animations de mouvement et les captures
    if (lastMove) {
      const fromSq = lastMove.from;
      const toSq = lastMove.to;
      const color = lastMove.color;

      const movingPieceMesh = this.piecesMap.get(fromSq);
      const capturedPieceMesh = this.piecesMap.get(toSq);

      if (movingPieceMesh) {
        // Supprimer la pièce de départ de la map immédiate (elle est en transition)
        this.piecesMap.delete(fromSq);

        let capturedMesh: THREE.Group | undefined = undefined;
        let capturedSquare: string | undefined = undefined;
        let capturingColor: string | undefined = undefined;

        // Gérer la capture physique (disparition et explosion) - PROPAGÉ À L'ATTERRISSAGE
        if (capturedPieceMesh) {
          capturedMesh = capturedPieceMesh;
          capturedSquare = toSq;
          capturingColor = color; // the capturing piece's color

          this.piecesMap.delete(toSq);
        }

        // Créer l'animation de translation/saut
        const fromPos = this.squareToVector3(fromSq);
        const toPos = this.squareToVector3(toSq);
        const type = newPiecesMap.get(toSq)?.toLowerCase() || '';

        const anim: PieceAnimation = {
          pieceMesh: movingPieceMesh,
          fromPos: fromPos,
          toPos: toPos,
          progress: 0.0,
          duration: 0.55,
          isLeap: type === 'n', // Les cavaliers sautent en cloche !
          capturedMesh,
          capturedSquare,
          capturingColor
        };
        this.animations.push(anim);

        // Ré-enregistrer à sa destination future
        this.piecesMap.set(toSq, movingPieceMesh);
      }
    }

    // 2. Synchroniser les pièces non concernées par l'animation en cours
    // On nettoie les pièces qui n'existent plus ou sont mal placées
    this.piecesMap.forEach((mesh, sq) => {
      if (!newPiecesMap.has(sq)) {
        // Supprimé (ex: roque, ou coup bizarre non animé)
        // Vérifier si cette pièce est dans une animation active pour ne pas la supprimer en plein mouvement
        const isAnimating = this.animations.some(a => a.pieceMesh === mesh);
        if (!isAnimating) {
          this.piecesGroup?.remove(mesh);
          this.piecesMap.delete(sq);
        }
      }
    });

    // Ajouter ou recréer les nouvelles pièces
    newPiecesMap.forEach((type, sq) => {
      const existingMesh = this.piecesMap.get(sq);
      if (!existingMesh) {
        // Nouvelle pièce à créer
        const mesh = this.createPieceMesh(type);
        mesh.userData = { type: type }; // Enregistrer le type de pièce
        const pos = this.squareToVector3(sq);
        mesh.position.copy(pos);
        this.piecesGroup?.add(mesh);
        this.piecesMap.set(sq, mesh);
      } else {
        // S'assurer que le mesh correspond au type (en cas de promotion)
        if (existingMesh.userData?.type !== type) {
          // Le symbole a changé (promotion) ! On détruit l'ancien mesh et on recrée le nouveau.
          this.piecesGroup?.remove(existingMesh);
          existingMesh.traverse((child) => {
            if (child instanceof THREE.Mesh) {
              child.geometry.dispose();
              if (Array.isArray(child.material)) {
                child.material.forEach((mat) => mat.dispose());
              } else {
                child.material.dispose();
              }
            }
          });
          
          const mesh = this.createPieceMesh(type);
          mesh.userData = { type: type };
          const pos = this.squareToVector3(sq);
          mesh.position.copy(pos);
          this.piecesGroup?.add(mesh);
          this.piecesMap.set(sq, mesh);
        }
      }
    });

    // 3. Mettre à jour l'état de l'échec au roi
    if (state.is_check) {
      // Trouver la case du roi en échec
      const checkKingSymbol = state.turn === 'white' ? 'K' : 'k';
      const checkKingPiece = newPieces.find((p: any) => p.type === checkKingSymbol);
      if (checkKingPiece) {
        this.highlightCheckSquare(checkKingPiece.square);
      }
    } else {
      this.clearCheckHighlight();
    }
  }

  // Animation de particules d'explosion pour une pièce capturée
  private triggerCaptureExplosion(sqName: string, capturingColor: string): void {
    if (!this.particlesGroup) return;

    const pos = this.squareToVector3(sqName, 0.2);
    const particleCount = 40; // plus de particules
    const color = capturingColor === 'white' ? 0x00e5ff : 0xff3264; // couleur de la pièce qui capture

    // 1. Créer l'onde de choc circulaire (shockwave) au sol
    const size = 0.85;
    const ringGeom = new THREE.RingGeometry(size * 0.1, size * 0.14, 32);
    const ringMat = new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: 0.9,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending
    });
    const ringMesh = new THREE.Mesh(ringGeom, ringMat);
    ringMesh.rotation.x = Math.PI / 2; // à plat sur le plateau
    ringMesh.position.copy(pos);
    ringMesh.position.y = 0.015; // au niveau du sol
    this.group.add(ringMesh);

    this.shockwaves.push({
      mesh: ringMesh,
      maxRadius: size * 1.5,
      life: 1.0,
      decay: 2.2 // fade-out rapide de ~0.45s
    });

    // 2. Explosion de particules 3D classique
    const geom = new THREE.SphereGeometry(0.06, 5, 5); // plus grand (was 0.035)
    const mat = new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: 1.0,
      blending: THREE.AdditiveBlending
    });

    for (let i = 0; i < particleCount; i++) {
      const pMesh = new THREE.Mesh(geom, mat.clone());
      pMesh.position.copy(pos);

      // Vitesse aléatoire sphérique
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos((Math.random() * 2) - 1);
      const speed = 1.0 + Math.random() * 2.0;

      const vx = speed * Math.sin(phi) * Math.cos(theta);
      const vy = speed * Math.cos(phi) + 1.2; // éjecté plus haut
      const vz = speed * Math.sin(phi) * Math.sin(theta);

      const p: ChessParticle = {
        mesh: pMesh,
        velocity: new THREE.Vector3(vx, vy, vz),
        life: 1.0,
        decay: 0.6 + Math.random() * 0.8 // plus lent (was 1.2 - 2.7)
      };

      this.particlesGroup.add(pMesh);
      this.particles.push(p);
    }
  }

  // Highlight la case du roi en échec (rouge clignotant)
  private highlightCheckSquare(sqName: string): void {
    this.checkSquareName = sqName;
    const pos = this.squareToVector3(sqName, 0.01);

    if (!this.checkHighlight) {
      const size = 0.85;
      const geom = new THREE.PlaneGeometry(size - 0.02, size - 0.02);
      const mat = new THREE.MeshBasicMaterial({
        color: 0xff0000,
        transparent: true,
        opacity: 0.5,
        side: THREE.DoubleSide
      });
      this.checkHighlight = new THREE.Mesh(geom, mat);
      this.checkHighlight.rotation.x = Math.PI / 2;
      this.group.add(this.checkHighlight);
    }

    this.checkHighlight.position.copy(pos);
    this.checkHighlight.visible = true;

    // Créer l'alerte holographique 3D d'échec (sans emoji)
    if (!this.checkFloatingText) {
      this.checkFloatingText = this.createFloatingText("ECHEC", "#ff3264");
      this.group.add(this.checkFloatingText);
    }
  }

  private clearCheckHighlight(): void {
    if (this.checkHighlight) {
      this.checkHighlight.visible = false;
    }
    if (this.checkFloatingText) {
      this.group.remove(this.checkFloatingText);
      const ud = this.checkFloatingText.userData;
      if (ud) {
        if (ud.geometry) ud.geometry.dispose();
        if (ud.material) ud.material.dispose();
        if (ud.texture) ud.texture.dispose();
      }
      this.checkFloatingText = null;
    }
    this.checkSquareName = null;
  }

  // Génère un mesh de texte 3D flottant avec un canvas et des effets néon
  private createFloatingText(text: string, color: string): THREE.Mesh {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 128;
    const ctx = canvas.getContext('2d')!;

    ctx.clearRect(0, 0, 512, 128);
    ctx.font = 'bold 72px monospace';
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    ctx.shadowColor = color;
    ctx.shadowBlur = 15;
    ctx.fillText(text, 256, 64);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;

    const geom = new THREE.PlaneGeometry(1.6, 0.4);
    const mat = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending
    });

    const mesh = new THREE.Mesh(geom, mat);
    mesh.userData = { geometry: geom, material: mat, texture: texture };
    return mesh;
  }

  // Affiche un grand texte de fin de partie flottant au centre du plateau
  private showGameOverText(text: string, color: string): void {
    this.hideGameOverText();

    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 256;
    const ctx = canvas.getContext('2d')!;

    ctx.clearRect(0, 0, 1024, 256);
    ctx.font = 'bold 96px monospace';
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    ctx.shadowColor = color;
    ctx.shadowBlur = 25;
    ctx.fillText(text, 512, 128);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;

    const geom = new THREE.PlaneGeometry(3.6, 0.9);
    const mat = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending
    });

    this.gameOverTextMesh = new THREE.Mesh(geom, mat);
    this.gameOverTextMesh.position.set(0, 2.2, 0); // lévite au-dessus du centre
    this.group.add(this.gameOverTextMesh);
  }

  // Efface le texte de fin de partie
  private hideGameOverText(): void {
    if (this.gameOverTextMesh) {
      this.group.remove(this.gameOverTextMesh);
      this.gameOverTextMesh.geometry.dispose();
      if (Array.isArray(this.gameOverTextMesh.material)) {
        // no-op
      } else if (this.gameOverTextMesh.material) {
        if ((this.gameOverTextMesh.material as any).map) (this.gameOverTextMesh.material as any).map.dispose();
        this.gameOverTextMesh.material.dispose();
      }
      this.gameOverTextMesh = null;
    }
  }

  // Génère des particules de sillage néon derrière les pièces en mouvement
  private spawnTrailParticle(pos: THREE.Vector3, color: number): void {
    if (!this.particlesGroup) return;

    const geom = new THREE.SphereGeometry(0.035, 4, 4);
    const mat = new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending
    });
    const pMesh = new THREE.Mesh(geom, mat);

    // Flottement aléatoire autour de la position actuelle
    pMesh.position.copy(pos).add(new THREE.Vector3(
      (Math.random() - 0.5) * 0.08,
      (Math.random() - 0.5) * 0.08,
      (Math.random() - 0.5) * 0.08
    ));

    const p: ChessParticle = {
      mesh: pMesh,
      velocity: new THREE.Vector3(
        (Math.random() - 0.5) * 0.15,
        Math.random() * 0.15, // dérive vers le haut
        (Math.random() - 0.5) * 0.15
      ),
      life: 1.0,
      decay: 2.2 // s'estompe en 0.45s
    };

    this.particlesGroup.add(pMesh);
    this.particles.push(p);
  }

  // Met à jour l'état de réflexion de JARVIS sur le plateau (animation de pulsion de ses pièces)
  public handleThinking(thinking: boolean): void {
    this.isThinking = thinking;
    if (!thinking) {
      // Restaurer l'intensité émissive normale des pièces noires
      const blackMat = this.materials.get('black_piece') as THREE.MeshStandardMaterial;
      const blackFlatMat = this.materials.get('black_piece_flat') as THREE.MeshStandardMaterial;
      if (blackMat) blackMat.emissiveIntensity = 0.08;
      if (blackFlatMat) blackFlatMat.emissiveIntensity = 0.08;
    }
  }

  // Met à jour les éléments DOM du chronomètre
  private updateTimerUI(): void {
    const formatTime = (secs: number) => {
      const minutes = Math.floor(secs / 60);
      const seconds = Math.floor(secs % 60);
      return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    };

    const playerTime = this.playerColor === 'white' ? this.whiteTime : this.blackTime;
    const jarvisTime = this.playerColor === 'white' ? this.blackTime : this.whiteTime;

    const whiteTimerEl = document.getElementById('chess-timer-white');
    if (whiteTimerEl) {
      whiteTimerEl.textContent = formatTime(playerTime);
    }
    const blackTimerEl = document.getElementById('chess-timer-black');
    if (blackTimerEl) {
      blackTimerEl.textContent = formatTime(jarvisTime);
    }
  }

  // Boucle de rendu / mise à jour
  public update(dt: number): void {
    if (!this.active) return;

    // Mise à jour des chronomètres
    if (this.isGameTimerActive) {
      if (this.currentTurn === "white") {
        this.whiteTime = Math.max(0, this.whiteTime - dt);
        if (this.whiteTime === 0) {
          this.isGameTimerActive = false;
          const turnEl = document.getElementById('chess-meta-turn');
          if (turnEl) {
            turnEl.textContent = "TEMPS ÉCOULÉ - JARVIS GAGNE";
            turnEl.style.color = "#ff3264";
          }
          const logEl = document.getElementById('chess-log-text');
          if (logEl) logEl.textContent = "Partie terminée : Vous avez perdu au temps !";
        }
      } else {
        this.blackTime = Math.max(0, this.blackTime - dt);
        if (this.blackTime === 0) {
          this.isGameTimerActive = false;
          const turnEl = document.getElementById('chess-meta-turn');
          if (turnEl) {
            turnEl.textContent = "TEMPS ÉCOULÉ - VOUS GAGNEZ";
            turnEl.style.color = "#00e5ff";
          }
          const logEl = document.getElementById('chess-log-text');
          if (logEl) logEl.textContent = "Partie terminée : JARVIS a perdu au temps !";
        }
      }
      this.updateTimerUI();
    }

    // 1. Mettre à jour les animations de déplacement des pièces
    for (let i = this.animations.length - 1; i >= 0; i--) {
      const anim = this.animations[i];
      anim.progress += dt / anim.duration;

      if (anim.progress >= 1.0) {
        // Terminé
        anim.pieceMesh.position.copy(anim.toPos);

        // Déclencher la capture physique (disparition et explosion) à l'impact
        if (anim.capturedMesh && anim.capturedSquare && anim.capturingColor) {
          this.triggerCaptureExplosion(anim.capturedSquare, anim.capturingColor);

          // Cloner les matériaux pour modifier l'opacité
          anim.capturedMesh.traverse((child) => {
            if (child instanceof THREE.Mesh) {
              child.material = (child.material as THREE.Material).clone();
              child.material.transparent = true;
            }
          });

          this.dyingPieces.push({
            mesh: anim.capturedMesh,
            duration: 0.8,
            progress: 0.0
          });
        }

        this.animations.splice(i, 1);
      } else {
        // Interpolation linéaire pour X et Z
        const currentPos = new THREE.Vector3().lerpVectors(anim.fromPos, anim.toPos, anim.progress);

        // Si Cavalier : courbe de saut parabolique sur Y
        if (anim.isLeap) {
          const height = 0.9; // hauteur max du saut
          currentPos.y = Math.sin(anim.progress * Math.PI) * height;
        } else {
          // Glissement léger au-dessus du sol
          currentPos.y = 0.0;
        }

        anim.pieceMesh.position.copy(currentPos);

        // Générer des particules de sillage néon pendant le mouvement
        const type = anim.pieceMesh.userData?.type || 'P';
        const isWhitePiece = type === type.toUpperCase();
        const trailColor = isWhitePiece ? 0x00e5ff : 0xff2e4d;
        this.spawnTrailParticle(currentPos, trailColor);
      }
    }

    // 2. Mettre à jour les pièces capturées (animation de disparition)
    for (let i = this.dyingPieces.length - 1; i >= 0; i--) {
      const anim = this.dyingPieces[i];
      anim.progress += dt / anim.duration;

      if (anim.progress >= 1.0) {
        // Supprimer définitivement
        this.piecesGroup?.remove(anim.mesh);
        anim.mesh.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.geometry.dispose();
            if (Array.isArray(child.material)) {
              child.material.forEach((mat) => mat.dispose());
            } else {
              child.material.dispose();
            }
          }
        });
        this.dyingPieces.splice(i, 1);
      } else {
        // Animation : Tipping/Chute sur le côté + descente sous le plateau
        anim.mesh.rotation.z = anim.progress * (Math.PI / 2.2); // S'allonge à presque 90°
        anim.mesh.position.y = -anim.progress * 0.4; // Descend sous le plateau

        // Fondu progressif d'opacité
        anim.mesh.traverse((child) => {
          if (child instanceof THREE.Mesh && child.material) {
            child.material.opacity = 1.0 - anim.progress;
          }
        });
      }
    }

    // 3. Mettre à jour les particules d'explosion
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.life -= dt * p.decay;

      if (p.life <= 0.0) {
        this.particlesGroup?.remove(p.mesh);
        p.mesh.geometry.dispose();
        (p.mesh.material as THREE.Material).dispose();
        this.particles.splice(i, 1);
      } else {
        // Appliquer vitesse
        p.mesh.position.addScaledVector(p.velocity, dt);
        // Ralentissement + gravité légère
        p.velocity.y -= 3.0 * dt; // gravité
        p.velocity.multiplyScalar(0.96); // friction

        // Réduire taille et opacité
        p.mesh.scale.setScalar(p.life);
        if (Array.isArray(p.mesh.material)) {
          // Pas concerné
        } else if (p.mesh.material) {
          p.mesh.material.opacity = p.life;
        }
      }
    }

    // 3b. Mettre à jour les ondes de choc (shockwaves)
    for (let i = this.shockwaves.length - 1; i >= 0; i--) {
      const sw = this.shockwaves[i];
      sw.life -= dt * sw.decay;

      if (sw.life <= 0.0) {
        this.group.remove(sw.mesh);
        sw.mesh.geometry.dispose();
        (sw.mesh.material as THREE.Material).dispose();
        this.shockwaves.splice(i, 1);
      } else {
        const progress = 1.0 - sw.life;
        const currentScale = 1.0 + progress * 6.0; // grandit jusqu'à 7x sa taille
        sw.mesh.scale.set(currentScale, currentScale, 1.0);
        if (Array.isArray(sw.mesh.material)) {
          // no-op
        } else if (sw.mesh.material) {
          sw.mesh.material.opacity = sw.life;
        }
      }
    }

    // 4. Effet de clignotement de l'échec (rouge pulsé)
    if (this.checkHighlight && this.checkHighlight.visible) {
      this.checkPulseTime += dt * 5.0;
      const opacity = 0.3 + Math.sin(this.checkPulseTime) * 0.25;
      (this.checkHighlight.material as THREE.MeshBasicMaterial).opacity = opacity;
    }

    // 5. Effet de pulsation émissive des pièces noires quand JARVIS réfléchit
    if (this.isThinking) {
      this.thinkingPulseTime += dt * 4.0;
      const intensity = 0.08 + (Math.sin(this.thinkingPulseTime) + 1.0) * 0.12; // varie de 0.08 à 0.32
      const blackMat = this.materials.get('black_piece') as THREE.MeshStandardMaterial;
      const blackFlatMat = this.materials.get('black_piece_flat') as THREE.MeshStandardMaterial;
      if (blackMat) blackMat.emissiveIntensity = intensity;
      if (blackFlatMat) blackFlatMat.emissiveIntensity = intensity;
    }

    // 6. Mettre à jour les textes holographiques flottants (billboard & lévitation)
    if (this.checkFloatingText && this.checkSquareName) {
      this.checkFloatingText.quaternion.copy(this.camera.quaternion);
      this.floatingTime += dt;
      const basePos = this.squareToVector3(this.checkSquareName, 1.25);
      this.checkFloatingText.position.copy(basePos);
      this.checkFloatingText.position.y += Math.sin(this.floatingTime * 4.0) * 0.08;
    }

    if (this.gameOverTextMesh) {
      this.gameOverTextMesh.quaternion.copy(this.camera.quaternion);
      this.floatingTime += dt;
      this.gameOverTextMesh.position.y = 2.2 + Math.sin(this.floatingTime * 2.5) * 0.12;
    }
  }

  // Mouse selection / drag and drop helpers
  private isEventOnUI(e: MouseEvent): boolean {
    return !!((e.target as HTMLElement).closest('#settings-modal') || 
              (e.target as HTMLElement).closest('#holo-chess-panel') || 
              (e.target as HTMLElement).tagName === 'BUTTON');
  }

  private getSquareFromEvent(e: MouseEvent): string | null {
    const canvas = document.getElementById('holo-three-canvas');
    if (!canvas) return null;

    const rect = canvas.getBoundingClientRect();
    const mouse = new THREE.Vector2();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    this.camera.updateMatrixWorld(true);
    this.raycaster.setFromCamera(mouse, this.camera);

    if (this.boardSquares.length > 0 && this.piecesGroup) {
      // Raycasting sur le plateau (sans outerLine) ET les pièces 3D
      const targets = [...this.boardSquares, ...this.piecesGroup.children];
      const intersects = this.raycaster.intersectObjects(targets, true);

      for (let i = 0; i < intersects.length; i++) {
        const hit = intersects[i].object;
        let sqName: string | null = null;

        // 1. Essayer de voir si l'objet cliqué est une pièce ou fait partie d'une pièce
        let curr: THREE.Object3D | null = hit;
        while (curr && curr !== this.scene) {
          for (const [sq, mesh] of this.piecesMap.entries()) {
            if (mesh === curr) {
              sqName = sq;
              break;
            }
          }
          if (sqName) break;
          curr = curr.parent;
        }

        // Si la pièce touchée est la pièce actuellement sélectionnée, et qu'il y a d'autres éléments
        // (comme la case du plateau) sous le curseur, on l'ignore. Cela évite l'occlusion 3D pour le déplacement.
        if (sqName && sqName === this.selectedSquare && i < intersects.length - 1) {
          continue;
        }

        // 2. Sinon, essayer de voir s'il s'agit d'une case du plateau
        if (!sqName) {
          curr = hit;
          while (curr && curr !== this.scene) {
            if (curr.userData?.squareName) {
              sqName = curr.userData.squareName;
              break;
            }
            curr = curr.parent;
          }
        }

        if (sqName) {
          return sqName;
        }
      }
    }
    return null;
  }

  private _onContextMenu = (e: MouseEvent): void => {
    if (this.active) {
      e.preventDefault();
    }
  };

  private _onMouseDown = (e: MouseEvent): void => {
    if (!this.active) return;
    if (this.isEventOnUI(e)) return;

    if (e.button === 2) {
      this.isRotating = true;
      this.previousMousePosition = { x: e.clientX, y: e.clientY };
      return;
    }

    // Tester d'abord l'intersection avec les boutons 3D
    const hitBtn = this.check3dButtonHitFromEvent(e);
    if (hitBtn) {
      this.trigger3dButtonAction(hitBtn);
      return;
    }

    if (!this.gameStarted) return;

    const sqName = this.getSquareFromEvent(e);
    console.log("[CHESS DEBUG] MouseDown sur case:", sqName);
    if (!sqName) return;

    // Tenter de sélectionner une pièce du joueur avec des coups légaux de départ
    const hasLegalMoves = this.legalMoves.some(m => m.startsWith(sqName));
    if (this.currentTurn === this.playerColor && hasLegalMoves) {
      // Si on clique sur une pièce différente alors qu'une pièce était sélectionnée,
      // on change la sélection
      this.selectedSquare = sqName;
      this.highlightSelection(sqName);
    }
  };

  private _onMouseUp = (e: MouseEvent): void => {
    if (!this.active || !this.gameStarted) return;
    if (this.isEventOnUI(e)) return;

    if (this.isRotating) {
      this.isRotating = false;
      return;
    }

    const sqName = this.getSquareFromEvent(e);
    console.log("[CHESS DEBUG] MouseUp sur case:", sqName, "selectedSquare:", this.selectedSquare);

    if (!sqName) {
      // Relâché hors du plateau -> désélectionner
      this.clearSelection();
      return;
    }

    if (this.selectedSquare && this.selectedSquare !== sqName) {
      const uciMove = this.selectedSquare + sqName;
      const matchedMove = this.legalMoves.find(m => m.startsWith(uciMove));
      console.log("[CHESS DEBUG] Drag-drop ou clic-mouvement détecté:", uciMove, "matchedMove:", matchedMove);

      if (matchedMove) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          console.log("[CHESS DEBUG] Envoi du coup:", matchedMove);
          this.ws.send(JSON.stringify({
            type: "user_input",
            text: matchedMove
          }));
        }
        this.clearSelection();
      } else {
        // Relâché sur une case vide non valide -> désélectionner si c'est un drag
        // Si c'est un clic simple sur une autre pièce valide, MouseDown a déjà changé la sélection.
        // Mais si c'est un clic sur une case non valide, on nettoie tout.
        this.clearSelection();
      }
    } else if (this.selectedSquare === sqName) {
      // Même case -> on garde la sélection pour le clic simple
      console.log("[CHESS DEBUG] Clic simple maintenu sur:", sqName);
    }
  };


  private highlightSelection(sqName: string): void {
    this.clearSelectionVisuals();

    const size = 0.85;

    // 1. Highlight de la pièce sélectionnée (Cercle bleu cyan)
    const selectionPos = this.squareToVector3(sqName, 0.01);
    const selGeom = new THREE.RingGeometry(size * 0.35, size * 0.45, 32);
    const selMat = new THREE.MeshBasicMaterial({
      color: 0x00e5ff,
      transparent: true,
      opacity: 0.8,
      side: THREE.DoubleSide
    });
    this.selectionHighlight = new THREE.Mesh(selGeom, selMat);
    this.selectionHighlight.rotation.x = Math.PI / 2;
    this.selectionHighlight.position.copy(selectionPos);
    this.group.add(this.selectionHighlight);

    // 2. Highlight des coups légaux de destination (Cercles verts)
    const destinations = this.legalMoves
      .filter(m => m.startsWith(sqName))
      .map(m => m.substring(2, 4));

    const ringGeom = new THREE.RingGeometry(size * 0.18, size * 0.26, 16);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x00ff88,
      transparent: true,
      opacity: 0.75,
      side: THREE.DoubleSide
    });

    destinations.forEach(dest => {
      const destPos = this.squareToVector3(dest, 0.015);
      const ringMesh = new THREE.Mesh(ringGeom, ringMat);
      ringMesh.rotation.x = Math.PI / 2;
      ringMesh.position.copy(destPos);
      this.group.add(ringMesh);
      this.legalMoveHighlights.push(ringMesh);
    });
  }

  private clearSelectionVisuals(): void {
    if (this.selectionHighlight) {
      this.group.remove(this.selectionHighlight);
      this.selectionHighlight.geometry.dispose();
      (this.selectionHighlight.material as THREE.Material).dispose();
      this.selectionHighlight = null;
    }

    this.legalMoveHighlights.forEach(mesh => {
      this.group.remove(mesh);
      mesh.geometry.dispose();
      (mesh.material as THREE.Material).dispose();
    });
    this.legalMoveHighlights = [];
  }

  private clearSelection(): void {
    this.selectedSquare = null;
    this.clearSelectionVisuals();
  }

  private _onMouseMove = (e: MouseEvent): void => {
    if (!this.active || !this.gameStarted) return;

    if (this.isRotating) {
      const deltaMove = {
        x: e.clientX - this.previousMousePosition.x,
        y: e.clientY - this.previousMousePosition.y
      };

      this.group.rotation.y += deltaMove.x * 0.005;
      this.group.rotation.x += deltaMove.y * 0.005;
      this.group.rotation.x = Math.max(-0.55, Math.min(0.95, this.group.rotation.x));

      this.previousMousePosition = { x: e.clientX, y: e.clientY };
      return;
    }

    const sqName = this.getSquareFromEvent(e);
    this.updateHover(sqName);
  };

  private updateHover(sqName: string | null): void {
    if (this.hoveredSquare === sqName) return;
    this.hoveredSquare = sqName;

    // Supprimer l'ancien highlight de survol
    if (this.hoverHighlight) {
      this.group.remove(this.hoverHighlight);
      this.hoverHighlight.geometry.dispose();
      (this.hoverHighlight.material as THREE.Material).dispose();
      this.hoverHighlight = null;
    }

    if (!sqName) return;

    // Si on survole une case, dessiner un fin liseré de survol carré
    const size = 0.85;
    const pos = this.squareToVector3(sqName, 0.012);
    
    // Déterminer la couleur : vert si c'est un coup légal de la pièce sélectionnée, sinon orange/cyan
    let isLegalTarget = false;
    if (this.selectedSquare) {
      const uciMove = this.selectedSquare + sqName;
      isLegalTarget = this.legalMoves.some(m => m.startsWith(uciMove));
    }

    const color = isLegalTarget ? 0x00ff88 : 0xffaa00;
    
    // Créer un liseré carré (RingGeometry avec 4 segments, pivoté de 45 degrés pour former un carré)
    const geom = new THREE.RingGeometry(size * 0.40, size * 0.46, 4, 1, 0, Math.PI * 2);
    geom.rotateZ(Math.PI / 4);
    
    const mat = new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: 0.6,
      side: THREE.DoubleSide
    });

    this.hoverHighlight = new THREE.Mesh(geom, mat);
    this.hoverHighlight.rotation.x = Math.PI / 2;
    this.hoverHighlight.position.copy(pos);
    this.group.add(this.hoverHighlight);
  }

  // ── HANDS INTERACTION ─────────────────────────────────────
  public updateHandsInteraction(
    pos0: THREE.Vector3 | null,
    pinched0: boolean,
    pos1: THREE.Vector3 | null,
    pinched1: boolean
  ): void {
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
        this.group.rotation.x = THREE.MathUtils.clamp(this.group.rotation.x, -0.55, 0.95);
      }

      this.lastTwoPos0 = pos0.clone();
      this.lastTwoPos1 = pos1.clone();
      this.lastTwoDist = dist;
      return;
    }

    // Réinitialiser les états 2 mains si non pincés simultanément
    this.lastTwoPos0 = null;
    this.lastTwoPos1 = null;
    this.lastTwoDist = null;

    // ── GESTE MONO-MAIN (HOVER / SELECTION) ────────────────────
    const handWorldPos = pos0 || pos1;
    const isPinched = pos0 ? pinched0 : pinched1;

    if (!handWorldPos) {
      if (this.wasHandActive) {
        this.updateHover(null);
        this.wasHandActive = false;
      }
      this.wasHandPinched = false;
      return;
    }

    this.wasHandActive = true;

    // Obtenir la case survolée par le pointeur 3D de la main
    const sqName = this.getSquareFromWorldPosition(handWorldPos);
    this.updateHover(sqName);

    // Gérer le clic / déplacement
    if (isPinched && !this.wasHandPinched) {
      this.wasHandPinched = true;

      // Tester l'intersection avec les boutons 3D
      const hitBtn = this.check3dButtonHitFromWorldPos(handWorldPos);
      if (hitBtn) {
        this.trigger3dButtonAction(hitBtn);
        return;
      }

      if (this.gameStarted && sqName) {
        const hasLegalMoves = this.legalMoves.some(m => m.startsWith(sqName));
        if (this.currentTurn === this.playerColor && hasLegalMoves) {
          this.selectedSquare = sqName;
          this.highlightSelection(sqName);
          console.log("[CHESS DEBUG] Hand pinch select square:", sqName);
        }
      }
    } else if (!isPinched && this.wasHandPinched) {
      this.wasHandPinched = false;
      if (this.gameStarted && this.selectedSquare) {
        console.log("[CHESS DEBUG] Hand pinch release. Selected:", this.selectedSquare, "Target:", sqName);
        if (sqName && this.selectedSquare !== sqName) {
          const uciMove = this.selectedSquare + sqName;
          const matchedMove = this.legalMoves.find(m => m.startsWith(uciMove));
          if (matchedMove) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              console.log("[CHESS DEBUG] Hand envoye le coup:", matchedMove);
              this.ws.send(JSON.stringify({
                type: "user_input",
                text: matchedMove
              }));
            }
            this.clearSelection();
          } else {
            this.clearSelection();
          }
        } else if (sqName === this.selectedSquare) {
          console.log("[CHESS DEBUG] Hand simple click on:", sqName);
        } else {
          this.clearSelection();
        }
      }
    }
  }

  private getSquareFromWorldPosition(worldPos: THREE.Vector3): string | null {
    this.camera.updateMatrixWorld(true);
    const direction = worldPos.clone().sub(this.camera.position).normalize();
    this.raycaster.set(this.camera.position, direction);

    if (this.boardSquares.length > 0 && this.piecesGroup) {
      const targets = [...this.boardSquares, ...this.piecesGroup.children];
      const intersects = this.raycaster.intersectObjects(targets, true);

      for (let i = 0; i < intersects.length; i++) {
        const hit = intersects[i].object;
        let sqName: string | null = null;

        // 1. Essayer de voir si l'objet cliqué est une pièce ou fait partie d'une pièce
        let curr: THREE.Object3D | null = hit;
        while (curr && curr !== this.scene) {
          for (const [sq, mesh] of this.piecesMap.entries()) {
            if (mesh === curr) {
              sqName = sq;
              break;
            }
          }
          if (sqName) break;
          curr = curr.parent;
        }

        if (sqName && sqName === this.selectedSquare && i < intersects.length - 1) {
          continue;
        }

        // 2. Sinon, essayer de voir s'il s'agit d'une case du plateau
        if (!sqName) {
          curr = hit;
          while (curr && curr !== this.scene) {
            if (curr.userData?.squareName) {
              sqName = curr.userData.squareName;
              break;
            }
            curr = curr.parent;
          }
        }

        if (sqName) {
          return sqName;
        }
      }
    }
    return null;
  }

  // ── MOVE HISTORY (SAN) ──────────────────────────────────
  private updateHistoryUI(history: string[]): void {
    const listEl = document.getElementById('chess-history-list');
    if (!listEl) return;

    listEl.innerHTML = '';
    
    // Grouper les coups par paire (Blanc / Noir)
    for (let i = 0; i < history.length; i += 2) {
      const moveNum = Math.floor(i / 2) + 1;
      const whiteMove = history[i];
      const blackMove = history[i + 1] || '';

      const rowEl = document.createElement('div');
      rowEl.style.display = 'contents';

      const whiteEl = document.createElement('div');
      whiteEl.style.color = '#00e5ff';
      whiteEl.style.textShadow = '0 0 4px rgba(0, 229, 255, 0.4)';
      whiteEl.textContent = `${moveNum}. ${whiteMove}`;

      const blackEl = document.createElement('div');
      blackEl.style.color = '#ff3264';
      blackEl.style.textShadow = '0 0 4px rgba(255, 50, 100, 0.4)';
      blackEl.textContent = blackMove ? `${blackMove}` : '';

      rowEl.appendChild(whiteEl);
      rowEl.appendChild(blackEl);
      listEl.appendChild(rowEl);
    }

    const containerEl = document.getElementById('chess-history-container');
    if (containerEl) {
      containerEl.scrollTop = containerEl.scrollHeight;
    }
  }

  // ── LAST MOVE HIGHLIGHT ───────────────────────────────────
  private createNeonOutline(sqName: string, color: number): THREE.Group {
    const group = new THREE.Group();
    const pos = this.squareToVector3(sqName, 0.008);
    const size = 0.85;

    // Contour fin interne (intensité)
    const geomInner = new THREE.RingGeometry(size * 0.44, size * 0.46, 4);
    geomInner.rotateZ(Math.PI / 4);
    const matInner = new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: 0.9,
      side: THREE.DoubleSide
    });
    const meshInner = new THREE.Mesh(geomInner, matInner);
    meshInner.rotation.x = Math.PI / 2;
    group.add(meshInner);

    // Contour épais externe (halo doux)
    const geomOuter = new THREE.RingGeometry(size * 0.42, size * 0.49, 4);
    geomOuter.rotateZ(Math.PI / 4);
    const matOuter = new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide
    });
    const meshOuter = new THREE.Mesh(geomOuter, matOuter);
    meshOuter.rotation.x = Math.PI / 2;
    group.add(meshOuter);

    group.position.copy(pos);
    return group;
  }

  private clearLastMoveHighlights(): void {
    this.lastMoveHighlights.forEach(group => {
      this.group.remove(group);
      group.traverse(child => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose();
          if (Array.isArray(child.material)) {
            child.material.forEach(m => m.dispose());
          } else {
            child.material.dispose();
          }
        }
      });
    });
    this.lastMoveHighlights = [];
  }
}

