# J.A.R.V.I.S — File and Architecture Guide (v11)

Inventory of the **J.A.R.V.I.S** project, folder by folder: what each file does. Designed to be read at the start of a new conversation (human or AI) to get your bearings. Development conventions are in [CLAUDE.md](../../CLAUDE.md), detailed history in [CHANGELOG.md](../../CHANGELOG.md).

Paths relative to the project root. Updated on 11/25/2026.

---

## Project Root

*   **[main.py](../../main.py)**: entry point (~300 lines). Orchestrates startup in a specific order (console, speech engine, audio models, modules, AI keys and clients) then runs `main()`: frontend, WebSocket server + voice listening (`demarrer_ia`), native window. Shared state is in `backend/core/shared.py`.
*   **[start.bat](../../start.bat)**: launches the backend in a console. **[install.bat](../../install.bat)**: creates the venv, installs Python and Node dependencies, generates `.env`, installs the git hook. The Windows installer launches JARVIS via `venv\Scripts\pythonw.exe main.py` (without a console).
*   **[requirements.txt](../../requirements.txt)** (UTF-16), **[pyproject.toml](../../pyproject.toml)** (ruff, pytest), **[skills-lock.json](../../skills-lock.json)**: dependencies and tool settings.
*   **[README.md](../../README.md)**, **[CHANGELOG.md](../../CHANGELOG.md)**, **[LICENSE](../../LICENSE)** (GPL-3.0 or later), **[PRIVACY.md](../../PRIVACY.md)**: overview, history, license, privacy.
*   **CLAUDE.md**: architecture guide and conventions for the AI (local, not tracked by git).
*   **`.env`**: API keys (`GEMINI_API_KEY`, `GROQ_API_KEY`…), editable from the HUD (keys are never sent back in cleartext over the WebSocket).
*   **`jarvis_config.json`**: user preferences (microphone, first name, voice, **language** `fr` / `en`, custom applications, console options…). Excluded from git.
*   **`jarvis_audit.log`**: JSONL log of sensitive actions (confirmations, restarts…), written by `core/audit_log.py`.

