import * as THREE from 'three';
import { feature } from 'topojson-client';

interface RadarConnection {
  ip: string;
  port: number;
  process: string;
  country: string;
  cc: string;
  city?: string;
  lat: number;
  lon: number;
  isp: string;
  risk: 'normal' | 'medium' | 'high';
  hostname?: string;
  service?: string;
  duration_s: number;
  is_new: boolean;
  is_filtered: boolean;
  port_scan: boolean;
}

interface ArcData {
  curve: THREE.QuadraticBezierCurve3;
  lineMesh: THREE.Line;
  headMesh: THREE.Mesh;
  headProgress: number;
  headSpeed: number;
  baseColor: number;
}

const RISK_COLOR: Record<string, number> = {
  normal: 0x00e5ff,
  medium: 0xff8a1a,
  high:   0xff2e4d,
};


// Préchargement des frontières pays en arrière-plan dès l'import du module
let _countryBorderPoints: THREE.Vector3[][] | null = null;
let _bordersReady = false;

(async () => {
  try {
    const topo = await import('world-atlas/countries-110m.json');
    const geojson = feature(topo as any, (topo as any).objects.countries) as any;
    _countryBorderPoints = [];
    for (const f of geojson.features) {
      const geom = f.geometry;
      const polys: number[][][][] =
        geom.type === 'Polygon'      ? [geom.coordinates] :
        geom.type === 'MultiPolygon' ? geom.coordinates   : [];
      for (const poly of polys) {
        for (const ring of poly) {
          // Éviter les lignes qui "coupent" à travers le globe entre 179° et -179°
          const pts: THREE.Vector3[] = [];
          let prevLon: number | null = null;
          for (const [lon, lat] of ring as [number, number][]) {
            if (prevLon !== null && Math.abs(lon - prevLon) > 170) {
              if (pts.length > 1) _countryBorderPoints!.push([...pts]);
              pts.length = 0;
            }
            pts.push(_ll2v(lat, lon, 2.205));
            prevLon = lon;
          }
          if (pts.length > 1) _countryBorderPoints!.push(pts);
        }
      }
    }
    _bordersReady = true;
  } catch (e) {
    console.warn('[RADAR] Frontières pays non disponibles :', e);
  }
})();

function _ll2v(lat: number, lon: number, r: number): THREE.Vector3 {
  const phi   = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
     r * Math.cos(phi),
     r * Math.sin(phi) * Math.sin(theta)
  );
}

export class NetworkRadar {
  public active = false;
  private scene: THREE.Scene;
  private camera: THREE.Camera;
  private group: THREE.Group;

  private globeGroup: THREE.Group | null = null;
  private arcsGroup: THREE.Group | null = null;
  private dotsGroup: THREE.Group | null = null;

  private arcs: Map<string, ArcData> = new Map();
  private destDots: Map<string, THREE.Mesh> = new Map();

  private _allConnections: RadarConnection[] = [];
  private _showFiltered = false;
  private _highlightedIp: string | null = null;
  private _targetRotY: number | null = null;
  private _onCanvasClick: ((e: MouseEvent) => void) | null = null;
  private _searchQuery = '';
  private _activeTab: 'active' | 'blocked' = 'active';
  private _blockedIps: string[] = [];

  private static readonly HL_COLOR = 0xa855f7;

  private readonly R = 2.2;
  private readonly LOCAL_LAT = 46.0;
  private readonly LOCAL_LON = 2.0;

  private savedCameraPos = new THREE.Vector3();
  private globeRotY = 0;
  private time = 0;

  // Mouse drag pour rotation globe
  private _mouseRightDown = false;
  private _mouseLastX = 0;
  private _mouseLastY = 0;
  private _globeRotX = 0;
  private _onMouseDown: ((e: MouseEvent) => void) | null = null;
  private _onMouseMove: ((e: MouseEvent) => void) | null = null;
  private _onMouseUp: ((e: MouseEvent) => void) | null = null;
  private _onContextMenu: ((e: MouseEvent) => void) | null = null;

