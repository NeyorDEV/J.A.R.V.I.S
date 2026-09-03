# J.A.R.V.I.S — Guide des Fichiers & Architecture (v8.9)

Ce document propose un inventaire complet et détaillé de chaque fichier et dossier constituant le projet **J.A.R.V.I.S**. Il est conçu pour être lu par l'IA au début de chaque nouvelle conversation afin de comprendre instantanément le rôle de chaque composant et d'éviter toute perte de repères.

---

## 📂 RACINE DU PROJET (n:\JARVIS)

### 🖥️ Scripts d'entrée & Utilitaires Principaux
*   **[main.py](file:///n:/JARVIS/main.py)** : L'orchestrateur central du backend (anciennement `main2.py`). Il gère la boucle principale, le serveur WebSocket (`ws://localhost:8765`), la capture audio (PyAudio), la détection de parole (VAD), la biométrie vocale, la transcription (STT), et la génération de réponses (LLM) avec synthèse vocale (TTS) en streaming.
*   **[antivirus_scanner.py](file:///n:/JARVIS/tools/antivirus_scanner.py)** : Scanner de sécurité à la demande et résident. Il surveille l'écriture de scripts malveillants sur le PC et permet de lancer des analyses de répertoires.
*   **[secure_browser.py](file:///n:/JARVIS/tools/secure_browser.py)** : Implémentation d'un navigateur sécurisé et contrôlé.
*   **[consulter_memoire.py](file:///n:/JARVIS/tools/consulter_memoire.py)** : Script console rapide pour lire les faits stockés dans la mémoire locale de JARVIS.

### ⚙️ Fichiers de Configuration & États (Dossier `data/` et `config/`)
*   **[.env](file:///n:/JARVIS/.env)** : Fichier contenant les clés API sensibles (`GEMINI_API_KEY`, `GROQ_API_KEY`, `SERPAPI_API_KEY`, etc.). Modifiable à chaud depuis l'interface HUD.
*   **[jarvis_config.json](file:///n:/JARVIS/jarvis_config.json)** : Configuration utilisateur (seuil micro, entités Home Assistant, chemins d'applications, etc.).
*   **[.jarvis_cache_version](file:///n:/JARVIS/.jarvis_cache_version)** : Identifiant court de version de cache.

### 📂 Sous-dossier `data/` (Bases de Données Locales)
*   **[jarvis_memoire.json](file:///n:/JARVIS/data/jarvis_memoire.json)** : Mémoire clé-valeur persistante (faits, préférences utilisateur, codes d'accès).
*   **[jarvis_listes.json](file:///n:/JARVIS/data/jarvis_listes.json)** : Stockage persistant des todos, notes et listes de courses.
*   **[alarmes.json](file:///n:/JARVIS/data/alarmes.json)** : Stockage persistant des alarmes et des minuteurs actifs.
*   **[jarvis_conversations.json](file:///n:/JARVIS/data/jarvis_conversations.json)** : Cache local des derniers échanges conversationnels.
*   **[jarvis_synapses.json](file:///n:/JARVIS/data/jarvis_synapses.json)** : Métadonnées associées aux connexions neuronales du cortex 3D.

### 📂 Sous-dossier `config/` (Identifiants & Clés)
*   **[credentials.json](file:///n:/JARVIS/config/credentials.json)** : Fichier d'authentification pour les API Google Workspace.
*   **[token.pickle](file:///n:/JARVIS/config/token.pickle)** : Jeton de session Google persisté.
*   **[adb_key](file:///n:/JARVIS/config/adb_key)** : Clé privée de signature ADB pour le contrôle de la TV.
*   **[adb_key.pub](file:///n:/JARVIS/config/adb_key.pub)** : Clé publique de signature ADB.

### 📂 Sous-dossier `docs/` (Documentations)
*   **[JARVIS_Commandes.txt](file:///n:/JARVIS/docs/JARVIS_Commandes.txt)** : Liste exhaustive de toutes les commandes vocales supportées par le système.
*   **[jarvis_fonctionnalites.txt](file:///n:/JARVIS/docs/jarvis_fonctionnalites.txt)** : Descriptif détaillé de chaque fonctionnalité programmée.

### 📂 Sous-dossier `tests/` (Tests & Diagnostics)
*   **[deezer_controller_fuzzy_test.py](file:///n:/JARVIS/tools/tests/deezer_controller_fuzzy_test.py)** : Test de correspondance floue pour la sélection des chansons/artistes sur Deezer.

### 📑 Scripts Batch de Lancement
*   **[CLAUDE.md](file:///n:/JARVIS/CLAUDE.md)** : Guide d'architecture générale et conventions de développement pour l'IA.
*   **[README.md](file:///n:/JARVIS/README.md)** : Fichier d'accueil basique.
*   **[requirements.txt](file:///n:/JARVIS/requirements.txt)** : Liste des dépendances Python du projet.
*   **[DEMARRER_JARVIS.bat](file:///n:/JARVIS/DEMARRER_JARVIS.bat)** : Lanceur rapide du serveur backend.
*   **[CONSULTER_MEMOIRE.bat](file:///n:/JARVIS/CONSULTER_MEMOIRE.bat)** : Lanceur rapide pour `consulter_memoire.py`.
*   **[VIDER_CACHE_JARVIS.bat](file:///n:/JARVIS/VIDER_CACHE_JARVIS.bat)** : Script de maintenance pour purger les fichiers temporaires et réinitialiser le cache.
*   **[RESTAURER_JARVIS.bat](file:///n:/JARVIS/RESTAURER_JARVIS.bat)** : Utilitaire de restauration en cas d'erreur de mise à jour ou de corruption.
*   **[install.bat](file:///n:/JARVIS/install.bat)** : Script d'installation automatique des dépendances et de configuration du projet.

---

## 🧠 DOSSIER `core/` (Cœur du Système)
Fichiers gérant les entrées/sorties physiques, la biométrie et les liaisons API de base.

*   **[config.py](file:///n:/JARVIS/backend/core/config.py)** : Configuration globale (clés API, modèle actif, index audio, redirection automatique des liens web vers Opera GX).
*   **[brain.py](file:///n:/JARVIS/backend/core/brain.py)** : Client d'appel principal vers Gemini avec mécanisme de secours (fallback) vers Groq en cas d'erreur réseau ou de limite de quota.
*   **[ha_mcp_client.py](file:///n:/JARVIS/backend/core/ha_mcp_client.py)** : Client MCP pour Home Assistant. Découvre dynamiquement les outils exposés par le serveur MCP natif de HA et route les instructions domotiques en langage naturel via function-calling Gemini — remplace l'ancien système d'actions codées en dur par appareil.
*   **[prompt_builder.py](file:///n:/JARVIS/backend/core/prompt_builder.py)** : Assembleur du *System Prompt* de JARVIS. Injecte de manière optimisée la date/heure actuelle, les faits en mémoire, et les schémas d'actions JSON.
*   **[audio_stream.py](file:///n:/JARVIS/backend/core/audio_stream.py)** : Gestionnaire de flux audio d'entrée (PyAudio). capture les blocs audio du micro physique ou virtuel.
*   **[vad.py](file:///n:/JARVIS/backend/core/vad.py)** : Détection d'Activité Vocale (Voice Activity Detection). Analyse l'audio via Silero VAD (ONNX) et détermine quand l'utilisateur commence et arrête de parler.
*   **[stt.py](file:///n:/JARVIS/backend/core/stt.py)** : Speech-to-Text. Transcrit l'audio via l'API ultra-rapide Groq Whisper avec repli sur Google STT si nécessaire. Filtre également les hallucinations connues de Whisper.
*   **[speech.py](file:///n:/JARVIS/backend/core/speech.py)** : Text-to-Speech (TTS). Gère la file d'attente de parole en parallèle, en lisant les phrases au fil de leur génération via `edge_tts` et en contrôlant les interruptions utilisateur (Barge-in / Claps).
*   **[tts_local.py](file:///n:/JARVIS/backend/core/tts_local.py)** : Synthèse vocale locale alternative basée sur le modèle Kokoro-82M ONNX (exécutable hors-ligne).
*   **[wakeword.py](file:///n:/JARVIS/backend/core/wakeword.py)** : Logique de détection passive du mot clé "jarvis".
*   **[intent_dispatcher.py](file:///n:/JARVIS/backend/core/intent_dispatcher.py)** : Parse les réponses de l'IA. Si un bloc JSON d'action est détecté, il extrait l'action et l'exécute via le module système correspondant.
*   **[webview_cache.py](file:///n:/JARVIS/backend/core/webview_cache.py)** : Gestion et nettoyage du cache des interfaces WebView locales.

---

## 🛠️ DOSSIER `module/` (Modules Métier & Intégrations)
Fichiers implémentant les fonctionnalités métier autonomes de JARVIS.

*   **[memory_manager.py](file:///n:/JARVIS/backend/module/memory_manager.py)** : Gère le dictionnaire de faits locaux clé-valeur (`jarvis_memoire.json` dans `data/`), sa sérialisation et sa mise à jour à chaud.
*   **[vector_memory.py](file:///n:/JARVIS/backend/module/vector_memory.py)** : Implémente la mémoire épisodique vectorielle avec ChromaDB et des embeddings locaux (`all-MiniLM-L6-v2`) pour stocker et rechercher les conversations passées.
*   **[alarm_manager.py](file:///n:/JARVIS/backend/module/alarm_manager.py)** : Gestionnaire d'alarmes, réveils et minuteurs persistants (`alarmes.json` dans `data/`) avec alertes vocales actives.
*   **[file_manager.py](file:///n:/JARVIS/backend/module/file_manager.py)** : Opérations locales sur le système de fichiers (lister, créer des répertoires, renommer, trier intelligemment le dossier Downloads, etc.).
*   **[browser_service.py](file:///n:/JARVIS/backend/module/browser_service.py)** : Agent de navigation autonome sous Selenium/Playwright permettant de naviguer et d'extraire des informations.
*   **[visual_web_agent.py](file:///n:/JARVIS/backend/module/visual_web_agent.py)** : Version avancée d'autopilote de navigation. Utilise Gemini Vision pour analyser des captures d'écran du navigateur Opera GX et cliquer de manière ciblée (coordonnées x, y).
*   **[os_autopilot_agent.py](file:///n:/JARVIS/backend/module/os_autopilot_agent.py)** : Autopilote global du système Windows. Utilise PyAutoGUI pour simuler des entrées clavier complexes, des clics de souris et piloter des fenêtres système.
*   **[google_services.py](file:///n:/JARVIS/backend/module/google_services.py)** : Intégration officielle avec les APIs Google Workspace (Gmail, Calendar, Google Drive, Google Sheets, Google Tasks).
*   **[meteo_domotique.py](file:///n:/JARVIS/backend/module/meteo_domotique.py)** : Météo (Open-Meteo) et API REST Home Assistant pour le tableau de bord HUD. Le pilotage vocal de la domotique passe désormais par le client MCP (`core/ha_mcp_client.py`).
*   **[homepod_audio.py](file:///n:/JARVIS/backend/module/homepod_audio.py)** : Module de routage de la sortie vocale ou musicale de JARVIS vers un HomePod ou une enceinte AirPlay distante.
*   **[image_generator.py](file:///n:/JARVIS/backend/module/image_generator.py)** : Générateur d'illustrations IA s'appuyant sur l'API gratuite Pollinations.
*   **[image_search.py](file:///n:/JARVIS/backend/module/image_search.py)** : Service de recherche et d'affichage d'images issues du Web.
*   **[sports_web.py](file:///n:/JARVIS/backend/module/sports_web.py)** : Récupère les scores de football et classements sportifs via TheSportsDB ou scraping.
*   **[uninstaller_helper.py](file:///n:/JARVIS/backend/module/uninstaller_helper.py)** : Scanne la base de registre Windows (32/64 bits) pour lister les logiciels installés et déclencher des désinstallations propres.
*   **[winget_manager.py](file:///n:/JARVIS/backend/module/winget_manager.py)** : Interagit avec l'outil de gestion de paquets Windows (Winget) pour vérifier les mises à jour logicielles disponibles sur la machine.
*   **[vision_module.py](file:///n:/JARVIS/backend/module/vision_module.py)** : Capture et analyse le flux de la webcam ou de l'écran principal pour décrire ce qui s'y passe via Gemini Vision.
*   **[weather_music_service.py](file:///n:/JARVIS/backend/module/weather_music_service.py)** : Service d'agrégation météo (wttr.in/Open-Meteo) et d'infos musicales.
*   **[jarvis_agent.py](file:///n:/JARVIS/backend/module/jarvis_agent.py)** : Classe agent encapsulée pour l'exécution asynchrone des modèles.
*   **[chess_manager.py](file:///n:/JARVIS/backend/module/chess_manager.py)** : Gère la logique de jeu d'échecs (validation des coups de l'utilisateur, moteur de jeu local Python-Chess).
*   **[network_radar.py](file:///n:/JARVIS/backend/module/network_radar.py)** : Scanne le réseau local pour découvrir les adresses IP et appareils connectés.

---

## 🎛️ DOSSIER `controller/` (Pilotes Système Windows)
Pilotes légers pour manipuler les applications installées sur le PC de l'utilisateur.

*   **[app_launcher.py](file:///n:/JARVIS/backend/controller/app_launcher.py)** : Catalogue et lance les applications locales (jeux, IDEs, outils) et gère leur fermeture sécurisée.
*   **[spotify_controller.py](file:///n:/JARVIS/backend/controller/spotify_controller.py)** : Contrôle de l'application Spotify Windows (Play, Pause, Suivant, Précédent, récupération du titre courant).
*   **[deezer_controller.py](file:///n:/JARVIS/backend/controller/deezer_controller.py)** : Contrôleur complexe de Deezer Windows par automatisation d'API ou de fenêtres locales.
*   **[homepod_controller.py](file:///n:/JARVIS/backend/controller/homepod_controller.py)** : Contrôle des commandes multimédias des enceintes HomePod.
*   **[tv_worker.py](file:///n:/JARVIS/backend/controller/tv_worker.py)** : Script s'exécutant en arrière-plan pour surveiller et piloter la TV connectée ou le Chromecast via des commandes ADB.

---

## 🔌 DOSSIER `plugins/` (Résolveurs d'Intention Directe)
Ces fichiers interceptent la commande vocale de l'utilisateur *avant* qu'elle ne soit envoyée au LLM. Si une expression régulière correspond, le plugin s'exécute immédiatement (temps de réponse < 50ms).

*   **[time_resolver.py](file:///n:/JARVIS/backend/plugins/time_resolver.py)** : Résout instantanément l'heure et la date.
*   **[system_resolver.py](file:///n:/JARVIS/backend/plugins/system_resolver.py)** : Récupère les statistiques système (CPU, RAM, GPU) de la machine hôte.
*   **[memory_resolver.py](file:///n:/JARVIS/backend/plugins/memory_resolver.py)** : Gère les demandes manuelles d'apprentissage ("se souvenir de X" ou "oublier Y").
*   **[app_launcher_resolver.py](file:///n:/JARVIS/backend/plugins/app_launcher_resolver.py)** : Intercepte les lancements et fermetures d'applications locales.
*   **[dom_controller_resolver.py](file:///n:/JARVIS/backend/plugins/dom_controller_resolver.py)** : Résout les requêtes de contrôle de l'interface (ex : "ferme le menu", "affiche le calendrier").
*   **[globe_resolver.py](file:///n:/JARVIS/backend/plugins/globe_resolver.py)** : Résout les commandes destinées au globe 3D (ex : "zoome", "va à Paris").
*   **[tv_resolver.py](file:///n:/JARVIS/backend/plugins/tv_resolver.py)** : Contrôle la télévision (allumer, changer d'application).
*   **[recipe_resolver.py](file:///n:/JARVIS/backend/plugins/recipe_resolver.py)** : Gère les recettes de cuisine dynamiques.
*   **[local_resolver.py](file:///n:/JARVIS/backend/plugins/local_resolver.py)** : Exécute des actions sur les fichiers locaux (ex : ouvrir le dossier Downloads).
*   **[local_mode_resolver.py](file:///n:/JARVIS/backend/plugins/local_mode_resolver.py)** : Force le passage en mode local (LLM Ollama hors-ligne).
*   **[network_resolver.py](file:///n:/JARVIS/backend/plugins/network_resolver.py)** : Déclenche l'analyse réseau (Network Radar).
*   **[uninstaller_resolver.py](file:///n:/JARVIS/backend/plugins/uninstaller_resolver.py)** : Lance l'interface de désinstallation d'applications.
*   **[image_search_resolver.py](file:///n:/JARVIS/backend/plugins/image_search_resolver.py)** : Déclenche la recherche d'images en ligne.
*   **[list_manager.py](file:///n:/JARVIS/backend/plugins/list_manager.py)** : Ajoute, supprime ou liste les éléments des todos et listes de courses (ciblant `data/jarvis_listes.json`).
*   **[os_autopilot_resolver.py](file:///n:/JARVIS/backend/plugins/os_autopilot_resolver.py)** : Route vers l'autopilote du système d'exploitation.
*   **[spatial_explorer.py](file:///n:/JARVIS/backend/plugins/spatial_explorer.py)** : Gère l'affichage de l'explorateur de fichiers 3D.
*   **[dev_swarm_resolver.py](file:///n:/JARVIS/backend/plugins/dev_swarm_resolver.py)** : Orchestrateur de l'essaim d'élite à 6 agents autonomes (PM, UI, DEV, SEC, QA, OPS). Conçoit et crée des projets web complets, effectue l'audit visuel multi-scroll par captures d'écran et valide 100% des fonctionnalités en sandbox.
*   **[developer_resolver.py](file:///n:/JARVIS/backend/plugins/developer_resolver.py)** : Permet à JARVIS de modifier son propre code source et de lancer des diagnostics système.
*   **[website_resolver.py](file:///n:/JARVIS/backend/plugins/website_resolver.py)** : Résout la génération de sites web à la volée et le protocole d'énigme secret d'anniversaire ("lance l'énigme") avec ouverture plein écran automatique dans Opera GX.
*   **[document_generator_resolver.py](file:///n:/JARVIS/backend/plugins/document_generator_resolver.py)** : Génère des documents Word/PowerPoint/Excel/PDF à la demande vocale (contenu produit par Gemini en JSON structuré, mis en forme par python-docx/python-pptx/openpyxl/reportlab) et fusionne des PDF existants.
*   **[competence_check_connexion.py](file:///n:/JARVIS/backend/plugins/competence_check_connexion.py)** : Effectue des vérifications rapides d'état de connexion.

---

## 🎨 DOSSIER `frontend/src/` (HUD Web Three.js)
Interface utilisateur principale, de style "Iron Man HUD".

### 🔗 Fichiers de structure & Initialisation
*   **[main.ts](file:///n:/JARVIS/interfaces/frontend/src/main.ts)** : Point d'entrée de l'application. Gère la connexion WebSocket permanente avec le backend, distribue les actions reçues au HUD, et gère les widgets.
*   **[ws_link.ts](file:///n:/JARVIS/interfaces/frontend/src/ws_link.ts)** : Couche réseau gérant l'état de la connexion WebSocket.

### 🔮 Modélisations et Composants 3D (Three.js)
*   **[orb.ts](file:///n:/JARVIS/interfaces/frontend/src/orb.ts)** : L'orbe réactif central (Arc Reactor). Anime les points 3D selon les états (`listening` : pulsation lente, `thinking` : rotation rapide, `speaking` : ondes vocales). Incorpore également l'algorithme d'affichage de mots 3D par projection de pixels.
*   **[globe.ts](file:///n:/JARVIS/interfaces/frontend/src/globe.ts)** : Globe 3D réaliste (texture jour/nuit, nuages) lié à Leaflet 2D pour les navigations cartographiques vocales.
*   **[chess_map.ts](file:///n:/JARVIS/interfaces/frontend/src/chess_map.ts)** : Implémentation du plateau d'échecs 3D holographique interactif et jouable en tactile ou par commande vocale.
*   **[domotic_map.ts](file:///n:/JARVIS/interfaces/frontend/src/domotic_map.ts)** : Représentation 3D extrudée des pièces de l'habitat pour visualiser et commuter l'état des appareils Home Assistant connectés.
*   **[cortex_map.ts](file:///n:/JARVIS/interfaces/frontend/src/cortex_map.ts)** : Graphe 3D représentant la constellation des souvenirs neuronaux de ChromaDB et de la mémoire locale. Permet de modifier ou supprimer un souvenir en cliquant sur un nœud.
*   **[spatial_explorer.ts](file:///n:/JARVIS/interfaces/frontend/src/spatial_explorer.ts)** : Explorateur de fichiers 3D interactif représentant les dossiers sous forme de tores et les fichiers sous forme d'octaèdres 3D avec volet de prévisualisation.
*   **[swarm_lounge.ts](file:///n:/JARVIS/interfaces/frontend/src/swarm_lounge.ts)** : Salon de discussion en 3D isométrique pour l'essaim d'agents de développement. Les agents PM, DEV et QA y déambulent sous forme de sphères physiques et échangent des bulles de dialogue de télémétrie en temps réel pendant qu'ils codent.

### 🖼️ Composants d'Interface HUD & Widgets
*   **[widgets.ts](file:///n:/JARVIS/interfaces/frontend/src/widgets.ts)** : Gère le cycle de vie et l'affichage des widgets d'information (Météo locale, Calendrier Google, Deezer).
*   **[ha_dashboard.ts](file:///n:/JARVIS/interfaces/frontend/src/ha_dashboard.ts)** : Tableau de bord de raccourcis rapides pour le contrôle domotique de Home Assistant.
*   **[hand_tracking.ts](file:///n:/JARVIS/interfaces/frontend/src/hand_tracking.ts)** : Mode réalité augmentée (AR) s'appuyant sur la webcam et MediaPipe pour piloter l'interface HUD, glisser et redimensionner les widgets par simples pincements de doigts.
*   **[cards.ts](file:///n:/JARVIS/interfaces/frontend/src/cards.ts)** : Notifications système fluorescentes flottantes s'affichant en haut à droite avec minuterie de fermeture automatique.
*   **[holo_clock.ts](file:///n:/JARVIS/interfaces/frontend/src/holo_clock.ts)** : Horloge HUD holographique.
*   **[screen_capture.ts](file:///n:/JARVIS/interfaces/frontend/src/screen_capture.ts)** : Module frontend facilitant la capture d'écran pour l'envoyer au backend.

### 📂 Sous-dossiers UI & Panneaux
*   **[ui/](file:///n:/JARVIS/interfaces/frontend/src/ui)** :
    *   `draggable.ts` : Ajoute le support du glisser-déposer sur les éléments DOM.
    *   `carousel.ts` : Carrousel de médias et d'images.
    *   `effects.ts` : Effets sonores d'interface et animations lumineuses néon.
    *   `tips.ts` : Système d'affichage de conseils et raccourcis d'utilisation.
*   **[panels/](file:///n:/JARVIS/interfaces/frontend/src/panels)** :
    *   `antivirus_panel.ts` : Interface utilisateur pour lancer des analyses antivirus et voir les menaces détectées.
    *   `winget_panel.ts` : Terminal graphique affichant la progression des mises à jour Windows Winget en cours.
    *   `uninstaller_panel.ts` : Panneau de recherche et de déclenchement rapide de la désinstallation de programmes Windows.
    *   `shopping_panel.ts` : Visualisation graphique des todos et listes de courses.
    *   `image_panels.ts` : Galerie d'images affichant les images générées par IA ou trouvées sur le web.

---

## 🔌 MODULES EXTENSION CHROME & APPLICATION MOBILE

### 🌐 Extension Google Chrome (`chrome_extension/`)
Permet à JARVIS de contrôler le navigateur de l'utilisateur par l'intermédiaire d'un WebSocket local.
*   **[manifest.json](file:///n:/JARVIS/interfaces/chrome_extension/manifest.json)** : Fichier d'enregistrement de l'extension Chrome.
*   **[background.js](file:///n:/JARVIS/interfaces/chrome_extension/background.js)** : Script de fond qui ouvre la connexion avec le serveur local de JARVIS.
*   **[content.js](file:///n:/JARVIS/interfaces/chrome_extension/content.js)** : Script injecté dans les pages web. Dessine le curseur néon virtuel et exécute les clics et saisies demandés par JARVIS.

### 📱 Application Mobile (`mobile/`)
Version simplifiée du HUD optimisée pour les smartphones.
*   **[index.html](file:///n:/JARVIS/interfaces/mobile/index.html)** : Structure simplifiée du HUD mobile.
*   **[app.js](file:///n:/JARVIS/interfaces/mobile/app.js)** : Liaison WebSocket mobile, gestionnaire de requêtes vocales locales via la Web Speech API du téléphone.
*   **[orb.js](file:///n:/JARVIS/interfaces/mobile/orb.js)** : Version allégée de l'orbe 3D Three.js.
*   **[style.css](file:///n:/JARVIS/interfaces/mobile/style.css)** : Thème néon responsive pour mobile.

---

## 🧪 ENTRAÎNEMENT & INITIALISATION

### 🎙️ Entraînement Wake Word (`training/`)
*   **[jarvis_fr_colab.ipynb](file:///n:/JARVIS/tools/training/wakeword/jarvis_fr_colab.ipynb)** : Notebook Google Colab permettant d'entraîner le modèle de détection du mot clé de réveil ("jarvis") adapté à la voix en français de l'utilisateur.

### 🏁 Configuration Initiale (`_setup/`)
*   **[setup_deps.bat](file:///n:/JARVIS/tools/_setup/setup_deps.bat)** : Installation des dépendances avancées.
*   **[rename_user.py](file:///n:/JARVIS/tools/_setup/rename_user.py)** : Script utilitaire pour renommer les références utilisateur dans les fichiers d'empreintes biométriques vocales.
