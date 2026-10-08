"""Resolver local des commandes vocales d'échecs (coups, parties)."""

import asyncio
import re

import chess

import core.shared as shared
from core.speech import parler
from core.web_bridge import diffuser_echecs
from module.chess_manager import ChessGame
from core.interlocuteur import nom_espace, nom_virgule


def _ressemble_a_un_coup(t):
    """Mot de pièce ou case d'échiquier en mot entier : « roi » était trouvé dans
    « froid », « tour » dans « Tours », « droite »… (« il fait froid ? » devenait un coup)."""
    return bool(re.search(r"\b(pion|cavalier|fou|tour|dame|reine|roi|roque)\b", t)
                or re.search(r"\b[a-h][1-8]\b", t))


def _annonce_fin(resultat, couleur_joueur, remarque=""):
    """Phrase de fin de partie selon la couleur jouée (avant, avec les noirs, la victoire
    du joueur donnait « Fin de partie » et celle de JARVIS n'était pas annoncée)."""
    prefixe = f"{remarque} " if remarque else ""
    if resultat == "1/2-1/2":
        return f"{prefixe}Match nul. Bien joué de part et d'autre."
    joueur_gagne = (resultat == "1-0") == (couleur_joueur == chess.WHITE)
    if joueur_gagne:
        return f"{prefixe}Félicitations, vous avez gagné ! Je m'incline."
    return f"{prefixe}Échec et mat. J'ai gagné la partie."