  // Hand drag pour rotation globe via MediaPipe
  private _onHandMove: ((e: any) => void) | null = null;
  private _isHandDragging = false;
  private _lastHandX = 0;
  private _lastHandY = 0;

  constructor(scene: THREE.Scene, camera: THREE.Camera) {
    this.scene = scene;
    this.camera = camera;
    this.group = new THREE.Group();
    this.group.name = 'network_radar_group';
  }

  // ── Activation ──────────────────────────────────────────────────────────────

  public activate(): void {
    if (this.active) return;
    this.active = true;

    this.scene.traverse(child => {
      if (['domotic_group', 'cortex_group', 'explorer_group', 'chess_map_group']
          .includes(child.name)) child.visible = false;
    });

    this.savedCameraPos.copy(this.camera.position);
    this.scene.add(this.group);

    this.globeGroup = new THREE.Group();
    this.arcsGroup  = new THREE.Group();
    this.dotsGroup  = new THREE.Group();
    this.group.add(this.globeGroup, this.arcsGroup, this.dotsGroup);

    this.buildGlobe();

    this.camera.position.set(0, 1.5, 6.2);
    (this.camera as any).lookAt(new THREE.Vector3(0, 0, 0));

    const panel = document.getElementById('network-radar-panel');
    if (panel) panel.style.display = 'flex';

    // Barre de recherche
    const searchInput = document.getElementById('radar-search') as HTMLInputElement | null;
    if (searchInput) {
      searchInput.value = '';
      this._searchQuery = '';
      searchInput.addEventListener('input', () => {
        this._searchQuery = searchInput.value.toLowerCase().trim();
        this._refreshActiveList();
      });
    }

    // Exposition globale pour les boutons inline HTML
    (window as any)._networkRadar = this;

    this._setupMouseRotation();
  }

  public deactivate(): void {
    if (!this.active) return;
    this.active = false;

    this.scene.traverse(child => {
      if (['domotic_group', 'cortex_group'].includes(child.name)) child.visible = true;
    });

    this.clearAll();
    this.scene.remove(this.group);
    this.camera.position.copy(this.savedCameraPos);

    const panel = document.getElementById('network-radar-panel');
    if (panel) panel.style.display = 'none';

    // Reset état tabs/recherche
    this._searchQuery = '';
    this._activeTab = 'active';
    (window as any)._networkRadar = null;

    this._teardownMouseRotation();
  }

  // ── Onglets ─────────────────────────────────────────────────────────────────

