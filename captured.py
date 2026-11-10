"""The captured-pieces sidebar."""

from collections.abc import Sequence

from game import Move, Position, capture_square


def captured_pieces(history: Sequence[Position], moves: Sequence[Move]) -> list[str]:
    """Pieces taken by the played moves, with their type when captured.

    history[i] is the position before moves[i]. A promotion alone captures nothing;
    en passant captures the pawn beside the target square.
    """
    taken = (
        (before[0], capture_square(before[0], played[0], played[1]))
        for before, played in zip(history, moves, strict=True)
    )
    return sorted(board[square] for board, square in taken if square)
