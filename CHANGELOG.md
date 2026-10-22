# Changelog

## Non publié

- **Mises à jour** : vérification discrète de la dernière release GitHub ~3 s après le lancement (désactivable : case « Vérifier au lancement » dans Paramètres), bannière dans les Paramètres avec les notes de version, « Télécharger la mise à jour » (ouvre la page de la release) et « Plus tard », bouton « Vérifier les mises à jour » en bas des Paramètres, carte discrète au lancement. Comparaison de versions par nombres (9.10.0 > 9.9.9). Backend : `core/mises_a_jour.py`. Aucune installation automatique.

## 9.5.1 — Confidentialité et réglages personnels

- **Prénom du propriétaire configurable** : JARVIS appelle le propriétaire par le réglage `user_name` (assistant de premier lancement, Paramètres), « Neyor » seulement s'il est vide. L'âge et la date de naissance du créateur ne sont plus dans le code (`createur_infos`, `jarvis_config.json`).
- **Télé** : adresse, MAC et diffusion lues dans `.env` (`TV_IP`, `TV_MAC`, `TV_BROADCAST`) ; sans `TV_IP`, les commandes de télé répondent par une explication. Chemins `C:\Users\<nom>` remplacés par des chemins calculés (Discord, JoyToKey, Deezer, Opera GX, profil du navigateur) ; éditeur de code du HUD : dossier relatif au projet au lieu de `n:\JARVIS`.
- **Confidentialité** : `PRIVACY.md` (services contactés, ce qui reste sur le PC) et télémétrie anonyme de ChromaDB désactivée.
- **Antivirus** : les menaces gardent un texte lisible (les boutons passent sous le texte).
- **Dépendances** : pillow 13.0.0 et certifi 2026.10.19 (failles corrigées).
- **CI** : audit des dépendances avec exceptions documentées (chromadb en mode serveur, js2py).

## 9.5.0 — Panneaux refaits, assistant de premier lancement, installateur