### `config/` and `data/`
*   **`config/`**: `credentials.json` (Google API), `token.pickle` (Google token, created on first authorization), `adb_key` / `adb_key.pub` (TV control).
*   **`data/`**: JARVIS local state: `jarvis_memoire.json` (key-value facts), `chroma_db/` (vector memory), `jarvis_conversations.json`, `jarvis_listes.json` (groceries, notes, tasks), `alarmes.json`, `routines.json`, `jarvis_synapses.json` (3D cortex), `usage_llm.json` and `usage_stt.json` (Gemini and speech recognition usage), `traductions_en.json` (cache of translations in English mode), `skills/` (scripted skills), `gods_eye_view/` (God's Eye app installed on demand), `jarvis_run.log` (timestamped console log, in French regardless of language).

### `docs/` (two-language documentation)
*   **[docs/README.md](../README.md)**: documentation index (French). **[docs/en/README.md](../en/README.md)**: same index in English.
*   **`docs/fr/`** (reference) and **`docs/en/`** (translation) contain the same documents: **[JARVIS_Commandes.txt](JARVIS_Commandes.txt)** (voice commands by category), **[jarvis_fonctionnalites.txt](jarvis_fonctionnalites.txt)** (concise feature inventory), **[VUE_DE_DIEU.md](VUE_DE_DIEU.md)** (installation, France layers, and God View commands), and this guide. After modifying the French version, running `tools/docs_traduire.py <fichier>` updates the English.
*   `docs/AUDIT_BUGS.md`: full audit (local, excluded from git, never pushed).

### `tools/` (development and installer tools)
*   **[git-hooks/pre-commit](../../tools/git-hooks/pre-commit)**: checks Python syntax and `tsc` before each commit (copied to `.git/hooks/` by `install.bat`).
*   **[installateur/](../../tools/installateur)**: `JARVIS.iss` (Inno Setup), `construire.bat`, `preparer.py`: Windows installer build.
*   **[_setup/](../../tools/_setup)**: `dependances.bat` (installation called by the installer), `rename_user.py`.
*   **Translation (English)**: [i18n_extraire.py](../../tools/i18n_extraire.py) (extracts French strings from the HUD), [i18n_traduire.py](../../tools/i18n_traduire.py) (translates them into `en.json`), [i18n_exemples.py](../../tools/i18n_exemples.py) (FR/EN example commands for command translation), [i18n_console.py](../../tools/i18n_console.py) (console messages).
*   `antivirus_scanner.py`, `consulter_memoire.py` / `memoire.bat`, `vider_cache.bat`, `tests/`, `sandbox/`: miscellaneous utilities.

### `tests/`
pytest suite (`venv\Scripts\python.exe -m pytest tests`, never `pytest` alone): see [tests/](../../tests). `conftest.py` forces French language and a temporary config for each test (the real `jarvis_config.json` is never read or written). Test benches and captures (unversioned): `scratch/outils_test/`.

---

## `backend/core/`: System Core

### Startup, state, networking
*   **[shared.py](../../backend/core/shared.py)**: shared state (history, voice session, AI clients, WebSocket clients…). Always `shared.NOM`.
*   **[config.py](../../backend/core/config.py)**: API keys, models, voice (`VOIX_ACTUELLE`), wake word. **[ai_clients.py](../../backend/core/ai_clients.py)**: key loading, Gemini / Grok / Groq / Claude / Mistral clients, hot reload, deferred `client_gemini`.
*   **[prechargement.py](../../backend/core/prechargement.py)**, **[chargement_plugins.py](../../backend/core/chargement_plugins.py)**, **[voice_init.py](../../backend/core/voice_init.py)**: preloading large libraries, background plugin imports, Silero VAD and biometrics initialization.
*   **[lancement.py](../../backend/core/lancement.py)**: service status, port freeing, frontend (Vite or `dist/`), pywebview or browser window, and **`redemarrer()`** (restarts JARVIS from the HUD: launcher in a new console, closes the `start.bat` console).
*   **[web_bridge.py](../../backend/core/web_bridge.py)**: sending messages to the HUD from any thread (states, contextual cards with optional button, DOM actions). **[webview_cache.py](../../backend/core/webview_cache.py)**: WebView2 cache.
*   **[ws_handler.py](../../backend/core/ws_handler.py)**: WebSocket server (origin checking, routing). Heavy branches: [ws_reglages.py](../../backend/core/ws_reglages.py) (settings, **language**, `traduire`), [ws_systeme.py](../../backend/core/ws_systeme.py) (safe, groceries, uninstallation, files, Winget), [ws_securite.py](../../backend/core/ws_securite.py) (firewall, cache, antivirus), [ws_etat_systeme.py](../../backend/core/ws_etat_systeme.py) (status and tests on demand), [ws_assistant.py](../../backend/core/ws_assistant.py) (first-run wizard).
*   **[extension_bridge.py](../../backend/core/extension_bridge.py)**: authenticated bridge with the browser extension. **[api_locale.py](../../backend/core/api_locale.py)**: OpenAI-compatible local API (other tools on the PC talk to JARVIS like a model). **[mises_a_jour.py](../../backend/core/mises_a_jour.py)**: compares installed version with latest GitHub release. **[alertes_service.py](../../backend/core/alertes_service.py)**: HUD error cards when a service goes down.

### Voice: listening, speech, language
*   **[audio_stream.py](../../backend/core/audio_stream.py)**: microphone stream (PyAudio, 48 kHz filtered then downsampled to 16 kHz). **[vad.py](../../backend/core/vad.py)**: Silero VAD (ONNX) and CAM++ voice biometrics (`SpeakerBiometrics`). **[locuteur.py](../../backend/core/locuteur.py)**: who is speaking for a command. **[interlocuteur.py](../../backend/core/interlocuteur.py)**: first name of the person speaking and creator's identity. **[nommer.py](../../backend/core/nommer.py)**: first name spoken in response when the speaker changes.
*   **[ecoute.py](../../backend/core/ecoute.py)** / **[ecoute_outils.py](../../backend/core/ecoute_outils.py)**: listening loop (VAD, wake word, biometrics, stop commands); transcription and voice enrollment. **[stt_local.py](../../backend/core/stt_local.py)**: local Whisper (faster-whisper, GPU), first tier before Groq then Google. **[hallucinations.py](../../backend/core/hallucinations.py)**: phrases Whisper invents over noise (French and English). **[usage_stt.py](../../backend/core/usage_stt.py)**: speech recognition quota. **[voix_extraits.py](../../backend/core/voix_extraits.py)**: short enrollment clips. **[micro.py](../../backend/core/micro.py)**: `jarvis_config.json` configuration, microphone and clap detection.
*   **[speech.py](../../backend/core/speech.py)**: speech queue (`parler()`), ahead-of-time TTS generation, pygame playback, interruptions; in English mode, translates the phrase before speaking it. **[voix_registre.py](../../backend/core/voix_registre.py)**: voice engines tried in order (edge-tts, optional ElevenLabs, SAPI as fallback); **[voix_elevenlabs.py](../../backend/core/voix_elevenlabs.py)**. **[etat_parole.py](../../backend/core/etat_parole.py)**, **[repeter.py](../../backend/core/repeter.py)** ("repeat"), **[secrets_voix.py](../../backend/core/secrets_voix.py)** (keys are never spoken out loud).
*   **[i18n.py](../../backend/core/i18n.py)**: **JARVIS language** (`fr` / `en`, `langue` key in `jarvis_config.json`, hot reload): recognition codes, English edge-tts voice, prompt instructions, translation of spoken phrases (fast Gemini, disk cache), translation of English commands into French understood by resolvers, console messages and labels, restart notices. Data: **`commandes_fr_en.json`** (help example commands, built by `tools/i18n_exemples.py`) and **`console_fr_en.json`** (console messages, built by `tools/i18n_console.py`).

### Brain: processing and AI
*   **[traitement.py](../../backend/core/traitement.py)**: `gerer_reponse_ia`: local resolvers (`_ORDRE_RESOLVEURS`), command translation in English mode, intent router, AI response, speech then actions. **[intent_dispatcher.py](../../backend/core/intent_dispatcher.py)**: intent router via Gemini function calling (canonical phrase replayed in resolvers).
*   **[prompt_builder.py](../../backend/core/prompt_builder.py)**: domain-based system prompt (core + JSON action catalog based on the phrase); language instructions at the beginning and end in English. **[llm_chat.py](../../backend/core/llm_chat.py)**: `interroger_ia` (streaming Gemini, failover, vision). **[llm_providers.py](../../backend/core/llm_providers.py)** and **[llm_registry.py](../../backend/core/llm_registry.py)**: Grok, Ollama, Groq, Claude, Mistral. **[api_quota.py](../../backend/core/api_quota.py)**: rate limiting per engine. **[compression.py](../../backend/core/compression.py)**: summary of previous exchanges. **[citations.py](../../backend/core/citations.py)**: numbered sources. **[injection.py](../../backend/core/injection.py)**: prompt injection detection, URL validation.
*   **[usage_llm.py](../../backend/core/usage_llm.py)** and **[mesure_gemini.py](../../backend/core/mesure_gemini.py)**: Gemini costs (euros, spending limit, alerts); all SDK calls are tracked.
*   **[actions_ia.py](../../backend/core/actions_ia.py)** / **[actions_ia_services.py](../../backend/core/actions_ia_services.py)**: execution of LLM JSON actions. **[ha_mcp_client.py](../../backend/core/ha_mcp_client.py)** (Home Assistant) and **[mcp_client.py](../../backend/core/mcp_client.py)** (GitHub and other MCP servers).
*   **[confirmation.py](../../backend/core/confirmation.py)**: voice + HUD confirmation before destructive actions. **[audit_log.py](../../backend/core/audit_log.py)**: audit log. **[dossiers.py](../../backend/core/dossiers.py)**: real locations for Desktop / Documents / Downloads (including OneDrive). **[musique_id.py](../../backend/core/musique_id.py)**: "what's this song" (Shazam, then AudD as fallback).
*   **[module_catalogue.py](../../backend/core/module_catalogue.py)** and **[module_ecrans.py](../../backend/core/module_ecrans.py)**: report the cylinder category actually executed and the content of category screens to the HUD.
*   **[console_ui.py](../../backend/core/console_ui.py)**: console (live dashboard, message feed, rich), translated into English on display; everything is logged in French in `data/jarvis_run.log`. **[defilement.py](../../backend/core/defilement.py)**: feed scrolling.

---

## `backend/module/`: business modules

*   **Memory**: [memory_manager.py](../../backend/module/memory_manager.py) (key-value facts), [vector_memory.py](../../backend/module/vector_memory.py) (ChromaDB, past conversations).
*   **Time**: [alarm_manager.py](../../backend/module/alarm_manager.py) (persistent alarms and timers, durations and times also understood in English), [alarmes_local.py](../../backend/module/alarmes_local.py) (resolver), [routines.py](../../backend/module/routines.py) ("every day at 8 AM, give me the weather"), **[briefing.py](../../backend/module/briefing.py)** (morning briefing: date, weather, calendar, tasks, alarms, emails; Google sources only with a token usable without interaction).
*   **Google and web**: [google_services.py](../../backend/module/google_services.py) (Gmail, Calendar, Drive, Sheets, Docs, Tasks), [recherche_web.py](../../backend/module/recherche_web.py) (SerpAPI), [browser_service.py](../../backend/module/browser_service.py) (Playwright browser agent), [visual_web_agent.py](../../backend/module/visual_web_agent.py) and [os_autopilot_agent.py](../../backend/module/os_autopilot_agent.py) (vision-guided autopilots), [vision_module.py](../../backend/module/vision_module.py), [discord_service.py](../../backend/module/discord_service.py) (channel message via webhook or bot).
*   **Home and weather**: [meteo_domotique.py](../../backend/module/meteo_domotique.py) (Open-Meteo weather, Home Assistant API), [weather_music_service.py](../../backend/module/weather_music_service.py), [domotique_sim.py](../../backend/module/domotique_sim.py), [homepod_audio.py](../../backend/module/homepod_audio.py).
*   **Files and system**: [file_manager.py](../../backend/module/file_manager.py), [voice_vault.py](../../backend/module/voice_vault.py) (AES vault), [uninstaller_helper.py](../../backend/module/uninstaller_helper.py), [winget_manager.py](../../backend/module/winget_manager.py), [antivirus_live.py](../../backend/module/antivirus_live.py), [network_radar.py](../../backend/module/network_radar.py), [system_stats.py](../../backend/module/system_stats.py), [sandbox_executor.py](../../backend/module/sandbox_executor.py).
*   **Creation**: [image_generator.py](../../backend/module/image_generator.py) (FLUX on Cloudflare via [image_cloudflare.py](../../backend/module/image_cloudflare.py), Pollinations as fallback), [image_search.py](../../backend/module/image_search.py), [competences.py](../../backend/module/competences.py) (AI-generated skills, validated by AST analysis), [skills.py](../../backend/module/skills.py) and [skills_import.py](../../backend/module/skills_import.py) (script-based skills approved by SHA-256 hash).
*   **Games and views**: [chess_manager.py](../../backend/module/chess_manager.py), [echecs_local.py](../../backend/module/echecs_local.py), [globe_local.py](../../backend/module/globe_local.py), [cortex_service.py](../../backend/module/cortex_service.py).
*   **Local commands without AI**: [commandes_locales.py](../../backend/module/commandes_locales.py) and [commandes_locales_sections.py](../../backend/module/commandes_locales_sections.py).
*   **God's Eye View**: [vue_de_dieu.py](../../backend/module/vue_de_dieu.py) (installs, updates, launches, and stops the app in `data/gods_eye_view/`, French translation, layer positioning); layers and data for **France**: [gev_couches.js](../../backend/module/gev_couches.js) (hot-added layers), [gev_donnees_fr.py](../../backend/module/gev_donnees_fr.py) (charging stations, parking lots, floods, earthquakes, air quality, in the background), [gev_parkings.py](../../backend/module/gev_parkings.py) (voice search for parking), [gev_carburants_fr.py](../../backend/module/gev_carburants_fr.py), [gev_radars_fr.py](../../backend/module/gev_radars_fr.py), [gev_radar_fr.py](../../backend/module/gev_radar_fr.py) (Météo-France rain radar), [gev_cameras_fr.py](../../backend/module/gev_cameras_fr.py), [windy_relais.py](../../backend/module/windy_relais.py), [gev_cles.py](../../backend/module/gev_cles.py); translation: `gev_fr.json`. Details: [VUE_DE_DIEU.md](VUE_DE_DIEU.md).

---

## `backend/controller/`: application drivers

[app_launcher.py](../../backend/controller/app_launcher.py) (catalog, launching, closing), [deezer_controller.py](../../backend/controller/deezer_controller.py) and [deezer_cdp.py](../../backend/controller/deezer_cdp.py) (Deezer controlled in the background via its debugging port, without stealing focus), [spotify_controller.py](../../backend/controller/spotify_controller.py), [steam_controller.py](../../backend/controller/steam_controller.py) (installed games, launching), [homepod_controller.py](../../backend/controller/homepod_controller.py), [actions_pc.py](../../backend/controller/actions_pc.py).

---

## `backend/plugins/`: voice command resolvers

Intercept the phrase before the LLM: a regular expression on whole words matches the command, the plugin replies immediately. Each plugin is registered in `chargement_plugins._PLUGINS` and placed in `traitement._ORDRE_RESOLVEURS` (from most specific to most general); those that interact with the PC are denied to guests (`_INTERDITS_INVITE`).

*   **Voice and JARVIS itself**: [langue_resolver.py](../../backend/plugins/langue_resolver.py) ("switch to English", "speak French": changes the language, shows the restart notice), [briefing_resolver.py](../../backend/plugins/briefing_resolver.py) ("my day"), [repetition_resolver.py](../../backend/plugins/repetition_resolver.py), [quota_stt_resolver.py](../../backend/plugins/quota_stt_resolver.py), [cout_llm_resolver.py](../../backend/plugins/cout_llm_resolver.py), [musique_resolver.py](../../backend/plugins/musique_resolver.py), [local_mode_resolver.py](../../backend/plugins/local_mode_resolver.py) (offline local Ollama mode), [memory_resolver.py](../../backend/plugins/memory_resolver.py), [skills_resolver.py](../../backend/plugins/skills_resolver.py).
*   **Interface** (the globe has its resolver in `module/globe_local.py`): [dom_controller_resolver.py](../../backend/plugins/dom_controller_resolver.py) (widgets, settings, subtitles), [vue_de_dieu_resolver.py](../../backend/plugins/vue_de_dieu_resolver.py) ("activate God's Eye View", "find me an open parking lot in X"), [spatial_explorer.py](../../backend/plugins/spatial_explorer.py), [recipe_resolver.py](../../backend/plugins/recipe_resolver.py), [list_manager.py](../../backend/plugins/list_manager.py).
*   **PC and applications**: [app_launcher_resolver.py](../../backend/plugins/app_launcher_resolver.py), [system_resolver.py](../../backend/plugins/system_resolver.py), [time_resolver.py](../../backend/plugins/time_resolver.py), [local_resolver.py](../../backend/plugins/local_resolver.py), [uninstaller_resolver.py](../../backend/plugins/uninstaller_resolver.py), [network_resolver.py](../../backend/plugins/network_resolver.py), [navigateur_resolver.py](../../backend/plugins/navigateur_resolver.py), [steam_resolver.py](../../backend/plugins/steam_resolver.py), [tv_resolver.py](../../backend/plugins/tv_resolver.py), [discord_resolver.py](../../backend/plugins/discord_resolver.py), [os_autopilot_resolver.py](../../backend/plugins/os_autopilot_resolver.py).
*   **Creation**: [dev_swarm_resolver.py](../../backend/plugins/dev_swarm_resolver.py) (swarm of 6 agents building websites), [website_resolver.py](../../backend/plugins/website_resolver.py), [document_generator_resolver.py](../../backend/plugins/document_generator_resolver.py) (Word, PowerPoint, Excel, PDF), [image_search_resolver.py](../../backend/plugins/image_search_resolver.py), [image_edit_resolver.py](../../backend/plugins/image_edit_resolver.py), [developer_resolver.py](../../backend/plugins/developer_resolver.py), [plugin_creator_resolver.py](../../backend/plugins/plugin_creator_resolver.py), [extras.py](../../backend/plugins/extras.py) (currencies, capitals, quick questions), [competence_check_connexion.py](../../backend/plugins/competence_check_connexion.py) (example skill).

---

## `interfaces/frontend/src/`: web HUD (TypeScript, Three.js, Vite)

*   **[main.ts](../../interfaces/frontend/src/main.ts)**: entry point (imports and `init*()` in deliberate order: do not reorder). **[ws_link.ts](../../interfaces/frontend/src/ws_link.ts)**: shared socket.
*   **[i18n/i18n.ts](../../interfaces/frontend/src/i18n/i18n.ts)** and **`i18n/en.json`**: **HUD language**. DOM (text, `title`, `placeholder`, `aria-label`) and canvas translator, French → English dictionary (~1,800 strings, built by `tools/i18n_*.py` tools), templates for parameterized strings, requests the server to translate dynamic strings (cards, confirmations, module screens), dates and numbers localized by language (`t()`, `locale()`, `nomJour()`, `nomMois()`).
*   **Orb and cylinder**: [orb_cylindre.ts](../../interfaces/frontend/src/orb_cylindre.ts) (2D canvas holographic cylinder, states, category wheel, card textures cached by language), [orb_themes.ts](../../interfaces/frontend/src/orb_themes.ts) (21 categories and subcategories), [holo_clock.ts](../../interfaces/frontend/src/holo_clock.ts), [cards.ts](../../interfaces/frontend/src/cards.ts) (split-part notifications, with optional button).
*   **3D views**: [vues_3d.js](../../interfaces/frontend/src/vues_3d.js) (common host, hand controls), [globe.ts](../../interfaces/frontend/src/globe.ts), [chess_map.ts](../../interfaces/frontend/src/chess_map.ts), [domotic_map.ts](../../interfaces/frontend/src/domotic_map.ts), [cortex_map.ts](../../interfaces/frontend/src/cortex_map.ts), [spatial_explorer.ts](../../interfaces/frontend/src/spatial_explorer.ts), [network_radar.ts](../../interfaces/frontend/src/network_radar.ts), [swarm_lounge.ts](../../interfaces/frontend/src/swarm_lounge.ts), [hand_tracking.ts](../../interfaces/frontend/src/hand_tracking.ts) (AR mode, MediaPipe), [screen_capture.ts](../../interfaces/frontend/src/screen_capture.ts).
*   **Widgets**: [widgets.ts](../../interfaces/frontend/src/widgets.ts), [weather_vues.ts](../../interfaces/frontend/src/weather_vues.ts), [ha_dashboard.ts](../../interfaces/frontend/src/ha_dashboard.ts).
*   **`hud/`**: shared state (`state.ts`, `dom_refs.ts`), orb (`orb_state.ts`), wheel menu (`menu_roue.ts`), **exploded panels** (`eclate.ts`, `pieces_widgets.ts`, `pieces_outils.ts`: help, timers, home, settings including language selection, `pieces_tableaux.ts`, `pieces_alertes.ts`: notifications), help and command palette (`aide_commandes.ts`, `help_hud.ts`), settings (`settings.ts`), keyboard, subtitles, timer, boot (`boot.ts`, `boot_anim.ts`), God's Eye View (`vue_de_dieu.ts`), 3D views (`vues_3d.ts`), DOM actions sent by plugins (`dom_automation.ts`).
*   **`panels/`**: antivirus, uninstaller, winget, shopping list, recipe, vault, images, weather / temperature, system status, **first-launch wizard** (`setup_wizard.ts`: language selection, first name, voice, AI key, mic, fingerprint), updates, extension token, Discord settings, code workshop, confirmation, category screens.
*   **`ws/`**: `connection.ts` (connection, reconnection, server message translation into English), `messages_*.ts` (message handler branches, `handle*()` returns `true` if handled), `message_types.ts`.
*   **`ui/`**: button carousel, drag-and-drop, effects, tooltips. **`css/`**: numbered `01` to `20`, **critical cascade: do not reorder** (`13_panneaux_modules.css`: common panel styling, `15_eclate.css`: exploded parts, `19_vue_de_dieu.css`).
*   Outside `src/`: `index.html` (HUD structure), `public/assets/` (favicon and textures), `vite.config.ts`, `tsconfig.json`, `eslint.config.js`.

---

## `interfaces/chrome_extension/`

Allows JARVIS to control the user's browser via a token-authenticated local WebSocket: `manifest.json`, `background.js` (connection to the local server), `content.js` (virtual neon cursor, clicks and inputs requested by JARVIS).

---

## Standard checks

`venv\Scripts\python.exe -m compileall -q backend main.py` · `venv\Scripts\python.exe -m pytest tests` · `venv\Scripts\ruff.exe check .` · in `interfaces/frontend`: `npx tsc --noEmit -p .` and `npx eslint src`.
