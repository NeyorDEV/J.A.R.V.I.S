<div align="center">
  <img src="interfaces/frontend/public/assets/favicon.png" alt="J.A.R.V.I.S" width="160" />

  # J.A.R.V.I.S

  *A personal voice AI assistant, running on your own machine.*

  [![CI](https://github.com/NeyorDEV/J.A.R.V.I.S/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/NeyorDEV/J.A.R.V.I.S/actions/workflows/ci.yml)
  [![Python](https://img.shields.io/badge/python-3.12%2B-blue)](#prerequisites)
  [![Node](https://img.shields.io/badge/node-18%2B-339933?logo=node.js&logoColor=white)](#prerequisites)
  [![Frontend](https://img.shields.io/badge/frontend-Three.js%20%2B%20Vite-black)](interfaces/frontend)
  [![Docs](https://img.shields.io/badge/docs-files%20guide-orange)](docs/JARVIS_FILES_GUIDE.md)
  [![GitHub](https://img.shields.io/badge/github-NeyorDEV%2FJ.A.R.V.I.S-181717?logo=github&logoColor=white)](https://github.com/NeyorDEV/J.A.R.V.I.S)
</div>

---

Voice assistant: always-on speech recognition, voice biometrics, 3D HUD interface (Three.js), home automation, PC control, content generation (images, documents) and much more — all driven by voice, **in French or in English** (switchable on the fly).

Python backend (WebSocket) + TypeScript/Three.js frontend (Vite).

## Features

**Voice & AI**
- Always-on listening with wake word detection ("Jarvis") — transcription-based
- Speech-to-text in three tiers: local Whisper on the GPU (faster-whisper), then Groq Whisper, then Google STT; filter for the phrases Whisper invents on silence
- Streaming generative answers (Gemini as the main model, automatic failover to Groq / Claude / Mistral / Grok / local Ollama depending on availability)
- Text-to-speech (edge-tts, French and British English voices; ElevenLabs optional) with a speech queue and interruption ("stop", "silence", "shut up")
- **French and English**: say "passe en anglais" / "switch to English" (or use Settings, or the first-launch assistant). Recognition, voice, answers, HUD and console follow; English commands are understood by mapping them to the French command engine. A notice offers a **Restart now** button because the console and logs only follow after a restart. See [docs](docs/JARVIS_Commandes.txt) for the commands
- Iron Man-style JARVIS personality: composed, loyal, dry humour — answers are generated on the fly, never canned phrases
- **Speaker biometrics**: identifies who is speaking from their voiceprint (CAM++ / sherpa-onnx) and adapts permissions (guest vs authenticated user)
- Two-level memory: persistent key-value facts + vector memory (ChromaDB) of past conversations

**Interface (HUD)**
- Animated 3D orb (idle / listening / thinking / speaking)
- Calendar, weather and music widgets, shown on voice command; exploded panels around a holographic cylinder, with a command palette (Ctrl+K) of 272 example phrases
- Augmented reality mode (MediaPipe) with gesture drag-and-drop
- 3D globe + map for geographic navigation
- **God's Eye View** (optional, installed on demand): live 3D globe with flights, ships, satellites, earthquakes, public cameras and French open-data layers (fuel prices, charging stations, speed cameras, floods, rain radar, **car parks with live free spaces**), including voice search ("find me an open car park in Saint-Étienne"). See [docs/VUE_DE_DIEU.md](docs/VUE_DE_DIEU.md)

**Control & home automation**
- Home Assistant (lights, plugs, temperature, humidity, alarms, batteries...)
- Launching/closing applications, file and folder management
- Media control: Spotify, Deezer, TV (Chromecast/ADB), system volume
- Encrypted vault (AES/Fernet + PBKDF2) for confidential files, unlockable by voice
- Mandatory confirmation (voice or HUD) before any destructive action (uninstalling, deleting a file, emptying the vault)

**Content generation**
- Image generation (FLUX.1 on Cloudflare Workers AI, Pollinations as a fallback)
- On-demand Word / PowerPoint / Excel / PDF documents, PDF merging
- Autonomous web browsing agent
- Swarm of AI agents that builds complete websites

**Other**
- **Morning briefing**: "my day" / "ma journée" gives the date, weather, agenda, tasks, alarms and unread mail count in one sentence
- Alarms and timers (English durations too: "five minutes", "7 pm"); routines that replay a command every day or every few hours
- Voice commands for Discord messages (confirmed each time), Steam games, browser tabs (Chrome extension), music recognition ("what song is this")
- Usage meters: speech-recognition quota and Gemini spending with a daily cap
- Shopping / to-do lists
- Cooking recipes scaled to the number of guests
- "Skills" system: JARVIS can learn new abilities on demand (validated, sandboxed Python code)

## Tech stack

| Area | Technologies |
|---|---|
| Backend | Python 3, WebSocket (`websockets`), asyncio |
| LLM | Gemini (main), Groq, Claude (Anthropic), Mistral, Grok (xAI), Ollama (local, 100% offline) |
| Voice | Silero VAD, faster-whisper (local), Groq Whisper, edge-tts, sherpa-onnx (biometrics) |
| Frontend | TypeScript, Three.js, Vite (HUD with a built-in French/English translator) |
| Home automation | Home Assistant (REST API / MCP) |
| Storage | ChromaDB (vector memory), JSON files (config/memory/alarms) |

## Prerequisites

- Python 3.12+ with a virtual environment (`venv/`)
- Node.js 18+ (for the frontend)
- [Ollama](https://ollama.com) installed if you want the offline local mode
- API keys: Gemini (required), Groq (recommended for STT/TTS), Anthropic/Mistral/xAI (optional)

## Installation

### Windows installer (recommended)

Download `JARVIS-Setup-<version>.exe` from the [Releases](https://github.com/NeyorDEV/J.A.R.V.I.S/releases) page and run it. It installs for the current user (no administrator rights), installs Python 3.12 if it is missing, creates the virtual environment and installs the dependencies (a few minutes, internet connection required). JARVIS then starts from its shortcut with no console window, and a first-launch assistant helps you set up your name, an AI key (Gemini is free), the microphone and your voiceprint.

The installer is not code-signed yet: Windows SmartScreen may warn on first run. Choose *More info*, then *Run anyway*.

### From source

Double-click `install.bat` (at the project root): it creates the virtual environment, installs the Python and Node dependencies, and generates the `.env` file.

Then fill in the generated `.env` with at least:

```env
GEMINI_API_KEY=...
GROQ_API_KEY=...
# Optional
ANTHROPIC_API_KEY=...
MISTRAL_API_KEY=...
XAI_API_KEY=...
YOUTUBE_API_KEY=...
SERPAPI_API_KEY=...
GITHUB_MCP_TOKEN=...
# Android TV (ADB over the network) and Wake-on-LAN; TV commands are disabled without TV_IP
TV_IP=192.168.x.x
TV_MAC=aa-bb-cc-dd-ee-ff
# Optional: HomePod addresses (otherwise discovered on the network)
HOMEPOD_IP=
```

## Running the project

Double-click `start.bat` (at the project root): it starts the backend and the frontend. With the installer, use the shortcut instead (no console window). Language changes and "Restart now" relaunch JARVIS from the HUD in both cases.

The backend listens on `ws://localhost:8765`. Just say **"Jarvis"** followed by your command to activate it.

## Project structure

```
main.py             — Entry point: startup order, demarrer_ia() and main()
assets/              — Application icon
backend/
  core/              — Shared state (shared.py), WebSocket server, command processing,
                       LLM (+ engine registry), voice listening, VAD, biometrics, wake word, system prompt
  module/            — Memory, files, home automation, browser, images, vault...
  controller/        — Application control (Spotify, Deezer, TV, app launcher)
  plugins/           — Voice command resolvers (one file per domain)
                       (language switch, morning briefing, God's Eye View, Discord, Steam...)
  sandbox/           — Generated output (websites built by the dev swarm)
interfaces/
  frontend/          — Web HUD (Three.js, TypeScript, Vite)
  chrome_extension/  — Browser extension
tools/               — Installer (Inno Setup), git hook, translation tools (tools/i18n_*.py)
tests/               — pytest suite (`venv\Scripts\python.exe -m pytest tests`)
docs/                — Guides (French): files guide, voice commands, features, God's Eye View
scratch/             — Debug/exploration scripts (not versioned)
```

Developer checks: `venv\Scripts\python.exe -m pytest tests`, `venv\Scripts\ruff.exe check .`, and in `interfaces/frontend`: `npx tsc --noEmit -p .` and `npx eslint src`. English UI texts live in `interfaces/frontend/src/i18n/en.json`, generated by `tools/i18n_extraire.py` then `tools/i18n_traduire.py` (only new texts are translated).

## Security & privacy

- AES-256 encrypted vault for sensitive files (the password is never stored in plain text)
- Speaker voice recognition to restrict sensitive actions in guest mode
- Voice/HUD confirmation required before any destructive action (uninstall, deletion, vault)
- WebSocket origin check, sandboxing of AI-generated skills

---

<div align="center">

[Files guide](docs/JARVIS_FILES_GUIDE.md) · [Detailed features](docs/jarvis_fonctionnalites.txt) · [Voice commands](docs/JARVIS_Commandes.txt) · [Changelog](CHANGELOG.md) *(documentation in French)*

Personal project, developed and maintained by [@NeyorDEV](https://github.com/NeyorDEV).

</div>

## License

Copyright (C) 2026 NeyorDEV

J.A.R.V.I.S is free software, released under the [GNU General Public License v3.0 or later](LICENSE) (GPL-3.0-or-later).

This program comes with ABSOLUTELY NO WARRANTY; see the license for details.
Third-party libraries keep their own licenses (notably `python-chess`, GPL-3.0+).
