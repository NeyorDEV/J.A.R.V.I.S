"""
intent_dispatcher.py — Routeur d'intentions par function calling Gemini.

Quand aucun resolver par mots-clés n'a compris la phrase, on demande à un
modèle rapide de la mapper sur une intention connue. Chaque intention est
traduite en "phrase canonique" — une formulation que les resolvers existants
comprennent — puis repassée dans la chaîne de resolvers par main2.py.

Un faux négatif (pas d'appel de fonction) fait simplement suivre le chemin
historique vers interroger_ia : le dispatch est un raccourci, jamais un mur.
"""

from google.genai import types
from core.ai_clients import client_gemini as client

# Modèle rapide et peu coûteux : le routage est une tâche simple
INTENT_MODEL = "gemini-3.1-flash-lite"

_SYSTEM_INSTRUCTION = (
    "Tu es le routeur d'intentions de JARVIS, un assistant vocal domestique français. "
    "La phrase de l'utilisateur n'a pas été reconnue par les commandes par mots-clés. "
    "Si elle correspond CLAIREMENT et SANS AMBIGUÏTÉ à une des fonctions disponibles, appelle cette fonction. "
    "Sinon (conversation, question générale, demande d'information, requête complexe, "
    "phrase vague, interjection, ponctuation isolée, bruit de transcription, ou simplement "
    "le mot de réveil « jarvis » seul sans suite exploitable), "
    "ne fais AUCUN appel de fonction et ne réponds rien. "
    "En cas de doute, NE PAS appeler de fonction : un faux négatif est sans conséquence "
    "(la conversation continue normalement), un faux positif peut déclencher une action "
    "réelle non voulue par l'utilisateur."
)

_FUNCTION_DECLARATIONS = [
    {
        "name": "afficher_widget",
        "description": "Afficher ou masquer un widget du HUD : calendrier, météo ou lecteur de musique.",
        "parameters": {
            "type": "object",
            "properties": {
                "widget": {"type": "string", "enum": ["calendrier", "meteo", "musique"]},
                "visible": {"type": "boolean", "description": "true pour afficher, false pour masquer"},
            },
            "required": ["widget", "visible"],
        },
    },
    {
        "name": "lancer_application",
        # (l'exemple « spotify » faisait ouvrir Spotify pour « j'aimerais écouter de la musique »,
        #  au lieu de la musique par défaut — Deezer : c'est le rôle de controle_musique)
        "description": "Ouvrir/lancer une application ou un logiciel sur le PC nommé explicitement. "
                       "Pas pour une envie d'écouter de la musique : utiliser controle_musique ou jouer_musique_recherche.",
        "parameters": {
            "type": "object",
            "properties": {"nom": {"type": "string", "description": "Nom de l'application, ex: chrome, discord"}},
            "required": ["nom"],
        },
    },
    {
        "name": "fermer_application",
        "description": "Fermer/quitter une application sur le PC.",
        "parameters": {
            "type": "object",
            "properties": {"nom": {"type": "string"}},
            "required": ["nom"],
        },
    },
    {
        "name": "controle_musique",
        "description": "Mettre de la musique (« jouer » : playlist par défaut) ou contrôler la lecture en cours "
                       "(pause, reprise, changement de piste ; « passe / change la musique » = suivant).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["jouer", "pause", "reprendre", "suivant", "precedent"]},
            },
            "required": ["action"],
        },
    },
    {
        "name": "jouer_musique_recherche",
        "description": "Jouer un artiste, une chanson ou un genre musical précis.",
        "parameters": {
            "type": "object",
            "properties": {"recherche": {"type": "string", "description": "Artiste, titre ou genre, ex: Daft Punk"}},
            "required": ["recherche"],
        },
    },
    {
        "name": "volume",
        "description": "Monter ou baisser le volume sonore.",
        "parameters": {
            "type": "object",
            "properties": {"action": {"type": "string", "enum": ["monter", "baisser"]}},
            "required": ["action"],
        },
    },
    {
        "name": "minuteur",
        "description": "Démarrer ou annuler un minuteur / timer / rappel dans X temps.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["demarrer", "annuler"]},
                "duree": {"type": "string", "description": "Durée en français, ex: '10 minutes', '1 heure 30'"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "alarme",
        "description": "Programmer une alarme ou un réveil à une heure précise.",
        "parameters": {
            "type": "object",
            "properties": {"heure": {"type": "string", "description": "Heure au format français, ex: '7h30'"}},
            "required": ["heure"],
        },
    },
    {
        "name": "memoriser",
        "description": "Retenir/mémoriser une information que l'utilisateur veut que JARVIS n'oublie pas.",
        "parameters": {
            "type": "object",
            "properties": {"information": {"type": "string", "description": "L'information à retenir"}},
            "required": ["information"],
        },
    },
    {
        "name": "globe",
        "description": "Afficher un lieu, une ville ou un pays sur le globe 3D / la carte.",
        "parameters": {
            "type": "object",
            "properties": {"lieu": {"type": "string", "description": "Ville, pays ou lieu, ex: Tokyo"}},
            "required": ["lieu"],
        },
    },
    {
        "name": "tv",
        "description": "Lancer un contenu (film, série, vidéo, chaîne) sur la télévision.",
        "parameters": {
            "type": "object",
            "properties": {"contenu": {"type": "string", "description": "Le contenu à lancer sur la TV"}},
            "required": ["contenu"],
        },
    },
    # NOTE : « créer un site web » a été retiré de ce dispatcher. C'est une action
    # lourde (mobilise un swarm de 6 agents LLM, écrit des fichiers, prend des
    # minutes) qui a déjà son propre resolver dédié avec une vraie détection
    # verbe+nom (website_resolver.py). La confier à un modèle de classification
    # rapide sur du texte parfois très court est exactement le genre de décision
    # qui ne doit pas dépendre d'une heuristique faillible — vécu en réel : un
    # simple « Jarvis ! » sans suite a été classifié comme demande de site web.
]

