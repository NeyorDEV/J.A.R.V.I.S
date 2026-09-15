# Changelog

Changements non encore commités, en date du 2026-09-15.

## Renommage des scripts `.bat`

Tous les fichiers `.bat` du projet renommés vers des noms plus courts et cohérents :

- `DEMARRER_JARVIS.bat` → `start.bat` (renommé temporairement en `demarrer.bat` en cours de session, puis en `start.bat`)
- `install.bat` → `install.bat` (renommé temporairement en `installer.bat` en cours de session, puis revenu à `install.bat`)
- `tools/CONSULTER_MEMOIRE.bat` → `tools/memoire.bat`
- `tools/VIDER_CACHE_JARVIS.bat` → `tools/vider_cache.bat`
- `tools/_setup/setup_deps.bat` → `tools/_setup/dependances.bat`

## Refonte de `install.bat`

- Ajout des clés API manquantes au template `.env` généré (Anthropic, Mistral, OpenAI).
- Ajout de `anthropic` et `mistralai` à la liste des paquets `pip install`.
- Suppression de la fonctionnalité de personnalisation "Mickael" qui faisait du remplacement de chaînes dans le code source (morte) ; remplacée par une écriture dans `jarvis_config.json`.
- Refonte totale de l'affichage : suppression des tags `[SYSTEME]`/`[INFO]`/majuscules et des bannières ASCII `======`/`XXXXX`, remplacés par un style sobre avec séparateurs `--------`.
- Ajout d'un compteur d'étapes global `[n/7]` sur l'ensemble du script (au lieu d'un compteur local uniquement sur l'étape pip install).
- Tableau récapitulatif simplifié avec alignement en pointillés, bloc d'erreur simplifié (sans boîte ASCII), écran de fin restructuré.