- **« Jarvis » mal transcrit rattrapé** (en veille seulement) : « j'en révise », « j'ai un vice », « jar vis », « djarvis », « garvis »… sont remplacés par « jarvis » avant le test du mot d'éveil (`normaliser_mot_eveil`, `ecoute_outils.py`).
- **Coffre-fort renforcé** : dérivation de la clé à 600 000 itérations (les anciens coffres à 100 000 sont migrés au prochain déverrouillage, fichiers rechiffrés puis remplacés en un bloc), mot de passe de 8 caractères minimum à la création, délai croissant après 3 erreurs (30 s, 60 s, 120 s… plafond 1 h, `vault_tentatives.json`), comparaison en temps constant, écritures atomiques, message du serveur affiché dans le HUD.
- **Ménage CSS** : 58 règles mortes des anciens panneaux désinstallateur / winget retirées de `10_uninstaller_menu.css` (839 → 360 lignes).
- **Code mort supprimé** : 5 fichiers jamais appelés (`tv_worker.py`, `core/stt.py`, `jarvis_agent.py`, `website_builder.py`, `local_agent_manager.py`), 17 fonctions sans appelant (dont 7 de `spotify_controller` : les actions « spotify_* » passent par Deezer), le rappel d'alarme jamais défini, 41 imports inutilisés. Copies dans `scratch/code_mort_supprime_2026-10-19/`.
- **Module sports retiré** : `sports_web.py` supprimé, ainsi que les actions « sport_resultats / sport_classement / sport_live » et leur bloc dans le prompt. La recherche web SerpAPI (secours du LLM, navigateur agent, action `recherche_web`) vit désormais dans `module/recherche_web.py`.
- **Textes reformulés** : une centaine de messages de console, docstrings et prompts réécrits dans une quinzaine de fichiers (voix, vision, désinstallateur, compétences, lancement…). Aucun changement de comportement ; le banc des commandes reste à 0 différence. Copies d'origine dans `scratch/avant_reformulation_2026-10-19/`.
- **Fonctions renommées** : environ 145 noms de fonctions, classes et méthodes (Deezer, fichiers, Google, mémoire, météo/HA, désinstallateur, vision, quotas, envoi vers le HUD…) en 65 fichiers, appels, documentation et outils de test compris. Les noms de messages WebSocket et d'actions du HUD ne changent pas. Le banc des commandes (référence mise à jour) reste à 0 différence. Copies d'origine dans `scratch/avant_renommage_2026-10-19/`.
- **openWakeWord supprimé** (code, modèle `jarvis_fr.onnx`, dépendance, notebook d'entraînement, réglages `use_openwakeword` / `wakeword_threshold`) : le modèle ne reconnaissait pas toutes les voix. JARVIS transcrit chaque phrase (Silero VAD + Groq Whisper) et cherche « jarvis » dans le texte.
- **Interface : style « verre » futuriste** (`css/14_verre.css`) : tous les panneaux `.pm` (désinstallateur, winget, antivirus, domotique) passent en verre dépoli translucide, cadre néon à la teinte du module, coins repères, lignes de balayage. Courses, coffre-fort, recette et résultats d'images migrés vers ces panneaux (listes en cartes, cases en verre, boutons Orbitron). Plus aucune émoticône dans le HUD : icônes SVG au trait (boutons de la barre, paramètres, météo, globe, radar réseau — les drapeaux deviennent le code pays). Coffre-fort : plus d'`alert()` ni de `onclick` en ligne, noms de fichiers échappés. L'orbe est inchangé. Outils : `scratch/outils_test/capture_hud.py`.
- **Panneau « État du système »** (bouton ÉTAT du dock) : moteurs d'IA (actif / prêt / pause quota / absent, mis à jour toutes les 2 s), voix (micro, niveau en direct, locuteur reconnu), services (interfaces, mémoire vectorielle, Home Assistant, antivirus, musique, alarme) et ressources en jauges. Boutons « Tout tester » (requête minuscule à chaque moteur configuré + écoute du micro 1,5 s), test par moteur, « Tester le micro » et « Écouter ». Backend : `core/ws_etat_systeme.py` (messages `get_system_status`, `system_test`). Faux serveur de test mis à jour.
- **Assistant de premier lancement** (HUD, 5 étapes : profil et voix, clé d'IA, micro, empreinte vocale, récapitulatif) : s'ouvre seul quand aucune clé d'IA n'est utilisable. Chaque clé se teste avant d'être enregistrée (`core/ws_assistant.py`, requête minuscule avec la clé saisie, jamais renvoyée ni journalisée) ; l'enregistrement passe par `update_settings`. La voix choisie est mémorisée (`voix_jarvis`).
- **Installateur Windows** (`tools/installateur/`, Inno Setup) : installe pour l'utilisateur courant, installe Python 3.12 s'il manque, crée le venv et les dépendances, et lance JARVIS par un raccourci `pythonw.exe` (aucune console). `main.py` supporte l'absence de console ; une version installée sert `dist/` sans Vite. Corrections de `tools/_setup/dependances.bat` (parenthèses non échappées, fins de ligne CRLF) : le script s'arrêtait avant la fin.
- **Console futuriste** (`core/console_ui.py`) : libellés du fil en pastilles de couleur ; en grand terminal (au moins 100 x 30), tableau de bord plein écran (état en haut, fil encadré à gauche, panneaux moteurs d'IA avec pauses de quota / voix / ressources CPU-RAM-GPU-VRAM / session : niveau du micro, part de réponses locales / IA, latence moyenne ; services : HUD, Home Assistant, antivirus, musique, alarme — le dernier panneau est étiré jusqu'en bas). Le journal complet reste dans `data/jarvis_run.log` et le fil est réécrit dans le terminal à la fermeture. `"console_tableau": false` dans `jarvis_config.json` (ou `JARVIS_CONSOLE_TABLEAU=0`) rétablit le fil défilant avec bandeau épinglé ; petit terminal : bandeau compact.
- **Mises à jour majeures** : openai 3.35, mistralai 3.2, anthropic 1.15, google-genai 2.31, oauthlib 4.0, rich 15 (Python) ; vite 8.3, three 0.186, typescript-eslint 8.72 (interface). Retirés car inutilisés : google-generativeai et google-ai-generativelanguage (ancien SDK Gemini jamais importé), grpcio-status. requirements.txt aligné sur les versions réellement installées et testées (il ne pouvait plus se résoudre : conflit protobuf) ; protobuf reste en 6.33.6. Non montés : websockets 17 (google-genai exige < 17) et TypeScript 7 (typescript-eslint plante dessus). pip-audit : 70 → 7 vulnérabilités, toutes sans correctif (chromadb, js2py). Outils : `scratch/outils_test/verif_rapide.py` et `test_clients_llm.py`.
- **Dépendances : suite** : mcp 2.2.0, cryptography 50.0.2, setuptools 83.0.0 ; `transformers` (inutilisé) désinstallé ; PyPDF2 (abandonné) remplacé par pypdf 6.21.1 (lecture et fusion de PDF, `file_manager.py` et `document_generator_resolver.py`). Correctif au passage : avec mcp 2.x, la liste des outils MCP revenait toujours vide (`inputSchema` renommé `input_schema`). pip-audit : 9 vulnérabilités restantes (chromadb et js2py sans correctif, oauthlib 4 non testé). Versions d'avant : `scratch/outils_test/pip_freeze_avant_maj2_2026-10-20.txt`.
- **Failles de dépendances corrigées** : 11 paquets montés en version corrective ou mineure (aiohttp 3.14.4, pillow 12.3.0, pyasn1 0.6.4, soupsieve 2.9, anyio 4.14.2, httplib2 0.32.0, multidict 6.9.1, werkzeug 3.1.9, fsspec 2026.6.0, pydantic-settings 2.14.2, tinytag 2.3.0). pip-audit : 70 → 19 vulnérabilités. Restent : cryptography 50, oauthlib 4, setuptools (majeures), mcp 2.2.0 (dépendance mcp-types indisponible), chromadb et js2py (sans correctif). Versions d'avant : `scratch/outils_test/pip_freeze_avant_maj_2026-10-20.txt`.
- **Voix de JARVIS rétablie** : edge-tts 7.2.8 était refusé par Microsoft (403) et JARVIS parlait avec la voix de secours de Windows ; passage à 7.3.1.
- **Mises à jour de sécurité et de stabilité** (versions mineures, le reste bloqué) : cryptography 49, certifi, urllib3, requests, aiohttp, idna, sherpa-onnx 1.13.8, SpeechRecognition, pyatv 0.18, zeroconf, pycaw ; interface : vite 6.4.4, eslint et 5 failles npm des outils de construction corrigées. onnxruntime-gpu 1.26 inchangé (CUDA).
- **requirements.txt aligné sur les versions réellement utilisées** (il demandait rich 15 et anthropic 0.98, jamais testés avec JARVIS).

- **Bouton « Stopper JARVIS » retiré** (en bas à droite) : JARVIS comprend maintenant « stop » / « tais-toi » à la voix ; seul reste le bouton du micro.

**Style commun** pour le désinstallateur, les mises à jour (winget), la sécurité (antivirus) et la domotique : même cadre, en-tête déplaçable, recherche et pastilles de filtre, lignes et tuiles, une couleur par module, icônes vectorielles au lieu des emojis (`css/13_panneaux_modules.css`, `panels/pm_utils.ts`).
- **Désinstallateur** : taille et date d'installation (lues dans le registre), tri par nom / taille / date, action « Désinstaller » au survol, désinstallation en trois étapes visibles (désinstallation, analyse des traces, nettoyage) ; plus de fenêtres d'alerte du navigateur.
- **Mises à jour** : compteur et heure de vérification, versions « actuelle → nouvelle », état de chaque mise à jour sur sa ligne (le serveur indique le paquet en cours), journal repliable qui s'ouvre en cas d'échec ; « Tout » reste une seule commande winget --all (une seule demande d'autorisation Windows).
- **Sécurité** : anneau d'avancement, fichiers analysés, menaces, durée ; couleur selon l'état (analyse, sain, menace) ; une carte par menace avec ses actions ; protection en temps réel réglable depuis l'en-tête. Prénom écrit en dur retiré du message vocal de fin.
- **Domotique** : catégories en pastilles, tuiles compactes, états lisibles (« Allumée · 80 % », « Allumé · 142 W », « 19,4 °C », « À la base · 100 % »).
- **Corrigé** : les interrupteurs et « Actualiser » de la domotique ne faisaient plus rien après une reconnexion du HUD (connexion gardée du démarrage) ; le bouton « Protection temps réel » du menu n'enregistrait pas le réglage. Noms de programmes et d'appareils échappés dans le HTML. « Jarvis, oui. » ouvrait le calendrier : un simple acquiescement (« oui », « d'accord », « merci »…) n'est plus envoyé à l'aiguillage d'intentions par l'IA.

## 9.5.0 — 2026-10-08 — Corrections de l'audit complet

**Console refaite**
- **Tableau de bord en direct** : bandeau épinglé en bas du terminal (micro, voix reconnue et similarité, temps de session, HUD connectés, moteur IA, moteurs en pause, CPU/RAM, morceau en cours, modèle Ollama chargé), rafraîchi deux fois par seconde ; le fil défile au-dessus et reste consultable.
- **Fil des échanges** : ce que dit la personne (prénom, ou CLAVIER / INVITÉ) et ce que répond JARVIS, avec qui a répondu (résolution locale, Gemini, Ollama…), le délai et la similarité de la voix. Seuls l'essentiel, les avertissements et les erreurs s'affichent ; le détail technique complet, horodaté, va dans data/jarvis_run.log (« "console_detail": true » dans jarvis_config.json pour tout afficher). Couleurs : l'utilisateur en doré, JARVIS en cyan, modules en gris-bleu.
- **Morceau en cours** (bandeau et widget musique du HUD) : lu directement sur la page Deezer pilotée — titre, artiste, lecture/pause et position exacts. Avant, l'historique d'écoute affichait toujours le morceau précédent.
- **Deezer impossible à afficher** depuis la barre des tâches (même JARVIS fermé) : pour agir en arrière-plan, JARVIS rendait la fenêtre transparente et non activable ; une fenêtre déjà « calque » (Electron) gardait l'opacité 0 à la remise en état. Opacité rétablie, et réparation automatique des fenêtres de Deezer au démarrage, à « ouvre Deezer » (désormais au premier plan) et après chaque opération invisible.
- **Musique plus rapide** : Deezer est rendu pilotable (relancé si besoin, ~13 s à froid) pendant la recherche et la correction du nom, et non plus après (« joue Werenoi » : 20 s).
- **« Passe la musique »**, « change de chanson », « zappe ce morceau » passent au morceau suivant (la playlist était relancée).
- **Artistes mal transcrits** : « joue Werenoi » entendu « au renoir » ou « ou est renoi » lançait un autre titre. Quand le titre trouvé ne correspond pas à la demande, JARVIS cherche l'artiste réellement prononcé (classement des artistes Deezer, puis Gemini avec recherche Google), seulement si la proposition ressemble à ce qui a été entendu.

**Commandes mal comprises**
- **Ordre de priorité réel** : les resolvers passaient dans l'ordre alphabétique, avant la chaîne prévue. Une seule liste ordonnée, du plus précis au plus général (`_ORDRE_RESOLVEURS`, `core/traitement.py`) ; un resolver en erreur ne bloque plus la suite. Le pré-filtre vocal `executer_action_pc`, qui doublait la chaîne avec des règles grossières, est supprimé.
- **Alarmes, minuteurs, rappels** traités localement (`module/alarmes_local.py`) : « mets une alarme à 7 h » ou « mets un minuteur de 5 minutes » partaient dans Deezer. Compte à rebours sur le HUD, « arrête le minuteur », « rappelle-moi de… dans 20 minutes ».
- **Heures comprises** : « dans 2h30 », « dans une heure », « 7h du soir », « 8h et demie », « dans 90 secondes », « demain à 6h30 » ; une heure invalide n'est plus une erreur.
- **Mots entiers** au lieu de sous-chaînes : « lance le radar réseau » ne lance plus EA App, « arrête le téléchargement » n'éteint plus la télé, « recette du carpaccio » ne lance plus l'autopilote, « fais une visite guidée » ne lance plus l'essaim, « lance le jeu Minecraft » n'ouvre plus les échecs, « il fait froid ? » n'est plus un coup d'échecs.
- **Deezer** n'est cherché que pour une vraie demande de musique ; « arrête la musique » ne ferme plus tous les navigateurs ; le volume sans cible règle le PC.
- **Calcul** sans `eval()` et seulement sur une vraie demande (« le PSG a gagné 3-0 » n'est plus une soustraction) ; puissances et racines gérées.
- **Listes** : « vide / efface ma liste de courses » et « supprime le lait de ma liste » agissent enfin.
- **Mémoire** : l'oubli exige une demande explicite ; le cache sémantique ne répond plus pour les actualités, scores, prix.
- Corrigés aussi : « mémoire » (RAM), batterie d'un téléphone, capitales accentuées, heure dans une autre ville, sous-titres, compétences listées, changement de voix, recette qui avalait la commande suivante, ouverture « ouvre la calculatrice », dossiers avec article.

**Sécurité**
- **Enrôlement vocal** : une voix inconnue ne peut plus s'ajouter au profil du créateur ; seul le créateur enregistre la voix d'autrui.
- **Mode invité** appliqué aux resolvers (autopilote, essaim, plugins, désinstalleur, mémoire, coffre, compétences…), plus seulement aux actions de l'IA.
- **Confirmations** : envoi et suppression d'e-mails, suppression d'événements et de tâches, partage Drive, autopilote, création de plugin, auto-évolution du code, suppression d'une menace. Les réponses vocales ponctuées (« Oui. », « oui, vas-y ») sont comprises ; la question ouvre la session vocale et s'affiche sur tous les HUD.
- **Contrôle de sûreté** du code généré renforcé (contournements par `getattr`, `importlib`, `open(…, "w")`, `__subclasses__` bloqués) ; les scripts de l'essaim sont contrôlés avant exécution et Node tourne avec ses permissions limitées au dossier du projet.
- **Désinstalleur** : l'échec ou l'annulation n'est plus annoncé « terminé » ; les résidus doivent porter exactement le nom du programme, et un nom partagé (Python 3.12 / 3.14) ou un dossier en cours d'utilisation est écarté.
- **Antivirus temps réel** : n'arrête plus les programmes lancés depuis %TEMP% (installeurs, mises à jour) — simple alerte ; alertes affichées et annoncées.
- **Coffre-fort** : reverrouillage après 10 min, l'original peut être mis à la corbeille, plus d'écrasement de fichiers du même nom.
- Auto-évolution du code et création de plugins rebranchées, réservées au créateur, avec confirmation et consignes à jour.

**Fonctions qui ne marchaient pas**
- **Vision** (« clique sur… », caméra, vision du navigateur) : client lu avant sa création.
- **Sans clé Gemini**, la moitié des plugins ne se chargeait pas ; clés changées dans les Paramètres prises en compte sans redémarrer (client Gemini différé).
- **Écoute non bloquante** pendant le traitement d'une commande ; les commandes clavier attendent leur tour au lieu d'être jetées ; « stop » au clavier fonctionne ; une alarme sonne même après un « stop ».
- **Moteurs IA** : les questions d'actualité vont d'abord à Gemini (recherche Google) ; une réponse interrompue n'est plus répétée par le moteur suivant ; interrupteurs des API des Paramètres appliqués.
- **Extension Chrome** acceptée par le WebSocket et passée en Manifest V3 ; agent web : bons chemins (extension, Opera GX).
- **Dossiers réels de Windows** (Bureau, Documents, Images sous OneDrive) pour l'ouverture, le tri, les documents générés.
- **« Stop » à la voix** : un « stop » bref dit pendant que JARVIS parle était jeté sans être transcrit (seule la transcription intermédiaire, après 1,2 s de parole continue, pouvait le voir) : il est maintenant transcrit et coupe la parole (« stop », « arrête », « tais-toi », « silence », « chut », « ça suffit »).
- **Capture du micro faussée** : le flux 48 kHz était ramené à 16 kHz en gardant un échantillon sur trois sans filtre passe-bas : sifflantes, souffle et bruit au-dessus de 8 kHz se repliaient dans la bande de la voix, d'où une empreinte vocale instable (0,57 à 0,66 en usage contre 0,77 à 0,89 entre échantillons d'enrôlement) et une transcription moins nette. Filtre anti-repliement ajouté (-68 dB sur le repliement, voix intacte) ; le gain logiciel n'écrête plus avant filtrage. Les profils vocaux sont à réenregistrer ; « enregistre ma voix » tapé au clavier du HUD lance l'enrôlement même si la voix n'est plus reconnue. L'audio des phrases d'enrôlement est désormais conservé (sample_N.wav) : un changement de modèle de reconnaissance recalcule les empreintes sans réenregistrer. (WeSpeaker ResNet293, meilleur sur le papier, testé puis écarté : il séparait moins bien les voix réelles que CAM++.)
- **« Stop » mal transcrit** : un mot isolé entendu par-dessus la voix de JARVIS devenait « top », « step » ou « c'est toi » (pour « tais-toi ») : Whisper reçoit une amorce avec le vocabulaire d'arrêt, et ces variantes sont acceptées dans un énoncé bref.
- **Intention reformulée** : « mets une alarme à 10h » proposée par l'aiguillage IA repartait à l'IA (alarmes, minuteurs et échecs n'étaient pas consultés pour la phrase reformulée).
- **Session vocale** : elle ne se ferme plus pendant une commande longue (lancement de Deezer) ; les 20 s comptent depuis la dernière parole de JARVIS.
- **« Ferme Deezer »** : Whisper entend « ferme 10 heures » (« Deezer » ≈ « dizeur ») — après un verbe d'application, « 10 heures » est compris comme Deezer ; et Deezer, absent du catalogue, ne pouvait pas être fermé.
- **Fermeture d'applications** : demande de fermeture d'abord (Word, Excel… peuvent proposer d'enregistrer ; avant, ils étaient tués d'office), arrêt forcé au bout de 3 s seulement pour musique, messageries et lanceurs ; « Update.exe » (installeur partagé par de nombreuses applis) n'est plus tué avec Discord ; refusé en mode invité.
- **« J'ai envie d'écouter de la musique »** lance directement la playlist (la formule était prise pour un titre à chercher).
- **Reconnaissance de la voix** : une voix reconnue le reste une minute pour les phrases courtes (seuil 0,50 au lieu de 0,60 ; une autre voix obtient ~0,40) — plus de bascule en mode invité au milieu d'une conversation.
- **Mémoire sémantique** : « raconte-moi une histoire », une blague, une idée… ne resservent plus mot pour mot la réponse précédente.
- **Moteurs IA** : Gemini 3.5 Flash-Lite répond en premier (1re phrase en ~1,2 s) ; Groq gratuit (8 000 jetons/min pour un prompt de ~6 000) ne passait qu'une question par minute et faisait attendre jusqu'à 20 s — il sert désormais de secours. Gemini 3.8 Flash remplace 3.7 en 2e choix. Mistral passe à Ministral 8B (Medium, Small et 14B refusés sur le compte gratuit) avec lecture phrase par phrase. Une limite atteinte met le moteur en pause aussitôt, sans attente silencieuse de la bibliothèque. « J'ai envie de musique » lance la musique par défaut au lieu d'ouvrir Spotify.
- **Ollama (local)** : gemma4:12b (meilleur français sur 12 Go de VRAM, 1re phrase ~2 s) puis gemma4 e4b (~1 s) ; llama3.1:8b et mistral-nemo retirés. Réponse lue phrase par phrase, modèle préchargé dès « active le mode local », mémoire vidéo libérée après 10 min sans usage (1 h en mode local) au lieu d'être gardée jusqu'au redémarrage.
- **Heure et date sans IA** : « il est quelle heure ? », « on est quel jour ? », mois, année répondent instantanément (elles partaient aux moteurs en ligne : jusqu'à 20 s quand Groq ne répondait pas). Groq bloqué abandonné après 8 s au lieu de 15, et son erreur enfin affichée.
- **HUD figé** pendant certaines commandes (recherche Spotify, appel WhatsApp, musique YouTube, modes boulot/gaming, vision, volume Deezer/Spotify) : des pauses bloquaient tout le serveur jusqu'à 14 s, bouton stop et confirmations compris. Elles laissent désormais la main.
- **Météo** : le widget et « quel temps fait-il » suivent la position réelle de l'appareil (celle du globe), plus la ville de la configuration.
- **Liste de courses** : panneau refait (champ, bouton « Ajouter », croix de fermeture n'avaient plus de style), compteur d'articles et état vide.
- HUD : bouton « Parcourir » de l'atelier, résultat d'export du coffre, vidage du cache, alertes antivirus, popup de confirmation fermé partout, état de Home Assistant exact, une seule confirmation pour le coffre.
- Google : titre vide ne supprime plus le premier élément, mails non marqués comme lus, dates lues en clair, appels hors de la boucle du HUD.
- Blocage d'IP : échec signalé quand les droits administrateur manquent.
- « Monsieur » remplacé par le prénom de la personne qui parle dans toutes les réponses.

**Installation et démarrage**
- `requirements.txt` : `chess`, `pytz`, `reportlab`, `send2trash`, `uiautomation` (JARVIS ne démarrait pas sur un PC neuf).
- `install.bat` et `tools/_setup/dependances.bat` imposent Python 3.12 ; l'installateur installe enfin `requirements.txt` et retrouve la racine du projet ; Node 22.
- Au démarrage, seule une ancienne instance de JARVIS est arrêtée (un autre projet Vite sur le port 5173 n'est plus tué).
- Code mort retiré : `core/brain.py`, Gemini Live (`core/gemini_live_bridge.py`, `src/live_audio.ts`).

## 2026-10-07 — Suppression de l'interface mobile

- **Dossier `interfaces/mobile/` supprimé** (page web pour smartphone), ainsi que son serveur HTTP sur le port 8080, le bouton MOBILE du carrousel et sa fenêtre d'adresse.
- **Le WebSocket n'écoute plus que sur la machine** (`localhost:8765`, et non plus sur tout le réseau) : un appareil du réseau local ne peut plus piloter JARVIS. Les pages servies depuis une adresse du réseau local sont aussi refusées.
- Retirés côté backend : la commande `mobile_command`, l'envoi de la voix au téléphone (`jarvis_audio`), le drapeau `_skip_pc_audio` (qui ne fonctionnait d'ailleurs pas : il était lu dans `core.config`, où il restait toujours faux) et l'affichage de l'adresse réseau au démarrage.

## 2026-10-07 — Globe 3D : correction de tous les bugs recensés

- **Un seul resolver** : `plugins/globe_resolver.py` (supprimé) et `module/globe_local.py` s'enregistraient sous le même nom et l'emportaient selon l'ordre de chargement ; la version du plugin envoyait « affiche la Terre » vers un lieu-dit près de La Rochelle, « ma position » au Bénin, et ne savait ni fermer, ni tracer d'itinéraire.
- **Plus de faux lieux** : un lieu n'est retenu que si Nominatim le juge assez important (les lieux-dits, rues, commerces homonymes sont écartés) ; « montre-moi la Terre » affiche la vue spatiale. Les déclencheurs génériques (« trouve », « où est »...) laissent la main à l'IA s'il n'y a pas de vrai lieu.
- **Itinéraires** : « de A à B » fonctionne (le « à » accentué n'était pas reconnu) ; tracé en grand cercle, cadré au milieu réel du trajet (Tokyo → Los Angeles visait l'Afrique).
- **Ma position** : position actuelle donnée par le service de localisation de Windows (Wi-Fi / réseau, à quelques kilomètres près, annoncée comme telle) au lieu de la géolocalisation du navigateur, refusée dans la fenêtre JARVIS ; à défaut, le domicile réglé dans JARVIS, présenté comme tel.
- **En-tête du globe retiré** (« J.A.R.V.I.S / SYSTÈME DE NAVIGATION / by Neyor »).
- **Vols** : un deuxième vol ne bascule plus sur la carte 2D ; la Terre reste centrée (le pivot de la caméra restait sur le dernier lieu survolé) ; altitude selon le type de lieu ; trajectoire sphérique qui ne traverse plus la Terre ; plus de vol vers 0,0 si un lieu est inconnu.
- **Carte 2D** : fermée avec le globe (elle réapparaissait à la réouverture) ; recentrée si un vol arrive pendant qu'elle est affichée ; imagerie satellite Esri avec noms de lieux (les tuiles Google n'étaient pas une API publique).
- **Zoom vocal** (« rapproche-toi », « éloigne-toi ») quand le globe est ouvert (le frontend signale son état au backend).
- **Gestes** : les mains tournent la Terre avec ses marqueurs et itinéraires (ils restaient en place) ; zoom à deux mains cohérent.
- **Performances** : la boucle de rendu du globe ne tourne plus que globe affiché (elle tournait en permanence depuis le démarrage de JARVIS) ; étoiles créées une seule fois.
- Divers : double fermeture du bouton ✕, fermeture puis réouverture rapides, latitude 0 traitée comme absente, horloge marquée « UTC » qui affichait l'heure locale, en-tête du globe masqué par le bouton CLAVIER.
- **Échecs** : « on joue aux échecs » ne lève plus d'erreur JavaScript (message sans état de partie).

## 2026-10-07 — Suppression du mode hologramme, vues 3D autonomes

- **Mode hologramme supprimé** : formes 3D, jeu de balle, dock, HUD, raccourcis clavier, bouton HOLO du carrousel et commandes vocales « mode hologramme » / « miroir holo » (`hologramme.js`, `hud/holo.ts` retirés).
- **Les vues 3D s'ouvrent directement à la voix**, sans passer par le holo : explorateur spatial, maison 3D, cortex, échecs, radar réseau. Nouveau module `vues_3d.js` (rendu Three.js avec lueur et fond étoilé, contrôle par les mains via la webcam conservé) piloté par `hud/vues_3d.ts`.
- **Une seule vue à la fois** : avant, ouvrir la maison laissait le cortex actif (jusqu'à trois vues superposées), et fermer le radar rouvrait le cortex. Fermer une vue ramène désormais à JARVIS.
- **Fermeture à la voix** : « ferme le cortex », « ferme la maison », « ferme l'explorateur spatial », « ferme le radar », « ferme la vue 3D », « retour Jarvis » (et l'ancien « ferme l'hologramme »). Bouton « ⌂ RETOUR JARVIS » conservé.
- **Corrigé au passage** : « explorateur spatial / 3D » ouvrait l'Explorateur Windows (`plugins/app_launcher_resolver.py`), si bien que l'explorateur 3D ne s'ouvrait jamais à la voix ; « quitte les échecs » relançait le plateau (`plugins/dom_controller_resolver.py`). Le message d'erreur de la webcam (accès refusé…) s'affiche maintenant.

## 2026-10-06 — Contrôle Deezer en arrière-plan (`controller/deezer_cdp.py`)

- **Tout se fait en arrière-plan** : JARVIS pilote directement la page de l'appli Deezer par son port de débogage local (127.0.0.1). Deezer n'est jamais affiché ni mis au premier plan, qu'il soit réduit, caché dans la zone de notification ou sous un jeu plein écran. Commandes en 0,1 à 3 s.
- **Un titre est lancé depuis la liste des résultats de recherche** (et non plus depuis la page de l'album ou du titre) : Deezer enchaîne ensuite sur les titres suivants. La ligne visée a exactement ce titre et le bon album (pas de version karaoké ou de reprise).
- **Albums, playlists (les vôtres d'abord), « Top titres » ou mix d'un artiste** : ouverture par identifiant puis bouton de lecture de la page ou de la carte de l'artiste.
- **Résultat vérifié exactement** (identifiant du morceau ou du contexte de lecture) : en cas d'échec, JARVIS le dit au lieu d'annoncer « C'est parti ».
- **Pause, reprise, suivant, précédent** passent par le lecteur interne de Deezer : fini les « déjà en pause » erronés.
- **Plus aucun lien deezer://** : ils restauraient Deezer et lui donnaient le focus, ce qui vous sortait de votre jeu.
- Deezer est lancé avec ce port par JARVIS. S'il a été démarré autrement (raccourci, démarrage de Windows), JARVIS le relance une fois, réduit, à la première commande qui lance une musique.
- L'artiste choisi est l'homonyme le plus suivi (l'API Deezer plaçait parfois un « Ziak » à 252 fans avant le vrai).
- En secours, si ce pilotage est indisponible : accessibilité Windows, sans lien deezer:// ni clic souris réel, avec la même vérification. Deezer réduit est rendu réceptif de façon invisible le temps de l'action (il refuse sinon les commandes d'accessibilité).

## 2026-10-06 — Découpage de `main.ts` (HUD)

`interfaces/frontend/src/main.ts` passe de **3 323 à ~115 lignes** : il ne fait plus qu'orchestrer le démarrage. Son contenu est réparti dans 24 nouveaux fichiers (tous sous 350 lignes), **sans changement de logique** : code déplacé à l'identique, ordre d'évaluation des modules et d'initialisation conservé.

- `hud/` : `state.ts` (état partagé), `dom_refs.ts`, `orb_state.ts`, `menu.ts`, `settings.ts`, `keyboard.ts`, `help_hud.ts`, `subtitles.ts`, `holo.ts`, `boot.ts`, `timer_clock.ts`, `control_buttons.ts`, `carousel_actions.ts`, `dom_automation.ts`.
- `ws/` : `connection.ts` (connexion, reconnexion, aiguillage), `message_types.ts`, `messages_system.ts`, `messages_holo.ts`, `messages_hud.ts` — les branches de l'ancien gestionnaire de messages, dans le même ordre.
- `panels/` : `code_workshop.ts` (Swarm 3D, Website Builder, éditeur), `confirm_dialog.ts`, `weather_temp_panels.ts`, `recipe_panel.ts`, `vault_panel.ts`.

Vérifié par un banc de test qui injecte ~120 messages et interactions dans le HUD original puis dans le HUD découpé, en comparant l'état de tous les éléments du DOM : aucune différence. Testé aussi avec le vrai backend (connexion, démarrage, paramètres, commandes).

## 2026-10-06 — Neyor, et JARVIS appelle chacun par son prénom

- **Le créateur s'appelle désormais Neyor** (prononcé « Néyor ») : prompt système, accueil, empreinte vocale (`backend/core/voiceprints/neyor/`), configuration (`user_name`), faits mémorisés et historique des conversations.
- **Chacun est appelé par son prénom** : les quelque 250 réponses qui disaient « mylane » à tout le monde s'adressent maintenant à la personne qui a donné l'instruction, reconnue par la biométrie vocale (« Très bien Clara… »). Un invité n'est appelé par aucun prénom, et le clavier du HUD local compte comme le créateur. Nouveau module `core/interlocuteur.py` (`nom_espace()`, `nom_virgule()`, `nom_ou_utilisateur()`, `CREATEUR`, `NOM_CREATEUR`).
- **Prompts des IA** (système, vision, agent navigateur, recherche, Grok…) : le créateur reste nommé en dur (Neyor), le reste parle de la personne qui donne l'instruction. La consigne d'identité dit au LLM quel prénom employer selon le profil (créateur, utilisateur secondaire ou invité).
- **Prononciation** : la synthèse vocale dit « Néyor » ; le texte affiché garde « Neyor » (`core/speech.py`).
- **Correctif** : un fragment sans lettre ni chiffre (ex. un « » » isolé) n'est plus envoyé à la synthèse vocale, où il faisait échouer edge_tts.

## 2026-10-05 — Confirmation HUD, accueil, créateur

- **Confirmation par clic HUD réparée** : la désinstallation, le nettoyage de résidus et les suppressions (coffre-fort, explorateur spatial) s'exécutent désormais en tâche de fond (`core/ws_handler.py`). Avant, le gestionnaire WebSocket restait bloqué à attendre la confirmation et ne lisait le clic qu'après les 20 s d'expiration, donc l'action était toujours annulée ; seule la confirmation vocale fonctionnait.
- **Phrase de lancement** : « Tous mes systèmes sont opérationnels » remplacée par un accueil généré par l'IA à chaque démarrage (style JARVIS, adapté à l'heure, jamais deux fois le même), dans un thread pour ne pas retarder l'écoute. En secours si l'IA ne répond pas : « Bonjour/Bonsoir Neyor. Je suis prêt. Que puis-je faire pour vous ? ».
- **Plus de flatterie** : consigne explicite dans le prompt (ne plus parler du « génie » du créateur, pas de compliments gratuits) ; quand le créateur parle, JARVIS lui répond directement à la deuxième personne.
- **README traduit en anglais.**
- **Questions sur le créateur** : suppression des réponses préfaites (10 dans `commandes_locales_sections.py`, 1 dans `plugins/extras.py`). L'IA répond désormais avec ses propres mots grâce à une consigne ajoutée au prompt système (`core/prompt_builder.py`), en s'adressant directement au créateur.
- **Personnalité JARVIS d'Iron Man** (`core/prompt_builder.py`) : majordome numérique flegmatique et loyal, humour pince-sans-rire jamais annoncé, aucun point d'exclamation, vouvoiement, tournures typiques (« Si je puis me permettre… », « Je crains que… »), répliques toujours variées.
- **Autres phrases préfaites remplacées par l'IA** : salutations, « comment tu vas », « qui es-tu », blagues et citations (`plugins/extras.py`), « que peux-tu faire » (le panneau d'aide du HUD s'ouvre toujours) et application inconnue (fin des 6 phrases renvoyant vers « Antigravity de chez Google »). Les remarques pendant les parties d'échecs et les réponses capitales/monnaies restent locales.

## 2026-10-05 — Découpage de `main.py`

`main.py` passe de **7 278 à ~300 lignes** : il ne fait plus qu'orchestrer le démarrage. Son contenu est réparti dans `backend/` (29 nouveaux fichiers, tous sous 450 lignes), **sans changement de logique** : code déplacé à l'identique, ordre d'initialisation conservé.

**Nouveaux fichiers**
- `core/` : `shared.py` (état partagé), `console_ui.py`, `voice_init.py`, `etat_parole.py`, `chargement_plugins.py`, `web_bridge.py`, `ai_clients.py`, `llm_chat.py`, `llm_providers.py`, `traitement.py`, `actions_ia.py`, `actions_ia_services.py`, `ws_handler.py`, `ws_reglages.py`, `ws_systeme.py`, `ws_securite.py`, `ecoute.py`, `ecoute_outils.py`, `micro.py`, `lancement.py`.
- `module/` : `commandes_locales.py`, `commandes_locales_sections.py`, `echecs_local.py`, `globe_local.py`, `cortex_service.py`, `domotique_sim.py`, `antivirus_live.py`, `system_stats.py`.
- `controller/` : `actions_pc.py`.

**Comment c'est organisé**
- Les variables globales de `main.py` (historique, session vocale, clients IA, clients WebSocket...) vivent dans `core/shared.py` et s'utilisent via `shared.NOM`, pour que tous les modules partagent le même état.
- Les 4 fonctions géantes ont été découpées branche par branche, sans toucher à leur contenu : le gestionnaire WebSocket (818 lignes), le dispatcher d'actions JSON (816), la boucle d'écoute (577) et les commandes locales (565).
- `main.py` reproduit l'ordre d'import d'origine des modules du projet : plusieurs d'entre eux figent leur configuration à l'import (variables d'environnement lues avant/après le chargement du `.env`, attributs de `builtins`).

**Code mort retiré** (jamais exécuté) : `resoudre_extras_locaux` et `resoudre_infos_systeme_localement` (les versions des plugins `extras.py` / `system_resolver.py` étaient celles réellement utilisées), `chercher_youtube`, `devrait_elevancer_vers_cloud`, `liberer_port`, `nettoyer_accent` et leurs helpers.

**Bugs latents corrigés au passage** (variables rendues locales par un `import` placé dans une autre branche de la même fonction) :
- « ouvre calculatrice » (et les autres apps standard) plantait en `UnboundLocalError`.
- « mets ma playlist » via le clavier (lien musique par défaut) plantait de la même façon.
- Bloquer une IP depuis le radar ne prononçait pas la confirmation vocale si les réglages n'avaient pas été sauvegardés avant dans la session.

**Vérifications** : compilation, Ruff (aucun nom indéfini), comparaison automatique des liaisons de noms de chaque fonction avant/après (identiques), comparaison des injections `builtins` et de l'état après démarrage (identiques), lancement réel de JARVIS (console identique) et 29 scénarios WebSocket rejoués sur l'ancienne et la nouvelle version (réponses identiques).

## 2026-09-15

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
