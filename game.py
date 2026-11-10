"""Movement rules for the lab's chess variant.

Check, checkmate, stalemate, castling and en passant follow standard chess.
"""

from typing import Any

# A board maps squares such as "e2" to pieces such as "wP".
Board = dict[str, str]
# [board, side to move, castling rights, en passant square]; a list so moves can
# update it in place. Castling rights are written like "KQkq" (K and Q for White's
# kingside and queenside, lowercase for Black). The en passant square is the one a
# pawn skipped with a double step on the previous move, or None. A position given
# as only [board, side to move] has no castling rights and no en passant square.
Position = list[Any]
# (source, target), or (source, target, promotion) for a pawn reaching the last rank.
Move = tuple[str, str] | tuple[str, str, str]

FILES = "abcdefgh"
BACK_ROW = "RNBQKBNR"


def new_position() -> Position:
    board: Board = {}
    for file, piece in zip(FILES, BACK_ROW):
        board[file + "1"] = "w" + piece
        board[file + "2"] = "wP"
        board[file + "7"] = "bP"
        board[file + "8"] = "b" + piece
    return [board, "w", "KQkq", None]


def copy_position(position: Position) -> Position:
    """Copy the board, side to move, castling rights and en passant square."""
    return [position[0].copy(), *position[1:]]


def castling_rights(position: Position) -> str:
    return str(position[2]) if len(position) > 2 else ""


def en_passant_square(position: Position) -> str | None:
    return position[3] if len(position) > 3 else None


# For each castling right: the rook's file, the files that must be empty, the files
# the king stands on, crosses and lands on (none may be attacked), and the rook's
# destination file.
CASTLING = {
    "K": ("h", "fg", "efg", "f"),
    "Q": ("a", "bcd", "edc", "d"),
}


def coordinates(square: object) -> tuple[int, int]:
    if not isinstance(square, str) or len(square) != 2:
        raise ValueError("Expected a square such as e2")
    if square[0] not in FILES or square[1] not in "12345678":
        raise ValueError("Square is outside the board")
    return FILES.index(square[0]), int(square[1]) - 1


def other(side: str) -> str:
    return "b" if side == "w" else "w"


def in_check(board: Board, side: str) -> bool:
    king = next(
        (square for square, piece in board.items() if piece == side + "K"), None
    )
    return king is not None and any(
        king in reachable(board, square)
        for square, piece in board.items()
        if piece[0] != side
    )


def status(position: Position) -> str | None:
    """Return "check", "checkmate", "stalemate", or None for the side to move."""
    board, turn = position[:2]
    check = in_check(board, turn)
    if any(
        legal_moves(position, square)
        for square, piece in board.items()
        if piece[0] == turn
    ):
        return "check" if check else None
    return "checkmate" if check else "stalemate"


def winner(position: Position) -> str | None:
    if status(position) == "checkmate":
        return "White" if position[1] == "b" else "Black"
    return None


def legal_moves(position: Position, source: str) -> list[str]:
    """Moves for the side to move that do not leave its own king in check."""
    coordinates(source)
    board, turn = position[:2]
    piece = board.get(source)
    if not piece or piece[0] != turn:
        return []
    candidates = reachable(board, source)
    if piece[1] == "K":
        candidates += castling_targets(position, source)
    passant = en_passant_square(position)
    if piece[1] == "P" and passant and passant in pawn_captures(source, turn):
        candidates.append(passant)
    targets = []
    for target in candidates:
        trial = board.copy()
        apply_to_board(trial, source, target)
        if not in_check(trial, turn):
            targets.append(target)
    return targets


def pawn_captures(source: str, side: str) -> list[str]:
    """Squares diagonally in front of a pawn on source."""
    x, y = coordinates(source)
    ty = y + (1 if side == "w" else -1)
    return [
        FILES[tx] + str(ty + 1) for tx in (x - 1, x + 1) if 0 <= tx < 8 and 0 <= ty < 8
    ]


def castling_targets(position: Position, source: str) -> list[str]:
    """Squares the king on source can castle to."""
    board, turn = position[:2]
    rank = "1" if turn == "w" else "8"
    if source != "e" + rank or board.get(source) != turn + "K":
        return []
    targets = []
    for right, (rook_file, empty, walk, _) in CASTLING.items():
        if (right if turn == "w" else right.lower()) not in castling_rights(position):
            continue
        if board.get(rook_file + rank) != turn + "R":
            continue
        if any(file + rank in board for file in empty):
            continue
        if any(king_attacked_on(board, source, file + rank) for file in walk):
            continue
        targets.append(walk[-1] + rank)
    return targets


def king_attacked_on(board: Board, source: str, square: str) -> bool:
    trial = board.copy()
    trial[square] = trial.pop(source)
    return in_check(trial, trial[square][0])


def is_castling(board: Board, source: str, target: str) -> bool:
    piece = board.get(source)
    return (
        piece is not None
        and piece[1] == "K"
        and abs(ord(target[0]) - ord(source[0])) == 2
    )