async def resoudre_echecs_localement(texte):
    """
    Intercepte les commandes d'échecs en temps réel pour éviter le délai du LLM.
    """
    t = texte.lower().strip()
    
    if any(k in t for k in [
        "jouons aux echecs", "jouons aux échecs",
        "jouer aux echecs", "jouer aux échecs",
        "joue aux echecs", "joue aux échecs",
        "joues aux echecs", "joues aux échecs",
        "lance une partie d echecs", "lance une partie d'echecs", "lance une partie d'échecs",
        "partie d echecs", "partie d'echecs", "partie d'échecs",
        "commencer les echecs", "commencer les échecs",
        "lance les echecs", "lance les échecs",
        "lance le jeu d'echecs", "lance le jeu d'échecs"
    ]):
        # Si la commande contient déjà l'intention de démarrer, on passe directement au démarrage ci-dessous
        if not any(k in t for k in ["lance la partie", "démarre la partie", "commence la partie", "lance le jeu", "démarre le jeu"]):
            shared.CHESS_GAME = ChessGame()
            shared.CHESS_GAME_ACTIVE = False
            state = shared.CHESS_GAME.get_state()
            await diffuser_echecs({
                "action": "chess_start",
                "state": state
            })
            return f"Très bien{nom_espace()}. J'ai disposé le plateau 3D sur le HUD. Veuillez configurer la partie et la démarrer."

    # 1.5 Lancer / Démarrer la partie avec options
    # « lance le jeu Minecraft » démarrait une partie d'échecs : il faut parler d'échecs,
    # ou que le plateau soit déjà affiché (en attente de configuration).
    plateau_affiche = shared.CHESS_GAME is not None and not shared.CHESS_GAME_ACTIVE
    if any(k in t for k in ["lance la partie", "démarre la partie", "commence la partie", "lance le jeu", "démarre le jeu"]) \
            and ("echec" in t or "échec" in t or plateau_affiche):
        # Déterminer la couleur
        player_color = "white"
        if "noir" in t or "noire" in t or "noirs" in t:
            player_color = "black"
        
        # Déterminer la difficulté (Bot Elo)
        difficulty = "1000"
        if "facile" in t or "débutant" in t or "600" in t:
            difficulty = "600"
        elif "novice" in t or "800" in t:
            difficulty = "800"
        elif "moyen" in t or "amateur" in t or "1000" in t:
            difficulty = "1000"
        elif "difficile" in t or "intermédiaire" in t or "1400" in t:
            difficulty = "1400"
        elif "confirmé" in t or "1600" in t:
            difficulty = "1600"
        elif "expert" in t or "avancé" in t or "1800" in t:
            difficulty = "1800"
        elif "maître" in t or "master" in t or "2000" in t:
            difficulty = "2000"

        # Déterminer si on utilise le chronomètre (10 min)
        use_timer = "no"
        if "chrono" in t or "chronomètre" in t or "temps" in t or "limite" in t:
            if not "sans chrono" in t and not "sans temps" in t and not "sans limite" in t:
                use_timer = "yes"

        shared.CHESS_GAME = ChessGame()
        shared.CHESS_GAME.difficulty = difficulty
        shared.CHESS_GAME.player_color = chess.WHITE if player_color == "white" else chess.BLACK
        shared.CHESS_GAME_ACTIVE = True
        state = shared.CHESS_GAME.get_state()

        await diffuser_echecs({
            "action": "chess_start",
            "state": state,
            "difficulty": difficulty,
            "player_color": player_color,
            "use_timer": use_timer
        })

        color_text = "les Blancs" if player_color == "white" else "les Noirs"
        timer_text = "avec chronomètre" if use_timer == "yes" else "sans chronomètre"
        remark = f"Partie d'échecs démarrée avec {color_text}, niveau {difficulty} Elo, {timer_text}."

        if shared.CHESS_GAME.player_color == chess.BLACK:
            async def play_first_move_delayed():
                await asyncio.sleep(1.5) # Laisser pivoter le plateau
                if not shared.CHESS_GAME or not shared.CHESS_GAME_ACTIVE:
                    return
                await diffuser_echecs({
                    "action": "chess_thinking",
                    "thinking": True
                })
                thinking_time = shared.CHESS_GAME.calculate_thinking_time()
                await asyncio.sleep(thinking_time)
                if not shared.CHESS_GAME or not shared.CHESS_GAME_ACTIVE:
                    return
                j_move, j_remark, j_state = shared.CHESS_GAME.play_jarvis_move()
                await diffuser_echecs({
                    "action": "chess_game_state",
                    "state": j_state,
                    "last_move": {
                        "from": chess.square_name(j_move.from_square),
                        "to": chess.square_name(j_move.to_square),
                        "color": "white"
                    }
                })
                parler(j_remark)
            asyncio.create_task(play_first_move_delayed())

        return remark

    # 2. Recommencer la partie
    if any(k in t for k in ["recommence la partie", "réinitialise la partie", "relance la partie", "recommence le jeu"]):
        shared.CHESS_GAME = None
        shared.CHESS_GAME_ACTIVE = False
        await diffuser_echecs({
            "action": "chess_reset"
        })
        return f"Plateau df'échecs réinitialisé{nom_virgule()}. Les réglages sont de retour à l'écran de configuration."

    # 2.5 Arrêter une partie / Quitter le jeu
    if any(k in t for k in ["arrete les echecs", "stop echecs", "quitte les echecs", "ferme les echecs", "quitte la partie", "arrête la partie", "quitte le jeu", "arrête le jeu"]):
        shared.CHESS_GAME = None
        shared.CHESS_GAME_ACTIVE = False
        await diffuser_echecs({
            "action": "chess_stop"
        })
        return f"Jeu d'échecs fermé{nom_virgule()}. Retour au HUD standard."

    # 3. Jouer un coup (si une partie est active et démarrée)
    if shared.CHESS_GAME:
        if not shared.CHESS_GAME_ACTIVE:
            if _ressemble_a_un_coup(t):
                return f"La partie nf'est pas encore démarrée{nom_virgule()}. Veuillez cliquer sur 'DÉMARRER LA PARTIE' sur le HUD."
            return None

        try:
            # Essayer d'appliquer le coup du joueur
            move, state = shared.CHESS_GAME.play_player_move(texte)
            
            # Notifier le coup joué par le joueur
            await diffuser_echecs({
                "action": "chess_game_state",
                "state": state,
                "last_move": {
                    "from": chess.square_name(move.from_square),
                    "to": chess.square_name(move.to_square),
                    "color": "white" if shared.CHESS_GAME.player_color == chess.WHITE else "black"
                }
            })
            
            # Si le jeu est fini après le coup du joueur
            if state["is_game_over"]:
                couleur = shared.CHESS_GAME.player_color
                shared.CHESS_GAME = None
                shared.CHESS_GAME_ACTIVE = False
                return _annonce_fin(state["result"], couleur)
            
            # Notification que JARVIS réfléchit (effet visuel sur le HUD)
            await diffuser_echecs({
                "action": "chess_thinking",
                "thinking": True
            })
            
            # JARVIS réfléchit un temps dynamique similaire à un humain
            thinking_time = shared.CHESS_GAME.calculate_thinking_time()
            print(f"[CHESS] JARVIS réfléchit pendant {thinking_time:.2f} secondes (Elo: {shared.CHESS_GAME.difficulty})...")
            await asyncio.sleep(thinking_time)
            
            # Coup de JARVIS
            j_move, remark, j_state = shared.CHESS_GAME.play_jarvis_move()
            
            await diffuser_echecs({
                "action": "chess_game_state",
                "state": j_state,
                "last_move": {
                    "from": chess.square_name(j_move.from_square),
                    "to": chess.square_name(j_move.to_square),
                    "color": "black" if shared.CHESS_GAME.player_color == chess.WHITE else "white"
                }
            })
            
            if j_state["is_game_over"]:
                couleur = shared.CHESS_GAME.player_color
                shared.CHESS_GAME = None
                shared.CHESS_GAME_ACTIVE = False
                return _annonce_fin(j_state["result"], couleur, remark)
                    
            return remark
            
        except ValueError as e:
            # Si le texte ressemble à un coup d'échecs
            if _ressemble_a_un_coup(t):
                return str(e)
            
            # Sinon, on retourne None pour passer aux autres resolvers
            return None
            
    return None
