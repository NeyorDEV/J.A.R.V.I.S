// Briques graphiques du style « fin » (SVG en chaînes) : anneaux, graduations, axes, courbes. Voir css/17_fin.css.
// Toutes les couleurs sont passées en paramètre ; rien ici ne lit de donnée.
export const AX = 'fill="none" stroke="rgba(127,220,255,.14)" stroke-width=".6"';
export const AX2 = 'fill="none" stroke="rgba(127,220,255,.45)" stroke-width=".7"';
export const COUL = { cyan: "#2fd8ff", vert: "#4dff9b", jaune: "#ffd23a", orange: "#ff8a3a", rouge: "#ff5a3a", gris: "#7a86b8", violet: "#b79bff" };

export const bornes = (v: number, a: number, b: number): number => Math.min(b, Math.max(a, v));

/** Anneau découpé en parts (chaque part : fraction 0..1 et couleur), sur un fond d'anneau pâle. */
export function donut(cx: number, cy: number, r: number, parts: { f: number; c: string }[], sw = 5): string {
  const C = 2 * Math.PI * r;
  let off = 0, s = "";
  for (const p of parts) {
    const L = C * bornes(p.f, 0, 1);
    s += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${p.c}" stroke-width="${sw}" stroke-dasharray="${Math.max(0, L - 1.2).toFixed(2)} ${C.toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})" style="filter:drop-shadow(0 0 2px ${p.c})"/>`;
    off += L;
  }
  return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="rgba(127,220,255,.14)" stroke-width="${sw}"/>${s}`;
}

/** Graduations d'un cadran (une grande tous les 5). */
export function ticks(cx: number, cy: number, r: number, n: number): string {
  let s = "";
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2, l = i % 5 ? 2.5 : 5;
    s += `<line x1="${(cx + Math.sin(a) * r).toFixed(1)}" y1="${(cy - Math.cos(a) * r).toFixed(1)}" x2="${(cx + Math.sin(a) * (r + l)).toFixed(1)}" y2="${(cy - Math.cos(a) * (r + l)).toFixed(1)}" stroke="rgba(127,220,255,.5)" stroke-width=".6"/>`;
  }
  return s;
}

/** Anneau de jauge avec graduations et valeur au centre (`texte`), `f` de 0 à 1. */
export function jauge(taille: number, f: number, couleur: string, texte: string, legende = ""): string {
  const c = taille / 2, r = c - 11, C = 2 * Math.PI * r;
  return `<svg width="${taille}" height="${taille}" viewBox="0 0 ${taille} ${taille}">${ticks(c, c, r + 4, 48)}<circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="rgba(127,220,255,.14)" stroke-width="4"/>
    <circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${couleur}" stroke-width="4" stroke-dasharray="${(C * bornes(f, 0, 1)).toFixed(1)} ${C.toFixed(1)}" transform="rotate(-90 ${c} ${c})" style="filter:drop-shadow(0 0 3px ${couleur})"/>
    <text x="${c}" y="${c + 5}" text-anchor="middle" font-size="${Math.round(taille / 5)}" font-weight="300" fill="#fff">${texte}</text>${legende ? `<text x="${c}" y="${c + 16}" text-anchor="middle" font-size="6" fill="#7fb8dc">${legende}</text>` : ""}</svg>`;
}

/** Chemin d'une courbe (valeurs 0..max) dans une boîte w×h ; `aire` : ferme vers le bas pour le remplissage. */
export function courbe(v: number[], w: number, h: number, max: number, aire = false): string {
  if (!v.length) return "";
  const pas = v.length > 1 ? w / (v.length - 1) : 0;
  const d = v.map((y, i) => `${i ? "L" : "M"}${(i * pas).toFixed(1)},${(h - (bornes(y, 0, max) / max) * h).toFixed(1)}`).join(" ");
  return aire ? `${d} L${((v.length - 1) * pas).toFixed(1)},${h} L0,${h}Z` : d;
}