_TOOLS = [types.Tool(function_declarations=_FUNCTION_DECLARATIONS)]


def _phrase_canonique(name: str, args: dict) -> str | None:
    """Traduit un appel de fonction en phrase que les resolvers par mots-clés comprennent."""
    if name == "afficher_widget":
        widget = args.get("widget")
        visible = args.get("visible", True)
        if widget == "calendrier":
            return "montre le calendrier" if visible else "masque le calendrier"
        if widget == "meteo":
            return "montre moi la meteo" if visible else "masque la meteo"
        if widget == "musique":
            return "montre la musique" if visible else "cache la musique"
        return None

    if name == "lancer_application":
        nom = (args.get("nom") or "").strip()
        return f"ouvre {nom}" if nom else None

    if name == "fermer_application":
        nom = (args.get("nom") or "").strip()
        return f"ferme {nom}" if nom else None

    if name == "controle_musique":
        return {
            "jouer": "mets de la musique",
            "pause": "mets en pause la musique",
            "reprendre": "reprends la musique",
            "suivant": "musique suivante",
            "precedent": "musique précédente",
        }.get(args.get("action"))

    if name == "jouer_musique_recherche":
        recherche = (args.get("recherche") or "").strip()
        return f"joue {recherche}" if recherche else None

    if name == "volume":
        return {"monter": "monte le volume", "baisser": "baisse le volume"}.get(args.get("action"))

    if name == "minuteur":
        if args.get("action") == "annuler":
            return "arrête le minuteur"
        duree = (args.get("duree") or "").strip()
        return f"mets un minuteur de {duree}" if duree else None

    if name == "alarme":
        heure = (args.get("heure") or "").strip()
        return f"mets une alarme à {heure}" if heure else None

    if name == "memoriser":
        info = (args.get("information") or "").strip()
        return f"retiens que {info}" if info else None

    if name == "globe":
        lieu = (args.get("lieu") or "").strip()
        return f"montre-moi {lieu}" if lieu else None

    if name == "tv":
        contenu = (args.get("contenu") or "").strip()
        return f"mets {contenu} sur la tv" if contenu else None

    return None


async def resoudre_intention_llm(texte: str) -> str | None:
    """Retourne la phrase canonique correspondant à l'intention, ou None.

    None = pas d'intention reconnue → main2.py continue vers interroger_ia.
    Toute erreur (réseau, quota…) retourne None : le dispatch ne bloque jamais.
    """
    try:
        response = await client.aio.models.generate_content(
            model=INTENT_MODEL,
            contents=[texte],
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                tools=_TOOLS,
                temperature=0.0,
            ),
        )
        function_calls = response.function_calls
        if not function_calls:
            return None
        fc = function_calls[0]
        phrase = _phrase_canonique(fc.name, dict(fc.args or {}))
        if phrase:
            try:
                print(f"[INTENT] Fonction choisie : {fc.name}({dict(fc.args or {})}) -> '{phrase}'")
            except Exception:
                pass  # Console sans UTF-8 : le log est cosmétique
        return phrase
    except Exception as e:
        print(f"[INTENT] Dispatch LLM indisponible : {e}")
        return None
