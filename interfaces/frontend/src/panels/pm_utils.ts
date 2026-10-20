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
  cadenas: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  cle: '<circle cx="8" cy="12" r="4"/><path d="M12 12h9M18 12v3"/>',
  telecharger: '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  document: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
  panier: '<path d="M3 4h2l2.4 11h10.2l2-8H6.2"/><circle cx="9" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/>',
  haut_parleur: '<path d="M4 10v4h4l5 4V6l-5 4zM16 9a4 4 0 0 1 0 6"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M4 18l5-5 4 4 3-3 4 4"/>',
  couvert: '<path d="M7 3v6a2 2 0 0 0 2 2v10M7 3v4M11 3v4M16 3c-2 2-2.5 5-2.5 8h2.5v10"/>',
  lecture: '<path d="M7 4l12 8-12 8z"/>',
  copier: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  rejouer: '<path d="M4 12a8 8 0 1 0 8-8M4 4v5h5"/>',
  discussion: '<path d="M4 5h16v11H9l-5 4z"/>',
  pouls: '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
  micro: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  clavier: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10"/>',
  puce: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"/>',
  utilisateur: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  palette: '<circle cx="12" cy="12" r="9"/><circle cx="8.5" cy="10" r="1"/><circle cx="12" cy="7.5" r="1"/><circle cx="15.5" cy="10" r="1"/>',
  applications: '<rect x="4" y="4" width="7" height="7"/><rect x="13" y="4" width="7" height="7"/><rect x="4" y="13" width="7" height="7"/><rect x="13" y="13" width="7" height="7"/>',
  musique: '<path d="M9 18V6l10-2v12"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="16" r="2"/>',
  oeil: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  oeil_barre: '<path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4M6.6 6.7A17 17 0 0 0 2 12s3.5 7 10 7a9.7 9.7 0 0 0 4-.9M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  main: '<path d="M8 12V5a1.5 1.5 0 0 1 3 0v6M11 11V3.5a1.5 1.5 0 0 1 3 0V11M14 11V5a1.5 1.5 0 0 1 3 0v8c0 4-2.5 7-6 7-2.5 0-4-1.3-5.4-3.4L3 13a1.5 1.5 0 0 1 2.5-1.6L8 14"/>',
  sablier: '<path d="M6 3h12M6 21h12M7 3c0 5 5 6 5 9s-5 4-5 9M17 3c0 5-5 6-5 9s5 4 5 9"/>',
  liste: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  souris: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 7v4"/>',
  globe_terre: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  crayon: '<path d="M4 20l1-4L16 5l3 3L8 19z"/><path d="M14 7l3 3"/>',
  avertissement: '<path d="M12 3 2 20h20L12 3zM12 10v5M12 17.5h.01"/>',
  ruche: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 8l4 2.3v4.4L12 17l-4-2.3v-4.4z"/>',
  position: '<path d="M12 21s7-6.2 7-11a7 7 0 0 0-14 0c0 4.8 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>',
  soleil_nuage: '<circle cx="9" cy="8" r="3"/><path d="M9 2v1.5M3 8h1.5M4.8 3.8l1 1M13.2 3.8l-1 1M7 19h9a3.5 3.5 0 0 0 0-7 5 5 0 0 0-9.6 1.5A2.8 2.8 0 0 0 7 19z"/>',
  nuage: '<path d="M7 19h10a4 4 0 0 0 .5-8 6 6 0 0 0-11.4 1.5A3.3 3.3 0 0 0 7 19z"/>',
  pluie: '<path d="M7 15h10a4 4 0 0 0 .5-8 6 6 0 0 0-11.4 1.5A3.3 3.3 0 0 0 7 15zM9 18l-1 3M13 18l-1 3M17 18l-1 3"/>',
  neige: '<path d="M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9M9 4l3 2 3-2M9 20l3-2 3 2"/>',
  orage: '<path d="M7 15h2M17 15a4 4 0 0 0 .5-8 6 6 0 0 0-11.4 1.5A3.3 3.3 0 0 0 7 15M13 11l-3 5h4l-3 5"/>',
  brouillard: '<path d="M4 9h16M3 13h18M6 17h12M8 5h8"/>',
  inconnu: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01"/>',
  epingle: '<path d="M9 4h6l-1 5 3 3H7l3-3-1-5zM12 12v8"/>',
};

/** SVG d'une icône (« ampoule », « corbeille »…), à insérer en HTML. */
export function icone(nom: string): string {
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${TRACES[nom] || TRACES.engrenage}</svg>`;
}
