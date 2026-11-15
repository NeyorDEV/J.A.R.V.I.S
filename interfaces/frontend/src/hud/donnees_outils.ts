// Dernières données reçues par les outils éclatés (aide, minuteurs, maison, réglages) : les pièces de pieces_outils.ts les lisent ici.
// Rien n'est inventé : tant que le backend n'a rien envoyé, les pièces l'écrivent.
export interface AlarmeHud { label: string; heure: string; restant: number }
export interface ProfilVocal { nom: string; echantillons: number }

export const donneesOutils = {
  alarmes: null as AlarmeHud[] | null,       // message « alarmes_liste » (backend/module/alarm_manager.py)
  alarmesRecues: 0,                          // performance.now() de la dernière réception : les « restant » avancent depuis
  reglages: { voix: "", motEveil: "", profils: null as ProfilVocal[] | null },   // message « settings_data »
};

/** Prévient les pièces ouvertes qu'une donnée a changé (pieces_outils.ts écoute cet événement). */
export const signalerOutils = (quoi: "alarmes" | "reglages" | "ha" | "minuteurs"): void => { window.dispatchEvent(new CustomEvent("outils-maj", { detail: quoi })); };
