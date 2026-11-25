# Documentation de J.A.R.V.I.S

*[English version](en/README.md)*

La documentation existe en **deux langues** : le français (`docs/fr/`, la référence) et l'anglais (`docs/en/`, une traduction des mêmes documents). Pour le projet lui-même (installation, fonctionnalités, licence), voir le [README principal](../README.md) (en anglais) et le [CHANGELOG](../CHANGELOG.md) (en français).

## Les documents

| Document | Contenu | Français | English |
|---|---|---|---|
| **Guide des fichiers** | À quoi sert chaque dossier et chaque fichier du projet (cœur, modules, plugins, HUD, outils, tests, données) | [fr/JARVIS_FILES_GUIDE.md](fr/JARVIS_FILES_GUIDE.md) | [en/JARVIS_FILES_GUIDE.md](en/JARVIS_FILES_GUIDE.md) |
| **Commandes vocales** | Toutes les commandes par catégorie, la langue (français / anglais), le briefing, les routines, la Vue de Dieu… | [fr/JARVIS_Commandes.txt](fr/JARVIS_Commandes.txt) | [en/JARVIS_Commandes.txt](en/JARVIS_Commandes.txt) |
| **Fonctionnalités** | Inventaire concis de ce que JARVIS sait faire, par domaine | [fr/jarvis_fonctionnalites.txt](fr/jarvis_fonctionnalites.txt) | [en/jarvis_fonctionnalites.txt](en/jarvis_fonctionnalites.txt) |
| **Vue de Dieu** | God's Eye View : installation à la demande, couches France (parkings, carburants, radars…), commandes, limites | [fr/VUE_DE_DIEU.md](fr/VUE_DE_DIEU.md) | [en/VUE_DE_DIEU.md](en/VUE_DE_DIEU.md) |

`docs/AUDIT_BUGS.md` (audit complet du code) est un fichier **local**, exclu de git : il n'est jamais poussé et n'a pas de version anglaise.

## Par où commencer

- **Utiliser JARVIS** : [Commandes vocales](fr/JARVIS_Commandes.txt), puis [Fonctionnalités](fr/jarvis_fonctionnalites.txt).
- **Comprendre le code** : [Guide des fichiers](fr/JARVIS_FILES_GUIDE.md), puis `CLAUDE.md` à la racine (conventions de développement, local).
- **Changer de langue** : dites « passe en anglais » ou « switch to English » (ou Paramètres, panneau Apparence). La documentation, elle, se choisit ici : `fr/` ou `en/`.

## Garder les deux langues à jour

Le français est la référence. Après avoir modifié un document de `docs/fr/`, régénérer sa traduction :

```powershell
venv\Scripts\python.exe tools\docs_traduire.py JARVIS_Commandes.txt
```

Sans argument, l'outil retraduit tous les documents de `docs/fr/`. Il contrôle chaque ligne (liens, extraits de code entre accents graves, puces, titres) et signale toute ligne qu'il n'a pas pu traduire proprement. Ce `README.md` et sa version anglaise (`en/README.md`) s'écrivent à la main.

Chaque nouvelle phrase d'une commande vocale française est traduite en phrase anglaise naturelle dans `docs/en/JARVIS_Commandes.txt` : en mode anglais, JARVIS comprend l'anglais en le ramenant à la commande française correspondante ; une traduction approximative d'une commande peut donc ne pas être reconnue telle quelle.
