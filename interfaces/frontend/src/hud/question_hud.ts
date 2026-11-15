// Question oui / non qui n'a rien de destructif (installer une appli, la mettre à jour…) : `confirm_request` avec `question: true`
// (backend/core/confirmation.py). Deux pièces éclatées bleues : la question et ses précisions à gauche, deux boutons OUI / NON à droite ;
// la réponse vocale reste interceptée par le backend, qui ferme la question (`confirm_closed`). Contrairement à la confirmation d'une action
// destructrice (hexagone à maintenir, écran rouge), un simple clic suffit.
import { wsRef } from "../ws_link";
import { fermerPieces, ouvrirPieces, type PieceDef } from "./eclate";

interface LigneQuestion { t: string; d?: string }
type EtatQuestion = "attente" | "oui" | "non" | "delai";
interface Question { id: string; message: string; lignes: LigneQuestion[]; duree: number; t0: number; etat: EtatQuestion; fin: number }

const RAISON = "question";
let q: Question | null = null;

const esc = (s: string): string => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const coupe = (s: string, n: number): string => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

function pieces(c: Question): PieceDef[] {
  const n = Math.min(4, c.lignes.length);
  return [
    { id: "q", cote: "g", rang: 0, w: 290, h: 96 + Math.ceil(c.message.length / 36) * 20 + n * 36, titre: "QUESTION", rendre: (k) => {
      const lignes = c.lignes.slice(0, 4).map((l) => `<div class="qh-ligne"><b>${esc(l.t)}</b>${l.d ? `<span>${esc(l.d)}</span>` : ""}</div>`).join("");
      k.innerHTML = `<div class="qh-message">${esc(c.message)}</div>${lignes}`;
    } },
    { id: "r", cote: "d", rang: 0, w: 240, h: 156, titre: "VOTRE RÉPONSE", rendre: (k) => {
      k.innerHTML = `<div class="qh-boutons"><button type="button" class="qh-btn qh-oui" data-rep="oui">OUI</button><button type="button" class="qh-btn qh-non" data-rep="non">NON</button></div>
        <div class="qh-delai"></div><div class="qh-aide">Tu peux aussi répondre à voix haute : « oui » ou « non ».</div>`;
      if (!k.dataset.ecoute) {
        k.dataset.ecoute = "1";
        k.addEventListener("click", (e) => {
          const b = (e.target as HTMLElement).closest("[data-rep]") as HTMLElement | null;
          if (b) repondre(b.dataset.rep === "oui");
        });
      }
    }, tick: (k) => {
      if (!q) return;
      const reste = Math.max(0, q.duree - (performance.now() - q.t0) / 1000), d = k.querySelector(".qh-delai");
      if (d) d.textContent = q.etat === "attente" ? `Sans réponse dans ${Math.ceil(reste)} s, la demande est annulée.` : q.etat === "oui" ? "C'est noté." : q.etat === "non" ? "Demande annulée." : "Sans réponse : demande annulée.";
      k.querySelectorAll<HTMLButtonElement>(".qh-btn").forEach((b) => { b.disabled = q!.etat !== "attente"; });
    } },
  ];
}

function terminer(etat: Exclude<EtatQuestion, "attente">): void {
  if (!q || q.etat !== "attente") return;
  q.etat = etat;
  window.clearTimeout(q.fin);
  const cette = q;
  window.setTimeout(() => { fermerPieces(RAISON); if (q === cette) q = null; }, 1400);
}

function repondre(oui: boolean): void {
  if (!q || q.etat !== "attente") return;
  wsRef.current?.send(JSON.stringify({ type: "confirm_response", id: q.id, confirmed: oui }));
  terminer(oui ? "oui" : "non");
}

export function afficherQuestion(id: string, message: string, lignes?: LigneQuestion[], duree?: number): void {
  if (q) window.clearTimeout(q.fin);
  const sec = duree && duree > 0 ? duree : 30;
  q = { id, message, lignes: lignes ?? [], duree: sec, t0: performance.now(), etat: "attente", fin: 0 };
  q.fin = window.setTimeout(() => terminer("delai"), sec * 1000 + 300);   // le backend a déjà annulé : il ferme aussi la demande
  ouvrirPieces(RAISON, pieces(q), undefined, true, () => ({ titre: "QUESTION", valeur: "?", sous: coupe(message.replace(/\s+/g, " "), 26).toUpperCase() }));
}

/** La question est résolue ailleurs (réponse vocale, autre fenêtre, délai écoulé). */
export function questionResolue(id: string, confirme?: boolean | null): void {
  if (!q || q.id !== id) return;
  terminer(confirme === true ? "oui" : confirme === false ? "non" : "delai");
}
