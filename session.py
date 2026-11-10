"""Application actions and information shown beside the board."""

import json
from pathlib import Path
from typing import Any

from captured import captured_pieces
from computer import choose_move
from game import (
    Move,
    Position,
    copy_position,
    legal_moves,
    move,
    new_position,
    promotes,
    status,
    winner,
)

# Legal from the standard starting position under this game's rules.
# Next move: b7-a8, capturing a rook and reaching the last rank.
PROMOTION_SETUP = [
    ("a2", "a4"),
    ("h7", "h5"),
    ("a4", "a5"),
    ("h5", "h4"),
    ("a5", "a6"),
    ("h4", "h3"),
    ("a6", "b7"),
    ("h3", "g2"),
]

OPPONENTS = ("human", "computer")
SAVE_VERSION = 2


def saved_moves(value: object) -> list[list[str]]:
    """Return a list of moves read from a save file, or raise ValueError."""
    if not isinstance(value, list) or not all(
        isinstance(entry, list)
        and len(entry) in (2, 3)
        and all(isinstance(part, str) for part in entry)
        for entry in value
    ):
        raise ValueError("The saved moves are damaged")
    return value


def square(action: dict[str, Any], key: str) -> str:
    value = action.get(key)
    if not isinstance(value, str):
        raise TypeError("Expected a square such as e2")
    return value


class Session:
    def __init__(self, opponent: str = "human", save_path: Path | None = None) -> None:
        self.save_path = save_path
        self.reset(opponent)

    def reset(self, opponent: str = "human") -> None:
        if opponent not in OPPONENTS:
            raise ValueError("Unknown opponent")
        self.position: Position = new_position()
        self.notation: list[str] = []
        self.captured: list[str] = []
        self.opponent = opponent
        # The position before each played move; history[i] precedes notation[i].
        self.history: list[Position] = []
        # Every move played from the start, so a saved game can be replayed.
        self.moves: list[Move] = []
        # Moves taken back by undo, the next one to redo last.
        self.undone: list[Move] = []

    def play(self, source: str, target: str, promotion: str | None = None) -> None:
        """Play a new move, which discards anything left to redo."""
        self.undone.clear()
        self.apply(source, target, promotion)

    def apply(self, source: str, target: str, promotion: str | None = None) -> None:
        before = copy_position(self.position)
        label = move(self.position, source, target, promotion)
        self.history.append(before)
        self.notation.append(label)
        self.moves.append(
            (source, target) if promotion is None else (source, target, promotion)
        )
        self.after_move()

    def after_move(self) -> None:
        self.captured = captured_pieces(self.history, self.moves)

    def undo(self) -> None:
        """Take back the last move; against the computer, return to the human's turn.

        At the start of the game there is nothing to take back and nothing changes.
        """
        if not self.history:
            return
        self.take_back()
        if self.opponent == "computer" and self.position[1] == "b" and self.history:
            self.take_back()
        # Recompute anything derived from the position, as after a move.
        self.after_move()

    def take_back(self) -> None:
        self.position = self.history.pop()
        self.notation.pop()
        self.undone.append(self.moves.pop())

    def redo(self) -> None:
        """Restore what the last undo took back; against the computer, the whole round.

        The computer's reply is the one that was undone, not chosen again. With
        nothing to redo, nothing changes.
        """
        if not self.undone:
            return
        self.apply(*self.undone.pop())
        if self.opponent == "computer" and self.position[1] == "b" and self.undone:
            self.apply(*self.undone.pop())

    def view(self) -> dict[str, Any]:
        # Copies, so a view kept by the caller does not change with later moves.
        return {
            "board": dict(self.position[0]),
            "turn": self.position[1],
            "moves": list(self.notation),
            "opponent": self.opponent,
            "status": status(self.position),
            "winner": winner(self.position),
            "can_redo": bool(self.undone),
            **self.sidebar(),
        }

    def computer_to_move(self) -> bool:
        return (
            self.opponent == "computer"
            and self.position[1] == "b"
            and status(self.position) not in ("checkmate", "stalemate")
        )

    def sidebar(self) -> dict[str, Any]:
        return {"captured": list(self.captured)}

    def configured_save_path(self) -> Path:
        if self.save_path is None:
            raise ValueError("Saving is not available")
        return self.save_path

    def save(self) -> None:
        """Write the game to the save file, replacing any earlier save."""
        path = self.configured_save_path()
        data = {
            "version": SAVE_VERSION,
            "opponent": self.opponent,
            "board": self.position[0],
            "turn": self.position[1],
            "notation": self.notation,
            "moves": [list(entry) for entry in self.moves],
            # The moves redo would restore, in the order it restores them.
            "redo": [list(entry) for entry in reversed(self.undone)],
        }
        partial = path.with_name(path.name + ".tmp")
        partial.write_text(json.dumps(data, indent=2), encoding="utf-8")
        partial.replace(path)

    def load(self) -> None:
        """Replace the game with the saved one, or leave it unchanged on failure.

        The moves are replayed from the starting position and must reproduce the
        saved board, turn and notation, which also rebuilds the undo history. The
        redo continuation is played and taken back again, so it must be legal too.
        """
        path = self.configured_save_path()
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ValueError("No saved game") from None
        except OSError as error:
            raise ValueError("Could not read the saved game") from error
        data = json.loads(text)
        # Version 1 saves came before redo and have nothing to redo.
        if not (isinstance(data, dict) and data.get("version") in (1, SAVE_VERSION)):
            raise ValueError("Not a saved game from this version")
        moves = saved_moves(data.get("moves"))
        redo = saved_moves(data.get("redo") if data["version"] > 1 else [])
        restored = type(self)(data.get("opponent", ""), self.save_path)
        for entry in moves:
            restored.play(*entry)
        if (
            restored.position[0] != data.get("board")
            or restored.position[1] != data.get("turn")
            or restored.notation != data.get("notation")
        ):
            raise ValueError("The saved game does not match its moves")
        for entry in redo:
            restored.apply(*entry)
        for _ in redo:
            restored.take_back()
        restored.after_move()
        # Take every attribute, including any that after_move maintains.
        vars(self).update(vars(restored))

    def dispatch(self, action: dict[str, Any]) -> dict[str, Any]:
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(
                square(action, "source"),
                square(action, "target"),
                action.get("promotion"),
            )
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            choice = choose_move(self.position)
            if choice is None:
                raise ValueError("The computer has no move")
            self.play(*choice)
        elif command == "undo":
            self.undo()
        elif command == "redo":
            self.redo()
        elif command == "legal":
            source = square(action, "source")
            targets = legal_moves(self.position, source)
            return {
                "targets": targets,
                "promotions": [
                    t for t in targets if promotes(self.position, source, t)
                ],
            }
        elif command == "new":
            self.reset(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.reset()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        elif command == "save":
            self.save()
        elif command == "load":
            self.load()
        else:
            raise ValueError("Unknown action")
        return self.view()