  public switchTab(tab: 'active' | 'blocked'): void {
    this._activeTab = tab;
    const listEl    = document.getElementById('radar-connections-list');
    const blockedEl = document.getElementById('radar-blocked-list');
    const statsBar  = document.getElementById('radar-stats-bar');
    const searchBar = document.getElementById('radar-search-bar');
    const tabActive  = document.getElementById('radar-tab-active');
    const tabBlocked = document.getElementById('radar-tab-blocked');

    if (tab === 'active') {
      if (listEl)    listEl.style.display    = 'block';
      if (blockedEl) blockedEl.style.display = 'none';
      if (statsBar)  statsBar.style.display  = 'flex';
      if (searchBar) searchBar.style.display = 'block';
      if (tabActive)  { tabActive.style.background  = 'rgba(0,229,255,0.1)'; tabActive.style.color  = '#00e5ff'; }
      if (tabBlocked) { tabBlocked.style.background = 'none';                tabBlocked.style.color = 'rgba(0,229,255,0.4)'; }
    } else {
      if (listEl)    listEl.style.display    = 'none';
      if (blockedEl) blockedEl.style.display = 'block';
      if (statsBar)  statsBar.style.display  = 'none';
      if (searchBar) searchBar.style.display = 'none';
      if (tabActive)  { tabActive.style.background  = 'none';                  tabActive.style.color  = 'rgba(0,229,255,0.4)'; }
      if (tabBlocked) { tabBlocked.style.background = 'rgba(168,85,247,0.12)'; tabBlocked.style.color = '#c084fc'; }
      // Demander la liste au backend
      const ws = (window as any)._jarvisWs;
      if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'get_blocked_ips' }));
      this._renderBlockedList();
    }
  }

  public handleBlockedIps(ips: string[]): void {
    this._blockedIps = ips;
    const countEl = document.getElementById('radar-blocked-count');
    if (countEl) countEl.textContent = ips.length > 0 ? `(${ips.length})` : '';
    if (this._activeTab === 'blocked') this._renderBlockedList();
  }

  private _renderBlockedList(): void {
    const el = document.getElementById('radar-blocked-list');
    if (!el) return;
    if (this._blockedIps.length === 0) {
      el.innerHTML = `<div style="padding:20px;text-align:center;color:rgba(0,229,255,0.3);font-size:10px;letter-spacing:1px;">AUCUNE IP BLOQUÉE</div>`;
      return;
    }
    el.innerHTML = this._blockedIps.map(ip => `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 12px;border-bottom:1px solid rgba(255,46,77,0.1);">
        <span style="color:#ff2e4d;font-size:11px;font-weight:bold;">⊘ ${ip}</span>
        <button onclick="(function(){var ws=window._jarvisWs;if(ws&&ws.readyState===1)ws.send(JSON.stringify({type:'unblock_ip',ip:'${ip}'}))})()"
          style="background:rgba(255,46,77,0.1);border:1px solid rgba(255,46,77,0.3);color:#ff6b7a;font-family:monospace;font-size:9px;padding:2px 8px;cursor:pointer;border-radius:2px;letter-spacing:1px;">
          DÉBLOQUER
        </button>
      </div>`).join('');
  }

  private _refreshActiveList(): void {
    const filteredCount = this._allConnections.filter(c => c.is_filtered).length;
    const visible = this._showFiltered
      ? this._allConnections
      : this._allConnections.filter(c => !c.is_filtered);
    this.updatePanel(visible, filteredCount);
  }

  // ── Rotation souris ─────────────────────────────────────────────────────────

  private _setupMouseRotation(): void {
    const canvas = document.getElementById('holo-three-canvas');
    if (!canvas) return;

    this._onMouseDown = (e: MouseEvent) => {
      if (e.button === 2) {
        this._mouseRightDown = true;
        this._mouseLastX = e.clientX;
        this._mouseLastY = e.clientY;
      }
    };
    this._onMouseMove = (e: MouseEvent) => {
      if (!this._mouseRightDown) return;
      const dx = e.clientX - this._mouseLastX;
      const dy = e.clientY - this._mouseLastY;
      this._mouseLastX = e.clientX;
      this._mouseLastY = e.clientY;
      this.globeRotY  += dx * 0.006;
      this._globeRotX += dy * 0.006;
      this._globeRotX  = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, this._globeRotX));
      [this.globeGroup, this.arcsGroup, this.dotsGroup].forEach(g => {
        if (g) { g.rotation.y = this.globeRotY; g.rotation.x = this._globeRotX; }
      });
    };
    this._onMouseUp = () => { this._mouseRightDown = false; };
    this._onContextMenu = (e: MouseEvent) => { e.preventDefault(); e.stopPropagation(); };

    this._onCanvasClick = (e: MouseEvent) => {
      if (e.button !== 0 || this._mouseRightDown) return;
      this._handleGlobeClick(e.clientX, e.clientY);
    };

    // Intégration geste main pour rotation globe réseau
    this._onHandMove = (e: any) => {
      if (!this.active) return;
      const { x, y, pinched } = e.detail;
      if (pinched) {
        if (!this._isHandDragging) {
          this._isHandDragging = true;
          this._lastHandX = x;
          this._lastHandY = y;
        } else {
          const dx = x - this._lastHandX;
          const dy = y - this._lastHandY;
          this.globeRotY += dx * 0.006;
          this._globeRotX += dy * 0.006;
          this._globeRotX = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, this._globeRotX));
          this._lastHandX = x;
          this._lastHandY = y;
        }
      } else {
        this._isHandDragging = false;
      }
    };

    canvas.addEventListener('mousedown',    this._onMouseDown);
    canvas.addEventListener('click',        this._onCanvasClick);
    window.addEventListener('mousemove',    this._onMouseMove);
    window.addEventListener('mouseup',      this._onMouseUp);
    canvas.addEventListener('contextmenu',  this._onContextMenu);
    document.addEventListener('jarvis-hand-move', this._onHandMove);
  }

  private _teardownMouseRotation(): void {
    const canvas = document.getElementById('holo-three-canvas');
    if (this._onMouseDown)   canvas?.removeEventListener('mousedown',   this._onMouseDown);
    if (this._onCanvasClick) canvas?.removeEventListener('click',        this._onCanvasClick);
    if (this._onMouseMove)   window.removeEventListener('mousemove',     this._onMouseMove);
    if (this._onMouseUp)     window.removeEventListener('mouseup',       this._onMouseUp);
    if (this._onContextMenu) canvas?.removeEventListener('contextmenu',  this._onContextMenu);
    if (this._onHandMove)    document.removeEventListener('jarvis-hand-move', this._onHandMove);
    this._onMouseDown = this._onCanvasClick = this._onMouseMove = this._onMouseUp = this._onContextMenu = this._onHandMove = null;
  }

  private _handleGlobeClick(cx: number, cy: number): void {
    const canvas = document.getElementById('holo-three-canvas') as HTMLCanvasElement | null;
    const rect = canvas?.getBoundingClientRect();
    if (!rect) return;
    const cam = this.camera as THREE.PerspectiveCamera;
    let nearestIp: string | null = null;
    let nearestDist = 48; // seuil en pixels

    const worldPos = new THREE.Vector3();
    for (const [ip, dot] of this.destDots) {
      dot.getWorldPosition(worldPos);
      const proj = worldPos.clone().project(cam);
      if (proj.z > 1) continue; // derrière la caméra
      const sx = ((proj.x + 1) / 2) * rect.width  + rect.left;
      const sy = ((-proj.y + 1) / 2) * rect.height + rect.top;
      const d  = Math.hypot(cx - sx, cy - sy);
      if (d < nearestDist) { nearestDist = d; nearestIp = ip; }
    }

    if (nearestIp) {
      const conn = this._allConnections.find(c => c.ip === nearestIp);
      if (conn) {
        if (this._highlightedIp === conn.ip) {
          // Re-clic sur le même point → déselection
          this._highlightedIp = null;
          this._targetRotY    = null;
        } else {
          const p = _ll2v(conn.lat, conn.lon, this.R);
          this._targetRotY    = Math.atan2(-p.x, p.z);
          this._highlightedIp = conn.ip;
        }
        const filteredCount = this._allConnections.filter(c => c.is_filtered).length;
        const visible = this._showFiltered
          ? this._allConnections
          : this._allConnections.filter(c => !c.is_filtered);
        this.updatePanel(visible, filteredCount);
      }
    }
  }

  // ── Globe ───────────────────────────────────────────────────────────────────

  private buildGlobe(): void {
    if (!this.globeGroup) return;
    const R = this.R;

    // Sphère de base
    this.globeGroup.add(new THREE.Mesh(
      new THREE.SphereGeometry(R, 64, 64),
      new THREE.MeshBasicMaterial({ color: 0x000d1a, transparent: true, opacity: 0.92 })
    ));

    // Frontières pays (si déjà chargées) — sinon on les ajoute en différé
    this.addCountryBorders();

    // Graticule léger (lignes de lat/lon) par-dessus les frontières
    const graticule = new THREE.LineBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.04 });
    for (let lat = -80; lat <= 80; lat += 20) {
      const pts: THREE.Vector3[] = [];
      for (let lon = 0; lon <= 362; lon += 2) pts.push(this.ll2v(lat, lon, R + 0.015));
      this.globeGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), graticule));
    }
    for (let lon = 0; lon < 360; lon += 20) {
      const pts: THREE.Vector3[] = [];
      for (let lat = -90; lat <= 90; lat += 2) pts.push(this.ll2v(lat, lon, R + 0.015));
      this.globeGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), graticule));
    }

    // Halo atmosphérique
    this.globeGroup.add(new THREE.Mesh(
      new THREE.SphereGeometry(R + 0.18, 32, 32),
      new THREE.MeshBasicMaterial({
        color: 0x0055ff, transparent: true, opacity: 0.055,
        side: THREE.BackSide, blending: THREE.AdditiveBlending
      })
    ));

    // Point local France
    this.addLocalDot();
  }

  private addCountryBorders(): void {
    if (!this.globeGroup) return;

    const doAdd = (borders: THREE.Vector3[][]) => {
      if (!this.globeGroup) return;
      const mat = new THREE.LineBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.22 });
      for (const pts of borders) {
        this.globeGroup.add(new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(pts),
          mat
        ));
      }
    };

    if (_bordersReady && _countryBorderPoints) {
      doAdd(_countryBorderPoints);
    } else {
      // Différé : attendre que le chargement TopoJSON se termine
      const check = setInterval(() => {
        if (_bordersReady) {
          clearInterval(check);
          if (_countryBorderPoints && this.active) doAdd(_countryBorderPoints);
        }
      }, 200);
    }
  }

  private addLocalDot(): void {
    if (!this.dotsGroup) return;
    const pos = this.ll2v(this.LOCAL_LAT, this.LOCAL_LON, this.R + 0.04);

    const dot = new THREE.Mesh(
      new THREE.SphereGeometry(0.07, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0x00ff88, blending: THREE.AdditiveBlending })
    );
    dot.position.copy(pos);
    dot.userData.isLocal = true;
    this.dotsGroup.add(dot);

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.10, 0.16, 32),
      new THREE.MeshBasicMaterial({
        color: 0x00ff88, transparent: true, opacity: 0.65,
        side: THREE.DoubleSide, blending: THREE.AdditiveBlending
      })
    );
    ring.position.copy(pos);
    ring.lookAt(new THREE.Vector3(0, 0, 0));
    ring.userData.isLocal = true;
    this.dotsGroup.add(ring);
  }

  // ── Connexions ──────────────────────────────────────────────────────────────

  public toggleFilter(): void {
    this._showFiltered = !this._showFiltered;
    this._applyConnections(this._allConnections);
  }

  public handleRadarUpdate(connections: RadarConnection[]): void {
    if (!this.active) return;
    this._allConnections = connections;
    this._applyConnections(connections);
  }

  private _applyConnections(connections: RadarConnection[]): void {
    const visible = this._showFiltered
      ? connections
      : connections.filter(c => !c.is_filtered);

    const newIps = new Set(visible.map(c => c.ip));

    for (const [ip, arc] of this.arcs) {
      if (!newIps.has(ip)) {
        this.arcsGroup?.remove(arc.lineMesh, arc.headMesh);
        arc.lineMesh.geometry.dispose();
        (arc.lineMesh.material as THREE.Material).dispose();
        arc.headMesh.geometry.dispose();
        (arc.headMesh.material as THREE.Material).dispose();
        this.arcs.delete(ip);

        const d = this.destDots.get(ip);
        if (d) {
          this.dotsGroup?.remove(d);
          d.geometry.dispose();
          (d.material as THREE.Material).dispose();
          this.destDots.delete(ip);
        }
      }
    }

    for (const conn of visible) {
      if (!this.arcs.has(conn.ip)) this.addArc(conn);
    }

    const filteredCount = connections.filter(c => c.is_filtered).length;
    this.updatePanel(visible, filteredCount);
  }

  private addArc(conn: RadarConnection): void {
    const R = this.R;
    const color = RISK_COLOR[conn.risk] ?? RISK_COLOR.normal;

    const from = this.ll2v(this.LOCAL_LAT, this.LOCAL_LON, R + 0.04);
    const to   = this.ll2v(conn.lat, conn.lon, R + 0.04);
    const mid  = from.clone().add(to).multiplyScalar(0.5).normalize().multiplyScalar(R * 1.85);

    const curve = new THREE.QuadraticBezierCurve3(from, mid, to);

    const lineMesh = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(curve.getPoints(80)),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.22 })
    );
    this.arcsGroup?.add(lineMesh);

    const headMesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.048, 8, 8),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 1.0, blending: THREE.AdditiveBlending })
    );
    headMesh.position.copy(from);
    this.arcsGroup?.add(headMesh);

    const destDot = new THREE.Mesh(
      new THREE.SphereGeometry(0.05, 8, 8),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending })
    );
    destDot.position.copy(to);
    this.dotsGroup?.add(destDot);
    this.destDots.set(conn.ip, destDot);

    this.arcs.set(conn.ip, {
      curve, lineMesh, headMesh,
      headProgress: Math.random(),
      headSpeed: 0.28 + Math.random() * 0.18,
      baseColor: color,
    });
  }

  // ── Panel HUD ───────────────────────────────────────────────────────────────

  private _applyRowHighlight(row: HTMLElement): void {
    row.style.background    = 'rgba(140, 60, 255, 0.25)';
    row.style.borderLeft    = '3px solid #a855f7';
    row.style.paddingLeft   = '11px';
    row.style.boxShadow     = 'inset 0 0 14px rgba(140,60,255,0.2)';
    const proc = row.querySelector<HTMLElement>('.radar-proc');
    if (proc) { proc.style.color = '#e0b8ff'; proc.style.textShadow = '0 0 8px rgba(168,85,247,0.9)'; }
    const loc = row.querySelector<HTMLElement>('.radar-loc');
    if (loc)  loc.style.color = '#c084fc';
    const ip = row.querySelector<HTMLElement>('.radar-ip');
    if (ip)   ip.style.color = 'rgba(230,210,255,0.95)';
  }

  private _clearRowHighlight(row: HTMLElement): void {
    row.style.background    = '';
    row.style.borderLeft    = '';
    row.style.paddingLeft   = '';
    row.style.boxShadow     = '';
    const proc = row.querySelector<HTMLElement>('.radar-proc');
    if (proc) { proc.style.color = ''; proc.style.textShadow = ''; }
    const loc = row.querySelector<HTMLElement>('.radar-loc');
    if (loc)  loc.style.color = '';
    const ip = row.querySelector<HTMLElement>('.radar-ip');
    if (ip)   ip.style.color = '';
  }

  private _fmtDuration(s: number): string {
    if (s < 60)   return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m${String(s % 60).padStart(2,'0')}s`;
    return `${Math.floor(s / 3600)}h${Math.floor((s % 3600) / 60)}m`;
  }

  private updatePanel(connections: RadarConnection[], filteredCount: number): void {
    const countries = new Set(connections.map(c => c.country));
    const threats   = connections.filter(c => c.risk !== 'normal');

    const el = (id: string) => document.getElementById(id);
    const count    = el('radar-count');
    const ctryEl   = el('radar-countries');
    const threatEl = el('radar-threats');
    const listEl   = el('radar-connections-list');
    const filterBtn = el('radar-filter-btn');

    if (count)    count.textContent = String(connections.length);
    if (ctryEl)   ctryEl.textContent = String(countries.size);
    if (threatEl) {
      const n = threats.length;
      threatEl.textContent = `${n} menace${n !== 1 ? 's' : ''}`;
      threatEl.style.color = n > 0 ? '#ff2e4d' : '#00ff88';
    }
    if (filterBtn) {
      if (filteredCount > 0) {
        filterBtn.style.display = 'inline-block';
        filterBtn.textContent = this._showFiltered
          ? `Masquer sys (${filteredCount})`
          : `+ ${filteredCount} sys`;
      } else {
        filterBtn.style.display = 'none';
      }
    }

    if (!listEl) return;
    listEl.innerHTML = '';

    const q = this._searchQuery;
    const filtered = q
      ? connections.filter(c =>
          c.ip.includes(q) ||
          c.process.toLowerCase().includes(q) ||
          c.country.toLowerCase().includes(q) ||
          (c.hostname ?? '').toLowerCase().includes(q) ||
          (c.city ?? '').toLowerCase().includes(q) ||
          c.cc.toLowerCase().includes(q)
        )
      : connections;

    const sorted = [...filtered].sort((a, b) => {
      const o: Record<string, number> = { high: 0, medium: 1, normal: 2 };
      return (o[a.risk] ?? 2) - (o[b.risk] ?? 2);
    });

    if (sorted.length === 0 && q) {
      listEl.innerHTML = `<div style="padding:20px;text-align:center;color:rgba(0,229,255,0.3);font-size:10px;letter-spacing:1px;">AUCUN RÉSULTAT POUR "${q.toUpperCase()}"</div>`;
      return;
    }

    for (const c of sorted) {
      const flag     = c.cc || '--';
      const colorHex = '#' + (RISK_COLOR[c.risk] ?? RISK_COLOR.normal).toString(16).padStart(6, '0');
      const dot      = `<span style="color:${colorHex};font-size:10px;flex-shrink:0">●</span>`;
      const dur      = this._fmtDuration(c.duration_s ?? 0);
      const proc     = c.process.replace(/\.exe$/i, '');
      const svc      = c.service ? ` <span class="radar-svc">${c.service}</span>` : '';
      const host     = c.hostname ? `<span class="radar-host">${c.hostname}</span>` : '';
      const loc      = c.city
        ? `${flag} ${c.city}, ${c.cc}`
        : `${flag} ${c.country}`;

      let badges = '';
      if (c.is_new)    badges += `<span class="radar-badge-new">NEW</span>`;
      if (c.port_scan) badges += `<span class="radar-badge-scan">SCAN</span>`;

      const isHL = c.ip === this._highlightedIp;
      const row  = document.createElement('div');
      row.className = 'radar-conn-row';
      row.title = `Clic : centrer sur ${c.country}`;
      if (isHL) this._applyRowHighlight(row);
      row.innerHTML =
        // Ligne 1 : indicateur + badges + processus + port + service + bloquer
        `<div class="rcr-top">` +
          `<div class="rcr-left">` +
            `${dot}${badges}` +
            `<span class="radar-proc">${proc}</span>` +
          `</div>` +
          `<div class="rcr-right">` +
            `<span class="radar-port">:${c.port}${svc}</span>` +
            `<button class="radar-block-btn" title="Bloquer ${c.ip} via pare-feu" ` +
              `onclick="event.stopPropagation();(function(){var ws=window._jarvisWs;` +
              `if(ws&&ws.readyState===1)ws.send(JSON.stringify({type:'block_ip',ip:'${c.ip}'}))})()">⊘</button>` +
          `</div>` +
        `</div>` +
        // Ligne 2 : IP + hostname + localisation + durée
        `<div class="rcr-bot">` +
          `<div class="rcr-left">` +
            `<span class="radar-ip">${c.ip}${host ? ' / ' : ''}${host}</span>` +
          `</div>` +
          `<div class="rcr-right">` +
            `<span class="radar-loc">${loc}</span>` +
            `<span class="radar-dur">${dur}</span>` +
          `</div>` +
        `</div>`;

      // Clic sur la ligne → zoom globe + surbrillance (re-clic = déselection)
      row.addEventListener('click', () => {
        if (this._highlightedIp === c.ip) {
          // Déselection
          this._highlightedIp = null;
          this._targetRotY    = null;
          listEl?.querySelectorAll<HTMLElement>('.radar-conn-row').forEach(r => this._clearRowHighlight(r));
        } else {
          const p = _ll2v(c.lat, c.lon, this.R);
          this._targetRotY    = Math.atan2(-p.x, p.z);
          this._highlightedIp = c.ip;
          listEl?.querySelectorAll<HTMLElement>('.radar-conn-row').forEach(r => this._clearRowHighlight(r));
          this._applyRowHighlight(row);
        }
      });

      listEl.appendChild(row);
    }
  }

  // ── Update loop ─────────────────────────────────────────────────────────────

  public update(dt: number): void {
    if (!this.active) return;
    this.time += dt;

    if (this._targetRotY !== null) {
      // Interpolation angle court (chemin le plus court sur le cercle)
      let diff = this._targetRotY - this.globeRotY;
      while (diff >  Math.PI) diff -= Math.PI * 2;
      while (diff < -Math.PI) diff += Math.PI * 2;
      this.globeRotY += diff * Math.min(dt * 3.5, 1);
      if (Math.abs(diff) < 0.008) { this.globeRotY = this._targetRotY; this._targetRotY = null; }
    } else if (!this._mouseRightDown) {
      this.globeRotY += dt * 0.04;
    }
    [this.globeGroup, this.arcsGroup, this.dotsGroup].forEach(g => {
      if (g) { g.rotation.y = this.globeRotY; g.rotation.x = this._globeRotX; }
    });

    const HL        = NetworkRadar.HL_COLOR;
    const hasHL     = this._highlightedIp !== null;
    const pulse     = 0.5 + Math.sin(this.time * 3.5) * 0.35;

    for (const [ip, arc] of this.arcs) {
      arc.headProgress += dt * arc.headSpeed;
      if (arc.headProgress > 1.0) arc.headProgress -= 1.0;
      arc.headMesh.position.copy(arc.curve.getPoint(arc.headProgress));

      const isHL    = ip === this._highlightedIp;
      const c       = isHL ? HL : arc.baseColor;
      const lineMat = arc.lineMesh.material as THREE.LineBasicMaterial;
      lineMat.color.setHex(c);
      // Quand une sélection est active : les autres arcs s'effacent presque entièrement
      lineMat.opacity = isHL ? 0.82 : (hasHL ? 0.05 : 0.22);
      const headMat = arc.headMesh.material as THREE.MeshBasicMaterial;
      headMat.color.setHex(c);
      headMat.opacity = isHL ? 1.0 : (hasHL ? 0.08 : 1.0);
    }

    for (const [ip, dot] of this.destDots) {
      const mat  = dot.material as THREE.MeshBasicMaterial;
      const isHL = ip === this._highlightedIp;
      mat.color.setHex(isHL ? HL : (this.arcs.get(ip)?.baseColor ?? RISK_COLOR.normal));
      mat.opacity = isHL ? Math.max(pulse, 0.85) : (hasHL ? 0.08 : pulse);
    }

    if (this.dotsGroup) {
      const localPulse = 0.75 + Math.sin(this.time * 2.5) * 0.25;
      this.dotsGroup.traverse(child => {
        if (child instanceof THREE.Mesh && child.userData.isLocal) {
          (child.material as THREE.MeshBasicMaterial).opacity = localPulse;
        }
      });
    }
  }

  // ── Utilitaires ─────────────────────────────────────────────────────────────

  private ll2v(lat: number, lon: number, r: number = this.R): THREE.Vector3 {
    return _ll2v(lat, lon, r);
  }

  private clearAll(): void {
    for (const arc of this.arcs.values()) {
      arc.lineMesh.geometry.dispose();
      (arc.lineMesh.material as THREE.Material).dispose();
      arc.headMesh.geometry.dispose();
      (arc.headMesh.material as THREE.Material).dispose();
    }
    this.arcs.clear();

    for (const dot of this.destDots.values()) {
      dot.geometry.dispose();
      (dot.material as THREE.Material).dispose();
    }
    this.destDots.clear();

    [this.globeGroup, this.arcsGroup, this.dotsGroup].forEach(g => {
      g?.traverse(child => {
        if (child instanceof THREE.Mesh || child instanceof THREE.Line) {
          child.geometry?.dispose();
          if (Array.isArray(child.material)) child.material.forEach(m => m.dispose());
          else child.material?.dispose();
        }
      });
      if (g) this.group.remove(g);
    });
    this.globeGroup = null;
    this.arcsGroup  = null;
    this.dotsGroup  = null;
  }
}
