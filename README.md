<div align="center">
  <img src="interfaces/frontend/public/assets/favicon.png" alt="J.A.R.V.I.S" width="160" />

  # J.A.R.V.I.S

  *Assistant IA vocal personnel, sur ta machine.*

  [![Python](https://img.shields.io/badge/python-3.12%2B-blue)](#prérequis)
  [![Node](https://img.shields.io/badge/node-18%2B-339933?logo=node.js&logoColor=white)](#prérequis)
  [![Frontend](https://img.shields.io/badge/frontend-Three.js%20%2B%20Vite-black)](interfaces/frontend)
  [![Docs](https://img.shields.io/badge/docs-guide%20des%20fichiers-orange)](docs/JARVIS_FILES_GUIDE.md)
  [![GitHub](https://img.shields.io/badge/github-NeyorDEV%2FJ.A.R.V.I.S-181717?logo=github&logoColor=white)](https://github.com/NeyorDEV/J.A.R.V.I.S)
</div>

---

Assistant vocal : reconnaissance vocale en continu, biométrie de la voix, interface HUD 3D (Three.js), domotique, contrôle du PC, génération de contenu (images, documents) et bien plus — le tout piloté à la voix, en français.

Backend Python (WebSocket) + Frontend TypeScript/Three.js (Vite).

## Fonctionnalités

**Voix & IA**
- Écoute continue avec détection de mot de réveil ("Jarvis") — locale (openWakeWord) ou par transcription
- Transcription vocale via Groq Whisper (fallback Google STT)
- Réponses génératives en streaming (Gemini en principal, bascule automatique sur Groq / Claude / Mistral / Grok / Ollama local selon disponibilité)
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
- Confirmation obligatoire (voix ou HUD) avant toute action destructrice (désinstallation, suppression de fichier, vidage du coffre-fort)

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
| LLM | Gemini (principal), Groq, Claude (Anthropic), Mistral, Grok (xAI), Ollama (local, 100% offline) |
| Voix | Silero VAD, openWakeWord, Groq Whisper, edge-tts, sherpa-onnx (biométrie) |
| Frontend | TypeScript, Three.js, Vite |
| Domotique | Home Assistant (REST API / MCP) |
| Stockage | ChromaDB (mémoire vectorielle), fichiers JSON (config/mémoire/alarmes) |

## Prérequis

- Python 3.12+ avec un environnement virtuel (`venv/`)
- Node.js 18+ (pour le frontend)
- [Ollama](https://ollama.com) installé si le mode local hors-ligne est souhaité
- Clés API : Gemini (obligatoire), Groq (recommandé pour STT/TTS), Anthropic/Mistral/xAI (optionnelles)

## Installation

Double-cliquer sur `install.bat` (à la racine) : il crée l'environnement virtuel, installe les dépendances Python et Node, et génère le fichier `.env`.

Compléter ensuite le `.env` généré avec au minimum :

```env
GEMINI_API_KEY=...
GROQ_API_KEY=...
# Optionnels
ANTHROPIC_API_KEY=...
MISTRAL_API_KEY=...
XAI_API_KEY=...
YOUTUBE_API_KEY=...
SERPAPI_API_KEY=...
GITHUB_MCP_TOKEN=...
```

## Lancer le projet

Double-cliquer sur `start.bat` (à la racine) : il lance le backend et le frontend.

Le backend écoute sur `ws://localhost:8765`. Dites simplement **"Jarvis"** suivi de votre commande pour l'activer.

## Structure du projet

```
main.py             — Point d'entrée : ordre de démarrage, start_ia() et main()
assets/              — Icône de l'application
backend/
  core/              — État partagé (shared.py), serveur WebSocket, traitement des commandes,
                       LLM (+ registre de moteurs), écoute vocale, VAD, biométrie, wake word, prompt système
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
- Confirmation vocale/HUD requise avant toute action destructrice (désinstallation, suppression, coffre-fort)
- Origin check WebSocket, sandboxing des compétences générées par l'IA

---

<div align="center">

[Guide des fichiers](docs/JARVIS_FILES_GUIDE.md) · [Fonctionnalités détaillées](docs/jarvis_fonctionnalites.txt) · [Commandes vocales](docs/JARVIS_Commandes.txt) · [Changelog](CHANGELOG.md)

Projet personnel, développé et maintenu par [@NeyorDEV](https://github.com/NeyorDEV).

</div>
