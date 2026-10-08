import builtins
import asyncio
import re
import os
from core.interlocuteur import nom_virgule

def nettoyer_accent(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

def _set_homepod_audio(actif: bool):
    """Bascule la sortie audio HomePod à chaud sans redémarrer."""
    import core.speech as speech_module
    try:
        if actif:
            from module.homepod_audio import jouer_sur_homepod
            speech_module._USE_HOMEPOD = True
            speech_module.jouer_sur_homepod = jouer_sur_homepod
        else:
            speech_module._USE_HOMEPOD = False
    except Exception as e:
        print(f"[HOMEPOD] Erreur bascule audio : {e}")
        return False
    os.environ["USE_HOMEPOD_AUDIO"] = "true" if actif else "false"
    return True

async def resoudre_dom_hud(cmd):
    """Gère le contrôle de l'interface graphique (DOM) du HUD via WebSocket."""
    t = nettoyer_accent(cmd.lower().replace("-", " ").strip())

    # S'il s'agit d'une commande complexe, composée ou contenant des formulaires,
    # on renvoie None pour laisser le "cerveau" IA (LLM) s'en occuper de façon autonome.
    exclusion_patterns = [
        r"\bet\b", r"\bpuis\b", r"\bprenom\b", r"\bnom\b", r"\bage\b", 
        r"\bsaisis\b", r"\btape\b", r"\becris\b", r"\bremplace\b", r"\blien\b"
    ]
    if any(re.search(pattern, t) for pattern in exclusion_patterns):
        return None

    # --- 1. PARAMÈTRES / CONFIGURATION (Commandes Simples et Instantanées) ---
    if any(k in t for k in ["ouvre les parametres", "affiche les parametres", "ouvre la config", "affiche la config", "ouvre les reglages"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#settings-button")
            return f"J'ouvre les paramètres de votre HUD{nom_virgule()}."
            
    if any(k in t for k in ["ferme les parametres", "masque les parametres", "ferme la config", "masque la config", "ferme les reglages"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#settings-close-btn")
            return f"Je ferme les paramètres{nom_virgule()}."

    # --- 3. TEXTE / SOUS-TITRES (HUD TEXT) ---
    # Le texte a ses tirets remplacés par des espaces (« sous titres ») : les mots-clés
    # écrits « sous-titres » ne correspondaient jamais. « desactive » est testé avant
    # « active », qu'il contient.
    if any(k in t for k in ["desactive les sous titres", "desactive le texte", "masque les sous titres", "masque le texte", "coupe le texte", "coupe les sous titres"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#subtitle-toggle")
            return f"Affichage des sous-titres désactivé{nom_virgule()}."

    if any(k in t for k in ["active les sous titres", "active le texte", "affiche les sous titres", "affiche le texte"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#subtitle-toggle")
            return f"Affichage des sous-titres activé{nom_virgule()}."

    # --- 4. MODE CLAVIER ---
    if any(k in t for k in ["active le clavier", "ouvre le clavier", "affiche le clavier"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#keyboard-toggle")
            return f"Clavier de commande activé{nom_virgule()}."
            
    if any(k in t for k in ["desactive le clavier", "ferme le clavier", "masque le clavier", "coupe le clavier"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#keyboard-toggle")
            return f"Clavier désactivé{nom_virgule()}."

    # --- 5. DÉTAILS DE RECETTE (RECIPE MODAL) ---
    if any(k in t for k in ["ferme la recette", "masque la recette"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#close-recipe")
            return f"Je ferme la fiche recette{nom_virgule()}."

    # --- 6. CAPTEURS INTÉRIEURS (TEMP PANEL) ---
    if any(k in t for k in ["ferme le panneau temperature", "ferme la temperature", "masque la temperature"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#tp-close-btn")
            return f"Je masque les capteurs intérieurs{nom_virgule()}."

    # --- 7. METEO PANEL (panneau Iron Man latéral) ---
    if any(k in t for k in ["ferme la meteo", "masque la meteo", "ferme le panneau meteo"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#wp-close-btn")
            return f"Je masque la météo{nom_virgule()}."

    # --- 8. SORTIE AUDIO HOMEPOD ---
    if any(k in t for k in ["passe ta voix sur le homepod", "mets ta voix sur le homepod",
                              "utilise le homepod", "active le homepod", "parle sur le homepod",
                              "voix sur le homepod", "bascule sur le homepod"]):
        ok = _set_homepod_audio(True)
        return f"Basculement sur le HomePod effectué{nom_virgule()}." if ok else f"Impossible de basculer sur le HomePod{nom_virgule()}."

    if any(k in t for k in ["repasse sur le casque", "reviens sur le casque", "desactive le homepod",
                              "coupe le homepod", "voix sur le casque", "bascule sur le casque"]):
        _set_homepod_audio(False)
        return f"Je repasse sur le casque{nom_virgule()}."

    # --- 9. WIDGET CALENDRIER ---
    if any(k in t for k in ["montre le calendrier", "montre moi le calendrier", "affiche le calendrier",
                              "ouvre le calendrier", "widget calendrier", "montre le widget calendrier"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("add_class", selector="#calendar-hud", class_name="hud-revealed")
            return f"Calendrier affiché{nom_virgule()}."

    if any(k in t for k in ["cache le calendrier", "masque le calendrier", "ferme le calendrier",
                              "retire le calendrier", "cache le widget calendrier"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("remove_class", selector="#calendar-hud", class_name="hud-revealed")
            return f"Calendrier masqué{nom_virgule()}."

    # --- 9. WIDGET MÉTÉO (panneau bottom-right) ---
    if any(k in t for k in ["montre moi la meteo", "montre la meteo", "affiche la meteo", "affiche moi la meteo",
                              "widget meteo", "montre le widget meteo", "affiche le widget meteo",
                              "montre moi le widget meteo"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("add_class", selector="#weather-hud", class_name="hud-revealed")
            return f"Widget météo affiché{nom_virgule()}."

    if any(k in t for k in ["cache le widget meteo", "masque le widget meteo", "ferme le widget meteo",
                              "retire le widget meteo"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("remove_class", selector="#weather-hud", class_name="hud-revealed")
            return f"Widget météo masqué{nom_virgule()}."

    # --- 10. WIDGET MUSIQUE ---
    if any(k in t for k in ["montre la musique", "montre moi la musique", "montre-moi la musique",
                              "affiche la musique", "affiche moi la musique", "affiche-moi la musique",
                              "widget musique", "montre le widget musique", "affiche le widget musique",
                              "montre le lecteur", "affiche le lecteur"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("add_class", selector="#music-hud", class_name="hud-revealed")
            return f"Widget musique affiché{nom_virgule()}."

    if any(k in t for k in ["cache la musique", "masque la musique", "ferme la musique",
                              "cache le widget musique", "masque le widget musique",
                              "cache le lecteur", "masque le lecteur"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("remove_class", selector="#music-hud", class_name="hud-revealed")
            return f"Widget musique masqué{nom_virgule()}."



    # --- 11b. MODE ÉCHECS ---
    # (« quitte / ferme / arrête les échecs » est laissé à module/echecs_local.py)
    if any(k in t for k in ["echecs", "echec", "mode echecs", "joue aux echecs", "on joue aux echecs", "on joue une partie d echecs", "partie d echecs", "jeu d echecs", "lance les echecs", "ouvre les echecs"])             and not any(k in t for k in ["quitte", "ferme", "arrete", "stop"]):
        if hasattr(builtins, "CONNECTED_CLIENTS") and builtins.CONNECTED_CLIENTS:
            import json, asyncio
            msg = json.dumps({"action": "chess_start"})
            await asyncio.gather(*[ws.send(msg) for ws in builtins.CONNECTED_CLIENTS], return_exceptions=True)
            return f"Déploiement du plateau d'échecs 3D{nom_virgule()}."

    # --- 12. MODE AR (HAND TRACKING) ---
    if any(k in t for k in ["active le mode ar", "active l'ar", "lance le mode ar", "active le tracking", "active les gestes", "lance l'ar", "ouvre l'ar"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#gestures-toggle:not(.active)")
            return f"J'active le mode de détection AR{nom_virgule()}."

    if any(k in t for k in ["desactive le mode ar", "desactive l'ar", "coupe le mode ar", "coupe l'ar", "ferme l'ar", "desactive le tracking", "desactive les gestes"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#gestures-toggle.active")
            return f"Je désactive le mode de détection AR{nom_virgule()}."

    # --- 13. MODE AR MIROIR ---
    if any(k in t for k in ["active le miroir ar", "active l'ar miroir", "bascule en ar miroir", "ar miroir"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#gestures-mirror:not(.active)")
            return f"Mode miroir AR activé{nom_virgule()}."

    if any(k in t for k in ["desactive le miroir ar", "desactive l'ar miroir", "reviens en ar direct", "ar direct"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#gestures-mirror.active")
            return f"Mode miroir AR désactivé. Retour au flux direct{nom_virgule()}."

    return None

# Injection builtins pour la résolution locale globale
builtins.resoudre_dom_hud = resoudre_dom_hud
