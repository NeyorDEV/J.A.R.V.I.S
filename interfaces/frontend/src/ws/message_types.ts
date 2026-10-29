// Forme des messages reçus du backend (extrait du gestionnaire de main.ts).
export type JarvisMessage = {
  state?: string;
  action?: string;
  muted?: boolean;
  volume?: number;
  id?: string;
  duration?: number;
  text?: string;
  type?: string;
  version?: string;
  url?: string;
  cpu?: number;
  ram?: number;
  prompt?: string;
  title?: string;
  icon?: string;
  weather?: any;
  weather_type?: string;
  status_text?: string;
  data?: Record<string, any>;
  categorie?: string;   // module_trouve : catégorie du cylindre
  sous?: string | null; // module_trouve : sous-catégorie
  vue?: string;         // weather_view : vue demandée
  forecast?: any;
  sous_titre?: string;  // module_ecran : sous-titre, lignes et pied (voir panels/ecran_module.ts)
  lignes?: any[];
  pied?: string | null;       // weather_forecast / weather_view : prévisions (voir weather_vues.ts)
};
