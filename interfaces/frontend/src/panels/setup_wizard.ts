// ── ASSISTANT DE PREMIER LANCEMENT : prénom et voix, clé d'IA, micro, empreinte vocale (css/14_verre.css) ──
// S'ouvre seul quand JARVIS n'a aucune clé d'IA utilisable (backend : core/ws_assistant.py) ;
// l'enregistrement passe par « update_settings », comme la page Paramètres.
import { wsRef } from "../ws_link";
import { esc, icone } from "./pm_utils";
import { definirLangue, langueActuelle } from "../i18n/i18n";

// Voix de JARVIS dans la langue choisie (core/i18n.py : mêmes noms côté serveur)
const nomVoix = (v: string): string => (langueActuelle() === "en" ? (v === "homme" ? "Ryan · en-GB" : "Sonia · en-GB") : v === "homme" ? "Henri · fr-FR" : "Denise · fr-FR");

type Moteur = "gemini" | "groq" | "mistral";
interface Test { ok: boolean; detail: string; duree: number }

const MOTEURS: { id: Moteur; nom: string; env: string; role: string; lien: string; aide: string }[] = [
  { id: "gemini", nom: "Gemini", env: "GEMINI_API_KEY", role: "REQUIS", lien: "https://aistudio.google.com/apikey", aide: "Google AI Studio · gratuit" },
  { id: "groq", nom: "Groq", env: "GROQ_API_KEY", role: "SECOURS", lien: "https://console.groq.com/keys", aide: "gratuit" },
  { id: "mistral", nom: "Mistral", env: "MISTRAL_API_KEY", role: "SECOURS", lien: "https://console.mistral.ai/api-keys", aide: "" },
];
const NOMS_ETAPES = ["Profil", "Clé IA", "Micro et voix", "Options", "Terminé"];
const ETAPE_FINALE = NOMS_ETAPES.length;
interface Local { ollama_installe: boolean; ollama_actif: boolean; modele: string; modele_present: boolean; gpu: string | null; vram_go: number | null }
// Services facultatifs : texte seul, rien n'est configuré ici (backend : core/ws_assistant.py n'en sait rien)
const SERVICES: { nom: string; detail: string }[] = [
  { nom: "Musique : Spotify ou Deezer", detail: "Installez l'application Windows : JARVIS la pilote, sans clé. Un lien de playlist se règle dans Paramètres › Musique." },
  { nom: "Google : Gmail, Agenda, Drive", detail: "Demande un fichier config/credentials.json créé dans Google Cloud (OAuth « application de bureau »), puis une connexion à la première utilisation." },
  { nom: "Maison connectée : Home Assistant", detail: "Renseignez HA_URL et HA_TOKEN dans le fichier .env du dossier d'installation, puis redémarrez JARVIS." },
  { nom: "Autres clés d'IA et de recherche", detail: "OpenAI, SerpAPI, YouTube, Claude, Grok : Paramètres › Clés API." },
  { nom: "Vue de Dieu : globe en direct", detail: "Dites « active la vue de Dieu » : JARVIS propose de l'installer (téléchargement depuis GitHub, une seule fois)." },
  { nom: "Liste des commandes", detail: "Dites « Jarvis, que peux-tu faire » pour afficher tout ce que JARVIS sait faire." },
];
const COMMANDE_MODELE = (modele: string) => `ollama pull ${modele}`;

const etat = {
  etape: 1,
  nom: "",
  voix: "homme" as "homme" | "femme",
  cles: { gemini: "", groq: "", mistral: "" } as Record<Moteur, string>,
  tests: {} as Partial<Record<Moteur, Test | "en_cours">>,
  micros: [] as { index: number; name: string }[],
  micro: null as number | null,
  testMicro: null as Test | null,
  niveau: 0,
  empreinte: "aucune" as "aucune" | "lancee" | "passee",
  local: null as Local | "en_cours" | null,
  copie: false,
  services: false,
};
let minuteurNiveau: number | undefined;

