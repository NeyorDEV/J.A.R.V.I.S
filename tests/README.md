# Tests versionnés

Lancés par la CI (job « Tests (pytest) ») et en local :

```bash
venv\Scripts\python.exe -m pip install pytest
venv\Scripts\python.exe -m pytest tests -q
```

Ils ne testent que des **fonctions pures** : aucune dépendance de l'application (ni micro, ni GPU, ni réseau), seulement `pytest` et `requests`. Ils importent le code du backend tel quel (`conftest.py`).

| Fichier | Ce qu'il garde |
|---|---|
| `test_confirmation.py` | Réponse vocale à une confirmation : stricte pour les actions destructrices (« oui mais… » vaut refus), simple pour une question |
| `test_hallucinations.py` | Phrases inventées par Whisper sur du bruit, sans jamais bloquer une vraie commande (« active les sous-titres ») |
| `test_repeter.py` | « Répète » : reconnaissance de la demande, mémoire de la dernière réponse |
| `test_donnees_gev.py` | Conversions des données de la Vue de Dieu (électricité, sécheresse, trafic, Seveso, baignade, avalanche, vigilance) et présence de tous les jeux |
| `test_vue_de_dieu_commandes.py` | « Ouvre la vue de Dieu avec… » et pilotage des couches (analyse des phrases) |

Les essais qui ouvrent un navigateur (Vue de Dieu, HUD) ou simulent le PC restent dans `scratch/outils_test/` (non versionné) : voir son `README.md`.
**Règle** : une correction de bug ou une nouvelle commande vocale ajoute son cas ici si elle repose sur une fonction pure.
