/**
 * J.A.R.V.I.S — Notifications : les cartes contextuelles arrivent en pièces éclatées dans six zones libres autour du cylindre
 * (hud/pieces_alertes.ts), avec une forme et une couleur par priorité.
 */
import { afficherNotification, type Priorite } from "./hud/pieces_alertes";

export interface CardOptions {
  id?: string;
  title: string;
  type?: 'info' | 'system' | 'media' | 'alert' | 'search';
  content: string;
  duration?: number; // ms, selon la priorité par défaut
  icon?: string;
  priorite?: Priorite;
}

class CardManager {
  public showCard(options: CardOptions) {
    const priorite: Priorite = options.priorite ?? (options.type === 'alert' ? 'critique' : 'info');
    afficherNotification({ id: options.id, titre: options.title, texte: options.content, priorite, duree: options.duration, icone: options.icon });
  }
}

export const cardManager = new CardManager();
