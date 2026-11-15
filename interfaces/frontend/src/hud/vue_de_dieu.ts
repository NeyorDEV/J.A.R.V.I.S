// Vue de Dieu : God's Eye View (interfaces/gods_eye_view, lancé par backend/module/vue_de_dieu.py) en plein écran dans le HUD.
// Le backend démarre le petit serveur local et envoie `vue_de_dieu_show` ; le HUD sort la vue du cylindre (comme les vues 3D),
// attend que le serveur réponde, puis charge l'appli entière dans une iframe. `vue_de_dieu_goto` déplace la caméra (ancre de lien
// partageable) ; la croix, Échap ou « ferme la vue de Dieu » referment, et le HUD l'annonce au backend pour qu'il arrête le serveur.
import { wsRef } from "../ws_link";
import { hideCarouselArrow, showCarouselArrow } from "../ui/carousel";
import { fermerPleinEcran, ouvrirPleinEcran } from "./plein_ecran";

const racine = document.getElementById("vue-de-dieu") as HTMLDivElement | null;
const cadre = document.getElementById("vdd-cadre") as HTMLIFrameElement | null;
const etat = document.getElementById("vdd-etat") as HTMLElement | null;
const bouton = document.getElementById("vdd-fermer") as HTMLButtonElement | null;
const barre = document.getElementById("vdd-barre") as HTMLElement | null;
const barreI = document.getElementById("vdd-barre-i") as HTMLElement | null;
const notes = document.getElementById("vdd-notes") as HTMLElement | null;

const MODULE: [string, string] = ["JEUX ET 3D", "Vue de Dieu"];
const DELAI_SERVEUR_MS = 90_000;   // le premier démarrage de l'appli peut être long
let ouverte = false, fermeture = false, sonde = 0, jeton = 0, urlCourante = "";

function signaler(o: boolean): void {
  try { wsRef.current?.send(JSON.stringify({ type: "vue_de_dieu_state", ouverte: o })); } catch { /* socket fermée : le backend s'arrêtera avec JARVIS */ }
}

function message(texte: string): void { if (etat) etat.textContent = texte; }

/** Attend que le serveur de l'appli réponde (une requête sans CORS aboutit dès qu'il écoute), puis charge l'iframe. */
function attendreServeur(url: string, ce: number): void {
  const debut = performance.now();
  const essai = async (): Promise<void> => {
    if (ce !== jeton || !ouverte || !cadre) return;
    try {
      await fetch(url, { mode: "no-cors", cache: "no-store" });
      message("CHARGEMENT DU GLOBE…");
      cadre.src = url;
      return;
    } catch { /* pas encore démarré */ }
    if (performance.now() - debut > DELAI_SERVEUR_MS) { message("LA VUE DE DIEU NE RÉPOND PAS · DIS « FERME LA VUE DE DIEU »"); return; }
    sonde = window.setTimeout(() => { void essai(); }, 600);
  };
  void essai();
}

export function vueDeDieuOuverte(): boolean { return ouverte; }

export function ouvrirVueDeDieu(url: string, installation = false): void {
  if (!racine || !cadre) return;
  if (ouverte) return;
  ouverte = true; fermeture = false; urlCourante = url;
  const ce = ++jeton;
  racine.classList.remove("vdd-pret");
  notes?.replaceChildren(); notes?.classList.remove("vdd-actif");   // les notes d'une mise à jour précédente ne restent pas
  message(installation ? "INSTALLATION DE GOD'S EYE VIEW…" : "LANCEMENT DE LA VUE DE DIEU…");
  progresVueDeDieu(installation ? "INSTALLATION DE GOD'S EYE VIEW…" : "LANCEMENT DE LA VUE DE DIEU…", installation ? 0 : null);
  cadre.removeAttribute("src");
  cadre.onload = () => { if (ce === jeton && cadre.getAttribute("src")) racine.classList.add("vdd-pret"); };
  racine.style.display = "block";
  hideCarouselArrow();
  signaler(true);
  // la vue sort du cylindre ; l'orbe n'est masqué qu'une fois la vue étendue par-dessus (comme les vues 3D)
  ouvrirPleinEcran("vue-de-dieu", racine, MODULE, () => {
    const orbCanvas = document.getElementById("orb-canvas");
    if (orbCanvas) orbCanvas.style.display = "none";
  });
  if (!installation) attendreServeur(url, ce);   // en installation, le backend annonce « prête » (vue_de_dieu_pret) quand il a fini
}

