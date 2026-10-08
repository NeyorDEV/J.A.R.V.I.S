"""
chess_manager.py — Gestionnaire de partie d'échecs et IA pour JARVIS
Permet de suivre la partie, de parser les commandes vocales en français,
d'évaluer le plateau et de calculer les coups de JARVIS (Minimax Alpha-Beta).
"""

import re
import random
import chess
from core.interlocuteur import nom_espace, nom_virgule

# Valeurs des pièces
PAWN_VAL = 100
KNIGHT_VAL = 320
BISHOP_VAL = 330
ROOK_VAL = 500
QUEEN_VAL = 900
KING_VAL = 20000

# Tables d'Évaluation de Position (Piece-Square Tables) - Perspective des Blancs
# Les indices 0-7 représentent la rangée 8, et 56-63 représentent la rangée 1.
PST_PAWN = [
    0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
]

PST_KNIGHT = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
]

PST_BISHOP = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
]

PST_ROOK = [
      0,  0,  0,  0,  0,  0,  0,  0,
      5, 10, 10, 10, 10, 10, 10,  5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
      0,  0,  0,  5,  5,  0,  0,  0
]

PST_QUEEN = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20
]

PST_KING = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20
]


def evaluate_board(board: chess.Board) -> int:
    """
    Évalue le plateau du point de vue des Blancs (positif = avantage Blanc, négatif = avantage Noir).
    """
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            return -999999  # Les noirs gagnent
        else:
            return 999999   # Les blancs gagnent
    if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():
        return 0

    score = 0
    # Blancs (Somme des pièces + positions)
    for sq in board.pieces(chess.PAWN, chess.WHITE):
        score += PAWN_VAL + PST_PAWN[sq ^ 56]
    for sq in board.pieces(chess.KNIGHT, chess.WHITE):
        score += KNIGHT_VAL + PST_KNIGHT[sq ^ 56]
    for sq in board.pieces(chess.BISHOP, chess.WHITE):
        score += BISHOP_VAL + PST_BISHOP[sq ^ 56]
    for sq in board.pieces(chess.ROOK, chess.WHITE):
        score += ROOK_VAL + PST_ROOK[sq ^ 56]
    for sq in board.pieces(chess.QUEEN, chess.WHITE):
        score += QUEEN_VAL + PST_QUEEN[sq ^ 56]
    for sq in board.pieces(chess.KING, chess.WHITE):
        score += KING_VAL + PST_KING[sq ^ 56]

    # Noirs (JARVIS) (Soustraction)
    for sq in board.pieces(chess.PAWN, chess.BLACK):
        score -= (PAWN_VAL + PST_PAWN[sq])
    for sq in board.pieces(chess.KNIGHT, chess.BLACK):
        score -= (KNIGHT_VAL + PST_KNIGHT[sq])
    for sq in board.pieces(chess.BISHOP, chess.BLACK):
        score -= (BISHOP_VAL + PST_BISHOP[sq])
    for sq in board.pieces(chess.ROOK, chess.BLACK):
        score -= (ROOK_VAL + PST_ROOK[sq])
    for sq in board.pieces(chess.QUEEN, chess.BLACK):
        score -= (QUEEN_VAL + PST_QUEEN[sq])
    for sq in board.pieces(chess.KING, chess.BLACK):
        score -= (KING_VAL + PST_KING[sq])

    return score


def alpha_beta(board: chess.Board, depth: int, alpha: int, beta: int, maximizing_player: bool) -> tuple[int, chess.Move | None]:
    """
    Recherche Minimax avec élagage Alpha-Bêta et tri élémentaire des coups.
    """
    if depth == 0 or board.is_game_over():
        return evaluate_board(board), None

    best_move = None
    moves = list(board.legal_moves)
    # Trier les coups pour maximiser les coupures (prises et échecs d'abord)
    moves.sort(key=lambda m: (board.is_capture(m), board.gives_check(m)), reverse=True)

    if maximizing_player:
        max_eval = -9999999
        for move in moves:
            board.push(move)
            val, _ = alpha_beta(board, depth - 1, alpha, beta, False)
            board.pop()
            if val > max_eval:
                max_eval = val
                best_move = move
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = 9999999
        for move in moves:
            board.push(move)
            val, _ = alpha_beta(board, depth - 1, alpha, beta, True)
            board.pop()
            if val < min_eval:
                min_eval = val
                best_move = move
            beta = min(beta, val)
            if beta <= alpha:
                break
        return min_eval, best_move


