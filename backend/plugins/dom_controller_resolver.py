import builtins
import asyncio
import re
import os

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
            return "J'ouvre les paramètres de votre HUD, Monsieur."
            
    if any(k in t for k in ["ferme les parametres", "masque les parametres", "ferme la config", "masque la config", "ferme les reglages"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#settings-close-btn")
            return "Je ferme les paramètres, Monsieur."

    # --- 3. TEXTE / SOUS-TITRES (HUD TEXT) ---
    if any(k in t for k in ["active les sous-titres", "active le texte", "affiche les sous-titres", "affiche le texte"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#subtitle-toggle")
            return "Affichage des sous-titres activé, Monsieur."
            
    if any(k in t for k in ["desactive les sous-titres", "desactive le texte", "masque les sous-titres", "masque le texte", "coupe le texte"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#subtitle-toggle")
            return "Affichage des sous-titres désactivé, Monsieur."

    # --- 4. MODE CLAVIER ---
    if any(k in t for k in ["active le clavier", "ouvre le clavier", "affiche le clavier"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#keyboard-toggle")
            return "Clavier de commande activé, Monsieur."
            
    if any(k in t for k in ["desactive le clavier", "ferme le clavier", "masque le clavier", "coupe le clavier"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#keyboard-toggle")
            return "Clavier désactivé, Monsieur."

    # --- 5. DÉTAILS DE RECETTE (RECIPE MODAL) ---
    if any(k in t for k in ["ferme la recette", "masque la recette"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#close-recipe")
            return "Je ferme la fiche recette, Monsieur."

    # --- 6. CAPTEURS INTÉRIEURS (TEMP PANEL) ---
    if any(k in t for k in ["ferme le panneau temperature", "ferme la temperature", "masque la temperature"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#tp-close-btn")
            return "Je masque les capteurs intérieurs, Monsieur."

    # --- 7. METEO PANEL (panneau Iron Man latéral) ---
    if any(k in t for k in ["ferme la meteo", "masque la meteo", "ferme le panneau meteo"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#wp-close-btn")
            return "Je masque la météo, Monsieur."

    # --- 8. SORTIE AUDIO HOMEPOD ---
    if any(k in t for k in ["passe ta voix sur le homepod", "mets ta voix sur le homepod",
                              "utilise le homepod", "active le homepod", "parle sur le homepod",
                              "voix sur le homepod", "bascule sur le homepod"]):
        ok = _set_homepod_audio(True)
        return "Basculement sur le HomePod effectué, Monsieur." if ok else "Impossible de basculer sur le HomePod, Monsieur."

    if any(k in t for k in ["repasse sur le casque", "reviens sur le casque", "desactive le homepod",
                              "coupe le homepod", "voix sur le casque", "bascule sur le casque"]):
        _set_homepod_audio(False)
        return "Je repasse sur le casque, Monsieur."

    # --- 9. WIDGET CALENDRIER ---
    if any(k in t for k in ["montre le calendrier", "montre moi le calendrier", "affiche le calendrier",
                              "ouvre le calendrier", "widget calendrier", "montre le widget calendrier"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("add_class", selector="#calendar-hud", class_name="hud-revealed")
            return "Calendrier affiché, Monsieur."

    if any(k in t for k in ["cache le calendrier", "masque le calendrier", "ferme le calendrier",
                              "retire le calendrier", "cache le widget calendrier"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("remove_class", selector="#calendar-hud", class_name="hud-revealed")
            return "Calendrier masqué, Monsieur."

    # --- 9. WIDGET MÉTÉO (panneau bottom-right) ---
    if any(k in t for k in ["montre moi la meteo", "montre la meteo", "affiche la meteo", "affiche moi la meteo",
                              "widget meteo", "montre le widget meteo", "affiche le widget meteo",
                              "montre moi le widget meteo"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("add_class", selector="#weather-hud", class_name="hud-revealed")
            return "Widget météo affiché, Monsieur."

    if any(k in t for k in ["cache le widget meteo", "masque le widget meteo", "ferme le widget meteo",
                              "retire le widget meteo"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("remove_class", selector="#weather-hud", class_name="hud-revealed")
            return "Widget météo masqué, Monsieur."

    # --- 10. WIDGET MUSIQUE ---
    if any(k in t for k in ["montre la musique", "montre moi la musique", "montre-moi la musique",
                              "affiche la musique", "affiche moi la musique", "affiche-moi la musique",
                              "widget musique", "montre le widget musique", "affiche le widget musique",
                              "montre le lecteur", "affiche le lecteur"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("add_class", selector="#music-hud", class_name="hud-revealed")
            return "Widget musique affiché, Monsieur."

    if any(k in t for k in ["cache la musique", "masque la musique", "ferme la musique",
                              "cache le widget musique", "masque le widget musique",
                              "cache le lecteur", "masque le lecteur"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("remove_class", selector="#music-hud", class_name="hud-revealed")
            return "Widget musique masqué, Monsieur."



    # --- 11. MODE HOLOGRAMME (HOLO) ---
    if any(k in t for k in ["holo", "mode holo", "hologramme", "mode hologramme", "active le mode hologramme", "active le mode holo", "active l'hologramme", "ouvre l'hologramme", "lance le mode hologramme", "active hologramme", "lance l'hologramme", "active holo", "ouvre holo"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#holo-button:not([aria-pressed=\"true\"])")
            return "J'active le mode hologramme, Monsieur."

    if any(k in t for k in ["desactive le mode hologramme", "desactive l'hologramme", "ferme l'hologramme", "masque l'hologramme", "coupe l'hologramme", "desactive le mode holo", "desactive holo", "ferme holo", "coupe holo"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#holo-button[aria-pressed=\"true\"]")
            return "Je désactive le mode hologramme, Monsieur."

    # --- 11b. MODE ÉCHECS ---
    if any(k in t for k in ["echecs", "echec", "mode echecs", "joue aux echecs", "on joue aux echecs", "on joue une partie d echecs", "partie d echecs", "jeu d echecs", "lance les echecs", "ouvre les echecs"]):
        if hasattr(builtins, "CONNECTED_CLIENTS") and builtins.CONNECTED_CLIENTS:
            import json, asyncio
            msg = json.dumps({"action": "chess_start"})
            await asyncio.gather(*[ws.send(msg) for ws in builtins.CONNECTED_CLIENTS], return_exceptions=True)
            return "Déploiement du plateau d'échecs 3D, Monsieur."

    # --- 12. MODE AR (HAND TRACKING) ---
    if any(k in t for k in ["active le mode ar", "active l'ar", "lance le mode ar", "active le tracking", "active les gestes", "lance l'ar", "ouvre l'ar"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#gestures-toggle:not(.active)")
            return "J'active le mode de détection AR, Monsieur."

    if any(k in t for k in ["desactive le mode ar", "desactive l'ar", "coupe le mode ar", "coupe l'ar", "ferme l'ar", "desactive le tracking", "desactive les gestes"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#gestures-toggle.active")
            return "Je désactive le mode de détection AR, Monsieur."

    # --- 13. MODE AR MIROIR ---
    if any(k in t for k in ["active le miroir ar", "active l'ar miroir", "bascule en ar miroir", "ar miroir"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#gestures-mirror:not(.active)")
            return "Mode miroir AR activé, Monsieur."

    if any(k in t for k in ["desactive le miroir ar", "desactive l'ar miroir", "reviens en ar direct", "ar direct"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#gestures-mirror.active")
            return "Mode miroir AR désactivé. Retour au flux direct, Monsieur."

    # --- 14. MODE HOLO MIROIR ---
    if any(k in t for k in ["active le miroir en mode holo", "active le miroir holo", "active l'hologramme miroir", "miroir holo"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#holo-btn-mirror:not(.active)")
            return "Mode miroir activé pour l'hologramme, Monsieur."

    if any(k in t for k in ["desactive le miroir en mode holo", "desactive le miroir holo", "desactive l'hologramme miroir", "reviens en holo direct", "hologramme direct"]):
        if hasattr(builtins, "send_web_action"):
            await builtins.send_web_action("click", selector="#holo-btn-mirror.active")
            return "Mode miroir désactivé pour l'hologramme, Monsieur."

    return None

# Injection builtins pour la résolution locale globale
builtins.resoudre_dom_hud = resoudre_dom_hud
