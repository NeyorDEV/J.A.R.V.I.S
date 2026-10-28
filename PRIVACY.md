# Privacy policy

J.A.R.V.I.S is a free, open-source voice assistant that runs on your own PC. **The project maintainers operate no server, run no analytics and receive no data from your installation.** There is no account, no telemetry and no tracking. (The vector memory library, ChromaDB, is configured with its anonymous telemetry turned off.)

Everything JARVIS stores stays in its installation folder on your PC: settings (`jarvis_config.json`), API keys (`.env`), memory, conversations, alarms, lists, voiceprints and the encrypted vault (`data/`, `backend/core/voiceprints/`). Uninstalling the program does not delete these files.

## Data sent to third-party services

JARVIS only contacts a service when the matching feature is used. You choose which AI providers are active by entering your own API keys, and you can switch each provider off in **Settings › API keys**.

| Purpose | Service | What is sent |
|---|---|---|
| Answering questions | Google Gemini, Groq, Mistral, Anthropic (Claude), xAI (Grok) | Your request, the recent conversation and the assistant's instructions, with your own API key |
| Speech recognition | Groq (Whisper); Google speech recognition as a fallback | Short audio clips of every stretch of speech detected by the microphone (the wake word is looked for in the transcription) |
| Speech synthesis | Microsoft Edge text-to-speech (`edge-tts`) | The text JARVIS is about to say |
| Web and image search | SerpAPI, DuckDuckGo | Your search query |
| Image generation | Pollinations | The image description |
| Weather and places | Open-Meteo, wttr.in, OpenStreetMap Nominatim | Approximate coordinates or place names |
| Network radar | ip-api.com, ipify | IP addresses of your active connections (for a world map); your public IP |
| Music and video | Deezer API, YouTube API | Search terms |
| Smart home | Your own Home Assistant server | Commands you give |
| Page summary (browser extension) | Google Gemini | The text of the current page, only when you ask JARVIS to summarize it; the extension never reads pages on its own, and sites you list as forbidden in its options are never read |
| Discord messages | Discord (webhook or bot API) | The message you asked JARVIS to send and the target channel, only after you confirm; webhook addresses are stored locally and never shown in clear in the interface |
| Update check | GitHub (public API, no account or key) | A request for the latest release of this project, about 3 seconds after start and when you click *Check for updates*. Turn the automatic check off in Settings (*Check at launch*). Nothing is downloaded or installed without you |
| First-run downloads | GitHub, Hugging Face, python.org, PyPI, Microsoft | Standard download requests (voice-detection and speaker models, Python, dependencies, WebView2) |

These services have their own privacy policies. **To keep everything on your PC**, switch off every cloud provider and use the offline mode with [Ollama](https://ollama.com): your questions to the AI then stay local. Speech transcription, speech synthesis, search, weather and the network radar still use the internet when they are used.

## Voice

The microphone is read continuously. A voice-activity detector running on your PC cuts the audio into speech segments; **each speech segment is sent for transcription** (Groq Whisper, or the Google fallback) because JARVIS looks for the wake word "Jarvis" in the transcribed text. Silence and noise are not sent. Nothing is recorded to disk apart from the voiceprint samples you explicitly enroll. Without the wake word, JARVIS ignores what it heard once the transcription is done. You can mute the microphone at any time from the interface. Speech transcription currently needs an internet connection: there is no fully offline voice mode yet.

Voiceprints (optional) are computed and stored locally on your PC.

## Contact

Questions or requests: open an issue at https://github.com/NeyorDEV/J.A.R.V.I.S/issues.
