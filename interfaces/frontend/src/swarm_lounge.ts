import * as THREE from 'three';
interface Agent {
  name: string;
  role: 'PM' | 'UI' | 'DEV' | 'SEC' | 'QA' | 'OPS';
  color: string;
  x: number;
  z: number;
  targetX: number;
  targetZ: number;
  state: 'idle' | 'wandering' | 'conversing' | 'typing';
  bubbleText: string;
  bubbleTimer: number;
  group: THREE.Group;
  walkTime: number;
  bubbleEl?: HTMLDivElement;
  
  // Live Telemetry
  taskName: string;
  projectName: string;
  startTime: number;
  elapsedTime: number;
  tokens: number;
  cost: number;
  active: boolean;
}
export class SwarmLounge {
  private canvas: HTMLCanvasElement;
  private renderer!: THREE.WebGLRenderer;
  private scene!: THREE.Scene;
  private camera!: THREE.OrthographicCamera;
  
  private agents: Agent[] = [];
  private isSwarmActive = false;
  private activeAgentRole: 'PM' | 'UI' | 'DEV' | 'SEC' | 'QA' | 'OPS' | null = null;
  private animationFrameId: number | null = null;
  
  private width = 800;
  private height = 300;
  private time = 0;
  private bubbleContainer: HTMLDivElement | null = null;
  // HUD Elements
  private labelsOverlay: HTMLDivElement | null = null;
  private tableBody: HTMLTableSectionElement | null = null;
  private activeCountEl: HTMLSpanElement | null = null;
  // Dialogues passifs au repos
  private pmQuotes = [
    "Specs validées.",
    "Quel est le statut, DEV ?",
    "Le backlog est propre.",
    "On lance un sprint ?",
    "QA, as-tu fini les tests ?",
    "Sprint objectif atteint !"
  ];
  private uiQuotes = [
    "Design Glassmorphism validé.",
    "Palette HSL harmonisée.",
    "Layout responsive configuré.",
    "Composants UI fluides à 60 FPS."
  ];
  private devQuotes = [
    "J'optimise la récursivité.",
    "Le code compile chez moi.",
    "C'est pas un bug, c'est une feature.",
    "J'écris du code propre.",
    "Attention au Garbage Collector.",
    "Vitesse de compilation stable."
  ];
  private secQuotes = [
    "Scan d'injections XSS/SQL clean.",
    "Aucune fuite de clé API.",
    "Inputs utilisateur assainis.",
    "Politique de sécurité appliquée."
  ];
    private qaQuotes = [
    "Test dans la Sandbox OK...",
    "Zéro erreur de syntaxe.",
    "Exécution réelle validée !",
    "Test de couverture : 100%.",
    "DEV, regarde cette stacktrace !",
    "Pas de fuites mémoire."
  ];
  private opsQuotes = [
    "Manifeste requirements.txt généré.",
    "Environment Venv isolé prêt.",
    "Point d'entrée vérifié.",
    "Déploiement Sandbox réussi !"
  ];
  // Static 3D labels with their coordinate vectors
  private staticMarkers = [
    { name: "Desk 01", pos: new THREE.Vector3(0, 1.4, -2), color: "#00e5ff", element: null as HTMLDivElement | null },
    { name: "UI Studio", pos: new THREE.Vector3(-3, 1.4, -2), color: "#ec4899", element: null as HTMLDivElement | null },
    { name: "Security Gate", pos: new THREE.Vector3(3, 1.1, -2), color: "#a855f7", element: null as HTMLDivElement | null },
    { name: "Server Vault", pos: new THREE.Vector3(-6, 2.3, -5), color: "#ff9100", element: null as HTMLDivElement | null },
        { name: "QA Board", pos: new THREE.Vector3(6, 1.7, -5), color: "#eab308", element: null as HTMLDivElement | null },
    { name: "DevOps Console", pos: new THREE.Vector3(6, 1.4, 2), color: "#10b981", element: null as HTMLDivElement | null }
  ];
  constructor(canvasId: string) {
    this.canvas = document.getElementById(canvasId) as HTMLCanvasElement;
    if (!this.canvas) {
      throw new Error(`Canvas with id ${canvasId} not found`);
    }
    const parent = this.canvas.parentElement;
    if (parent) {
      // Nettoyer d'anciens conteneurs de bulles si rechargement
      const oldBubbles = parent.querySelector(".swarm-bubbles-container");
      if (oldBubbles) oldBubbles.remove();
      this.bubbleContainer = document.createElement("div");
      this.bubbleContainer.className = "swarm-bubbles-container";
      Object.assign(this.bubbleContainer.style, {
        position: 'absolute',
        inset: '0',
        pointerEvents: 'none',
        zIndex: '10'
      });
      parent.appendChild(this.bubbleContainer);
      // Récupérer les éléments du dashboard
      const dashboard = parent.closest("#swarm-lounge-hud");
      if (dashboard) {
        this.labelsOverlay = dashboard.querySelector("#swarm-labels-overlay");
        this.tableBody = dashboard.querySelector("#swarm-lounge-table-body");
        this.activeCountEl = dashboard.querySelector("#swarm-active-count");
      }
    }
    this.initThree();
    this.initOffice();
    this.initAgents();
    this.initSidebarEvents();
    this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
    // Observer le changement de taille du conteneur parent (redimensionnement manuel du widget)
    if (parent && typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(() => {
        this.resizeCanvas();
      });
      observer.observe(parent);
    }
  }
  private initThree() {
    this.scene = new THREE.Scene();
    // Le fond de la scène reste transparent pour fusionner avec le HUD
    // Caméra orthographique pour une vraie perspective isométrique
    const aspect = this.width / this.height;
        const d = 7.5; // Zoom optimal pour cadrer tout le bureau 3D
    this.camera = new THREE.OrthographicCamera(-d * aspect, d * aspect, d, -d, 1, 1000);
        // Position angulaire de la caméra isométrique centrée
    this.camera.position.set(18, 14, 18);
        this.camera.lookAt(0, -0.2, 0);
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true
    });
    this.renderer.setSize(this.width, this.height);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.setClearColor(0x000000, 0); // Rendu transparent
    // Lumières douces et blanches pour un rendu de bureau clair
    const ambient = new THREE.AmbientLight(0xf1f5f9, 1.8); // Ambiante blanche et lumineuse
    this.scene.add(ambient);
    const dirLight = new THREE.DirectionalLight(0xffffff, 3.2); // Lumière principale blanche
    dirLight.position.set(12, 22, 8);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 1024;
    dirLight.shadow.mapSize.height = 1024;
    dirLight.shadow.bias = -0.001;
    this.scene.add(dirLight);
    const backLight = new THREE.DirectionalLight(0x93c5fd, 1.5); // Lumière de remplissage bleue
    backLight.position.set(-10, 8, -5);
    this.scene.add(backLight);
    // Lumières néon localisées de faible portée pour faire ressortir les stations
    const pmLight = new THREE.PointLight(0xff9100, 1.2, 6);
    pmLight.position.set(-6, 2, -5);
    this.scene.add(pmLight);
    const devLight = new THREE.PointLight(0x00e5ff, 1.2, 6);
    devLight.position.set(0, 2, -2);
    this.scene.add(devLight);
    const qaLight = new THREE.PointLight(0xff2e4d, 1.2, 6);
    qaLight.position.set(6, 2, -5);
    this.scene.add(qaLight);
  }
  /**
   * Construit la scène de bureau isométrique en 3D
   */
  private initOffice() {
        // 1. Sol clair épuré brillant (white tiles look) étendu
    const floorGeo = new THREE.PlaneGeometry(24, 24);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.2,
      metalness: 0.02
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    this.scene.add(floor);
    // Grille douce sur le sol étendu
    const grid = new THREE.GridHelper(24, 24, 0xcbd5e1, 0xe2e8f0);
    grid.position.y = 0.01;
    (grid.material as THREE.Material).opacity = 0.25;
    (grid.material as THREE.Material).transparent = true;
    this.scene.add(grid);
    // 2. Cloisons en verre épurées (glass partitions)
    const glassGeo = new THREE.BoxGeometry(0.04, 1.8, 6.0);
    const glassMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.15,
      roughness: 0.05,
      metalness: 0.9
    });
    const frameGeo = new THREE.BoxGeometry(0.08, 0.06, 6.0);
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.8, roughness: 0.2 });
    // Cloison de gauche (délimite le coffre du PM)
    const glass1 = new THREE.Mesh(glassGeo, glassMat);
    glass1.position.set(-3.5, 0.9, -1.5);
    this.scene.add(glass1);
    const frame1 = new THREE.Mesh(frameGeo, frameMat);
    frame1.position.set(-3.5, 1.8, -1.5);
    this.scene.add(frame1);
    // Cloison de droite (délimite le tableau du QA)
    const glass2 = new THREE.Mesh(glassGeo, glassMat);
    glass2.position.set(3.5, 0.9, -1.5);
    this.scene.add(glass2);
    const frame2 = new THREE.Mesh(frameGeo, frameMat);
    frame2.position.set(3.5, 1.8, -1.5);
    this.scene.add(frame2);
    // 3. Desk 01 (Workstation du DEV au centre)
    const deskGroup = new THREE.Group();
    deskGroup.position.set(0, 0, -2);
    
    // Plateau table
    const table = new THREE.Mesh(
      new THREE.BoxGeometry(3, 0.08, 1.4),
      new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.4 })
    );
    table.position.y = 1.0;
    table.castShadow = true;
    table.receiveShadow = true;
    deskGroup.add(table);
    // Pieds table
    const legGeo = new THREE.BoxGeometry(0.08, 1.0, 0.08);
    const legMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.8 });
    const positions = [
      [-1.4, 0.5, -0.6], [1.4, 0.5, -0.6],
      [-1.4, 0.5, 0.6], [1.4, 0.5, 0.6]
    ];
    positions.forEach(pos => {
      const leg = new THREE.Mesh(legGeo, legMat);
      leg.position.set(pos[0], pos[1], pos[2]);
      deskGroup.add(leg);
    });
    // Écran 1 (Gauche)
    const screen1 = new THREE.Mesh(
      new THREE.BoxGeometry(0.8, 0.5, 0.06),
      new THREE.MeshStandardMaterial({ color: 0x0f172a })
    );
    screen1.position.set(-0.5, 1.4, -0.4);
    screen1.rotation.y = 0.2;
    deskGroup.add(screen1);
        const face1 = new THREE.Mesh(
      new THREE.PlaneGeometry(0.76, 0.46),
      new THREE.MeshBasicMaterial({ color: 0x00e5ff, toneMapped: false }) // Écran allumé cyan
    );
    face1.position.set(-0.5, 1.4, -0.36);
    face1.rotation.y = 0.2;
    deskGroup.add(face1);
    // Écran 2 (Droit)
    const screen2 = new THREE.Mesh(
      new THREE.BoxGeometry(0.8, 0.5, 0.06),
      new THREE.MeshStandardMaterial({ color: 0x0f172a })
    );
    screen2.position.set(0.5, 1.4, -0.4);
    screen2.rotation.y = -0.2;
    deskGroup.add(screen2);
    const face2 = new THREE.Mesh(
      new THREE.PlaneGeometry(0.76, 0.46),
      new THREE.MeshBasicMaterial({ color: 0x00e5ff, toneMapped: false })
    );
    face2.position.set(0.5, 1.4, -0.36);
    face2.rotation.y = -0.2;
    deskGroup.add(face2);
    this.scene.add(deskGroup);
    // 4. Vault (Coffre/Serveur du PM)
    const vault = new THREE.Mesh(
      new THREE.BoxGeometry(1.6, 2.2, 1.6),
      new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.3, metalness: 0.5 })
    );
    vault.position.set(-6, 1.1, -5);
    vault.castShadow = true;
    this.scene.add(vault);
    // Néons de statut sur le serveur
    const neonPM = new THREE.Mesh(
      new THREE.BoxGeometry(1.4, 0.08, 0.08),
      new THREE.MeshBasicMaterial({ color: 0xff9100 })
    );
        neonPM.position.set(-6, 1.8, -4.18);
    this.scene.add(neonPM);
    // 5. Whiteboard (Tableau de QA)
    const boardGroup = new THREE.Group();
    boardGroup.position.set(6, 0, -5);
    const board = new THREE.Mesh(
      new THREE.BoxGeometry(3.2, 2.0, 0.1),
      new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.2 })
    );
    board.position.y = 1.6;
    board.castShadow = true;
    boardGroup.add(board);
    // Trépieds tableau
    const standGeo = new THREE.BoxGeometry(0.08, 1.0, 0.08);
    const stand1 = new THREE.Mesh(standGeo, legMat);
    stand1.position.set(-1.5, 0.5, 0);
    boardGroup.add(stand1);
    const stand2 = new THREE.Mesh(standGeo, legMat);
    stand2.position.set(1.5, 0.5, 0);
    boardGroup.add(stand2);
    this.scene.add(boardGroup);
    // 6. Security Gate (Turnstile à l'entrée)
    const gateGroup = new THREE.Group();
    gateGroup.position.set(0, 0, 5);
    const postMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.8 });
    const postGeo = new THREE.CylinderGeometry(0.12, 0.12, 1.4, 16);
    const post1 = new THREE.Mesh(postGeo, postMat);
    post1.position.set(-1.2, 0.7, 0);
    gateGroup.add(post1);
    const post2 = new THREE.Mesh(postGeo, postMat);
    post2.position.set(1.2, 0.7, 0);
    gateGroup.add(post2);
    // Ligne laser de sécurité (Rouge)
    const laser = new THREE.Mesh(
      new THREE.CylinderGeometry(0.02, 0.02, 2.4, 8),
      new THREE.MeshBasicMaterial({ color: 0xff2e4d })
    );
    laser.rotation.z = Math.PI / 2;
    laser.position.set(0, 0.8, 0);
    gateGroup.add(laser);
    this.scene.add(gateGroup);
    // Créer les marqueurs HTML statiques projetés
    if (this.labelsOverlay) {
      this.labelsOverlay.innerHTML = "";
      this.staticMarkers.forEach(marker => {
        const el = document.createElement("div");
        el.className = "lounge-3d-marker";
        el.style.color = marker.color;
        el.textContent = marker.name;
        this.labelsOverlay!.appendChild(el);
        marker.element = el;
      });
    }
  }
  private initAgents() {
    this.agents = [
      {
        name: "orange-agent",
        role: "PM",
        color: "#ff9100", // Orange
        x: -5,
        z: -2,
        targetX: -5,
        targetZ: -2,
        state: "idle",
        bubbleText: "",
        bubbleTimer: 0,
        group: this.createAgentMesh(0xff9100),
        walkTime: 0,
                taskName: "En attente",
        projectName: "---",
        startTime: 0,
        elapsedTime: 0,
        tokens: 0,
        cost: 0,
        active: false
      },
      {
        name: "pink-agent",
        role: "UI",
        color: "#ec4899", // Rose / Pink
        x: -3,
        z: 1,
        targetX: -3,
        targetZ: 1,
        state: "idle",
        bubbleText: "",
        bubbleTimer: 0,
        group: this.createAgentMesh(0xec4899),
        walkTime: Math.PI * 0.25,
        taskName: "En attente",
        projectName: "---",
        startTime: 0,
        elapsedTime: 0,
        tokens: 0,
        cost: 0,
        active: false
      },
      {
        name: "blue-agent",
        role: "DEV",
        color: "#00e5ff", // Cyan
        x: 0,
        z: 2,
        targetX: 0,
        targetZ: 2,
        state: "idle",
        bubbleText: "",
        bubbleTimer: 0,
        group: this.createAgentMesh(0x00e5ff),
        walkTime: Math.PI * 0.5,
                taskName: "Prêt",
        projectName: "---",
        startTime: 0,
        elapsedTime: 0,
        tokens: 0,
        cost: 0,
        active: false
      },
      {
                name: "purple-agent",
        role: "SEC",
        color: "#a855f7", // Violet
        x: 3,
        z: 1,
        targetX: 3,
        targetZ: 1,
        state: "idle",
        bubbleText: "",
        bubbleTimer: 0,
        group: this.createAgentMesh(0xa855f7),
        walkTime: Math.PI * 0.75,
        taskName: "En attente",
        projectName: "---",
        startTime: 0,
        elapsedTime: 0,
        tokens: 0,
        cost: 0,
        active: false
      },
      {
        name: "yellow-agent",
        role: "QA",
                color: "#eab308", // Jaune / Or
        x: 5,
        z: -2,
        targetX: 5,
        targetZ: -2,
        state: "idle",
        bubbleText: "",
        bubbleTimer: 0,
                group: this.createAgentMesh(0xeab308),
        walkTime: Math.PI,
                taskName: "En attente",
        projectName: "---",
        startTime: 0,
        elapsedTime: 0,
        tokens: 0,
        cost: 0,
        active: false
      },
      {
        name: "emerald-agent",
        role: "OPS",
        color: "#10b981", // Émeraude / Vert
        x: 4,
        z: 3,
        targetX: 4,
        targetZ: 3,
        state: "idle",
        bubbleText: "",
        bubbleTimer: 0,
        group: this.createAgentMesh(0x10b981),
        walkTime: Math.PI * 1.25,
        taskName: "En attente",
        projectName: "---",
        startTime: 0,
        elapsedTime: 0,
        tokens: 0,
        cost: 0,
        active: false
      }
    ];
    this.agents.forEach(agent => {
      this.scene.add(agent.group);
      this.createHTMLBubble(agent);
    });
    this.renderTable();
  }
  /**
   * Crée la figurine 3D d'un agent (bonhomme capsule brillant)
   */
  private createAgentMesh(colorHex: number): THREE.Group {
    const group = new THREE.Group();
        // Matériau très brillant pour effet figurine plastique premium style jouet
    const material = new THREE.MeshStandardMaterial({
      color: colorHex,
      roughness: 0.05,
      metalness: 0.1
    });
    // Corps plus grand (Capsule/Cylindre arrondi)
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.38, 0.38, 0.95, 16),
      material
    );
    body.position.y = 0.58;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);
    // Tête assortie
    const head = new THREE.Mesh(
      new THREE.SphereGeometry(0.38, 16, 16),
      material
    );
    head.position.y = 1.2;
    head.castShadow = true;
    group.add(head);
    // Visière lumineuse (Yeux)
    const visor = new THREE.Mesh(
      new THREE.BoxGeometry(0.46, 0.1, 0.1),
      new THREE.MeshBasicMaterial({ color: 0xffffff })
    );
    visor.position.set(0, 1.18, 0.28);
    group.add(visor);
    // Bras gauche
    const leftArm = new THREE.Mesh(
      new THREE.SphereGeometry(0.1, 8, 8),
      material
    );
    leftArm.position.set(-0.48, 0.65, 0);
    leftArm.name = "leftArm";
    group.add(leftArm);
        // Bras droit
    const rightArm = new THREE.Mesh(
      new THREE.SphereGeometry(0.1, 8, 8),
      material
    );
    rightArm.position.set(0.48, 0.65, 0);
    rightArm.name = "rightArm";
    group.add(rightArm);
    // Pied gauche
    const leftFoot = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 8, 8),
      material
    );
    leftFoot.position.set(-0.2, 0.08, 0);
    leftFoot.name = "leftFoot";
    leftFoot.castShadow = true;
    group.add(leftFoot);
    // Pied droit
    const rightFoot = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 8, 8),
      material
    );
    rightFoot.position.set(0.2, 0.08, 0);
    rightFoot.name = "rightFoot";
    rightFoot.castShadow = true;
    group.add(rightFoot);
    return group;
  }
  /**
   * Crée la bulle de dialogue HTML superposée au canvas
   */
  private createHTMLBubble(agent: Agent) {
    if (!this.bubbleContainer) return;
    const bubble = document.createElement("div");
    bubble.className = "swarm-html-bubble";
    Object.assign(bubble.style, {
      position: 'absolute',
      background: 'rgba(5, 8, 16, 0.95)',
      border: `1px solid ${agent.color}`,
      color: '#ffffff',
            padding: '4px 8px',
      borderRadius: '4px',
      fontFamily: "'Courier New', monospace",
      fontSize: '8px',
      whiteSpace: 'nowrap',
      pointerEvents: 'none',
      transform: 'translate(-50%, -100%)',
      display: 'none',
      boxShadow: `0 0 10px ${agent.color}44`,
      zIndex: '20',
      transition: 'opacity 0.15s ease'
    });
    bubble.innerHTML = `
      <div class="bubble-text"></div>
      <div style="position:absolute; bottom:-6px; left:50%; transform:translateX(-50%); color:${agent.color}; font-size:9px; line-height:1;">▼</div>
    `;
    this.bubbleContainer.appendChild(bubble);
    agent.bubbleEl = bubble;
  }
  private initSidebarEvents() {
    // Boutons de la barre latérale - Actions interactives amusantes
    const actions: { [key: string]: { speaker: 'PM' | 'DEV' | 'QA', quote: string } } = {
      'lounge-action-board': { speaker: 'PM', quote: "Affichage du tableau Kanban sur l'écran central." },
      'lounge-action-sync': { speaker: 'DEV', quote: "Synchronisation de l'espace de travail..." },
      'lounge-action-github': { speaker: 'PM', quote: "Liaison au dépôt GitHub NeyorDEV/jarvis effectuée." },
      'lounge-action-assign': { speaker: 'PM', quote: "Ticket JARVIS-409 assigné au développeur." },
      'lounge-action-column': { speaker: 'PM', quote: "Limite de travail en cours fixée à 5." },
      'lounge-action-queue': { speaker: 'QA', quote: "Revue de code mise en file d'attente." },
      'swarm-add-agent-btn': { speaker: 'PM', quote: "Recherche de nœuds d'agents... Réseau stable." }
    };
        Object.keys(actions).forEach(id => {
      const btn = document.getElementById(id);
      if (btn) {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          const item = actions[id];
          const agent = this.agents.find(a => a.role === item.speaker);
          if (agent) {
            agent.bubbleText = item.quote;
            agent.bubbleTimer = 150; // 2.5 secondes
            
            // Effet d'animation de survol de bras de l'agent
            agent.state = 'typing';
            setTimeout(() => {
              if (agent.state === 'typing' && !this.isSwarmActive) {
                agent.state = 'idle';
              }
            }, 2500);
          }
        });
      }
    });
  }
  public start() {
    if (this.animationFrameId) return;
    const loop = () => {
      this.update();
      this.draw();
      this.time++;
      this.animationFrameId = requestAnimationFrame(loop);
    };
    this.animationFrameId = requestAnimationFrame(loop);
  }
  public stop() {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }
  public updateSwarmStatus(
        agentRole: 'PM' | 'UI' | 'DEV' | 'SEC' | 'QA' | 'OPS' | null, 
    status: 'in_progress' | 'success' | 'failure' | 'idle',
    message?: string,
    projectName?: string
  ) {
    const proj = projectName || "jarvis_swarm";
    const msg = message || (status === 'success' ? "Tâche validée avec succès" : status === 'failure' ? "Échec de traitement" : "Prêt");
    if (status === 'in_progress') {
      this.isSwarmActive = true;
      this.activeAgentRole = agentRole;
      this.agents.forEach(agent => {
        if (agent.role === agentRole) {
          agent.active = true;
          agent.taskName = msg;
          agent.projectName = proj;
          agent.startTime = performance.now();
          agent.elapsedTime = 0;
          agent.tokens = agent.tokens === 0 ? 1200 : agent.tokens;
          agent.cost = agent.cost === 0 ? 0.0018 : agent.cost;
        } else {
          agent.active = false;
        }
      });
    } else {
      this.isSwarmActive = false;
      this.activeAgentRole = null;
      
      this.agents.forEach(agent => {
        if (agent.active) {
          agent.active = false;
          agent.taskName = status === 'success' ? "Terminé (Succès)" : "Terminé (Échec)";
        }
      });
    }
    this.renderTable();
  }
  private resizeCanvas() {
    const container = this.canvas.parentElement;
    if (container) {
      const rect = container.getBoundingClientRect();
            this.width = rect.width || 500;
      this.height = rect.height || 280;
      
      this.canvas.width = this.width;
      this.canvas.height = this.height;
      if (this.renderer && this.camera) {
        this.renderer.setSize(this.width, this.height);
        const aspect = this.width / this.height;
        const d = 6.2; // Zoom ajusté
        this.camera.left = -d * aspect;
        this.camera.right = d * aspect;
        this.camera.top = d;
        this.camera.bottom = -d;
        this.camera.updateProjectionMatrix();
      }
    }
  }
  private update() {
    // 1. Déclencher des répliques aléatoires au repos
    if (!this.isSwarmActive && Math.random() < 0.004) {
      const agent = this.agents[Math.floor(Math.random() * this.agents.length)];
      if (agent.bubbleTimer <= 0) {
        let quote = "";
        if (agent.role === "PM") quote = this.pmQuotes[Math.floor(Math.random() * this.pmQuotes.length)];
        else if (agent.role === "UI") quote = this.uiQuotes[Math.floor(Math.random() * this.uiQuotes.length)];
        else if (agent.role === "DEV") quote = this.devQuotes[Math.floor(Math.random() * this.devQuotes.length)];
        else if (agent.role === "SEC") quote = this.secQuotes[Math.floor(Math.random() * this.secQuotes.length)];
        else if (agent.role === "QA") quote = this.qaQuotes[Math.floor(Math.random() * this.qaQuotes.length)];
        else if (agent.role === "OPS") quote = this.opsQuotes[Math.floor(Math.random() * this.opsQuotes.length)];
        
        agent.bubbleText = quote;
        agent.bubbleTimer = 180; // 3 secondes
      }
    }
        // 2. Mettre à jour les agents et la télémétrie active
    let tableNeedsRefresh = false;
    this.agents.forEach(agent => {
      if (agent.bubbleTimer > 0) {
        agent.bubbleTimer--;
      }
      // Incrémentation en temps réel des compteurs de télémétrie active
      if (agent.active) {
        agent.elapsedTime = performance.now() - agent.startTime;
                // Simuler une augmentation progressive des tokens
        if (this.time % 20 === 0) {
          agent.tokens += Math.floor(Math.random() * 20) + 10;
          agent.cost = agent.tokens * 0.0000015; // Gemini Flash pricing model
        }
        tableNeedsRefresh = true;
      }
      // Déterminer la position cible selon l'activité de l'essaim
      if (this.isSwarmActive) {
        // En mission : positions fixes devant leurs terminaux
        if (agent.role === "PM") {
                    agent.targetX = -6; // Coffre Serveur
          agent.targetZ = -3.2;
        } else if (agent.role === "UI") {
          agent.targetX = -3; // UI Studio
          agent.targetZ = -0.5;
        } else if (agent.role === "DEV") {
                    agent.targetX = 0; // Bureau central
          agent.targetZ = -0.5;
        } else if (agent.role === "SEC") {
          agent.targetX = 3; // Security Gate
          agent.targetZ = -0.5;
        } else if (agent.role === "QA") {
                    agent.targetX = 6; // Tableau blanc
          agent.targetZ = -3.2;
        } else if (agent.role === "OPS") {
          agent.targetX = 6; // DevOps Console
          agent.targetZ = 2;
        }
        if (this.activeAgentRole === agent.role) {
          agent.state = 'typing';
          if (Math.random() < 0.015 && agent.bubbleTimer <= 0) {
                        const statusMsgs: Record<string, string> = {
              "PM": "Conception des spécifications...",
              "UI": "Création du Design System Glassmorphic...",
              "DEV": "Implémentation du code source...",
              "SEC": "Audit des vulnérabilités & failles...",
              "QA": "Exécution sandbox & validation...",
              "OPS": "Packaging & déploiement sandbox..."
            };
            agent.bubbleText = statusMsgs[agent.role] || "En action...";
            agent.bubbleTimer = 80;
          }
        } else {
          agent.state = 'idle';
        }
      } else {
        // Au repos : vagabondage aléatoire
        agent.state = 'wandering';
        const dist = Math.sqrt(Math.pow(agent.x - agent.targetX, 2) + Math.pow(agent.z - agent.targetZ, 2));
        if (dist < 0.3) {
          // Nouvelle destination dans la pièce
          agent.targetX = (Math.random() - 0.5) * 12;
          agent.targetZ = -3 + Math.random() * 7;
        }
      }
      // Déplacement fluide vers la cible (interpolation)
      const dx = agent.targetX - agent.x;
      const dz = agent.targetZ - agent.z;
      const dist = Math.sqrt(dx * dx + dz * dz);
      
      const isMoving = dist > 0.1;
      
      if (isMoving) {
        const speed = this.isSwarmActive ? 0.08 : 0.035;
        agent.x += (dx / dist) * speed;
        agent.z += (dz / dist) * speed;
        agent.walkTime += 0.15;
                // S'orienter vers la direction du mouvement
        const angle = Math.atan2(dx, dz);
        agent.group.rotation.y = angle;
      } else {
        // Face à l'écran/action en activité
        if (agent.state === "typing" || this.isSwarmActive) {
          agent.group.rotation.y = Math.PI; // Face au tableau ou bureau
        } else {
          agent.group.rotation.y = Math.sin(this.time * 0.01) * 0.2; // Petit balancement
        }
      }
      // Appliquer les coordonnées à la figurine 3D
      agent.group.position.x = agent.x;
      agent.group.position.z = agent.z;
      // Animation des bras et pieds
      const leftFoot = agent.group.getObjectByName("leftFoot") as THREE.Mesh;
      const rightFoot = agent.group.getObjectByName("rightFoot") as THREE.Mesh;
      const leftArm = agent.group.getObjectByName("leftArm") as THREE.Mesh;
      const rightArm = agent.group.getObjectByName("rightArm") as THREE.Mesh;
      if (isMoving) {
        // Balancement des pieds et saut léger
        agent.group.position.y = Math.abs(Math.sin(agent.walkTime * 2)) * 0.22;
        if (leftFoot && rightFoot) {
          leftFoot.position.z = Math.sin(agent.walkTime * 2) * 0.2;
          rightFoot.position.z = -Math.sin(agent.walkTime * 2) * 0.2;
        }
        if (leftArm && rightArm) {
          leftArm.position.z = -Math.sin(agent.walkTime * 2) * 0.25;
          rightArm.position.z = Math.sin(agent.walkTime * 2) * 0.25;
          leftArm.position.y = 0.65 + Math.sin(agent.walkTime * 2) * 0.1;
          rightArm.position.y = 0.65 - Math.sin(agent.walkTime * 2) * 0.1;
        }
      } else {
                // Rester au sol, lévitation/respiration douce
        agent.group.position.y = Math.sin(this.time * 0.05 + agent.walkTime) * 0.03;
        if (leftFoot && rightFoot) {
          leftFoot.position.z = 0;
          rightFoot.position.z = 0;
        }
        if (leftArm && rightArm) {
          if (agent.state === 'typing') {
            // Animation de frappe de code (bras s'agitent)
            leftArm.position.set(-0.35, 0.72, 0.22);
            rightArm.position.set(0.35, 0.72, 0.22);
            leftArm.position.y = 0.72 + Math.sin(this.time * 0.4) * 0.08;
            rightArm.position.y = 0.72 + Math.cos(this.time * 0.4) * 0.08;
          } else {
            // Bras ballants repos
            leftArm.position.set(-0.48, 0.65, 0);
            rightArm.position.set(0.48, 0.65, 0);
          }
        }
      }
    });
    if (tableNeedsRefresh) {
      this.renderTable();
    }
  }
  private draw() {
    this.renderer.render(this.scene, this.camera);
    this.updateHTMLBubbles();
    this.update3DMarkers();
  }
  /**
   * Projette la position 3D de chaque agent pour placer sa bulle HTML
   */
  private updateHTMLBubbles() {
    this.agents.forEach(agent => {
      const bubble = agent.bubbleEl;
      if (!bubble) return;
            if (agent.bubbleTimer > 0) {
        bubble.querySelector(".bubble-text")!.textContent = agent.bubbleText;
        bubble.style.display = 'block';
        const vector = new THREE.Vector3();
        agent.group.getWorldPosition(vector);
        vector.y += 1.6; // Offset au-dessus de la tête
        vector.project(this.camera);
        const x = (vector.x * 0.5 + 0.5) * this.width;
        const y = (-(vector.y) * 0.5 + 0.5) * this.height;
        bubble.style.left = `${x}px`;
        bubble.style.top = `${y}px`;
        bubble.style.opacity = '1';
      } else {
        bubble.style.opacity = '0';
        setTimeout(() => {
          if (agent.bubbleTimer <= 0) {
            bubble.style.display = 'none';
          }
        }, 150);
      }
    });
  }
  /**
   * Projette les étiquettes statiques et dynamiques du bureau en 3D vers l'écran 2D
   */
  private update3DMarkers() {
    if (!this.labelsOverlay) return;
    // 1. Projeter les marqueurs de zone statiques
    this.staticMarkers.forEach(marker => {
      if (!marker.element) return;
      
      const vec = marker.pos.clone();
      vec.project(this.camera);
      
      // Si hors caméra, cacher
      if (Math.abs(vec.x) > 1 || Math.abs(vec.y) > 1) {
        marker.element.style.display = 'none';
                return;
      }
      
      const x = (vec.x * 0.5 + 0.5) * this.width;
      const y = (-(vec.y) * 0.5 + 0.5) * this.height;
      
      marker.element.style.left = `${x}px`;
      marker.element.style.top = `${y}px`;
      marker.element.style.display = 'flex';
    });
    // 2. Projeter des marqueurs dynamiques pour chaque agent au-dessus de son corps
    this.agents.forEach(agent => {
      let markerEl = agent.group.userData.markerEl as HTMLDivElement | null;
      if (!markerEl && this.labelsOverlay) {
        markerEl = document.createElement("div");
        markerEl.className = "lounge-3d-marker";
        markerEl.style.color = agent.color;
        this.labelsOverlay!.appendChild(markerEl);
        agent.group.userData.markerEl = markerEl;
      }
      
      if (markerEl) {
                markerEl.textContent = `AGENT: ${agent.role}`; // Nom de rôle lisible (ex: AGENT: DEV)
      }
      
      if (markerEl) {
        const vec = new THREE.Vector3();
        agent.group.getWorldPosition(vec);
        vec.y += 1.4; // Position au dessus du corps
        vec.project(this.camera);
        
        if (Math.abs(vec.x) > 1 || Math.abs(vec.y) > 1) {
          markerEl.style.display = 'none';
          return;
        }
        
        const x = (vec.x * 0.5 + 0.5) * this.width;
        const y = (-(vec.y) * 0.5 + 0.5) * this.height;
        
        markerEl.style.left = `${x}px`;
        markerEl.style.top = `${y}px`;
        markerEl.style.display = 'flex';
      }
    });
  }
  private renderTable() {
    const tbody = this.tableBody;
    if (!tbody) return;
    
    // Mettre à jour l'indicateur d'agents actifs de la barre latérale
    if (this.activeCountEl) {
      const activeCount = this.agents.filter(a => a.active).length;
      this.activeCountEl.textContent = `${activeCount > 0 ? activeCount : 3} Agents Active`;
    }
    
    tbody.innerHTML = "";
    this.agents.forEach(agent => {
      const row = document.createElement("tr");
      if (agent.active) {
        row.className = "active-row";
      }
            const durationStr = this.formatDuration(agent.elapsedTime);
      const costStr = agent.cost > 0 ? `$${agent.cost.toFixed(4)}` : "$0.0000";
      const tokensStr = agent.tokens.toLocaleString();
      
      row.innerHTML = `
        <td>
          <div class="agent-cell">
            <span class="agent-dot ${agent.role.toLowerCase()}"></span>
            <span>${agent.name}</span>
          </div>
        </td>
        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis;" title="${agent.taskName}">${agent.taskName}</td>
        <td>${agent.projectName}</td>
        <td class="duration-cell">${durationStr}</td>
        <td>${tokensStr}</td>
        <td style="color: rgba(255, 255, 255, 0.95); font-weight: 600;">${costStr}</td>
      `;
      tbody.appendChild(row);
    });
  }
  private formatDuration(ms: number): string {
    if (ms <= 0) return "00:00:00";
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    const centiseconds = Math.floor((ms % 1000) / 10);
    
    const minStr = minutes.toString().padStart(2, '0');
    const secStr = seconds.toString().padStart(2, '0');
    const centiStr = centiseconds.toString().padStart(2, '0');
    
    return `${minStr}:${secStr}:${centiStr}`;
  }
}