`tools/_setup/dependances.bat` mis à jour de façon similaire (ajout de `mistralai`, suppression de l'ancien branding "techenclair.fr").

## Intégration CI / linting

- **`.github/workflows/ci.yml`** (nouveau) : deux jobs sur `ubuntu-latest`.
  - `python` : compile tous les `.py` suivis par git (hors `tools/sandbox/`, `tools/tests/`, `tools/training/`) via `py_compile`, puis lance `ruff check .` (non bloquant).
  - `frontend` : `npm ci`, `tsc --noEmit` (bloquant), `npm run lint` (non bloquant).
- **`pyproject.toml`** (nouveau) : config `ruff` ciblée sur les vraies erreurs uniquement (`F401`, `F811`, `F821`, `F841`), volontairement sans règles de style, avec exclusions pour les patterns intentionnels du projet (`import *`, notebooks, sandbox/tests/training).
- **`interfaces/frontend/eslint.config.js`** (nouveau) : config flat ESLint 9 + `typescript-eslint`, `any` autorisé, imports/variables inutilisés en warning seulement.
- **`interfaces/frontend/package.json`** : ajout de `eslint` et `typescript-eslint` en devDependencies, ajout du script `"lint": "eslint src"`.

## Corrections de bugs trouvées via le nouveau linter

- **`backend/plugins/dev_swarm_resolver.py`** : `await notify(...)` appelait une fonction jamais définie → `NameError` garanti sur le chemin de rejet sandbox. Corrigé en `await diffuser_dev_swarm(...)`.
- **`tools/tests/deezer_controller_fuzzy_test.py`** : fichier corrompu (contenu stocké en chaîne échappée tronquée en plein milieu). Réécrit entièrement comme un harnais de test manuel interactif important les vraies fonctions de `backend/controller/deezer_controller.py`.
- **Bug asyncio répété** : `parler()` (dans `backend/core/speech.py`) est une fonction **synchrone**, mais plusieurs appels utilisaient `await parler(...)` / `await parler_callback(...)`, provoquant `TypeError: object NoneType can't be used in 'await' expression`.
  - `tools/antivirus_scanner.py` : 3 occurrences corrigées, plus suppression du prénom "Mickael" codé en dur dans le message de fin d'analyse.
  - `backend/controller/app_launcher.py` : 3 occurrences corrigées (`mode_boulot`, `mode_gaming`, `mode_rocket_league`).

## Page paramètres — cohérence des polices

- Police `Orbitron` manquante sur plusieurs éléments de la page settings (titres de cartes, labels, nav, boutons, switches) et sur les champs de saisie (texte, nombre, url, select, champs de clé API, formulaire d'app). Tous alignés sur `Orbitron` dans `interfaces/frontend/src/css/01_base_hud.css`.

## Panneaux Winget / Désinstallateur / Antivirus / Domotique

- **Police incorrecte sur texte en gras** : bug de substitution de police Chromium/WebView2 (une police sans vraie graisse grasse comme `Courier New` se fait remplacer entièrement au lieu d'être synthétisée en gras). Corrigé en ajoutant `Consolas` en tête de la pile de polices sur les conteneurs (`.uninstaller-panel`, `.ha-panel`, `.av-panel`) et sur les surcharges spécifiques (`.uninstaller-search-box input`, `.uninstaller-app-btn`, `.uninstaller-btn`).
- **Décalage horizontal des noms de logiciels dans le panneau Winget** : `winget_panel.ts` ajoutait un style inline `display:flex` sans `flex-direction:row`, laissant la classe CSS `.uninstaller-app-info` en `flex-direction: column` — les lignes se centraient différemment selon la longueur du nom. Corrigé en ajoutant `flex-direction:row` au style inline.
- **Barre de scan orange sur un panneau censé être cyan** : la variable CSS `--panel-laser` (animation `holo-scan-line`, définie dans `11_clock_tips_keyboard.css`) n'avait pas de surcharge cyan pour `#winget-panel`, contrairement à `--un-rgb`. Ajout de `--panel-laser: #00e5ff;` sur `#winget-panel`.

## Suppression de la fonctionnalité "GPU Boost"

Bouton visuel de qualité de rendu de l'orbe 3D, entièrement mort côté backend (aucun listener WebSocket pour `toggle_gpu`). Supprimé intégralement :

- `interfaces/frontend/index.html` : bouton `#gpu-button` du dock.
- `interfaces/frontend/src/main.ts` : déclaration, entrées d'aide vocale, handlers de clic, binding carrousel.
- `interfaces/frontend/src/orb.ts` : méthode `setQuality()` et son entrée d'interface (sans impact visuel, le renderer s'initialise déjà à `devicePixelRatio`).
- `backend/plugins/dom_controller_resolver.py` : bloc de commandes vocales "active/désactive le GPU".

## Suppression du navigateur intégré (`secure_browser.py`)

Navigateur pywebview ancrable/détachable avec toolbar et adblock injectés (distinct de l'agent de navigation autonome `module/browser_service.py`, conservé intact). Supprimé intégralement :

- **`tools/secure_browser.py`** : fichier supprimé (~630 lignes, incluant les appels Win32 de docking).
- **`main.py`** : 4 handlers WebSocket (`open_browser`, `dock_browser`, `undock_browser`, `close_browser`), la commande vocale d'ouverture du navigateur, l'initialisation de la fenêtre webview et son callback de redimensionnement. La commande vocale de fermeture des navigateurs externes (Chrome/Edge/Firefox/Opera/Brave, pour couper musique/vidéo en fond) a été conservée car indépendante.
- **`interfaces/frontend/index.html`** : bouton `#carousel-browser-btn` et bloc de contrôles flottants `#hud-browser-controls`.
- **`interfaces/frontend/src/main.ts`** : handler WS `browser_state`, logique `updateBrowserUIState`, handlers des boutons ancrer/fermer, binding carrousel.
- **`interfaces/frontend/src/css/10_uninstaller_menu.css`** : bloc CSS `body.browser-open` / `#hud-browser-controls` / `.hud-browser-btn` (~90 lignes).
- **`docs/JARVIS_FILES_GUIDE.md`** : entrée de documentation obsolète retirée.

Vérifié : aucune référence restante (`secure_browser`, `hud-browser`, `carousel-browser`, etc.), `py_compile` et `tsc --noEmit` passent.

## Dossier `assets`

Icônes et images regroupées dans un dossier dédié, avec mise à jour des références :

- `jarvis_icon.ico` → `assets/jarvis_icon.ico` (icône de la fenêtre app, référencée dans `main.py`).
- `favicon.png`, `earth-blue-marble.jpg`, `earth-night.jpg`, `earth-topology.png` → `interfaces/frontend/public/assets/` (doivent rester sous `public/` pour être servies par Vite ; références mises à jour dans `index.html` et `globe.ts`).

## Confirmation avant action destructrice

Nouveau garde-fou (voix **et** HUD) avant toute action destructrice : désinstallation d'un logiciel, nettoyage de résidus, suppression d'un fichier du coffre-fort, suppression d'un fichier/dossier via l'explorateur spatial.

- **`backend/core/confirmation.py`** (nouveau) : une confirmation en attente à la fois, résoluble par clic HUD (`confirm_response`) ou réponse vocale ("oui"/"non" et variantes) — interceptée **avant** le verrou de traitement des commandes pour éviter un deadlock logique.
- **`interfaces/frontend/src/css/12_confirm_dialog.css`** (nouveau) + popup HTML dans `index.html` + câblage dans `main.ts`.
- Gates ajoutés dans `main.py` (coffre-fort, désinstallation, nettoyage de résidus) et `backend/plugins/spatial_explorer.py` (suppression de fichier/dossier).

## Registre des moteurs LLM

- **`backend/core/llm_registry.py`** (nouveau) : les paliers Groq → Claude → Mistral de `demander_ia` (main.py) sont enregistrés et pilotés par une seule boucle au lieu de 3 blocs `if/elif` quasi identiques. Ajouter un nouveau provider à ce palier = un `register()`, plus besoin de dupliquer le bloc de routage.
- Volontairement non touché : Gemini (streaming multi-modèles + Google Search + cooldown par modèle), Grok, Ollama et SerpAPI (fallbacks avec logique métier trop spécifique pour être généralisée sans risque).

## Client MCP générique + serveur GitHub

- **`backend/core/mcp_client.py`** (nouveau) : client MCP multi-serveurs (SSE ou Streamable HTTP) — ajouter un serveur ne demande qu'une entrée dans `MCP_SERVERS`, contrairement à `ha_mcp_client.py` (client dédié Home Assistant, conservé tel quel, non touché).
- Premier serveur branché : **GitHub** (serveur MCP distant officiel, via une nouvelle variable `GITHUB_MCP_TOKEN` dans le `.env`).
- `main.py` : nouveau handler `github_action` (même principe que `ha_action`). `prompt_builder.py` : Gemini sait générer cette action pour les demandes liées à GitHub.

## Journal d'audit

- **`backend/core/audit_log.py`** (nouveau) : journal append-only en JSONL (`jarvis_audit.log`) pour les actions sensibles, jusqu'ici visibles seulement en console et perdues au redémarrage.
- Branché sur `confirmation.py` (chaque confirmation résolue est journalisée) et sur `competences.py` (création, refus par le contrôle de sûreté, suppression, exécution et erreurs d'exécution d'une compétence générée par l'IA).

## Hook pre-commit versionné

- **`tools/git-hooks/pre-commit`** (nouveau, suivi par git) : copie du hook local existant (vérifie `py_compile` + `tsc --noEmit` avant chaque commit), qui n'était jusqu'ici jamais versionné.
- `install.bat` et `tools/_setup/dependances.bat` copient désormais ce fichier vers `.git/hooks/pre-commit` à chaque installation — le hook survit maintenant à une réinstallation ou un nouveau clone.

## `.claude` et `CLAUDE.md` retirés du suivi git

Ajoutés au `.gitignore` et retirés du suivi (`git rm --cached`) : configuration locale à la machine, pas destinée à être partagée sur le dépôt.

## README refait dans le style OpenJarvis

Logo centré, tagline, ligne de badges (Python, Node, frontend, docs, GitHub), section liens en bas pointant vers la documentation existante (`docs/JARVIS_FILES_GUIDE.md`, `docs/jarvis_fonctionnalites.txt`, `docs/JARVIS_Commandes.txt`, `CHANGELOG.md`). Contenu existant conservé et mis à jour (Mistral, confirmation avant action destructrice).

## Divers

- `.gitignore` mis à jour.
- `backend/core/tts_local.py` et `backend/core/kokoro/voices-v1.0.bin` supprimés (TTS local abandonné au profit d'edge_tts).
- `backend/module/memory_manager.py`, `backend/module/vector_memory.py` : ajustements (voir diff pour détail).
