/**
 * J.A.R.V.I.S — Horloge « lignes » (canvas 2D) : l'heure en grand entre deux lignes fines à repères ;
 * le curseur de la ligne de gauche avance avec les secondes, la date est dessous. Même teinte que l'orbe.
 */

import { TEINTES } from "./orb_cylindre";

const JOURS = ["DIMANCHE", "LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI"];
const MOIS = ["JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"];
const LARGEUR = 440, HAUTEUR = 84;
const p2 = (n: number): string => String(n).padStart(2, "0");
const A = (c: string, a: number): string => `rgba(${c},${a})`;

export function initHoloClock(): void {
  const container = document.getElementById("holo-clock-canvas-wrap");
  if (!container) return;
  container.innerHTML = "";

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const canvas = document.createElement("canvas");
  canvas.id = "holo-clock-canvas";
  canvas.width = LARGEUR * dpr; canvas.height = HAUTEUR * dpr;
  canvas.style.width = `${LARGEUR}px`; canvas.style.height = `${HAUTEUR}px`;
  container.appendChild(canvas);
  const g = canvas.getContext("2d") as CanvasRenderingContext2D;
  const ls = (px: number): void => { (g as unknown as { letterSpacing: string }).letterSpacing = `${px}px`; };

  function dessiner(): void {
    if (document.hidden) return;
    const d = new Date(), s = d.getSeconds() + d.getMilliseconds() / 1000;
    g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, LARGEUR, HAUTEUR);
    ls(9); g.font = "400 36px Orbitron,Consolas,monospace"; g.fillStyle = "#eaf8ff"; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(`${p2(d.getHours())}${Math.floor(s * 2) % 2 === 0 ? ":" : " "}${p2(d.getMinutes())}`, LARGEUR / 2 + 4, 34); ls(0);
    ([[24, 132, 1], [308, 416, -1]] as [number, number, number][]).forEach(([x0, x1, dir]) => {
      const bout = dir > 0 ? x1 : x0, debut = dir > 0 ? x0 : x1;
      g.strokeStyle = A("0,229,255", 0.5); g.lineWidth = 0.6; g.beginPath(); g.moveTo(x0, 34); g.lineTo(x1, 34); g.stroke();
      g.strokeStyle = A("150,230,255", 0.9); g.lineWidth = 1; g.beginPath(); g.moveTo(bout, 28); g.lineTo(bout, 40); g.stroke();
      g.fillStyle = A("0,229,255", 0.9); g.fillRect(debut - (dir > 0 ? 0 : 2), 32, 2, 4);
      for (let k = 1; k <= 3; k++) g.fillRect(debut + dir * (k * 8) - (dir > 0 ? 0 : 1), 33, 1, 2);
    });
    const px = 24 + (s / 60) * 108;
    g.shadowColor = "#00e5ff"; g.shadowBlur = 8; g.fillStyle = "#fff"; g.fillRect(px - 0.7, 30, 1.4, 8); g.shadowBlur = 0;
    ls(2); g.font = "400 9px Orbitron,Consolas,monospace"; g.fillStyle = A("0,229,255", 0.95); g.textAlign = "left"; g.fillText(p2(d.getSeconds()), 372, 51); ls(0);
    ls(3); g.font = "400 7.5px Orbitron,Consolas,monospace"; g.fillStyle = A("130,215,255", 0.85); g.textAlign = "center";
    g.fillText(`${JOURS[d.getDay()]} ${d.getDate()} ${MOIS[d.getMonth()]}`, LARGEUR / 2 + 1.5, 72); ls(0);
    // Même teinte que l'orbe (style choisi dans les Paramètres)
    const teinte = TEINTES[localStorage.getItem("jarvis-orb-style") || "cyan"] ?? 0;
    const filtre = teinte ? `hue-rotate(${teinte}deg)` : "";
    if (canvas.style.filter !== filtre) canvas.style.filter = filtre;
  }

  dessiner();
  setInterval(dessiner, 50);
}
