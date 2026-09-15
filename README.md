# J.A.R.V.I.S

Assistant vocal : reconnaissance vocale en continu, biométrie de la voix, interface HUD 3D (Three.js), domotique, contrôle du PC, génération de contenu (images, documents) et bien plus — le tout piloté à la voix, en français.

Backend Python (WebSocket) + Frontend TypeScript/Three.js (Vite).

## Fonctionnalités

**Voix & IA**
- Écoute continue avec détection de mot de réveil ("Jarvis") — locale (openWakeWord) ou par transcription
- Transcription vocale via Groq Whisper (fallback Google STT)
- Réponses génératives en streaming (Gemini en principal, bascule automatique sur Groq / Claude / Grok / Ollama local selon disponibilité)
- Synthèse vocale (edge-tts) avec file d'attente et interruption ("stop", "silence")
- **Reconnaissance biométrique du locuteur** : identifie qui parle par empreinte vocale (CAM++ / sherpa-onnx) et adapte les permissions (invité vs utilisateur authentifié)
- Mémoire à deux niveaux : faits clé-valeur persistants + mémoire vectorielle (ChromaDB) des conversations passées

**Interface (HUD)**
- Orbe 3D animé (idle / écoute / réflexion / parole)
- Widgets calendrier, météo, musique, affichables à la voix
- Mode réalité augmentée (MediaPipe) avec glisser-déposer gestuel
- Globe 3D + carte pour la navigation géographique

**Contrôle & domotique**
- Home Assistant (lumières, prises, température, humidité, alarmes, batteries...)
- Lancement/fermeture d'applications, gestion de fichiers et dossiers
- Contrôle média : Spotify, Deezer, TV (Chromecast/ADB), volume système
- Coffre-fort chiffré (AES/Fernet + PBKDF2) pour fichiers confidentiels, déverrouillable à la voix

**Génération de contenu**
- Génération d'images (Pollinations)
- Génération de documents Word / PowerPoint / Excel / PDF à la demande, fusion de PDF
- Agent de navigation web autonome
- Essaim d'agents IA pour générer des sites web complets

**Autres**
- Alarmes et minuteurs
- Listes de courses / tâches
- Recettes de cuisine adaptées au nombre de convives
- Système de "compétences" : JARVIS peut apprendre de nouvelles capacités à la demande (code Python validé et sandboxé)

## Stack technique

| Côté | Techs |
|---|---|
| Backend | Python 3, WebSocket (`websockets`), asyncio |
| LLM | Gemini (principal), Groq, Claude (Anthropic), Grok (xAI), Ollama (local, 100% offline) |
| Voix | Silero VAD, openWakeWord, Groq Whisper, edge-tts, sherpa-onnx (biométrie) |
| Frontend | TypeScript, Three.js, Vite |
| Domotique | Home Assistant (REST API) |
| Stockage | ChromaDB (mémoire vectorielle), fichiers JSON (config/mémoire/alarmes) |

## Prérequis

- Python 3.10+ avec un environnement virtuel (`venv/`)
- Node.js 18+ (pour le frontend)
- [Ollama](https://ollama.com) installé si le mode local hors-ligne est souhaité
- Clés API : Gemini (obligatoire), Groq (recommandé pour STT/TTS), Anthropic/xAI (optionnelles)

## Installation

```bash
# Backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Frontend
cd interfaces/frontend
npm install
```

Créer un fichier `.env` à la racine avec au minimum :

```env
GEMINI_API_KEY=...
GROQ_API_KEY=...
# Optionnels
ANTHROPIC_API_KEY=...
XAI_API_KEY=...
YOUTUBE_API_KEY=...
SERPAPI_API_KEY=...
```

## Lancer le projet

```bash
# Backend (depuis la racine)
python main.py

# Frontend (dans interfaces/frontend)
npm run dev
```

Le backend écoute sur `ws://localhost:8765`. Dites simplement **"Jarvis"** suivi de votre commande pour l'activer.

## Structure du projet

```
main.py             — Orchestrateur principal (WebSocket, VAD, STT, plugins, LLM)
backend/
  core/              — Client LLM, config, VAD, biométrie, wake word, prompt système
  module/            — Mémoire, fichiers, domotique, navigateur, images, coffre-fort...
  controller/        — Contrôle d'applications (Spotify, Deezer, TV, lanceur d'apps)
  plugins/           — Resolvers de commandes vocales (un fichier par domaine)
  sandbox/           — Sorties générées (sites web créés par le dev-swarm)
interfaces/
  frontend/          — HUD web (Three.js, TypeScript, Vite)
  mobile/            — Interface mobile compagnon
  chrome_extension/  — Extension navigateur
scratch/             — Scripts de debug/exploration (non versionnés)
```

## Sécurité & confidentialité

- Coffre-fort chiffré AES-256 pour les fichiers sensibles (mot de passe jamais stocké en clair)
- Reconnaissance vocale du locuteur pour restreindre les actions sensibles en mode invité
- Origin check WebSocket, sandboxing des compétences générées par l'IA

---

Projet personnel, développé et maintenu par [@NeyorDEV](https://github.com/NeyorDEV).
