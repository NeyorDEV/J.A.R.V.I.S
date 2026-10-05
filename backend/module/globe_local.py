"""Resolver local du globe 3D : navigation, itinéraires et position (sans IA)."""

import builtins

from core.web_bridge import geocode_lieu, send_globe_command


async def resoudre_globe_localement(texte: str):
    """Détecte les commandes de navigation globe et déclenche CesiumJS."""
    import re
    t = texte.lower().strip()

    _mots_fermer  = ["ferme la carte", "ferme le globe", "ferme globe", "cache la carte",
                     "cache le globe", "ferme la navigation", "quitte le globe", "quitte globe",
                     "sors du globe", "sortir du globe", "quitter le globe", "quitter globe",
                     "retour à jarvis", "ferme la vue", "masque la carte"]

    # 1. Fermer (Priorité absolue pour éviter le court-circuit de l'exclusion 'carte')
    if any(m in t for m in _mots_fermer):
        await send_globe_command(globe_action="hide")
        return "Navigation fermée. Je reviens à l'interface principale, mylane."
    
    # Éviter de déclencher le globe si on cherche un fichier ou dossier local ou une info générale/HUD
    # (ni si "affiche" est utilisé comme nom commun : "une affiche", "l'affiche" pour un poster/image)
    if any(k in t for k in ["dossier", "fichier", "document", "archive", "programme", "histoire", "blague", "raconte", "explique", "définition", "carte", "une affiche", "l'affiche", "cette affiche", "image", "photo", "dessin"]):
        return None

    # ── Mots-clés déclencheurs ───────────────────────────────────────────────
    _mots_globe   = ["affiche la terre", "montre la terre", "montre-moi la terre",
                     "globe terrestre", "affiche le globe", "vue de la terre",
                     "vue spatiale", "vue depuis l'espace", "vue de l'espace",
                     "montre la planète", "affiche la planète",
                     "zoom arrière total", "dézoom total"]

    _mots_ville   = ["affiche-moi", "affiche moi", "affiche", "montre-moi", "montre moi", "survole",
                     "navigue vers", "va vers", "zoome sur",
                     "fais un survol de", "localise", "trouve",
                     "où est", "ou est", "situe", "où se trouve", "ou se trouve"]

    _mots_route   = ["trace un itinéraire", "trace l'itinéraire", "itinéraire de",
                     "route de", "chemin de", "comment aller de",
                     "trace une route de", "trajet de", "trajet depuis"]

    _mots_position = ["ma position", "où suis-je", "ou suis-je",
                      "affiche ma position", "montre ma position",
                      "localise-moi", "localise moi", "où je suis"]

    # ── Ma position ──────────────────────────────────────────────────────────
    if any(m in t for m in _mots_position):
        # On délègue la géolocalisation au navigateur (navigator.geolocation)
        # bien plus précis que l'IP — le frontend gère tout
        await send_globe_command(globe_action="my_location")
        return "Localisation en cours, mylane. Le globe affiche votre position."

    # ── Globe Terre ───────────────────────────────────────────────────────────
    if any(m in t for m in _mots_globe):
        await send_globe_command(globe_action="show_earth")
        return "Vue depuis l'espace activée, mylane."

    # ── Itinéraire de X à Y ──────────────────────────────────────────────────
    if any(m in t for m in _mots_route):
        pattern = r"(?:de|depuis)\s+(.+?)\s+(?:a|vers|jusqu.a|et)\s+(.+?)(?:\s*[?!]?\s*$)" 
        match = re.search(pattern, t)
        if match:
            from_name = match.group(1).strip().title()
            to_name   = match.group(2).strip().title()
            lat1, lon1, _ = await geocode_lieu(from_name)
            lat2, lon2, _ = await geocode_lieu(to_name)
            if lat1 and lat2:
                await send_globe_command(
                    globe_action="route",
                    from_lat=lat1, from_lon=lon1, from_name=from_name,
                    to_lat=lat2,   to_lon=lon2,   to_name=to_name
                )
                return f"Itinéraire tracé de {from_name} à {to_name}, mylane."
            else:
                return f"Je n'ai pas pu localiser les deux villes, mylane. Vérifiez les noms et réessayez."
        return None

    # ── Fly to ville ─────────────────────────────────────────────────────────
    for mot in _mots_ville:
        if mot in t:
            # Extraire ce qui suit le mot déclencheur
            idx = t.find(mot)
            reste = t[idx + len(mot):].strip()
            # Nettoyer les tirets initiaux s'il reste un résidu de '-moi' mal digéré
            if reste.startswith("-"):
                reste = reste[1:].strip()
            if reste.startswith("moi "):
                reste = reste[4:].strip()
            # Nettoyer les articles
            for art in ["la ville de ", "la ville ", "le ", "la ", "l'", "les ", "ma ville ", "mon pays "]:
                if reste.startswith(art):
                    reste = reste[len(art):]
            reste = reste.rstrip(".,?!;").strip()
            if len(reste) >= 2:
                nom_lieu = reste.title()
                lat, lon, display = await geocode_lieu(nom_lieu)
                if lat:
                    # Altitude selon le type de lieu (ville proche = plus bas)
                    altitude = 300000
                    await send_globe_command(
                        globe_action="fly_to",
                        lat=lat, lon=lon,
                        target=nom_lieu,
                        altitude=altitude
                    )
                    return f"Survol de {nom_lieu} en cours, mylane."
                else:
                    return f"Je n'ai pas réussi à localiser {nom_lieu}, mylane. Essayez avec un nom plus précis."
            break

    return None


builtins.resoudre_globe_localement = resoudre_globe_localement