function envoyer(msg: object): void {
  const ws = wsRef.current;
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

function panneau(): HTMLElement | null {
  return document.getElementById("setup-wizard");
}

function motsCles(): Moteur[] {
  return MOTEURS.filter((m) => etat.tests[m.id] && etat.tests[m.id] !== "en_cours" && (etat.tests[m.id] as Test).ok).map((m) => m.id);
}

function pied(retour: boolean, suivant: string, options: { passer?: boolean; actif?: boolean; info?: string } = {}): string {
  const actif = options.actif !== false;
  return `${retour ? `<button class="pm-bouton discret" data-wz="retour">${icone("retour")} Retour</button>` : ""}
    ${options.info ? `<span class="wz-info">${esc(options.info)}</span>` : ""}
    <span style="margin-left:auto"></span>
    ${options.passer ? `<button class="pm-bouton discret" data-wz="passer">Passer cette étape</button>` : ""}
    <button class="pm-bouton plein" data-wz="suivant" ${actif ? "" : "disabled"}>${esc(suivant)}</button>`;
}

function resultat(t: Test | "en_cours" | undefined | null): string {
  if (!t) return "";
  if (t === "en_cours") return `<div class="wz-resultat">Test en cours…</div>`;
  const duree = t.duree ? ` · ${String(t.duree).replace(".", ",")} s` : "";
  return `<div class="wz-resultat ${t.ok ? "ok" : "ko"}">${esc(t.ok ? "Fonctionne" : "Échec")} · ${esc(t.detail)}${esc(duree)}</div>`;
}

/** Ligne d'état : pastille « ok » / « à faire » / « option » (ou l'étiquette donnée), nom, détail. */
function ligne(ok: boolean, texte: string, detail: string, avertir = false, etiquette = ""): string {
  const pastille = ok ? "ok" : etiquette || (avertir ? "à faire" : "option");
  return `<div class="pm-ligne"><span class="sys-pastille ${ok ? "ok" : avertir ? "warn" : ""}">${esc(pastille)}</span><div class="pm-texte"><div class="pm-nom">${esc(texte)}</div><div class="pm-detail">${esc(detail)}</div></div></div>`;
}

function verifierLocal(): void {
  etat.local = "en_cours";
  envoyer({ type: "setup_check_local" });
}

function dessiner(): void {
  const p = panneau();
  if (!p) return;
  const e = etat.etape;
  const etapes = document.getElementById("wz-etapes");
  if (etapes) {
    etapes.innerHTML = NOMS_ETAPES.map((n, i) => {
      const num = i + 1;
      const classe = num < e ? "fait" : num === e ? "on" : "";
      return `<div class="wz-etape ${classe}"><b>${num < e ? "✓" : num}</b>${esc(n)}</div>${num < NOMS_ETAPES.length ? '<div class="wz-trait"></div>' : ""}`;
    }).join("");
  }
  const corps = document.getElementById("wz-corps");
  const bas = document.getElementById("wz-pied");
  if (!corps || !bas) return;

  window.clearInterval(minuteurNiveau);
  minuteurNiveau = undefined;

  if (e === 1) {
    corps.innerHTML = `<h3>Faisons connaissance</h3>
      <p class="wz-intro">JARVIS s'adressera à vous par votre prénom. Tout se modifie plus tard dans les Paramètres.</p>
      <div class="wz-etiq">Langue / Language</div>
      <div class="wz-choix" data-i18n-skip>
        <button class="wz-opt ${langueActuelle() === "fr" ? "on" : ""}" data-langue="fr"><span>Français</span></button>
        <button class="wz-opt ${langueActuelle() === "en" ? "on" : ""}" data-langue="en"><span>English</span></button>
      </div>
      <div class="wz-etiq">Votre prénom</div>
      <input class="wz-champ" id="wz-nom" type="text" maxlength="30" autocomplete="off" placeholder="Votre prénom" value="${esc(etat.nom)}">
      <div class="wz-etiq">Voix de JARVIS</div>
      <div class="wz-choix">
        <button class="wz-opt ${etat.voix === "homme" ? "on" : ""}" data-voix="homme">${icone("haut_parleur")}<span>Voix d'homme<small>${nomVoix("homme")}</small></span></button>
        <button class="wz-opt ${etat.voix === "femme" ? "on" : ""}" data-voix="femme">${icone("haut_parleur")}<span>Voix de femme<small>${nomVoix("femme")}</small></span></button>
      </div>
      <div style="margin-top:12px"><button class="pm-bouton petit" data-wz="exemple">${icone("haut_parleur")} Écouter un exemple</button></div>`;
    bas.innerHTML = pied(false, "Continuer", { actif: etat.nom.trim().length > 0 });
  } else if (e === 2) {
    corps.innerHTML = `<h3>Donnez un cerveau à JARVIS</h3>
      <p class="wz-intro">Il lui faut au moins une clé d'IA. <b>Gemini est gratuit</b> et suffit pour commencer. Collez la clé puis testez-la.</p>
      ${MOTEURS.map((m) => `<div class="wz-cle">
        <div class="wz-cle-nom">${esc(m.nom)}<span class="wz-badge ${m.role === "REQUIS" ? "" : "opt"}">${m.role}</span>
          <small><a href="${esc(m.lien)}" target="_blank" rel="noopener noreferrer">obtenir une clé</a>${m.aide ? " · " + esc(m.aide) : ""}</small></div>
        <input class="wz-champ" type="password" data-cle="${m.id}" autocomplete="off" spellcheck="false" placeholder="Coller la clé…" value="${esc(etat.cles[m.id])}">
        <button class="pm-bouton petit" data-tester="${m.id}" ${etat.tests[m.id] === "en_cours" ? "disabled" : ""}>Tester</button>
      </div>${resultat(etat.tests[m.id])}`).join("")}
      <div class="wz-cle"><div class="wz-cle-nom">Claude · Grok<span class="wz-badge opt">OPTIONNEL</span><small>À ajouter plus tard dans les Paramètres</small></div></div>`;
    bas.innerHTML = pied(true, "Continuer", { actif: motsCles().length > 0, passer: true, info: "Vos clés restent sur ce PC (fichier .env)" });
  } else if (e === 3) {
    corps.innerHTML = `<h3>Micro et voix</h3>
      <p class="wz-intro">Parlez normalement : la barre doit bouger. JARVIS écoute le mot « Jarvis » en permanence, sans rien enregistrer.</p>
      <div class="wz-etiq">Micro utilisé</div>
      <select class="wz-champ" id="wz-micro">${etat.micros.length ? "" : '<option value="">Micro par défaut de Windows</option>'}
        ${etat.micros.map((m) => `<option value="${m.index}" ${etat.micro === m.index ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select>
      <div class="wz-etiq">Niveau en direct</div>
      <div class="wz-niveau"><i id="wz-niveau" style="width:${Math.round(etat.niveau * 100)}%"></i></div>
      <div style="margin-top:10px"><button class="pm-bouton petit" data-wz="test-micro">${icone("micro")} Tester le micro</button></div>
      ${resultat(etat.testMicro)}
      <div class="wz-etiq" style="margin-top:16px">Empreinte vocale · facultatif</div>
      <p class="wz-intro" style="margin:4px 0 8px">JARVIS vous reconnaît et refuse les actions sensibles aux autres voix. Il vous guide à voix haute : vous répétez quelques phrases d'une voix normale. L'empreinte reste sur ce PC.</p>
      ${etat.empreinte === "lancee" ? `<div class="wz-resultat ok">Enregistrement lancé : suivez les instructions de JARVIS à voix haute. Revenez ici quand il a terminé.</div>`
        : `<button class="pm-bouton petit" data-wz="empreinte">${icone("micro")} Commencer l'enregistrement</button>`}`;
    bas.innerHTML = pied(true, "Continuer", { passer: true });
    minuteurNiveau = window.setInterval(() => envoyer({ type: "get_system_status" }), 600);
  } else if (e === 4) {
    if (etat.local === null) verifierLocal();
    const l = etat.local && etat.local !== "en_cours" ? etat.local : null;
    const modele = l?.modele || "qwen3:4b-instruct";
    const ollama = !l ? ligne(false, "Ollama", "Vérification en cours…", false, "…")
      : l.ollama_actif ? ligne(true, "Ollama", "Installé et lancé")
      : l.ollama_installe ? ligne(false, "Ollama", "Installé mais pas lancé : ouvrez Ollama depuis le menu Démarrer, puis vérifiez à nouveau.", true)
      : ligne(false, "Ollama", "Absent : installez-le depuis ollama.com/download (gratuit, quelques minutes).", true);
    const mod = !l ? "" : l.modele_present ? ligne(true, `Modèle ${modele}`, "Présent · 2,5 Go · environ 4 Go de VRAM pendant les réponses")
      : ligne(false, `Modèle ${modele}`, "Absent : 2,5 Go à télécharger. Dans un terminal Windows, tapez la commande ci-dessous (Ollama doit être lancé).", true);
    const gpu = !l ? "" : l.gpu ? ligne(true, "Carte graphique NVIDIA", `${l.gpu} · ${l.vram_go} Go · transcription vocale et modèle hors ligne rapides`)
      : ligne(false, "Carte graphique NVIDIA", "Aucune détectée : le modèle hors ligne tournera sur le processeur (plus lent) et la transcription vocale passera par Groq, qui demande une clé (étape 2).", false, "option");
    corps.innerHTML = `<h3>Options facultatives</h3>
      <p class="wz-intro">Rien d'obligatoire sur cette page : tout peut se faire plus tard.</p>
      <div class="wz-etiq">Sans internet</div>
      <p class="wz-intro" style="margin:4px 0 8px">Si Internet ou les services d'IA tombent en panne, JARVIS peut continuer à répondre avec un petit modèle installé sur ce PC. Sans lui, il ne répond plus aux questions quand les services en ligne sont indisponibles.</p>
      ${ollama}${mod}${gpu}
      ${l && !l.modele_present ? `<div class="wz-cle" style="grid-template-columns:1fr auto"><input class="wz-champ" readonly value="${esc(COMMANDE_MODELE(modele))}"><button class="pm-bouton petit" data-wz="copier">${etat.copie ? "Copié" : "Copier"}</button></div>` : ""}
      <div style="margin-top:10px;display:flex;gap:8px"><button class="pm-bouton petit" data-wz="verifier-local" ${etat.local === "en_cours" ? "disabled" : ""}>Vérifier à nouveau</button>
        <button class="pm-bouton petit" data-wz="services">${etat.services ? "Masquer les autres services" : "Voir les autres services"}</button></div>
      ${etat.services ? `<div class="wz-etiq" style="margin-top:14px">Autres services : où les régler</div>${SERVICES.map((s) => ligne(false, s.nom, s.detail, false, "option")).join("")}` : ""}`;
    bas.innerHTML = pied(true, "Continuer", { passer: true });
  } else {
    const ia = motsCles();
    const micro = etat.micros.find((m) => m.index === etat.micro);
    corps.innerHTML = `<h3>JARVIS est prêt</h3>
      <p class="wz-intro">Voici l'état de votre installation. Tout reste modifiable à tout moment depuis les Paramètres.</p>
      ${ligne(ia.length > 0, "Moteur d'IA", ia.length ? `${ia.map((i) => MOTEURS.find((m) => m.id === i)!.nom).join(", ")} · test réussi` : "Aucune clé testée : ajoutez-en une dans Paramètres › Clés API", ia.length === 0)}
      ${ligne(!!etat.testMicro && etat.testMicro.ok, "Micro", etat.testMicro?.ok ? `${micro ? micro.name : "micro par défaut"} · signal reçu` : "Non testé", !(etat.testMicro && etat.testMicro.ok))}
      ${ligne(true, "Voix de JARVIS", nomVoix(etat.voix))}
      ${ligne(etat.empreinte === "lancee", "Empreinte vocale", etat.empreinte === "lancee" ? "Enregistrement lancé" : "Passée : à refaire en disant « enregistre ma voix »", etat.empreinte !== "lancee")}
      ${(() => {
        const l = etat.local && etat.local !== "en_cours" ? etat.local : null;
        if (!l) return ligne(false, "Mode hors ligne", "Non vérifié : Ollama et le modèle se préparent plus tard (page « Options »)", false, "option");
        return l.ollama_actif && l.modele_present ? ligne(true, "Mode hors ligne", `Ollama · ${l.modele} prêt`)
          : ligne(false, "Mode hors ligne", l.ollama_installe ? `Modèle ${l.modele} à télécharger : ollama pull ${l.modele}` : "Ollama absent : facultatif, voir ollama.com/download", false, "option");
      })()}
      <p class="wz-intro" style="margin-top:14px">Dites <b style="color:var(--pm-a)">« Jarvis »</b>, suivi de votre demande, ou écrivez-la dans la barre en haut à gauche.</p>`;
    bas.innerHTML = pied(true, "Lancer JARVIS");
  }
}

function ouvrir(): void {
  const p = panneau();
  if (!p) return;
  etat.etape = 1;
  p.classList.remove("hidden");
  p.classList.add("visible");
  envoyer({ type: "get_settings" });
  dessiner();
}

function fermer(): void {
  const p = panneau();
  window.clearInterval(minuteurNiveau);
  minuteurNiveau = undefined;
  if (p) {
    p.classList.remove("visible");
    p.classList.add("hidden");
  }
}

/** Enregistre tout (clés, prénom, voix, micro) et marque l'assistant comme terminé. */
function terminer(): void {
  const reglages: Record<string, unknown> = {
    user_name: etat.nom.trim(),
    voix_jarvis: etat.voix,
    assistant_termine: true,
  };
  if (etat.micro !== null) reglages.mic_device_index = etat.micro;
  envoyer({ type: "update_settings", settings: reglages });
  fermer();
}

function enregistrerCles(): void {
  const cles: Record<string, string> = {};
  MOTEURS.forEach((m) => {
    const t = etat.tests[m.id];
    if (etat.cles[m.id].trim() && t && t !== "en_cours" && t.ok) cles[m.env] = etat.cles[m.id].trim();
  });
  if (Object.keys(cles).length) envoyer({ type: "update_settings", settings: { api_keys: cles } });
}

function suivant(): void {
  if (etat.etape === 1) envoyer({ type: "update_settings", settings: { user_name: etat.nom.trim(), voix_jarvis: etat.voix } });
  if (etat.etape === 2) enregistrerCles();
  if (etat.etape >= ETAPE_FINALE) {
    terminer();
    return;
  }
  etat.etape += 1;
  dessiner();
}

export function handleSetupMessage(data: any): boolean {
  if (data.type === "setup_state") {
    etat.nom = etat.nom || String(data.nom || "");
    etat.voix = data.voix === "femme" ? "femme" : "homme";
    // Le panneau d'introduction (boot) doit avoir disparu avant l'ouverture
    if (data.besoin) window.setTimeout(ouvrir, 3500);
    return true;
  }
  if (data.type === "setup_local_result") {
    etat.local = {
      ollama_installe: !!data.ollama_installe, ollama_actif: !!data.ollama_actif, modele: String(data.modele || "qwen3:4b-instruct"),
      modele_present: !!data.modele_present, gpu: data.gpu ? String(data.gpu) : null, vram_go: data.vram_go ?? null,
    };
    if (etat.etape === 4) dessiner();
    return true;
  }
  if (data.type === "setup_key_result") {
    const id = data.moteur as Moteur;
    etat.tests[id] = { ok: !!data.ok, detail: String(data.detail || ""), duree: Number(data.duree) || 0 };
    if (etat.etape === 2) dessiner();
    return true;
  }
  // Messages partagés avec d'autres panneaux : on les lit sans les consommer
  if (data.type === "settings_data" && data.data) {
    etat.micros = Array.isArray(data.data.mic_list) ? data.data.mic_list : [];
    const choisi = data.data.mic_device_index;
    etat.micro = choisi === null || choisi === undefined ? (etat.micros[0]?.index ?? null) : Number(choisi);
    return false;
  }
  if (data.type === "system_test_result" && data.id === "micro") {
    etat.testMicro = { ok: !!data.ok, detail: String(data.detail || ""), duree: Number(data.duree) || 0 };
    if (etat.etape === 3) dessiner();
    return false;
  }
  if (data.type === "system_status" && data.voix && etat.etape === 3) {
    etat.niveau = Math.min(1, Number(data.voix.niveau) || 0);
    const barre = document.getElementById("wz-niveau");
    if (barre) barre.style.width = `${Math.round(etat.niveau * 100)}%`;
    return false;
  }
  return false;
}

export function initSetupWizard(): void {
  const p = panneau();
  if (!p) return;
  p.addEventListener("click", (ev) => {
    const cible = ev.target as HTMLElement;
    const bouton = cible.closest("button") as HTMLButtonElement | null;
    if (!bouton || bouton.disabled) return;
    const choixLangue = bouton.dataset.langue;
    if (choixLangue === "fr" || choixLangue === "en") {   // première étape : langue de l'interface, de la voix et des réponses
      definirLangue(choixLangue);
      envoyer({ type: "update_settings", settings: { langue: choixLangue } });
      dessiner();
      return;
    }
    const wz = bouton.dataset.wz;
    if (wz === "suivant") suivant();
    else if (wz === "retour") {
      etat.etape = Math.max(1, etat.etape - 1);
      dessiner();
    } else if (wz === "passer") {
      if (etat.etape === 2) {
        etat.etape += 1;
        dessiner();
      } else {
        if (etat.etape === 3 && etat.empreinte === "aucune") etat.empreinte = "passee";
        suivant();
      }
    } else if (wz === "services") {
      etat.services = !etat.services;
      dessiner();
    } else if (wz === "verifier-local") {
      verifierLocal();
      dessiner();
    } else if (wz === "copier") {
      const modele = etat.local && etat.local !== "en_cours" ? etat.local.modele : "qwen3:4b-instruct";
      navigator.clipboard?.writeText(COMMANDE_MODELE(modele)).then(() => { etat.copie = true; if (etat.etape === 4) dessiner(); }).catch(() => { /* presse-papiers refusé : la commande reste sélectionnable */ });
    } else if (wz === "exemple") {
      envoyer({ type: "update_settings", settings: { voix_jarvis: etat.voix } });
      envoyer({ type: "system_test", cible: "voix" });
    } else if (wz === "test-micro") {
      etat.testMicro = null;
      envoyer({ type: "system_test", cible: "micro" });
    } else if (wz === "empreinte") {
      etat.empreinte = "lancee";
      envoyer({ type: "user_input", text: "enregistre ma voix" });
      dessiner();
    } else if (bouton.dataset.tester) {
      const id = bouton.dataset.tester as Moteur;
      if (!etat.cles[id].trim()) return;
      etat.tests[id] = "en_cours";
      dessiner();
      envoyer({ type: "setup_test_key", moteur: id, cle: etat.cles[id].trim() });
    } else if (bouton.dataset.voix) {
      etat.voix = bouton.dataset.voix === "femme" ? "femme" : "homme";
      dessiner();
    }
  });
  // Saisies : on garde les valeurs sans redessiner à chaque touche
  p.addEventListener("input", (ev) => {
    const cible = ev.target as HTMLInputElement;
    if (cible.id === "wz-nom") {
      etat.nom = cible.value;
      const suiv = p.querySelector('[data-wz="suivant"]') as HTMLButtonElement | null;
      if (suiv) suiv.disabled = etat.nom.trim().length === 0;
    } else if (cible.dataset.cle) {
      const id = cible.dataset.cle as Moteur;
      etat.cles[id] = cible.value;
      delete etat.tests[id];
    }
  });
  p.addEventListener("change", (ev) => {
    const cible = ev.target as HTMLSelectElement;
    if (cible.id === "wz-micro") etat.micro = cible.value === "" ? null : Number(cible.value);
  });
}
