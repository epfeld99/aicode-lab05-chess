"""Application actions and information shown beside the board."""

from typing import Any

from computer import choose_move
from game import (
    Position,
    copy_position,
    legal_moves,
    move,
    new_position,
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


def square(action: dict[str, Any], key: str) -> str:
    value = action.get(key)
    if not isinstance(value, str):
        raise TypeError("Expected a square such as e2")
    return value


class Session:
    def __init__(self, opponent: str = "human") -> None:
        if opponent not in ("human", "computer"):
            raise ValueError("Unknown opponent")
        self.position: Position = new_position()
        self.notation: list[str] = []
        self.opponent = opponent
        # The position before each played move; history[i] precedes notation[i].
        self.history: list[Position] = []

    def play(self, source: str, target: str) -> None:
        before = copy_position(self.position)
        label = move(self.position, source, target)
        self.history.append(before)
        self.notation.append(label)
        self.after_move()

    def after_move(self) -> None:
        pass

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

    def view(self) -> dict[str, Any]:
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "opponent": self.opponent,
            "status": status(self.position),
            "winner": winner(self.position),
            **self.sidebar(),
        }

    def computer_to_move(self) -> bool:
        return (
            self.opponent == "computer"
            and self.position[1] == "b"
            and status(self.position) not in ("checkmate", "stalemate")
        )

    def sidebar(self) -> dict[str, Any]:
        return {}

    def dispatch(self, action: dict[str, Any]) -> dict[str, Any]:
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(square(action, "source"), square(action, "target"))
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            choice = choose_move(self.position)
            if choice is None:
                raise ValueError("The computer has no move")
            self.play(*choice)
        elif command == "undo":
            self.undo()
        elif command == "legal":
            return {"targets": legal_moves(self.position, square(action, "source"))}
        elif command == "new":
            self.__init__(action.get("opponent", "human"))  # type: ignore[misc]
        elif command == "promotion-setup":
            self.__init__()  # type: ignore[misc]
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        else:
            raise ValueError("Unknown action")
        return self.view()
