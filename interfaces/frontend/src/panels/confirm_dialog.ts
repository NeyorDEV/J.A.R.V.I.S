// Confirmation avant action destructrice (désinstallation, suppression...) : affichée en pièces éclatées autour du cylindre
// (hud/pieces_alertes.ts). La réponse se donne en maintenant l'hexagone 1 s, ou à la voix (« oui » / « non », interceptée par le backend).
import { afficherConfirmation, confirmationResolue, type HistoriqueConfirmation, type LigneConfirmation } from "../hud/pieces_alertes";

export function showConfirmDialog(id: string, message: string, lignes?: LigneConfirmation[], duree?: number, historique?: HistoriqueConfirmation | null) {
  afficherConfirmation(id, message, lignes, duree, historique);
}

// Confirmation résolue ailleurs (réponse vocale, autre fenêtre, délai écoulé) : les pièces se referment.
export function closeConfirmDialog(id: string, confirme?: boolean | null) {
  confirmationResolue(id, confirme);
}

export function initConfirmDialog(): void {
  // Rien à brancher : les boutons vivent dans les pièces, créées à la demande.
}
