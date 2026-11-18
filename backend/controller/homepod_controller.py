import asyncio
import pyatv
import os
from typing import Optional

# Configuration du HomePod
# Vous pouvez spécifier l'IP pour aller plus vite, sinon JARVIS le cherchera sur le réseau.
HOMEPOD_IP = os.getenv("HOMEPOD_IP", None)
HOMEPOD_SEJOUR_IP = os.getenv("HOMEPOD_SEJOUR_IP", None)
HOMEPOD_JEUX_IP = os.getenv("HOMEPOD_JEUX_IP", None)

async def find_homepod(identifier: Optional[str] = None):
    """Recherche un HomePod sur le réseau local."""
    # print(f"[HOMEPOD] Recherche du HomePod '{identifier}'...")
    loop = asyncio.get_event_loop()
    
    # Si l'identifiant ressemble à une IP, on scanne uniquement cet hôte pour une connexion instantanée
    is_ip = identifier and all(c in "0123456789." for c in identifier)
    if is_ip:
        discovered = await pyatv.scan(loop, hosts=[identifier], timeout=2)
    else:
        discovered = await pyatv.scan(loop, timeout=5)
    
    for device in discovered:
        if identifier:
            if identifier.lower() in device.name.lower() or identifier == device.address:
                return device
        else:
            # Par défaut, le premier HomePod trouvé : on écarte les appareils AirPlay dont le modèle est CONNU et n'est pas un HomePod (Apple TV, enceinte tierce),
            # « pause » mettait sinon en pause le premier appareil AirPlay venu
            modele = str(getattr(getattr(device, "device_info", None), "model", "") or "").lower()
            if not modele or "homepod" in modele or "homepod" in device.name.lower() or "unknown" in modele:
                return device
            
    return None

async def send_command(command: str, value: Optional[float] = None, identifier: Optional[str] = None):
    """Envoie une commande au HomePod (play, pause, stop, volume)."""
    try:
        # Résolution des IPs statiques du .env si l'identifiant vocal correspond
        target = identifier
        if identifier:
            ident_lower = identifier.lower()
            if "jeux" in ident_lower:
                target = HOMEPOD_JEUX_IP or identifier
            elif "sejour" in ident_lower or "séjour" in ident_lower or "salon" in ident_lower:
                target = HOMEPOD_SEJOUR_IP or identifier

        # Découverte ou utilisation de l'IP
        if target:
            device = await find_homepod(target)
        elif HOMEPOD_IP:
            device = await find_homepod(HOMEPOD_IP)
        else:
            device = await find_homepod()

        if not device:
            print(f"[HOMEPOD] Aucun HomePod trouvé pour '{target or 'par défaut'}'.")
            return False, "Aucun HomePod trouvé sur le réseau."

        print(f"[HOMEPOD] Connexion à {device.name} ({device.address})...")
        atv = await pyatv.connect(device, asyncio.get_event_loop())
        
        try:
            if command == "play":
                await atv.control.play()
            elif command == "pause":
                await atv.control.pause()
            elif command == "stop":
                await atv.control.stop()
            elif command == "next":
                await atv.control.next()
            elif command == "previous":
                await atv.control.previous()
            elif command == "volume" and value is not None:
                # pyatv utilise une échelle de 0 à 100 pour le volume
                await atv.audio.set_volume(value)
            
            return True, f"Commande {command} envoyée avec succès."
        finally:
            await asyncio.gather(*atv.close())
            
    except Exception as e:
        print(f"[HOMEPOD ERROR] {e}")
        return False, str(e)

async def get_playing_metadata(identifier: Optional[str] = None) -> Optional[str]:
    """Récupère les métadonnées de la chanson en cours sur le HomePod cible."""
    try:
        target = identifier
        if identifier:
            ident_lower = identifier.lower()
            if "jeux" in ident_lower:
                target = HOMEPOD_JEUX_IP or identifier
            elif "sejour" in ident_lower or "séjour" in ident_lower or "salon" in ident_lower:
                target = HOMEPOD_SEJOUR_IP or identifier

        device = await find_homepod(target)
        if not device:
            return None

        atv = await pyatv.connect(device, asyncio.get_event_loop())
        try:
            # pyatv >= 0.10 : currently_playing() a été supprimé.
            # On passe par le push_updater pour lire les métadonnées actuelles.
            playing = atv.metadata
            title  = getattr(playing, "title",  None)
            artist = getattr(playing, "artist", None)
            if title:
                return f"{artist or 'Artiste inconnu'} - {title}"
            return None
        except AttributeError:
            # L'interface de métadonnées n'est pas disponible sur cet appareil
            return None
        finally:
            await asyncio.gather(*atv.close())
    except Exception:
        # Erreur réseau ou appareil injoignable — on n'affiche rien pour ne pas polluer la console
        return None


if __name__ == "__main__":
    # Petit test de scan
    async def test():
        device = await find_homepod()
        if device:
            print(f"Trouvé : {device.name} à l'adresse {device.address}")
        else:
            print("Rien trouvé.")
            
    asyncio.run(test())
