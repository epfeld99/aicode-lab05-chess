"""The captured-pieces sidebar."""

from collections.abc import Sequence

from game import Move, Position


def captured_pieces(history: Sequence[Position], moves: Sequence[Move]) -> list[str]:
    """Pieces taken by the played moves, with their type when captured.

    history[i] is the position before moves[i]; a capture is whatever stood on
    the target square. A promotion alone captures nothing.
    """
    return sorted(
        before[0][played[1]]
        for before, played in zip(history, moves, strict=True)
        if played[1] in before[0]
    )