def capture_square(board: Board, source: str, target: str) -> str | None:
    """The square of the piece this move captures, or None.

    En passant is the only capture whose target square is empty: a pawn moving
    diagonally there takes the pawn beside it.
    """
    if target in board:
        return target
    piece = board.get(source)
    if piece and piece[1] == "P" and source[0] != target[0]:
        return target[0] + source[1]
    return None


def apply_to_board(board: Board, source: str, target: str) -> None:
    """Move the piece on the board, including castling's rook and en passant."""
    taken = capture_square(board, source, target)
    if taken:
        del board[taken]
    if is_castling(board, source, target):
        rank = source[1]
        rook_file, _, _, rook_to = CASTLING["K" if target[0] == "g" else "Q"]
        board[rook_to + rank] = board.pop(rook_file + rank)
    board[target] = board.pop(source)


def reachable(board: Board, source: str) -> list[str]:
    """Squares the piece on source attacks or can move to, ignoring check."""
    piece = board[source]
    turn = piece[0]
    x, y = coordinates(source)
    targets = []
    for tx in range(8):
        for ty in range(8):
            target = FILES[tx] + str(ty + 1)
            occupant = board.get(target)
            if target == source or (occupant and occupant[0] == turn):
                continue
            dx, dy = tx - x, ty - y
            kind = piece[1]
            allowed = False
            if kind == "P":
                direction = 1 if turn == "w" else -1
                home = 1 if turn == "w" else 6
                allowed = (
                    (dx == 0 and dy == direction and not occupant)
                    or (
                        dx == 0
                        and dy == 2 * direction
                        and y == home
                        and not occupant
                        and FILES[x] + str(y + direction + 1) not in board
                    )
                    or (abs(dx) == 1 and dy == direction and bool(occupant))
                )
            elif kind == "N":
                allowed = (abs(dx), abs(dy)) in ((1, 2), (2, 1))
            elif kind == "K":
                allowed = max(abs(dx), abs(dy)) == 1
            else:
                diagonal = abs(dx) == abs(dy)
                straight = dx == 0 or dy == 0
                allowed = (
                    (kind == "B" and diagonal)
                    or (kind == "R" and straight)
                    or (kind == "Q" and (diagonal or straight))
                )
                if allowed:
                    sx = (dx > 0) - (dx < 0)
                    sy = (dy > 0) - (dy < 0)
                    for step in range(1, max(abs(dx), abs(dy))):
                        intermediate = FILES[x + step * sx] + str(y + step * sy + 1)
                        if intermediate in board:
                            allowed = False
                            break
            if allowed:
                targets.append(target)
    return targets


PROMOTION_PIECES = ("Q", "R", "B", "N")


def promotes(position: Position, source: str, target: str) -> bool:
    piece = position[0].get(source)
    return bool(piece) and piece[1] == "P" and target[1] in "18"


def move(
    position: Position, source: str, target: str, promotion: str | None = None
) -> str:
    """Apply a move in place. Return a short move label.

    A pawn reaching the last rank needs promotion: "Q", "R", "B" or "N".
    """
    coordinates(target)
    if target not in legal_moves(position, source):
        raise ValueError("That move is not allowed")
    promoting = promotes(position, source, target)
    if promoting and (promotion is None or promotion not in PROMOTION_PIECES):
        raise ValueError("Choose a queen, rook, bishop or knight to promote to")
    if not promoting and promotion is not None:
        raise ValueError("Only a pawn reaching the last rank promotes")
    board = position[0]
    piece = board[source]
    captured = capture_square(board, source, target)
    castling = is_castling(board, source, target)
    apply_to_board(board, source, target)
    if promotion is not None:
        board[target] = piece[0] + promotion
    double_step = piece[1] == "P" and abs(int(target[1]) - int(source[1])) == 2
    passant = source[0] + str((int(source[1]) + int(target[1])) // 2)
    position[1] = other(position[1])
    position[2:] = [
        remaining_rights(castling_rights(position), source, target),
        passant if double_step else None,
    ]
    suffix = {"check": "+", "checkmate": "#"}.get(status(position) or "", "")
    if castling:
        return ("O-O" if target[0] == "g" else "O-O-O") + suffix
    chosen = "=" + promotion if promotion is not None else ""
    return source + ("x" if captured else "-") + target + chosen + suffix


# The castling right lost when a piece leaves or is captured on each square.
RIGHT_ON_SQUARE = {"e1": "KQ", "h1": "K", "a1": "Q", "e8": "kq", "h8": "k", "a8": "q"}


def remaining_rights(rights: str, source: str, target: str) -> str:
    """Rights left after a move: a king or rook that moves, or a rook that is
    captured on its starting square, ends castling on that side."""
    lost = RIGHT_ON_SQUARE.get(source, "") + RIGHT_ON_SQUARE.get(target, "")
    return "".join(right for right in rights if right not in lost)