/** Texte (et avancement de 0 à 1, null = sans barre) affiché sur l'écran d'attente pendant l'installation. */
export function progresVueDeDieu(texte: string, fraction?: number | null): void {
  if (texte) message(texte);
  if (barre) barre.classList.toggle("vdd-actif", typeof fraction === "number");
  if (barreI && typeof fraction === "number") barreI.style.width = `${Math.round(Math.min(1, Math.max(0, fraction)) * 100)}%`;
}

/** Notes de la version en cours d'installation (backend : liste de [genre, texte], « h » titre, « li » point, « p » paragraphe), lisibles et défilantes sur l'écran d'attente. */
export function notesVueDeDieu(tag: string, lignes: [string, string][]): void {
  if (!notes) return;
  notes.replaceChildren();
  if (!Array.isArray(lignes) || !lignes.length) { notes.classList.remove("vdd-actif"); return; }
  const titre = document.createElement("div");
  titre.className = "vdd-notes-titre"; titre.textContent = `NOUVEAUTÉS · ${tag}`;
  notes.append(titre);
  for (const [genre, texte] of lignes.slice(0, 300)) {
    const ligne = document.createElement("div");
    ligne.className = `vdd-n-${genre === "h" || genre === "li" ? genre : "p"}`; ligne.textContent = String(texte);
    notes.append(ligne);
  }
  notes.scrollTop = 0; notes.classList.add("vdd-actif");
}

/** Installation terminée : le serveur démarre, on attend qu'il réponde puis on charge l'appli. */
export function vueDeDieuPrete(url: string): void {
  if (!ouverte) return;
  urlCourante = url;
  progresVueDeDieu("DÉMARRAGE DE LA VUE DE DIEU…", null);
  attendreServeur(url, jeton);
}

/** Installation échouée : le message reste affiché quelques secondes, puis la vue se referme. */
export function erreurVueDeDieu(texte: string): void {
  if (!ouverte) return;
  progresVueDeDieu(texte, null);
  window.setTimeout(() => { if (ouverte && !cadre?.getAttribute("src")) fermerVueDeDieu(); }, 7000);
}

/** Déplace la caméra : l'ancre (`#v=2&lat=…&lon=…`) est lue par l'appli, qui l'écoute (hashchange). */
export function allerVueDeDieu(ancre: string): void {
  if (!ouverte || !cadre || !urlCourante || !ancre.startsWith("#v=2")) return;
  cadre.src = `${urlCourante}${ancre}`;
}

export function fermerVueDeDieu(): void {
  if (!racine || !ouverte || fermeture) return;
  fermeture = true; ouverte = false; jeton++;
  window.clearTimeout(sonde);
  showCarouselArrow();
  signaler(false);
  fermerPleinEcran("vue-de-dieu", racine, () => {
    racine.style.display = "none"; racine.classList.remove("vdd-pret");
    if (cadre) { cadre.onload = null; cadre.removeAttribute("src"); }   // la page se décharge : le globe libère la carte graphique
    fermeture = false;
  }, () => {
    const orbCanvas = document.getElementById("orb-canvas");
    if (orbCanvas) orbCanvas.style.display = "block";
  });
}

/** Bouton « utiliser la clé de JARVIS » des Paramètres de l'appli (script jarvis-partage.js, dans l'iframe) : le HUD relaie au backend, qui copie la clé. */
window.addEventListener("message", (e: MessageEvent) => {
  const d = e.data as { jarvis?: string; fournisseur?: string } | null;
  if (!cadre || e.source !== cadre.contentWindow || d?.jarvis !== "partager-cle" || typeof d.fournisseur !== "string") return;
  try { wsRef.current?.send(JSON.stringify({ type: "vue_de_dieu_partager_cle", fournisseur: d.fournisseur })); }
  catch { cadre.contentWindow?.postMessage({ jarvis: "partage-resultat", fournisseur: d.fournisseur, ok: false, texte: "JARVIS ne répond pas." }, "*"); }
});

/** Réponse du backend : affichée sur le bouton, dans l'iframe. */
export function partageCleVueDeDieu(fournisseur: string, ok: boolean, texte: string): void {
  cadre?.contentWindow?.postMessage({ jarvis: "partage-resultat", fournisseur, ok, texte }, "*");
}

bouton?.addEventListener("click", fermerVueDeDieu);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && ouverte) fermerVueDeDieu(); });