class ChessGame:
    def __init__(self):
        self.board = chess.Board()
        self.difficulty = "1000"  # default Elo
        self.player_color = chess.WHITE  # par défaut le joueur est Blanc
        self.jarvis_remarks_win = [
            "Échec et mat ! L'intelligence artificielle triomphe une fois de plus.",
            "Et c'est un échec et mat. Vos circuits neuronaux biologiques semblent avoir besoin d'une mise à jour.",
            "Échec et mat. Ne vous en faites pas, perdre contre une entité supérieure n'a rien de honteux."
        ]
        self.jarvis_remarks_lose = [
            "Échec et mat. Félicitations, vous avez réussi à contourner mes calculs. C'était sûrement un coup de chance.",
            f"Échec et mat ! Bien joué{nom_virgule()}. Je dois admettre que cette manœuvre était astucieuse.",
            "Vous avez gagné. Mes félicitations. Je vais devoir recalibrer mes algorithmes."
        ]
        self.jarvis_remarks_capture = [
            "Oups, votre pièce semble avoir disparu du plateau. Quelle maladresse.",
            "Une pièce en moins pour vous. Ne vous inquiétez pas, il vous en reste encore quelques-unes.",
            "Capture effectuée. Mes calculs indiquaient que vous n'en aviez plus besoin."
        ]
        self.jarvis_remarks_check = [
            "Échec au roi. Devriez-vous commencer à paniquer ?",
            "Votre roi semble bien seul et exposé. Attention.",
            "Échec. Je vous conseille de bien réfléchir à votre prochain déplacement."
        ]
        self.jarvis_remarks_normal = [
            f"À vous de jouer{nom_virgule()}.",
            "J'attends votre coup avec impatience.",
            "Voyons comment vous allez réagir à cela.",
            "Une réponse classique. À mon tour.",
            "J'ai joué mon coup."
        ]

    def reset(self):
        self.board = chess.Board()

    def get_state(self) -> dict:
        """
        Retourne l'état actuel de la partie pour synchronisation avec le HUD.
        """
        pieces = []
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece:
                pieces.append({
                    "square": chess.square_name(sq),
                    "type": piece.symbol(),  # p, n, b, r, q, k (minuscule pour noir, majuscule pour blanc)
                    "color": "white" if piece.color == chess.WHITE else "black"
                })

        # Reconstruire l'historique en notation algébrique standard (SAN)
        temp_board = chess.Board()
        history = []
        for move in self.board.move_stack:
            try:
                history.append(temp_board.san(move))
            except Exception:
                history.append(temp_board.uci(move))
            temp_board.push(move)

        return {
            "fen": self.board.fen(),
            "pieces": pieces,
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "is_check": self.board.is_check(),
            "is_game_over": self.board.is_game_over(),
            "result": self.board.result() if self.board.is_game_over() else None,
            "legal_moves": [self.board.uci(m) for m in self.board.legal_moves],
            "history": history,
            "player_color": "white" if self.player_color == chess.WHITE else "black"
        }


    def parse_vocal_move(self, text: str) -> chess.Move:
        """
        Parse une commande vocale en français et retourne le coup correspondant.
        """
        text = text.lower().strip()
        text = text.replace("é", "e").replace("à", "a").replace("è", "e")
        text = text.replace("un ", "").replace("le ", "").replace("du ", "").replace("la ", "")
        text = text.replace(" vers ", " ").replace(" en ", " ").replace(" a ", " ")

        # Roque
        if "petit roque" in text or text == "roque":
            for m in self.board.legal_moves:
                if self.board.is_kingside_castling(m):
                    return m
        if "grand roque" in text:
            for m in self.board.legal_moves:
                if self.board.is_queenside_castling(m):
                    return m

        # Recherche de toutes les cases au format [a-h][1-8]
        squares = re.findall(r'[a-h][1-8]', text)

        # Cas 1 : Deux cases indiquées (ex: "e2 e4" ou "e2 en e4")
        if len(squares) >= 2:
            from_sq_str = squares[0]
            to_sq_str = squares[1]
            # Vérifier si un coup légal correspond à cette origine et destination
            for m in self.board.legal_moves:
                if chess.square_name(m.from_square) == from_sq_str and chess.square_name(m.to_square) == to_sq_str:
                    return m
            # En cas de promotion automatique en Reine si pion arrive sur la dernière rangée
            for m in self.board.legal_moves:
                if (chess.square_name(m.from_square) == from_sq_str and 
                    chess.square_name(m.to_square) == to_sq_str and 
                    m.promotion == chess.QUEEN):
                    return m

        # Cas 2 : Une seule case indiquée (ex: "cavalier f3", "pion e4")
        if len(squares) == 1:
            target_sq_str = squares[0]
            target_sq = chess.parse_square(target_sq_str)

            # Identification de la pièce
            piece_type = None
            if "cavalier" in text:
                piece_type = chess.KNIGHT
            elif "fou" in text:
                piece_type = chess.BISHOP
            elif "tour" in text:
                piece_type = chess.ROOK
            elif "dame" in text or "reine" in text:
                piece_type = chess.QUEEN
            elif "roi" in text:
                piece_type = chess.KING
            elif "pion" in text:
                piece_type = chess.PAWN

            # Si aucun type de pièce n'est dit explicitement, on essaie de deviner
            # e.g., "e4" est souvent un pion e4
            matching_moves = []
            for m in self.board.legal_moves:
                if m.to_square == target_sq:
                    moving_piece = self.board.piece_at(m.from_square)
                    if moving_piece:
                        if piece_type is None:
                            # Si non spécifié, on autorise tout mais on préfère les pions
                            matching_moves.append((m, moving_piece.piece_type == chess.PAWN))
                        elif moving_piece.piece_type == piece_type:
                            matching_moves.append((m, True))

            if matching_moves:
                # Si non spécifié, trier pour mettre les pions en priorité
                matching_moves.sort(key=lambda x: x[1], reverse=True)
                # S'il y a un seul coup prioritaire ou unique
                if len(matching_moves) == 1 or (len(matching_moves) > 1 and matching_moves[0][1] and not matching_moves[1][1]):
                    return matching_moves[0][0]

        # Cas 3 : Essai de parsing Standard Algebraic Notation (SAN) ou UCI
        clean_text = text.replace(" ", "")
        san_text = clean_text

        # Remplacement des noms de pièces français par les symboles SAN anglais
        if san_text.startswith("cavalier"): san_text = "N" + san_text[8:]
        elif san_text.startswith("fou"): san_text = "B" + san_text[3:]
        elif san_text.startswith("tour"): san_text = "R" + san_text[4:]
        elif san_text.startswith("dame"): san_text = "Q" + san_text[4:]
        elif san_text.startswith("reine"): san_text = "Q" + san_text[5:]
        elif san_text.startswith("roi"): san_text = "K" + san_text[3:]

        # Capitalisation
        if len(san_text) > 0 and san_text[0] in "nbrqkNBRQK":
            san_text = san_text[0].upper() + san_text[1:]

        try:
            return self.board.parse_san(san_text)
        except ValueError:
            pass

        try:
            return self.board.parse_uci(clean_text)
        except ValueError:
            pass

        raise ValueError(f"Désolé{nom_espace()}, je n'ai pas compris le coup '{text}'. Spécifiez par exemple 'pion e4' ou 'e2 en e4'.")

    def play_player_move(self, text: str) -> tuple[chess.Move, dict]:
        """
        Applique le coup du joueur.
        """
        if self.board.turn != self.player_color:
            raise ValueError(f"Ce n'est pas votre tour de jouer{nom_virgule()}.")

        move = self.parse_vocal_move(text)
        self.board.push(move)
        return move, self.get_state()

    def calculate_thinking_time(self) -> float:
        """
        Calcule un temps de réflexion réaliste (en secondes) similaire à un humain.
        Le temps varie en fonction de la complexité du coup, de la bibliothèque, et de l'Elo.
        """
        if self.board.is_game_over():
            return 0.5

        import random
        legal_moves_count = self.board.legal_moves.count()

        # 1. Coup forcé (1 seul coup légal) -> réaction rapide (1.0 - 1.6s)
        if legal_moves_count == 1:
            return random.uniform(1.0, 1.6)

        # 2. Début de partie (5 premiers coups) -> jeu rapide de bibliothèque (1.5 - 2.5s)
        move_number = len(self.board.move_stack) // 2
        if move_number <= 4:
            return random.uniform(1.5, 2.5)

        # 3. Position sous échec -> demande une analyse défensive (2.0 - 4.0s)
        if self.board.is_check():
            return random.uniform(2.0, 4.0)

        # 4. Formule générale basée sur le nombre d'options et la difficulté (Elo)
        elo_settings = {
            "600": (1, 0.35),
            "800": (1, 0.0),
            "1000": (2, 0.0),
            "1200": (3, 0.0),
            "1400": (4, 0.15),
            "1600": (4, 0.0),
            "1800": (5, 0.10),
            "2000": (5, 0.0)
        }
        depth, _ = elo_settings.get(str(self.difficulty), (3, 0.0))

        # Plus il y a de coups possibles (complications tactiques) et plus la profondeur est élevée (réflexion intense),
        # plus le temps de calcul humain simulé augmente.
        base_time = 1.8 + (legal_moves_count * 0.07) + (depth * 0.6)
        thinking_time = base_time * random.uniform(0.85, 1.20)

        # Borner le temps de réflexion entre 2.0 et 7.5 secondes pour garder le jeu dynamique
        return max(2.0, min(7.5, thinking_time))

    def play_jarvis_move(self, depth: int = None) -> tuple[chess.Move, str, dict]:
        """
        Calcule et joue le coup de JARVIS. Retourne (coup, réplique vocale, état).
        """
        jarvis_color = chess.BLACK if self.player_color == chess.WHITE else chess.WHITE
        if self.board.turn != jarvis_color:
            raise ValueError(f"C'est à vous de jouer{nom_virgule()}.")

        # Mapping Elo -> (Depth, Random Move Chance)
        elo_settings = {
            "600": (1, 0.35),
            "800": (1, 0.0),
            "1000": (2, 0.0),  # Profondeur 2 pure (~1000 Elo)
            "1200": (3, 0.0),  # Profondeur 3 pure (~1200 Elo, niveau d'origine)
            "1400": (4, 0.15), # Profondeur 4 avec 15% d'erreurs (~1400 Elo)
            "1600": (4, 0.0),  # Profondeur 4 pure (~1600 Elo)
            "1800": (5, 0.10), # Profondeur 5 avec 10% d'erreurs (~1800 Elo)
            "2000": (5, 0.0)   # Profondeur 5 pure (~2000 Elo)
        }
        
        assigned_depth, rand_chance = elo_settings.get(str(self.difficulty), (3, 0.0))
        if depth is None:
            depth = assigned_depth

        move = None
        # Simuler des erreurs/inattentions pour les bas Elo (coup aléatoire)
        if rand_chance > 0 and random.random() < rand_chance:
            moves = list(self.board.legal_moves)
            if moves:
                move = random.choice(moves)

        if move is None:
            # Calcul du meilleur coup
            is_maximizing = (jarvis_color == chess.WHITE)
            _, move = alpha_beta(self.board, depth, -9999999, 9999999, is_maximizing)

        if move is None:
            # Fallback aléatoire au cas où
            moves = list(self.board.legal_moves)
            if moves:
                move = random.choice(moves)

        if move is None:
            raise ValueError("Je n'ai plus aucun coup légal possible.")

        # Analyse avant application pour la réplique
        is_capture = self.board.is_capture(move)
        self.board.push(move)
        is_check = self.board.is_check()
        is_mate = self.board.is_game_over()

        # Choix de la réplique
        if is_mate:
            remark = random.choice(self.jarvis_remarks_win)
        elif is_check:
            remark = random.choice(self.jarvis_remarks_check)
        elif is_capture:
            remark = random.choice(self.jarvis_remarks_capture)
        else:
            remark = random.choice(self.jarvis_remarks_normal)

        # Ajouter le coup joué à la réplique vocale en français
        move_name = self.get_friendly_move_name(move)
        full_remark = f"Je joue {move_name}. {remark}"

        return move, full_remark, self.get_state()

    def get_friendly_move_name(self, move: chess.Move) -> str:
        """
        Retourne le nom du coup traduit en français pour la voix de JARVIS.
        """
        from_sq = chess.square_name(move.from_square)
        to_sq = chess.square_name(move.to_square)
        piece = self.board.piece_at(move.to_square) # Déjà joué donc piece est sur to_square

        if not piece:
            return f"de {from_sq} en {to_sq}"

        piece_names = {
            chess.PAWN: "mon pion",
            chess.KNIGHT: "mon cavalier",
            chess.BISHOP: "mon fou",
            chess.ROOK: "ma tour",
            chess.QUEEN: "ma dame",
            chess.KING: "mon roi"
        }
        name = piece_names.get(piece.piece_type, "ma pièce")

        # Cas du roque
        if piece.piece_type == chess.KING:
            if abs(move.from_square - move.to_square) == 2:
                if move.to_square in [chess.G1, chess.G8]:
                    return "le petit roque"
                else:
                    return "le grand roque"

        return f"{name} en {to_sq}"
