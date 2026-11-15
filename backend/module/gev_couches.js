// Couches ajoutées par JARVIS à God's Eye View (écrit par JARVIS : module/gev_couches.js, copié par vue_de_dieu.py dans le dossier de l'appli sous le nom jarvis-couches.js ; l'appli n'est jamais modifiée).
// Elles passent par le point d'entrée que l'appli ouvre en mode développement (window.__gevQaRegisterLayer, serveur « vite dev » de JARVIS) : mêmes lignes dans la liste des couches, même interrupteur,
// même cycle de vie que les couches natives. Elles ne sont PAS dans les liens de partage (le registre d'état de l'appli est figé). Si l'appli retire ce point d'entrée, verifier_surcharges() le dit au lancement.
(() => {
  'use strict';
  const CARBURANTS = [['gazole', 'Diesel'], ['e10', 'E10'], ['sp95', 'SP95'], ['sp98', 'SP98'], ['e85', 'E85'], ['gplc', 'LPG']];
  const INDICE = { gazole: 0, sp95: 1, e10: 2, sp98: 3, e85: 4, gplc: 5 };
  const pause = (ms, signal) => new Promise((ok) => { const t = setTimeout(ok, ms); signal?.addEventListener('abort', () => { clearTimeout(t); ok(); }, { once: true }); });
  const delai = (signal, ms) => { try { return signal ? AbortSignal.any([signal, AbortSignal.timeout(ms)]) : AbortSignal.timeout(ms); } catch { return signal; } };   // expire seule : une requête en suspens ne fige pas la couche

  // ---- traduction française des textes de ces couches (l'appli ne connaît pas ces phrases) ---------------------------------------------------------------------------------
  // Active seulement si la page est en français (<html lang="fr">, choisi par le sélecteur de langue ou par défaut depuis JARVIS) ; sinon les textes restent en anglais.
  const estFr = () => /^fr/i.test(document.documentElement.lang || '');
  const FR = {
    'Diesel': 'Gazole', 'LPG': 'GPL', 'Close': 'Fermer', 'yes': 'oui', 'no': 'non',
    'Fuel prices · France': 'Prix des carburants · France', 'Fuel prices unavailable · retrying': 'Prix des carburants indisponibles · nouvel essai',
    'EV chargers · France': 'Bornes de recharge · France', 'Charging station': 'Borne de recharge', 'Operator': 'Exploitant', 'Charge points': 'Points de charge', 'Max power': 'Puissance max.', 'Connectors': 'Prises', 'Free': 'Gratuit', 'Hours': 'Horaires',
    'Source: IRVE consolidated file (data.gouv.fr)': 'Source : fichier consolidé IRVE (data.gouv.fr)', 'All stations': 'Toutes les stations', 'Fast ≥ 50 kW': 'Rapides ≥ 50 kW', 'Ultra ≥ 150 kW': 'Ultra-rapides ≥ 150 kW',
    'Flood vigilance · France': 'Vigilance crues · France', 'Green · no particular vigilance': 'Vert · pas de vigilance particulière', 'Yellow · be attentive': 'Jaune · soyez attentif', 'Orange · be very vigilant': 'Orange · soyez très vigilant', 'Red · absolute vigilance': 'Rouge · vigilance absolue',
    'Green': 'Vert', 'Yellow': 'Jaune', 'Orange': 'Orange', 'Red': 'Rouge', 'Vigilance': 'Vigilance', 'Vigicrues · Ministère de la Transition écologique': 'Vigicrues · ministère de la Transition écologique',
    'Source: Vigicrues (vigicrues.gouv.fr), reaches updated about every 30 minutes': 'Source : Vigicrues (vigicrues.gouv.fr), tronçons mis à jour environ toutes les 30 minutes', 'All reaches': 'Tous les tronçons', 'Alerts only': 'Alertes seulement',
    'Earthquakes · France region': 'Séismes · région France', 'Unknown region': 'Région inconnue', 'Time (UTC)': 'Heure (UTC)', 'Depth': 'Profondeur', 'Position': 'Position', 'Source: EMSC (seismicportal.eu)': 'Source : EMSC (seismicportal.eu)',
    '7 days': '7 jours', '30 days': '30 jours', 'Shallow (< 10 km)': 'Superficiel (< 10 km)', 'Intermediate (10–30 km)': 'Intermédiaire (10–30 km)', 'Deep (> 30 km)': 'Profond (> 30 km)',
    'Air quality · France': "Qualité de l'air · France", 'Good': 'Bon', 'Fair': 'Correct', 'Moderate': 'Moyen', 'Poor': 'Mauvais', 'Very poor': 'Très mauvais', 'Extremely poor': 'Extrêmement mauvais', 'Ozone': 'Ozone',
    'Model: CAMS Europe via Open-Meteo (about 11 km grid), not a ground station': "Modèle : CAMS Europe via Open-Meteo (grille d'environ 11 km), pas une station au sol",
    'Drone restrictions · France': 'Restrictions de drones · France', 'Flight prohibited': 'Vol interdit', 'Max height 30 m': 'Hauteur max. 30 m', 'Max height 50 m': 'Hauteur max. 50 m', 'Max height 60 m': 'Hauteur max. 60 m', 'Max height 100 m': 'Hauteur max. 100 m',
    'Prior notification only (drones over 900 g)': 'Notification préalable seulement (drones de plus de 900 g)', 'Notify > 900 g': 'Notifier > 900 g', 'Rule': 'Règle', 'Note': 'Remarque',
    'Source: IGN (data.geopf.fr), indicative: check the official map before flying': 'Source : IGN (data.geopf.fr), à titre indicatif : consultez la carte officielle avant de voler',
    'Zones only': 'Zones seulement', '+ Notification area': '+ Zone de notification', 'Zoom in (view under about 1°) to load the zones.': 'Zoomez (vue de moins de 1° environ) pour charger les zones.',
    'Zoom in (view under about 1°) to load the drone restriction zones.': 'Zoomez (vue de moins de 1° environ) pour charger les zones de restriction de drones.', 'Drone zones unavailable · retrying': 'Zones de drones indisponibles · nouvel essai',
    'The zones of this view could not be loaded (the previous ones may be outdated) · retrying.': "Les zones de cette vue n'ont pas pu être chargées (les précédentes peuvent être obsolètes) · nouvel essai.",
    'Weather alerts · France': 'Alertes météo · France', 'Wind': 'Vent', 'Rain / flood': 'Pluie / inondation', 'Thunderstorms': 'Orages', 'River floods': 'Crues', 'Snow / ice': 'Neige / verglas', 'Heatwave': 'Canicule', 'Extreme cold': 'Grand froid',
    'Avalanches': 'Avalanches', 'Waves / submersion': 'Vagues / submersion', 'All': 'Tous', 'Rain': 'Pluie', 'Storms': 'Orages', 'Floods': 'Crues', 'Snow/ice': 'Neige/verglas', 'Heat': 'Chaleur', 'Cold': 'Froid', 'Avalanche': 'Avalanche', 'Waves': 'Vagues',
    'Today': "Aujourd'hui", 'Tomorrow': 'Demain', 'All phenomena (highest level)': 'Tous les phénomènes (niveau le plus élevé)',
    'Needs METEOFRANCE_API_KEY subscribed to the Vigilance API (Power up panel) · retrying': "Nécessite METEOFRANCE_API_KEY abonnée à l'API Vigilance (panneau Power up) · nouvel essai",
  };
  const MODELES = [
    [/^(Motorway · )?Updated (.*) UTC · Source: data\.economie\.gouv\.fr$/, (m) => (m[1] ? 'Autoroute · ' : '') + 'Mis à jour ' + m[2] + ' UTC · Source : data.economie.gouv.fr'],
    [/^Show (.*) prices$/, (m) => 'Afficher les prix ' + (m[1] === 'Diesel' ? 'du gazole' : m[1] === 'LPG' ? 'du GPL' : 'du ' + m[1])],
    [/^Fuel prices at (\d+) French stations, per litre\. Green = cheapest 5%, red = dearest 5% for the chosen fuel\. Zoom in for the price labels; click a station for all its prices\.$/,
      (m) => 'Prix des carburants dans ' + m[1] + ' stations françaises, au litre. Vert = 5 % les moins chers, rouge = 5 % les plus chers pour le carburant choisi. Zoomez pour voir les prix ; cliquez sur une station pour tous ses prix.'],
    [/^(\d+) charging stations shown\. Colour = highest power of the station; size = number of charge points\. Click a station for details\.$/,
      (m) => m[1] + ' bornes de recharge affichées. Couleur = puissance maximale de la station ; taille = nombre de points de charge. Cliquez sur une station pour le détail.'],
    [/^(?:(\d+) reach\(es\) at yellow or above\. |No reach above green\. )Flood vigilance of the monitored rivers \(Vigicrues\); only the rivers covered by the State flood forecasting service are shown\.$/,
      (m) => (m[1] ? m[1] + ' tronçon(s) au jaune ou au-dessus. ' : 'Aucun tronçon au-dessus du vert. ') + "Vigilance crues des cours d'eau surveillés (Vigicrues) ; seuls les cours d'eau couverts par le service de prévision des crues de l'État sont affichés."],
    [/^(\d+) earthquakes of magnitude 1\.5 or more around France \(41–51\.5°N, 5\.5°W–10°E\)\. Size = magnitude, colour = depth\. Click one for details\.$/,
      (m) => m[1] + ' séismes de magnitude 1,5 ou plus autour de la France (41–51,5° N, 5,5° O–10° E). Taille = magnitude, couleur = profondeur. Cliquez sur l\'un d\'eux pour le détail.'],
    [/^(\d+) French cities\. European Air Quality Index from the Copernicus CAMS model \(about 11 km grid\): a model estimate, not a measurement at a station\.$/,
      (m) => m[1] + " villes françaises. Indice européen de qualité de l'air issu du modèle Copernicus CAMS (grille d'environ 11 km) : une estimation de modèle, pas une mesure en station."],
    [/^(\d+) zones loaded\. Red = flight prohibited; orange to yellow-green = maximum height \(30, 50, 60, 100 m\)\. The faint blue area \(button "\+ Notification area"\) only requires a prior notification for drones over 900 g, with no specific height limit\. Outside all zones the usual limit is 120 m\. Click a zone for details\.$/,
      (m) => m[1] + ' zones chargées. Rouge = vol interdit ; orange à jaune-vert = hauteur maximale (30, 50, 60, 100 m). La zone bleutée (bouton « + Zone de notification ») impose seulement une notification préalable pour les drones de plus de 900 g, sans limite de hauteur particulière. Hors de toute zone, la limite habituelle est de 120 m. Cliquez sur une zone pour le détail.'],
    [/^(?:(\d+) département\(s\) at yellow or above|No département above green) for (today|tomorrow)(?: \((.*)\))?\. Météo-France vigilance map(?:, updated (.*) UTC)?\. Click a département for its alerts\.$/,
      (m) => (m[1] ? m[1] + ' département(s) au jaune ou au-dessus' : 'Aucun département au-dessus du vert') + ' pour ' + (m[2] === 'today' ? "aujourd'hui" : 'demain') + (m[3] ? ' (' + tr(m[3]) + ')' : '') + '. Carte de vigilance Météo-France' + (m[4] ? ', mise à jour ' + m[4] + ' UTC' : '') + '. Cliquez sur un département pour ses alertes.'],
    [/^(Today|Tomorrow) · valid (.*) to (.*) UTC · Source: Météo-France$/, (m) => tr(m[1]) + ' · valide du ' + m[2] + ' au ' + m[3] + ' UTC · Source : Météo-France'],
    [/^Coast · (.*)$/, (m) => 'Côte · ' + tr(m[1])],
    [/^(.*) · (Good|Fair|Moderate|Poor|Very poor|Extremely poor)$/, (m) => m[1] + ' · ' + tr(m[2])],
    [/^(.*) unavailable · retrying$/, (m) => tr(m[1]) + ' indisponible · nouvel essai'],
    [/^Prior notification only/, (m) => FR['Prior notification only (drones over 900 g)']],
  ];
  function tr(s) {
    if (typeof s !== 'string' || !s || !estFr()) return s;
    if (Object.hasOwn(FR, s)) return FR[s];
    for (const [re, f] of MODELES) { const m = re.exec(s); if (m) return f(m); }
    return s;
  }
  window.__jarvisTraduire = tr;   // pour les tests
  function habiller(m) {   // traduit à la volée le nom, la source, les boutons, la légende, le texte d'information et les messages d'erreur d'une couche
    const rc = m.getRowControls.bind(m), gs = m.getStats.bind(m);
    m.name = tr(m.name); m.source = tr(m.source);
    m.getRowControls = () => { const c = rc(); return { ...c, chips: (c.chips || []).map((x) => ({ ...x, label: tr(x.label), title: tr(x.title) })), legend: (c.legend || []).map((x) => ({ ...x, label: tr(x.label), blurb: tr(x.blurb) })), info: tr(c.info) }; };
    m.getStats = () => { const s = gs(); return s && s.error ? { ...s, error: tr(s.error) } : s; };
    return m;
  }
  const hex = (c) => '#' + [c.red, c.green, c.blue].map((v) => Math.round(v * 255).toString(16).padStart(2, '0')).join('');

  function carburantsFrance(Cesium, viewer) {
    let points = null, etiquettes = null, gestionnaire = null, carte = null, minuteurEt = null;
    let donnees = [], carburant = 'e10', actif = false, derniere = null, erreur = null, ecouteur = null, bornes = null, charge = 0;
    const redessiner = () => { try { window.__godsEyeView?.requestRender?.(); } catch { /* sans effet */ } };
    const prevenir = () => { try { ecouteur?.(); } catch { /* sans effet */ } };

    // vert (bon marché) -> jaune -> rouge (cher), entre le 5e et le 95e centile du carburant choisi
    function couleur(t) {
      const a = Cesium.Color.fromCssColorString('#1fdc6e'), b = Cesium.Color.fromCssColorString('#ffd23a'), c = Cesium.Color.fromCssColorString('#ff3b3b');
      return t < 0.5 ? Cesium.Color.lerp(a, b, t * 2, new Cesium.Color()) : Cesium.Color.lerp(b, c, (t - 0.5) * 2, new Cesium.Color());
    }
    function vider() { points?.removeAll(); etiquettes?.removeAll(); }
    function construire() {
      vider();
      const i = INDICE[carburant];
      const valeurs = donnees.map((s) => s[4][i]).filter((v) => v != null).sort((x, y) => x - y);
      if (!valeurs.length) { bornes = null; return; }
      const bas = valeurs[Math.floor(valeurs.length * 0.05)], haut = valeurs[Math.min(valeurs.length - 1, Math.floor(valeurs.length * 0.95))];
      bornes = { bas, haut, mediane: valeurs[Math.floor(valeurs.length / 2)], n: valeurs.length };
      const INF = Number.POSITIVE_INFINITY;
      donnees.forEach((s, k) => {
        const p = s[4][i];
        if (p == null) return;
        const t = haut > bas ? Math.min(1, Math.max(0, (p - bas) / (haut - bas))) : 0.5;
        const position = Cesium.Cartesian3.fromDegrees(s[2], s[1], 20);
        points.add({ position, pixelSize: 8, color: couleur(t), outlineColor: Cesium.Color.BLACK.withAlpha(0.65), outlineWidth: 1.5, disableDepthTestDistance: INF,
          scaleByDistance: new Cesium.NearFarScalar(2e4, 1.5, 4e6, 0.55), id: { jarvisStation: k } });
      });
      mettreEtiquettes(); redessiner();
    }
    // prix écrits seulement quand la caméra est à moins de 120 km, pour les stations de la fenêtre visible (800 au plus), mis à jour à chaque déplacement
    function mettreEtiquettes() {
      etiquettes?.removeAll();
      if (!actif || !etiquettes || !donnees.length) return;
      const cam = viewer.camera, r = cam.computeViewRectangle?.(viewer.scene.globe.ellipsoid);
      if (!r || (cam.positionCartographic?.height ?? Infinity) > 120000) { redessiner(); return; }
      const d = Cesium.Math.toDegrees, w = d(r.west), s = d(r.south), e = d(r.east), n = d(r.north), i = INDICE[carburant];
      let nb = 0;
      for (let k = 0; k < donnees.length && nb < 800; k++) {
        const st = donnees[k], p = st[4][i];
        if (p == null || st[2] < w || st[2] > e || st[1] < s || st[1] > n) continue;
        etiquettes.add({ position: Cesium.Cartesian3.fromDegrees(st[2], st[1], 20), text: p.toFixed(3), font: '600 13px Consolas, monospace', fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(0, -17), disableDepthTestDistance: Number.POSITIVE_INFINITY, scale: 0.9, id: { jarvisStation: k } });
        nb++;
      }
      redessiner();
    }
    const planifierEtiquettes = () => { clearTimeout(minuteurEt); minuteurEt = setTimeout(mettreEtiquettes, 400); };

    function fermerCarte() { carte?.remove(); carte = null; }
    function ouvrirCarte(s) {
      fermerCarte();
      const d = document.createElement('div');
      d.setAttribute('data-jarvis-carte', 'carburants');
      d.style.cssText = 'position:fixed;left:50%;bottom:96px;transform:translateX(-50%);z-index:9999;min-width:260px;max-width:340px;padding:12px 14px;border:1px solid rgba(80,220,255,.45);border-radius:10px;background:rgba(8,18,28,.88);backdrop-filter:blur(10px);color:#d8f6ff;font:12px Consolas,monospace;box-shadow:0 8px 28px rgba(0,0,0,.5)';
      const titre = document.createElement('div'); titre.textContent = s[3]; titre.style.cssText = 'font-weight:700;letter-spacing:.04em;margin-bottom:8px;color:#8fefff';
      d.append(titre);
      CARBURANTS.forEach(([k, nom]) => {
        const v = s[4][INDICE[k]];
        const l = document.createElement('div'); l.style.cssText = 'display:flex;justify-content:space-between;padding:2px 0;' + (k === carburant ? 'color:#fff;font-weight:700' : 'opacity:' + (v == null ? '.35' : '.85'));
        const a = document.createElement('span'); a.textContent = tr(nom); const b = document.createElement('span'); b.textContent = v == null ? '—' : v.toFixed(3) + ' €/L';
        l.append(a, b); d.append(l);
      });
      const pied = document.createElement('div'); pied.textContent = tr((s[6] === 'A' ? 'Motorway · ' : '') + 'Updated ' + (s[5] || '?') + ' UTC · Source: data.economie.gouv.fr'); pied.style.cssText = 'margin-top:8px;font-size:10px;opacity:.55';
      const x = document.createElement('button'); x.textContent = '×'; x.setAttribute('aria-label', tr('Close')); x.style.cssText = 'position:absolute;top:4px;right:8px;background:none;border:0;color:#8fefff;font-size:16px;cursor:pointer';
      x.addEventListener('click', fermerCarte);
      d.append(pied, x); document.body.append(d); carte = d;
    }

    const couche = {
      id: 'fuel-prices-fr', name: 'Fuel prices · France', icon: '⛽', source: 'data.economie.gouv.fr · Licence Ouverte 2.0', updateInterval: 10 * 60000,
      init() {
        points = viewer.scene.primitives.add(new Cesium.PointPrimitiveCollection()); points.show = false;
        etiquettes = viewer.scene.primitives.add(new Cesium.LabelCollection()); etiquettes.show = false;
      },
      enable() {
        actif = true; if (points) points.show = true; if (etiquettes) etiquettes.show = true;
        viewer.camera.moveEnd.addEventListener(planifierEtiquettes); if (donnees.length) mettreEtiquettes();
        gestionnaire = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        gestionnaire.setInputAction((e) => {
          const p = viewer.scene.pick(e.position);
          const k = p?.id?.jarvisStation;
          if (k !== undefined && donnees[k]) ouvrirCarte(donnees[k]); else fermerCarte();
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
        redessiner();
      },
      disable() {
        actif = false; charge++; if (points) points.show = false; if (etiquettes) etiquettes.show = false;
        clearTimeout(minuteurEt); viewer.camera.moveEnd.removeEventListener(planifierEtiquettes); etiquettes?.removeAll();
        gestionnaire?.destroy(); gestionnaire = null; fermerCarte(); redessiner();
      },
      async update(_v, { signal } = {}) {
        if (!actif) return false;
        const moi = ++charge;
        // le fichier est téléchargé par JARVIS en tâche de fond : tant qu'il n'est pas là le serveur répond 503, on patiente
        for (let essai = 0; essai < 8 && actif && moi === charge; essai++) {
          try {
            const r = await fetch('/__jarvis/carburants-fr.json', { signal: delai(signal, 20000), cache: 'no-store' });
            if (r.ok) {
              const j = await r.json();
              if (!Array.isArray(j)) throw new Error('Malformed fuel data');
              if (moi !== charge) return false;
              donnees = j; derniere = Date.now(); erreur = null; construire(); prevenir(); return true;
            }
            if (r.status !== 503) throw new Error('Fuel prices HTTP ' + r.status);
          } catch (e) { if (signal?.aborted) return false; if (!/HTTP|Malformed/.test(String(e?.message))) { /* réseau : on réessaie */ } else { erreur = e.message; prevenir(); return false; } }
          await pause(3000, signal);
        }
        if (moi === charge && actif) { erreur = 'Fuel prices unavailable · retrying'; prevenir(); setTimeout(() => { if (actif && !donnees.length) this.update(null, {}); }, 20000); }
        return false;
      },
      destroy() {
        this.disable(); if (points) viewer.scene.primitives.remove(points); if (etiquettes) viewer.scene.primitives.remove(etiquettes); points = etiquettes = null;
      },
      getStats() { return { count: bornes ? bornes.n : 0, lastUpdate: derniere, error: erreur }; },
      getParams() { return { fuel: carburant }; },
      setParams(params) {
        if (!params || !Object.hasOwn(INDICE, params.fuel)) return false;
        if (params.fuel !== carburant) { carburant = params.fuel; if (actif && donnees.length) construire(); prevenir(); }
        return true;
      },
      setRowControlsListener(cb) { ecouteur = cb; },
      getRowControls() {
        const prix = (v) => (v == null ? '' : v.toFixed(3));
        return {
          chips: CARBURANTS.map(([k, nom]) => ({ id: 'fuel-' + k, label: nom, active: k === carburant, params: { fuel: k }, title: 'Show ' + nom + ' prices' })),
          legend: bornes ? [[prix(bornes.bas) + ' €', couleur(0)], [prix(bornes.mediane) + ' €', couleur(0.5)], [prix(bornes.haut) + ' €', couleur(1)]].map(([label, c]) => ({ label, color: hex(c), blurb: label + '/L' })) : [],
          info: 'Fuel prices at ' + (bornes ? bornes.n : 0) + ' French stations, per litre. Green = cheapest 5%, red = dearest 5% for the chosen fuel. Zoom in for the price labels; click a station for all its prices.',
        };
      },
    };
    return couche;
  }

  // ---- outils communs aux couches suivantes -------------------------------------------------------------------------------------------------------------------------
  const col = (Cesium, h, a = 1) => Cesium.Color.fromCssColorString(h).withAlpha(a);
  function carte(titre, lignes, pied) {   // fiche au clic (même style que celle des carburants) ; une seule à la fois
    titre = tr(titre); lignes = lignes.map(([k, v]) => [tr(k), tr(v)]); pied = tr(pied);
    document.querySelector('[data-jarvis-carte]')?.remove();
    const d = document.createElement('div');
    d.setAttribute('data-jarvis-carte', 'couche');
    d.style.cssText = 'position:fixed;left:50%;bottom:96px;transform:translateX(-50%);z-index:9999;min-width:260px;max-width:360px;padding:12px 14px;border:1px solid rgba(80,220,255,.45);border-radius:10px;background:rgba(8,18,28,.88);backdrop-filter:blur(10px);color:#d8f6ff;font:12px Consolas,monospace;box-shadow:0 8px 28px rgba(0,0,0,.5)';
    const t = document.createElement('div'); t.textContent = titre; t.style.cssText = 'font-weight:700;letter-spacing:.04em;margin:0 14px 8px 0;color:#8fefff'; d.append(t);
    for (const [k, v] of lignes) { const l = document.createElement('div'); l.style.cssText = 'display:flex;justify-content:space-between;gap:12px;padding:2px 0'; const a = document.createElement('span'); a.textContent = k; a.style.opacity = '.7'; const b = document.createElement('span'); b.textContent = v; b.style.textAlign = 'right'; l.append(a, b); d.append(l); }
    const p = document.createElement('div'); p.textContent = pied; p.style.cssText = 'margin-top:8px;font-size:10px;opacity:.55'; d.append(p);
    const x = document.createElement('button'); x.textContent = '×'; x.setAttribute('aria-label', 'Close'); x.style.cssText = 'position:absolute;top:4px;right:8px;background:none;border:0;color:#8fefff;font-size:16px;cursor:pointer'; x.addEventListener('click', () => d.remove());
    d.append(x); document.body.append(d); return d;
  }
  async function jsonAvecAttente(url, signal, encore) {   // 503 = fichier pas encore téléchargé par JARVIS : on patiente
    for (let essai = 0; essai < 8 && encore(); essai++) {
      try {
        const r = await fetch(url, { signal: delai(signal, 20000), cache: 'no-store' });
        if (r.ok) return await r.json();
        if (r.status !== 503) throw new Error('HTTP ' + r.status);
      } catch (e) { if (signal?.aborted) return null; if (/HTTP/.test(String(e?.message))) throw e; }
      await pause(3000, signal);
    }
    return null;
  }

  // Couche « à points, lignes et fiche » décrite par un spec : { id, name, icon, source, updateInterval, url, params, accepte(p), construire(donnees, ctx) -> { count, ... }, fiche(cle, donnees) -> [titre, lignes, pied], chips(params), legende(etat, params), info(etat) }
  function fabrique(Cesium, viewer, spec) {
    let pts = null, lab = null, lig = null, gestionnaire = null, donnees = null, actif = false, derniere = null, erreur = null, ecouteur = null, charge = 0, etat = { count: 0 };
    const params = { ...spec.params };
    const redessiner = () => { try { window.__godsEyeView?.requestRender?.(); } catch { /* sans effet */ } };
    const prevenir = () => { try { ecouteur?.(); } catch { /* sans effet */ } };
    const afficher = (v) => { for (const c of [pts, lab, lig]) if (c) c.show = v; };
    const reconstruire = () => { pts.removeAll(); lab.removeAll(); lig.removeAll(); etat = spec.construire(donnees, { Cesium, viewer, pts, lab, lig, params, col: (h, a) => col(Cesium, h, a) }) || { count: 0 }; redessiner(); };
    return {
      id: spec.id, name: spec.name, icon: spec.icon, source: spec.source, updateInterval: spec.updateInterval,
      init() {
        const prims = viewer.scene.primitives;
        pts = prims.add(new Cesium.PointPrimitiveCollection()); lab = prims.add(new Cesium.LabelCollection()); lig = prims.add(new Cesium.PolylineCollection()); afficher(false);
      },
      enable() {
        actif = true; afficher(true);
        gestionnaire = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        gestionnaire.setInputAction((e) => {
          const k = viewer.scene.pick(e.position)?.id?.jarvisCle;
          if (k !== undefined && k !== null && donnees) { const f = spec.fiche(k, donnees); if (f) carte(...f); } else document.querySelector('[data-jarvis-carte]')?.remove();
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
        redessiner();
      },
      disable() { actif = false; charge++; afficher(false); gestionnaire?.destroy(); gestionnaire = null; document.querySelector('[data-jarvis-carte]')?.remove(); redessiner(); },
      async update(_v, { signal } = {}) {
        if (!actif) return false;
        const moi = ++charge;
        try {
          const d = await jsonAvecAttente(spec.url, signal, () => actif && moi === charge);
          if (!d || moi !== charge) { if (moi === charge && actif && !signal?.aborted) { erreur = spec.name + ' unavailable · retrying'; prevenir(); setTimeout(() => { if (actif && !donnees) this.update(null, {}); }, 20000); } return false; }
          donnees = d; derniere = Date.now(); erreur = null; reconstruire(); prevenir(); return true;
        } catch (e) { if (signal?.aborted) return false; erreur = String(e?.message || e); prevenir(); return false; }
      },
      destroy() { this.disable(); for (const c of [pts, lab, lig]) if (c) viewer.scene.primitives.remove(c); pts = lab = lig = null; },
      getStats() { return { count: etat.count || 0, lastUpdate: derniere, error: erreur }; },
      getParams() { return { ...params }; },
      setParams(p) { const ok = spec.accepte(p || {}); if (!ok) return false; if (JSON.stringify(ok) !== JSON.stringify(Object.fromEntries(Object.keys(ok).map((k) => [k, params[k]])))) { Object.assign(params, ok); if (actif && donnees) reconstruire(); prevenir(); } return true; },
      setRowControlsListener(cb) { ecouteur = cb; },
      getRowControls() { return { chips: spec.chips(params), legend: spec.legende(etat, params), info: spec.info(etat) }; },
    };
  }
  const leg = (liste) => liste.map(([label, color, blurb]) => ({ label, color, blurb: blurb || label }));
  const chipsDe = (cle, options, params) => options.map(([v, label, title]) => ({ id: cle + '-' + v, label, active: params[cle] === v, params: { [cle]: v }, title: title || label }));

  // ---- bornes de recharge (IRVE) ----------------------------------------------------------------------------------------------------------------------------------------
  const PUISSANCES = [[22, '#4aa3ff', '≤ 22 kW'], [50, '#2de2d0', '23–50 kW'], [150, '#7dff5a', '51–150 kW'], [Infinity, '#ff4df0', '> 150 kW']];
  const rechargeFrance = (Cesium, viewer) => fabrique(Cesium, viewer, {
    id: 'ev-chargers-fr', name: 'EV chargers · France', icon: '🔌', source: 'IRVE · data.gouv.fr · Licence Ouverte 2.0', updateInterval: 6 * 3600000, url: '/__jarvis/donnees/recharge.json', params: { min: 0 },
    accepte: (p) => ([0, 50, 150].includes(p.min) ? { min: p.min } : null),
    construire(d, { pts, params, col: c }) {
      let n = 0;
      d.forEach((s, k) => {
        if (s[6] < params.min) return;
        const [, hexa] = PUISSANCES.find(([max]) => s[6] <= max);
        pts.add({ position: Cesium.Cartesian3.fromDegrees(s[2], s[1], 15), pixelSize: 5 + Math.min(5, Math.log2(Math.max(1, s[5]))), color: c(hexa, 0.95), outlineColor: Cesium.Color.BLACK.withAlpha(0.6), outlineWidth: 1,
          disableDepthTestDistance: Infinity, scaleByDistance: new Cesium.NearFarScalar(2e4, 1.4, 5e6, 0.35), id: { jarvisCle: k } }); n++;
      });
      return { count: n };
    },
    fiche: (k, d) => { const s = d[k]; return [s[3] || s[4] || 'Charging station', [['Operator', s[4] || '—'], ['Charge points', String(s[5])], ['Max power', s[6] + ' kW'], ['Connectors', s[7] || '—'], ['Free', s[8] ? 'yes' : 'no'], ['Hours', s[9] || '—']], 'Source: IRVE consolidated file (data.gouv.fr)']; },
    chips: (p) => chipsDe('min', [[0, 'All stations'], [50, 'Fast ≥ 50 kW'], [150, 'Ultra ≥ 150 kW']], p),
    legende: () => leg(PUISSANCES.map(([, c, l]) => [l, c])),
    info: (e) => (e.count || 0) + ' charging stations shown. Colour = highest power of the station; size = number of charge points. Click a station for details.',
  });

  // ---- vigilance crues (Vigicrues) --------------------------------------------------------------------------------------------------------------------------------------
  const NIVEAUX_CRUE = { 1: ['#2fd36b', 'Green · no particular vigilance', 2.5, 0.55], 2: ['#ffe14a', 'Yellow · be attentive', 4, 0.95], 3: ['#ff9a1f', 'Orange · be very vigilant', 5, 1], 4: ['#ff2b2b', 'Red · absolute vigilance', 6, 1] };
  const cruesFrance = (Cesium, viewer) => fabrique(Cesium, viewer, {
    id: 'flood-vigilance-fr', name: 'Flood vigilance · France', icon: '🌊', source: 'Vigicrues · Ministère de la Transition écologique', updateInterval: 15 * 60000, url: '/__jarvis/donnees/crues.json', params: { vue: 'all' },
    accepte: (p) => (['all', 'alerts'].includes(p.vue) ? { vue: p.vue } : null),
    construire(d, { lig, params, col: c }) {
      let n = 0, alertes = 0;
      d.forEach(([, niveau, lignes], k) => {
        if (niveau > 1) alertes++;
        if (params.vue === 'alerts' && niveau < 2) return;
        const [hexa, , largeur, alpha] = NIVEAUX_CRUE[niveau]; n++;
        for (const l of lignes) lig.add({ positions: Cesium.Cartesian3.fromDegreesArrayHeights(l.flatMap(([x, y]) => [x, y, 25])), width: largeur, material: Cesium.Material.fromType('Color', { color: c(hexa, alpha) }), id: { jarvisCle: k } });
      });
      return { count: n, alertes };
    },
    fiche: (k, d) => { const [nom, niveau] = d[k]; return [nom, [['Vigilance', NIVEAUX_CRUE[niveau][1]]], 'Source: Vigicrues (vigicrues.gouv.fr), reaches updated about every 30 minutes']; },
    chips: (p) => chipsDe('vue', [['all', 'All reaches'], ['alerts', 'Alerts only']], p),
    legende: () => leg(Object.values(NIVEAUX_CRUE).map(([c, l]) => [l.split(' · ')[0], c, l])),
    info: (e) => (e.alertes ? e.alertes + ' reach(es) at yellow or above. ' : 'No reach above green. ') + 'Flood vigilance of the monitored rivers (Vigicrues); only the rivers covered by the State flood forecasting service are shown.',
  });

  // ---- séismes en France (EMSC) -------------------------------------------------------------------------------------------------------------------------------------------
  const seismesFrance = (Cesium, viewer) => fabrique(Cesium, viewer, {
    id: 'earthquakes-fr', name: 'Earthquakes · France region', icon: '〰', source: 'EMSC · seismicportal.eu', updateInterval: 10 * 60000, url: '/__jarvis/donnees/seismes.json', params: { jours: 30 },
    accepte: (p) => ([7, 30].includes(p.jours) ? { jours: p.jours } : null),
    construire(d, { lab, pts, params, col: c }) {
      const limite = Date.now() - params.jours * 86400000; let n = 0;
      d.forEach((s, k) => {
        if (Date.parse(s[5] + 'Z') < limite) return; n++;
        const hexa = s[3] < 10 ? '#ff5a3c' : s[3] < 30 ? '#ffb13c' : '#7ad7ff', position = Cesium.Cartesian3.fromDegrees(s[2], s[1], 20);
        pts.add({ position, pixelSize: 4 + s[4] * 3.2, color: c(hexa, 0.8), outlineColor: Cesium.Color.WHITE.withAlpha(0.8), outlineWidth: 1, disableDepthTestDistance: Infinity, id: { jarvisCle: k } });
        if (s[4] >= 2.5) lab.add({ position, text: 'M' + s[4].toFixed(1), font: '600 13px Consolas, monospace', fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(0, -16), disableDepthTestDistance: Infinity, scale: 0.9, id: { jarvisCle: k } });
      });
      return { count: n };
    },
    fiche: (k, d) => { const s = d[k]; return ['M' + s[4].toFixed(1) + ' · ' + (s[6] || 'Unknown region'), [['Time (UTC)', s[5].replace('T', ' ')], ['Depth', s[3] + ' km'], ['Position', s[1].toFixed(3) + ', ' + s[2].toFixed(3)]], 'Source: EMSC (seismicportal.eu)']; },
    chips: (p) => chipsDe('jours', [[7, '7 days'], [30, '30 days']], p),
    legende: () => leg([['< 10 km', '#ff5a3c', 'Shallow (< 10 km)'], ['10–30 km', '#ffb13c', 'Intermediate (10–30 km)'], ['> 30 km', '#7ad7ff', 'Deep (> 30 km)']]),
    info: (e) => (e.count || 0) + ' earthquakes of magnitude 1.5 or more around France (41–51.5°N, 5.5°W–10°E). Size = magnitude, colour = depth. Click one for details.',
  });

  // ---- qualité de l'air (Open-Meteo, indice européen EAQI) ---------------------------------------------------------------------------------------------------------------
  const EAQI = [null, ['#50f0e6', 'Good'], ['#50ccaa', 'Fair'], ['#f0e641', 'Moderate'], ['#ff5050', 'Poor'], ['#960032', 'Very poor'], ['#7d2181', 'Extremely poor']];
  const airFrance = (Cesium, viewer) => fabrique(Cesium, viewer, {
    id: 'air-quality-fr', name: 'Air quality · France', icon: '🍃', source: 'Open-Meteo · Copernicus CAMS Europe · CC BY 4.0', updateInterval: 30 * 60000, url: '/__jarvis/donnees/air.json', params: {},
    accepte: () => ({}),
    construire(d, { pts, lab, col: c }) {
      d.forEach((s, k) => {
        const position = Cesium.Cartesian3.fromDegrees(s[2], s[1], 20);
        pts.add({ position, pixelSize: 16, color: c(EAQI[s[3]][0], 0.9), outlineColor: Cesium.Color.BLACK.withAlpha(0.65), outlineWidth: 1.5, disableDepthTestDistance: Infinity, scaleByDistance: new Cesium.NearFarScalar(3e5, 1.3, 6e6, 0.5), id: { jarvisCle: k } });
        lab.add({ position, text: s[0], font: '600 12px Consolas, monospace', fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(0, -20), distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 600000), disableDepthTestDistance: Infinity, scale: 0.85, id: { jarvisCle: k } });
      });
      return { count: d.length };
    },
    fiche: (k, d) => { const s = d[k], v = (x) => (x == null ? '—' : x.toFixed(1) + ' µg/m³'); return [s[0] + ' · ' + EAQI[s[3]][1], [['PM2.5', v(s[4])], ['PM10', v(s[5])], ['NO₂', v(s[6])], ['Ozone', v(s[7])], ['Time (UTC)', (s[8] || '').replace('T', ' ')]], 'Model: CAMS Europe via Open-Meteo (about 11 km grid), not a ground station']; },
    chips: () => [],
    legende: () => leg(EAQI.slice(1).map(([c, l]) => [l, c])),
    info: (e) => (e.count || 0) + ' French cities. European Air Quality Index from the Copernicus CAMS model (about 11 km grid): a model estimate, not a measurement at a station.',
  });

  // ---- restrictions de drones (IGN) : zones demandées à l'IGN pour la fenêtre visible, via le serveur de la vue ---------------------------------------------------------------
  // [règle IGN, couleur, libellé, opacité]. Sans limite (null) = grande zone « notification préalable obligatoire pour les drones de plus de 900 g », sans plafond de hauteur : bleu très léger
  const DRONE_STYLES = [[/interdit/i, '#ff3b3b', 'Flight prohibited', 0.4], [/30 ?m/, '#ff8a1f', 'Max height 30 m', 0.4], [/50 ?m/, '#ffb800', 'Max height 50 m', 0.4], [/60 ?m/, '#ffd400', 'Max height 60 m', 0.4], [/100 ?m/, '#c8e04a', 'Max height 100 m', 0.4], [/.*/, '#5aa0e6', 'Prior notification only (drones over 900 g)', 0.14]];
  function dronesFrance(Cesium, viewer) {
    let primitives = [], zones = [], boite = null, jeton = 0, actif = false, derniere = null, erreur = null, ecouteur = null, gestionnaire = null, minuteur = null, controle = null, cible = '', info = 'Zoom in (view under about 1°) to load the zones.';
    const prevenir = () => { try { ecouteur?.(); } catch { /* sans effet */ } };
    const redessiner = () => { try { window.__godsEyeView?.requestRender?.(); } catch { /* sans effet */ } };
    const style = (l) => DRONE_STYLES.find(([re]) => re.test(l || ''));
    const params = { notif: 'off' };   // la grande zone « notification » est masquée par défaut (c'est elle qui dessine de grands « carrés » bleutés)
    function effacer() { jeton++; for (const p of primitives) viewer.scene.groundPrimitives.remove(p); primitives = []; }
    const instanceId = (k, ids, lot) => { const id = { jarvisCle: k }; (ids.get(lot) || ids.set(lot, []).get(lot)).push(id); return id; };
    function dessiner(liste) {
      zones = liste; const moi = ++jeton;   // le nouveau dessin remplace l'ancien SEULEMENT quand il est prêt (sinon tout disparaît le temps que Cesium prépare les polygones)
      const nouveaux = [], ids = new Map(), groupes = new Map();   // un lot (GroundPrimitive) par catégorie : dans un même lot, là où deux zones se superposent une seule est dessinée (le rouge disparaissait sous la grande zone bleue)
      liste.forEach(([limite, polys], k) => {
        const st = style(limite);
        if (params.notif === 'off' && st === DRONE_STYLES[DRONE_STYLES.length - 1]) return;
        for (const p of polys) {
          const anneaux = p.map((a) => a.map(([x, y]) => Cesium.Cartesian3.fromDegrees(x, y)));
          if (!anneaux[0] || anneaux[0].length < 3) continue;
          (groupes.get(DRONE_STYLES.indexOf(st)) || groupes.set(DRONE_STYLES.indexOf(st), []).get(DRONE_STYLES.indexOf(st))).push(new Cesium.GeometryInstance({ geometry: new Cesium.PolygonGeometry({ polygonHierarchy: new Cesium.PolygonHierarchy(anneaux[0], anneaux.slice(1).map((h) => new Cesium.PolygonHierarchy(h))), perPositionHeight: false }),
            attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(col(Cesium, st[1], st[3])), show: new Cesium.ShowGeometryInstanceAttribute(false) }, id: instanceId(k, ids, DRONE_STYLES.indexOf(st)) }));
        }
      });
      // du plus général (bleu, dernier de la liste) au plus strict (rouge) : chaque lot est ajouté par-dessus le précédent
      [...groupes.keys()].sort((x, y) => y - x).forEach((cle) => { const lot = new Cesium.GroundPrimitive({ geometryInstances: groupes.get(cle), appearance: new Cesium.PerInstanceColorAppearance({ translucent: true, closed: false }), classificationType: Cesium.ClassificationType.BOTH, asynchronous: true }); viewer.scene.groundPrimitives.add(lot); lot.jarvisLot = cle; nouveaux.push(lot); });
      const debut = Date.now();
      const attendre = () => {
        if (moi !== jeton) { for (const l of nouveaux) viewer.scene.groundPrimitives.remove(l); return; }   // une vue plus récente a pris le relais
        if (nouveaux.every((l) => l.ready) || Date.now() - debut > 25000) {
          for (const l of nouveaux) { if (!l.ready) continue; for (const id of ids.get(l.jarvisLot) || []) { try { const at = l.getGeometryInstanceAttributes(id); at.show = Cesium.ShowGeometryInstanceAttribute.toValue(true, at.show); } catch { /* instance absente */ } } }   // tous les lots apparaissent ensemble
          const vieux = primitives; primitives = nouveaux; for (const v of vieux) viewer.scene.groundPrimitives.remove(v); redessiner(); return;
        }
        setTimeout(attendre, 80);
      };
      attendre(); redessiner();
    }
    async function charger() {
      if (!actif) return;
      const r = viewer.camera.computeViewRectangle?.(viewer.scene.globe.ellipsoid);
      if (!r) return;   // pas de fenêtre (caméra vers l'horizon) : on garde le dessin actuel
      const d = (x) => Cesium.Math.toDegrees(x), w = d(r.west), s = d(r.south), e = d(r.east), n = d(r.north);
      if (e - w > 1.0 || n - s > 1.0) { effacer(); zones = []; cible = ''; boite = null; info = 'Zoom in (view under about 1°) to load the drone restriction zones.'; prevenir(); return; }
      // la vue est déjà couverte par la dernière zone chargée : rien à recharger (avant : un rechargement à chaque petit déplacement faisait clignoter les zones)
      if (boite && w >= boite[0] && s >= boite[1] && e <= boite[2] && n <= boite[3] && (boite[2] - boite[0]) <= 6 * (e - w) && (boite[3] - boite[1]) <= 6 * (n - s)) return;
      const mx = Math.min((e - w) * 0.25, (1.2 - (e - w)) / 2), my = Math.min((n - s) * 0.25, (1.2 - (n - s)) / 2);   // marge de 25 % : on peut se déplacer sans recharger
      const req = [w - mx, s - my, e + mx, n + my], bbox = req.map((v) => v.toFixed(3)).join(',');
      if (bbox === cible) return; cible = bbox; controle?.abort(); controle = new AbortController();
      try {
        const rep = await fetch('/__jarvis/drones?bbox=' + bbox, { signal: delai(controle.signal, 70000) });
        if (!rep.ok) throw new Error('HTTP ' + rep.status);
        const liste = await rep.json(); if (!actif) return;
        dessiner(liste); boite = req; derniere = Date.now(); erreur = null; info = liste.length + ' zones loaded. Red = flight prohibited; orange to yellow-green = maximum height (30, 50, 60, 100 m). The faint blue area (button "+ Notification area") only requires a prior notification for drones over 900 g, with no specific height limit. Outside all zones the usual limit is 120 m. Click a zone for details.'; prevenir();
      } catch (e) { if (e?.name === 'AbortError') return; erreur = 'Drone zones unavailable · retrying'; cible = ''; boite = null; info = 'The zones of this view could not be loaded (the previous ones may be outdated) · retrying.'; prevenir(); setTimeout(planifier, 6000); }
    }
    const planifier = () => { clearTimeout(minuteur); minuteur = setTimeout(charger, 700); };
    return {
      id: 'drone-zones-fr', name: 'Drone restrictions · France', icon: '🚁', source: 'IGN Géoplateforme · restrictions UAS', updateInterval: 0,
      init() {},
      enable() {
        actif = true; viewer.camera.moveEnd.addEventListener(planifier);
        gestionnaire = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        gestionnaire.setInputAction((e) => {
          const k = viewer.scene.pick(e.position)?.id?.jarvisCle;
          if (k !== undefined && zones[k]) { const [limite, , remarque] = zones[k]; carte(limite || style(limite)[2], [['Rule', style(limite)[2]]].concat(remarque ? [['Note', String(remarque).slice(0, 140)]] : []), 'Source: IGN (data.geopf.fr), indicative: check the official map before flying'); } else document.querySelector('[data-jarvis-carte]')?.remove();
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
        planifier();
      },
      disable() { actif = false; clearTimeout(minuteur); controle?.abort(); cible = ''; boite = null; viewer.camera.moveEnd.removeEventListener(planifier); gestionnaire?.destroy(); gestionnaire = null; effacer(); zones = []; document.querySelector('[data-jarvis-carte]')?.remove(); redessiner(); },
      async update() { cible = ''; boite = null; await charger(); return true; },
      destroy() { this.disable(); },
      getStats() { return { count: zones.length, lastUpdate: derniere, error: erreur }; },
      getParams() { return { ...params }; },
      setParams(p) { if (!p || !['on', 'off'].includes(p.notif)) return false; if (p.notif !== params.notif) { params.notif = p.notif; if (actif && zones.length) dessiner(zones); prevenir(); } return true; },
      setRowControlsListener(cb) { ecouteur = cb; },
      getRowControls() { return { chips: chipsDe('notif', [['off', 'Zones only'], ['on', '+ Notification area']], params), legend: leg(DRONE_STYLES.filter((x, i) => params.notif === 'on' || i < DRONE_STYLES.length - 1).map(([, c, l]) => [l.replace('Max height ', '≤ ').replace('Prior notification only (drones over 900 g)', 'Notify > 900 g'), c, l])), info }; },
    };
  }

  // ---- vigilance météo (Météo-France, API Bulletin Vigilance) : départements colorés par niveau, aujourd'hui / demain, filtre par phénomène -----------------------------------------------
  const PHENOMENES = { 1: 'Wind', 2: 'Rain / flood', 3: 'Thunderstorms', 4: 'River floods', 5: 'Snow / ice', 6: 'Heatwave', 7: 'Extreme cold', 8: 'Avalanches', 9: 'Waves / submersion' };
  const COURT = { all: 'All', 1: 'Wind', 2: 'Rain', 3: 'Storms', 4: 'Floods', 5: 'Snow/ice', 6: 'Heat', 7: 'Cold', 8: 'Avalanche', 9: 'Waves' };
  const VIGILANCE = { 1: ['#2fd36b', 'Green · no particular vigilance', 0.1], 2: ['#ffe14a', 'Yellow · be attentive', 0.5], 3: ['#ff9a1f', 'Orange · be very vigilant', 0.6], 4: ['#ff2b2b', 'Red · absolute vigilance', 0.65] };
  function alertesFrance(Cesium, viewer) {
    let primitive = null, lignes = null, donnees = null, actif = false, derniere = null, erreur = null, ecouteur = null, gestionnaire = null, charge = 0, etat = { alertes: 0 };
    const params = { echeance: 'J', phen: 'all' };
    const prevenir = () => { try { ecouteur?.(); } catch { /* sans effet */ } };
    const redessiner = () => { try { window.__godsEyeView?.requestRender?.(); } catch { /* sans effet */ } };
    const periode = () => donnees?.periodes.find((p) => p.e === params.echeance) || donnees?.periodes[0];
    const niveau = (info) => (params.phen === 'all' ? info[0] : info[1][params.phen] || 1);
    function effacer() { if (primitive) { viewer.scene.groundPrimitives.remove(primitive); primitive = null; } lignes?.removeAll(); }
    function construire() {
      effacer(); const per = periode(); if (!per) return;
      const instances = []; let alertes = 0;
      donnees.depts.forEach(([code, , polys], k) => {
        const info = per.z[code]; if (!info) return;
        const n = niveau(info); if (n > 1) alertes++;
        const [hexa, , alpha] = VIGILANCE[n] || VIGILANCE[1];
        for (const poly of polys) {
          const an = poly.map((a) => a.map(([x, y]) => Cesium.Cartesian3.fromDegrees(x, y)));
          if (!an[0] || an[0].length < 3) continue;
          instances.push(new Cesium.GeometryInstance({ geometry: new Cesium.PolygonGeometry({ polygonHierarchy: new Cesium.PolygonHierarchy(an[0], an.slice(1).map((h) => new Cesium.PolygonHierarchy(h))), perPositionHeight: false }),
            attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(col(Cesium, hexa, alpha)) }, id: { jarvisCle: k } }));
          if (n > 1) lignes.add({ positions: Cesium.Cartesian3.fromDegreesArrayHeights(poly[0].flatMap(([x, y]) => [x, y, 30])), width: 2, material: Cesium.Material.fromType('Color', { color: col(Cesium, hexa, 0.9) }), id: { jarvisCle: k } });
        }
      });
      if (instances.length) { primitive = new Cesium.GroundPrimitive({ geometryInstances: instances, appearance: new Cesium.PerInstanceColorAppearance({ translucent: true, closed: false }), classificationType: Cesium.ClassificationType.BOTH, asynchronous: true }); viewer.scene.groundPrimitives.add(primitive); }
      etat = { alertes }; redessiner();
    }
    return {
      id: 'weather-alerts-fr', name: 'Weather alerts · France', icon: '⚠', source: 'Météo-France · Vigilance', updateInterval: 15 * 60000,
      init() { lignes = viewer.scene.primitives.add(new Cesium.PolylineCollection()); lignes.show = false; },
      enable() {
        actif = true; lignes.show = true;
        gestionnaire = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        gestionnaire.setInputAction((e) => {
          const k = viewer.scene.pick(e.position)?.id?.jarvisCle, per = periode();
          if (k === undefined || !per) { document.querySelector('[data-jarvis-carte]')?.remove(); return; }
          const [code, nom] = donnees.depts[k], info = per.z[code], cote = per.z[code + '10'], lignesFiche = [];
          for (const [ph, n] of Object.entries(info?.[1] || {})) if (n > 1) lignesFiche.push([PHENOMENES[ph] || ph, VIGILANCE[n][1].split(' · ')[0]]);
          for (const [ph, n] of Object.entries(cote?.[1] || {})) if (n > 1) lignesFiche.push(['Coast · ' + (PHENOMENES[ph] || ph), VIGILANCE[n][1].split(' · ')[0]]);
          const fmt = (s) => String(s || '').replace('T', ' ').slice(0, 16);
          carte(nom + ' (' + code + ')', lignesFiche.length ? lignesFiche : [['Vigilance', 'Green · no particular vigilance']], (params.echeance === 'J' ? 'Today' : 'Tomorrow') + ' · valid ' + fmt(per.d) + ' to ' + fmt(per.f) + ' UTC · Source: Météo-France');
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
        redessiner();
      },
      disable() { actif = false; charge++; effacer(); if (lignes) lignes.show = false; gestionnaire?.destroy(); gestionnaire = null; document.querySelector('[data-jarvis-carte]')?.remove(); redessiner(); },
      async update(_v, { signal } = {}) {
        if (!actif) return false;
        const moi = ++charge;
        try {
          const d = await jsonAvecAttente('/__jarvis/donnees/vigilance.json', signal, () => actif && moi === charge);
          if (!d || moi !== charge) { if (moi === charge && actif && !signal?.aborted) { erreur = 'Needs METEOFRANCE_API_KEY subscribed to the Vigilance API (Power up panel) · retrying'; prevenir(); setTimeout(() => { if (actif && !donnees) this.update(null, {}); }, 20000); } return false; }
          donnees = d; derniere = Date.now(); erreur = null; if (!d.periodes.some((p) => p.e === params.echeance)) params.echeance = d.periodes[0].e; construire(); prevenir(); return true;
        } catch (e) { if (signal?.aborted) return false; erreur = String(e?.message || e); prevenir(); return false; }
      },
      destroy() { this.disable(); if (lignes) viewer.scene.primitives.remove(lignes); lignes = null; },
      getStats() { return { count: etat.alertes, lastUpdate: derniere, error: erreur }; },
      getParams() { return { ...params }; },
      setParams(p) {
        if (!p) return false; let change = false;
        if (p.echeance && ['J', 'J1'].includes(p.echeance) && p.echeance !== params.echeance) { params.echeance = p.echeance; change = true; }
        if (p.phen !== undefined && Object.hasOwn(COURT, String(p.phen)) && String(p.phen) !== params.phen) { params.phen = String(p.phen); change = true; }
        if (change && actif && donnees) construire();
        if (change) prevenir();
        return true;
      },
      setRowControlsListener(cb) { ecouteur = cb; },
      getRowControls() {
        const jours = donnees?.periodes.map((p) => p.e) || ['J', 'J1'];
        return {
          chips: [...chipsDe('echeance', jours.map((e) => [e, e === 'J' ? 'Today' : 'Tomorrow']), params), ...Object.entries(COURT).map(([v, l]) => ({ id: 'phen-' + v, label: l, active: params.phen === v, params: { phen: v }, title: v === 'all' ? 'All phenomena (highest level)' : (PHENOMENES[v] || l) }))],
          legend: leg(Object.values(VIGILANCE).map(([c, l]) => [l.split(' · ')[0], c, l])),
          info: (etat.alertes ? etat.alertes + ' département(s) at yellow or above' : 'No département above green') + ' for ' + (params.echeance === 'J' ? 'today' : 'tomorrow') + (params.phen === 'all' ? '' : ' (' + (PHENOMENES[params.phen] || '') + ')') + '. Météo-France vigilance map' + (donnees?.maj ? ', updated ' + String(donnees.maj).replace('T', ' ').slice(0, 16) + ' UTC' : '') + '. Click a département for its alerts.',
        };
      },
    };
  }

  async function demarrer() {
    for (let i = 0; i < 240; i++) {   // l'appli met plusieurs secondes à démarrer ; 2 minutes au plus
      const g = window.__godsEyeView;
      if (g?.dataManager && g.viewer && window.__CESIUM__ && typeof window.__gevQaRegisterLayer === 'function') {
        try {
          for (const creer of [carburantsFrance, rechargeFrance, cruesFrance, seismesFrance, airFrance, dronesFrance, alertesFrance]) {   // une couche qui plante ne doit pas empêcher les autres
            try { window.__gevQaRegisterLayer(g.dataManager, habiller(creer(window.__CESIUM__, g.viewer))); } catch (e) { if (/not authorized|finalized/i.test(String(e && e.message))) throw e; if (!/Duplicate/.test(String(e && e.message))) console.warn('[JARVIS] Couche non ajoutée : ' + (e && e.message)); }
          }
          try {   // fait apparaître la ligne dans le panneau des couches (la liste est montée une seule fois au démarrage)
            const entree = document.querySelector('script[type="module"][src*="/src/main.js"]');
            const { application } = await import(entree.src);
            const { presentation } = application.getComponents().data;
            presentation.mount(presentation.panel._toggleContainer);
          } catch (e) { console.warn('[JARVIS] Panneau des couches non rafraîchi : ' + (e && e.message)); }
          return;
        } catch (e) { if (!/not authorized|finalized/i.test(String(e && e.message)) && !/Duplicate/.test(String(e && e.message))) { console.warn('[JARVIS] Couche non ajoutée : ' + (e && e.message)); return; } if (/Duplicate/.test(String(e.message))) return; }
      }
      await pause(500);
    }
    console.warn("[JARVIS] Couches JARVIS : l'appli n'a pas ouvert son point d'entrée (window.__gevQaRegisterLayer).");
  }
  // La rangée de villes du tiroir POSITION défile à l'horizontale mais sa barre est masquée : la molette ordinaire (verticale) la fait maintenant défiler aussi (comme Maj + molette ou un glissement à deux doigts).
  document.addEventListener('wheel', (e) => {
    const rangee = e.target?.closest?.('.location-pills, .poi-row-container');
    if (!rangee || rangee.scrollWidth <= rangee.clientWidth || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
    rangee.scrollLeft += e.deltaY; e.preventDefault();
  }, { passive: false });
  // Pilotage vocal : le HUD de JARVIS relaie {jarvis:'gev-cmd', id, op, ...} ; on agit sur l'interface comme le ferait un clic et on répond {jarvis:'gev-retour', id, ok, texte}.
  const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
  const mots = (s) => norm(s).split(' ').filter((m) => m.length > 1 && !['le', 'la', 'les', 'de', 'des', 'du', 'un', 'une', 'en', 'au', 'aux', 'et', 'couche', 'layer'].includes(m));
  function meilleur(requete, candidats) {   // candidats : [{el, textes:[...]}] ; score = mots de la requête retrouvés (égalité exacte préférée)
    const q = norm(requete), qm = mots(requete); let best = null, bs = 0;
    for (const c of candidats) {
      for (const tx of c.textes) {
        const n = norm(tx); if (!n) continue;
        let s = n === q ? 100 : 0;
        if (!s) { const hits = qm.filter((m) => n.split(' ').some((w) => w === m || (m.length > 3 && (w.startsWith(m) || m.startsWith(w) && w.length > 3)))).length; s = qm.length && hits === qm.length ? 10 + hits - n.length / 100 : 0; }
        if (s > bs) { bs = s; best = c; }
      }
    }
    return best;
  }
  const lignes = () => [...document.querySelectorAll('.data-toggle-row')].map((el) => ({ el, textes: [el.querySelector('.data-name')?.textContent, el.dataset.layerName, el.dataset.layerId] }));
  const actif = (el) => !!el.querySelector('.data-toggle-btn')?.classList.contains('active');
  const nomLigne = (el) => (el.querySelector('.data-name')?.textContent || el.dataset.layerId || '').trim();
  const visible = (e) => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
  const boutons = () => [...document.querySelectorAll('button, [role=button], [role=tab], [role=switch], input[type=checkbox]')].filter((e) => visible(e) || e.classList.contains('style-btn')).map((el) => ({ el, textes: [el.getAttribute('aria-label'), el.title, el.textContent] }));
  function executer(c) {
    if (c.op === 'liste') {
      const l = lignes().filter((x) => actif(x.el)).map((x) => nomLigne(x.el));
      return { ok: true, texte: l.length ? `Couches actives : ${l.join(', ')}.` : 'Aucune couche active.' };
    }
    if (c.op === 'couche') {
      const x = meilleur(c.nom, lignes());
      if (!x) return { ok: false, texte: `Je ne trouve pas de couche « ${c.nom} ».` };
      const nom = nomLigne(x.el);
      if (actif(x.el) === c.etat) return { ok: true, texte: `La couche ${nom} est déjà ${c.etat ? 'active' : 'désactivée'}.` };
      x.el.querySelector('.data-toggle-btn')?.click();
      return { ok: true, texte: `Couche ${nom} ${c.etat ? 'activée' : 'désactivée'}.` };
    }
    if (c.op === 'toutes_off') {
      let n = 0; for (const x of lignes()) if (actif(x.el)) { x.el.querySelector('.data-toggle-btn')?.click(); n++; }
      return { ok: true, texte: n ? `${n} couches désactivées.` : 'Aucune couche n\'était active.' };
    }
    if (c.op === 'option') {   // pastille (carburant, jour…) d'une couche, ou d'une couche précise si c.couche
      const portee = c.couche ? (meilleur(c.couche, lignes())?.el) : document;
      if (!portee) return { ok: false, texte: `Je ne trouve pas de couche « ${c.couche} ».` };
      const cand = [...portee.querySelectorAll('.data-toggle-controls button, .data-row-list button')].map((el) => ({ el, textes: [el.getAttribute('aria-label'), el.textContent] }));
      const x = meilleur(c.nom, cand) || (/diesel/i.test(c.nom) ? meilleur('gazole', cand) : null);
      if (!x) return { ok: false, texte: `Je ne trouve pas l'option « ${c.nom} ».` };
      x.el.click(); return { ok: true, texte: `Option ${x.el.textContent.trim()} choisie.` };
    }
    if (c.op === 'clic') {   // n'importe quel bouton visible de l'interface : préréglages visuels, HUD, cockpit, radio, tiroirs…
      const x = meilleur(c.nom, boutons());
      if (!x) return { ok: false, texte: `Je ne trouve pas de commande « ${c.nom} » à l'écran.` };
      x.el.click(); return { ok: true, texte: `${(x.el.getAttribute('aria-label') || x.el.textContent).trim().slice(0, 60)} : fait.` };
    }
    return { ok: false, texte: 'Commande inconnue.' };
  }
  window.addEventListener('message', (e) => {
    const c = e.data; if (!c || c.jarvis !== 'gev-cmd') return;
    let r; try { r = executer(c); } catch (err) { r = { ok: false, texte: 'La commande a échoué : ' + (err && err.message) }; }
    try { e.source?.postMessage({ jarvis: 'gev-retour', id: c.id, ok: r.ok, texte: r.texte }, '*'); } catch { /* sans effet */ }
  });
  // Netteté de la carte Google 3D : l'appli garde l'erreur d'écran par défaut de Cesium (16 px), d'où une Terre floue vue de loin ; on la baisse (plus de tuiles chargées, plus de réseau / GPU).
  setInterval(() => {
    try {
      const p = window.__godsEyeView?.viewer?.scene?.primitives, C = window.__CESIUM__;
      if (!p || !C) return;
      for (let i = 0; i < p.length; i++) { const t = p.get(i); if (t instanceof C.Cesium3DTileset && t.maximumScreenSpaceError > 6) { t.maximumScreenSpaceError = 6; t.dynamicScreenSpaceError = false; } }
    } catch { /* sans effet */ }
  }, 3000);
  demarrer();
})();
