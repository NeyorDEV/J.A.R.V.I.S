<div align="center">
  <img src="interfaces/frontend/public/assets/favicon.png" alt="J.A.R.V.I.S" width="160" />

  # J.A.R.V.I.S

  *A personal voice AI assistant, running on your own machine.*

  [![Python](https://img.shields.io/badge/python-3.12%2B-blue)](#prerequisites)
  [![Node](https://img.shields.io/badge/node-18%2B-339933?logo=node.js&logoColor=white)](#prerequisites)
  [![Frontend](https://img.shields.io/badge/frontend-Three.js%20%2B%20Vite-black)](interfaces/frontend)
  [![Docs](https://img.shields.io/badge/docs-files%20guide-orange)](docs/JARVIS_FILES_GUIDE.md)
  [![GitHub](https://img.shields.io/badge/github-NeyorDEV%2FJ.A.R.V.I.S-181717?logo=github&logoColor=white)](https://github.com/NeyorDEV/J.A.R.V.I.S)
</div>

---

Voice assistant: always-on speech recognition, voice biometrics, 3D HUD interface (Three.js), home automation, PC control, content generation (images, documents) and much more — all driven by voice, in French.

Python backend (WebSocket) + TypeScript/Three.js frontend (Vite).

## Features

**Voice & AI**
- Always-on listening with wake word detection ("Jarvis") — transcription-based
- Speech-to-text via Groq Whisper (Google STT fallback)
- Streaming generative answers (Gemini as the main model, automatic failover to Groq / Claude / Mistral / Grok / local Ollama depending on availability)
- Text-to-speech (edge-tts) with a speech queue and interruption ("stop", "silence")
- Iron Man-style JARVIS personality: composed, loyal, dry humour — answers are generated on the fly, never canned phrases
- **Speaker biometrics**: identifies who is speaking from their voiceprint (CAM++ / sherpa-onnx) and adapts permissions (guest vs authenticated user)
- Two-level memory: persistent key-value facts + vector memory (ChromaDB) of past conversations

**Interface (HUD)**
- Animated 3D orb (idle / listening / thinking / speaking)
- Calendar, weather and music widgets, shown on voice command
- Augmented reality mode (MediaPipe) with gesture drag-and-drop
- 3D globe + map for geographic navigation

**Control & home automation**
- Home Assistant (lights, plugs, temperature, humidity, alarms, batteries...)
- Launching/closing applications, file and folder management
- Media control: Spotify, Deezer, TV (Chromecast/ADB), system volume
- Encrypted vault (AES/Fernet + PBKDF2) for confidential files, unlockable by voice
- Mandatory confirmation (voice or HUD) before any destructive action (uninstalling, deleting a file, emptying the vault)

**Content generation**
- Image generation (Pollinations)
- On-demand Word / PowerPoint / Excel / PDF documents, PDF merging
- Autonomous web browsing agent
- Swarm of AI agents that builds complete websites

**Other**
- Alarms and timers
- Shopping / to-do lists
- Cooking recipes scaled to the number of guests
- "Skills" system: JARVIS can learn new abilities on demand (validated, sandboxed Python code)

## Tech stack

| Area | Technologies |
|---|---|
| Backend | Python 3, WebSocket (`websockets`), asyncio |
| LLM | Gemini (main), Groq, Claude (Anthropic), Mistral, Grok (xAI), Ollama (local, 100% offline) |
| Voice | Silero VAD, Groq Whisper, edge-tts, sherpa-onnx (biometrics) |
| Frontend | TypeScript, Three.js, Vite |
| Home automation | Home Assistant (REST API / MCP) |
| Storage | ChromaDB (vector memory), JSON files (config/memory/alarms) |

## Prerequisites

- Python 3.12+ with a virtual environment (`venv/`)
- Node.js 18+ (for the frontend)
- [Ollama](https://ollama.com) installed if you want the offline local mode
- API keys: Gemini (required), Groq (recommended for STT/TTS), Anthropic/Mistral/xAI (optional)

## Installation

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
```

## Running the project

Double-click `start.bat` (at the project root): it starts the backend and the frontend.

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
  sandbox/           — Generated output (websites built by the dev swarm)
interfaces/
  frontend/          — Web HUD (Three.js, TypeScript, Vite)
  chrome_extension/  — Browser extension
scratch/             — Debug/exploration scripts (not versioned)
```

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
