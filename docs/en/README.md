# J.A.R.V.I.S documentation

*[Version française](../README.md)*

The documentation exists in **two languages**: French (`docs/fr/`, the reference) and English (`docs/en/`, a translation of the same documents). For the project itself (installation, features, license), see the [main README](../../README.md) (in English) and the [CHANGELOG](../../CHANGELOG.md) (in French).

## The documents

| Document | Contents | Français | English |
|---|---|---|---|
| **Files guide** | What every folder and file of the project does (core, modules, plugins, HUD, tools, tests, data) | [fr/JARVIS_FILES_GUIDE.md](../fr/JARVIS_FILES_GUIDE.md) | [JARVIS_FILES_GUIDE.md](JARVIS_FILES_GUIDE.md) |
| **Voice commands** | All the commands by category, language (French / English), briefing, routines, God's Eye View… | [fr/JARVIS_Commandes.txt](../fr/JARVIS_Commandes.txt) | [JARVIS_Commandes.txt](JARVIS_Commandes.txt) |
| **Features** | A concise inventory of what JARVIS can do, by area | [fr/jarvis_fonctionnalites.txt](../fr/jarvis_fonctionnalites.txt) | [jarvis_fonctionnalites.txt](jarvis_fonctionnalites.txt) |
| **God's Eye View** | On-demand installation, French layers (car parks, fuel, speed cameras…), commands, limits | [fr/VUE_DE_DIEU.md](../fr/VUE_DE_DIEU.md) | [VUE_DE_DIEU.md](VUE_DE_DIEU.md) |

`docs/AUDIT_BUGS.md` (full code audit) is a **local** file excluded from git: it is never pushed and has no English version.

## Where to start

- **Using JARVIS**: [Voice commands](JARVIS_Commandes.txt), then [Features](jarvis_fonctionnalites.txt).
- **Understanding the code**: [Files guide](JARVIS_FILES_GUIDE.md), then `CLAUDE.md` at the root (development conventions, local).
- **Switching language**: say "switch to English" or "passe en français" (or Settings, Appearance panel). The documentation language is chosen here: `fr/` or `en/`.

## Keeping both languages in sync

French is the reference. After changing a document in `docs/fr/`, regenerate its translation:

```powershell
venv\Scripts\python.exe tools\docs_traduire.py JARVIS_Commandes.txt
```

With no argument the tool retranslates every document of `docs/fr/`. It checks each line (links, code spans between backticks, bullets, headings) and reports any line it could not translate cleanly. This `README.md` and its French counterpart (`../README.md`) are written by hand.

Voice command phrases in `docs/en/JARVIS_Commandes.txt` are natural English translations of the French ones: in English mode JARVIS understands English by mapping it to the matching French command, so an approximate translation of a command may not be recognized as written.
