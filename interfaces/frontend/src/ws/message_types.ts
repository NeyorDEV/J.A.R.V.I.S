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
  pcm_base64?: string;
  sample_rate?: number;
};
