// ── Utilitaires communs aux panneaux de modules (css/13_panneaux_modules.css) ──
// Désinstallateur, mises à jour (winget), sécurité (antivirus), domotique.

/** Texte inséré dans du HTML (noms de programmes, chemins, appareils…). */
export function esc(texte: unknown): string {
  return String(texte ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/** Initiales pour l'avatar d'une ligne : « Visual Studio Code » → « VS », « Steam » → « St ». */
export function initiales(nom: string): string {
  const mots = nom.replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter(Boolean);
  if (mots.length >= 2) return (mots[0][0] + mots[1][0]).toUpperCase();
  const m = mots[0] || "?";
  return m[0].toUpperCase() + (m[1] || "").toLowerCase();
}

/** Taille en Ko → « 412 Mo », « 8,4 Go ». Chaîne vide si inconnue. */
export function formatTaille(ko: number): string {
  if (!ko || ko <= 0) return "";
  if (ko < 1024) return `${ko} Ko`;
  const mo = ko / 1024;
  if (mo < 1024) return `${Math.round(mo)} Mo`;
  return `${(mo / 1024).toFixed(1).replace(".", ",")} Go`;
}

/** « 20260914 » → « 14/09/2026 ». Chaîne vide si inconnue. */
export function formatDate(aaaammjj: string): string {
  if (!/^\d{8}$/.test(aaaammjj || "")) return "";
  return `${aaaammjj.slice(6, 8)}/${aaaammjj.slice(4, 6)}/${aaaammjj.slice(0, 4)}`;
}

/** Nombre avec espaces de milliers : 4812 → « 4 812 ». */
export function formatNombre(n: number): string {
  return Math.round(n).toLocaleString("fr-FR");
}

// Icônes au trait (24×24, stroke = currentColor), sans dépendance externe.
const TRACES: Record<string, string> = {
  fermer: '<path d="M18 6 6 18M6 6l12 12"/>',
  recherche: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  corbeille: '<path d="M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
  actualiser: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
  bouclier: '<path d="M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6l-7-3z"/>',
  bouclier_ok: '<path d="M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6l-7-3z"/><path d="m9 12 2 2 4-4"/>',
  insecte: '<path d="M9 9V7a3 3 0 0 1 6 0v2M8 9h8v5a4 4 0 0 1-8 0V9zM3 13h5M16 13h5M4 8l4 2M20 8l-4 2M4 19l4-3M20 19l-4-3"/>',
  maison: '<path d="M4 11 12 4l8 7v8a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1v-8z"/>',
  dossier: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
  registre: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
  fleche: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  ok: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  erreur: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/>',
  ampoule: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/>',
  prise: '<path d="M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0V8zM12 17v5"/>',
  thermometre: '<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z"/>',
  goutte: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
  batterie: '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 11v2M7 10v4M11 10v4"/>',
  eclair: '<path d="M13 3 5 14h6l-1 7 8-11h-6l1-7z"/>',
  soleil: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  ventilateur: '<circle cx="12" cy="12" r="2"/><path d="M12 10c0-4 1-7 4-7 2 0 3 2 2 4-1 1.5-3.5 2.5-6 3M14 12c4 0 7 1 7 4 0 2-2 3-4 2-1.5-1-2.5-3.5-3-6M12 14c0 4-1 7-4 7-2 0-3-2-2-4 1-1.5 3.5-2.5 6-3M10 12c-4 0-7-1-7-4 0-2 2-3 4-2 1.5 1 2.5 3.5 3 6"/>',
  robot: '<rect x="5" y="8" width="14" height="11" rx="3"/><path d="M12 4v4M9 13h.01M15 13h.01M9 16h6"/>',
  flocon: '<path d="M12 2v20M4 6l16 12M20 6 4 18M9 3l3 3 3-3M9 21l3-3 3 3"/>',
  mouvement: '<circle cx="13" cy="4" r="2"/><path d="m9 20 3-6 3 2v5M8 12l2-4h4l3 4M6 9l4-1"/>',
  porte: '<path d="M6 21V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v17M4 21h16M14 12h.01"/>',
  robinet: '<path d="M4 9h9a3 3 0 0 1 3 3v2M8 9V6M5 6h6M16 18h.01M16 21h.01"/>',
  graphique: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  engrenage: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  epingle: '<path d="M9 4h6l-1 5 3 3H7l3-3-1-5zM12 12v8"/>',
};

/** SVG d'une icône (« ampoule », « corbeille »…), à insérer en HTML. */
export function icone(nom: string): string {
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${TRACES[nom] || TRACES.engrenage}</svg>`;
}
