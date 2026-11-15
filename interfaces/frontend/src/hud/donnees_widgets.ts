// Dernières données reçues par les widgets (météo, agenda, musique) : les pièces éclatées (pieces_widgets.ts) les lisent ici
// au moment de se dessiner et à chaque rafraîchissement, sans dépendre du DOM des anciennes boîtes.
export interface MeteoActuelle { city: string; temp: number; desc: string; apparent: number; humidity: number; wind: number; max: number; min: number }
export interface LigneAgenda { t: string; d?: string | null; jour?: string | null; v?: string | null; etat?: string | null }
export interface EtatMusique {
  hors: boolean; joue: boolean; titre: string; artiste: string; pochette: string;
  pos: number; dur: number; t0: number; volume: number | null;
}

export const donnees = {
  meteo: {} as Partial<Record<"local" | "monistrol", MeteoActuelle>>,
  agenda: null as LigneAgenda[] | null,
  agendaMessage: null as string | null,   // « Google Agenda n'est pas connecté » : dit à la place des rendez-vous quand il n'y en a pas à montrer
  musique: { hors: true, joue: false, titre: "DEEZER", artiste: "", pochette: "", pos: 0, dur: 0, t0: 0, volume: null } as EtatMusique,
};

/** Position de lecture courante, qui avance en continu entre deux mises à jour du backend. */
export const positionMusique = (): number => {
  const m = donnees.musique;
  return Math.min(m.dur, m.pos + (m.joue ? (performance.now() - m.t0) / 1000 : 0));
};
