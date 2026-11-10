"""Undo: reverse moves, restore captures, turn and notation.

Against the computer, one undo returns to the human's previous turn: it takes back the
computer's reply and the human move before it. If the computer has not replied (for
example because the human move ended the game), only the human move is taken back.
"""

from typing import Any

from game import copy_position, new_position
from session import Session


def play(session: Session, *moves: str) -> dict[str, Any]:
    view: dict[str, Any] = {}
    for text in moves:
        source, target = text.split("-")
        view = session.dispatch({"action": "move", "source": source, "target": target})
    return view


def undo(session: Session) -> dict[str, Any]:
    return session.dispatch({"action": "undo"})


def test_undo_reverses_a_move() -> None:
    session = Session()
    play(session, "e2-e4")
    view = undo(session)
    assert session.position == new_position()
    assert view["turn"] == "w"
    assert view["moves"] == []
    assert view["board"] == new_position()[0]


def test_undo_restores_the_captured_piece() -> None:
    session = Session()
    play(session, "e2-e4", "d7-d5", "e4-d5")
    assert session.notation[-1] == "e4xd5"
    assert len(session.position[0]) == 31
    view = undo(session)
    assert view["board"]["d5"] == "bP"
    assert view["board"]["e4"] == "wP"
    assert len(view["board"]) == 32
    assert view["turn"] == "w"
    assert view["moves"] == ["e2-e4", "d7-d5"]


def test_undo_restores_black_to_move() -> None:
    session = Session()
    play(session, "e2-e4", "e7-e5")
    view = undo(session)
    assert view["turn"] == "b"
    assert view["moves"] == ["e2-e4"]
    assert view["board"]["e7"] == "bP"
    assert "e5" not in view["board"]


def test_undo_restores_check_status_and_notation() -> None:
    session = Session()
    play(session, "e2-e4", "f7-f6", "d2-d4", "g7-g5", "d1-h5")
    assert session.view()["status"] == "checkmate"
    view = undo(session)
    assert view["status"] is None
    assert view["winner"] is None
    assert view["turn"] == "w"
    assert view["moves"] == ["e2-e4", "f7-f6", "d2-d4", "g7-g5"]


def test_repeated_undo_reaches_the_start() -> None:
    session = Session()
    play(session, "e2-e4", "d7-d5", "e4-d5", "d8-d5", "b1-c3")
    for _ in range(5):
        undo(session)
    assert session.position == new_position()
    assert session.notation == []


def test_undo_at_the_start_does_nothing() -> None:
    session = Session()
    before = session.view()
    assert undo(session) == before
    assert undo(session) == before
    assert session.position == new_position()


def test_extra_undo_after_reaching_the_start_does_nothing() -> None:
    session = Session()
    play(session, "g1-f3", "g8-f6")
    undo(session)
    undo(session)
    view = undo(session)
    assert session.position == new_position()
    assert view["moves"] == []
    assert view["turn"] == "w"


def test_a_different_move_after_undo_replaces_the_notation() -> None:
    session = Session()
    play(session, "e2-e4", "e7-e5")
    undo(session)
    view = play(session, "c7-c5")
    assert view["moves"] == ["e2-e4", "c7-c5"]
    assert view["board"]["c5"] == "bP"
    assert view["board"]["e7"] == "bP"
    assert view["turn"] == "w"


def test_undo_after_promotion_setup_reaches_the_start() -> None:
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    for _ in range(8):
        undo(session)
    assert session.position == new_position()
    assert session.notation == []


def test_new_game_clears_undo_history() -> None:
    session = Session()
    play(session, "e2-e4")
    session.dispatch({"action": "new"})
    undo(session)
    assert session.position == new_position()
    assert session.notation == []


def test_undo_against_the_computer_takes_back_the_reply_and_your_move() -> None:
    session = Session("computer")
    play(session, "e2-e4")
    session.dispatch({"action": "computer-move"})
    assert len(session.notation) == 2
    view = undo(session)
    assert session.position == new_position()
    assert view["turn"] == "w"
    assert view["moves"] == []
    assert view["opponent"] == "computer"


def test_undo_against_the_computer_returns_to_your_previous_turn() -> None:
    session = Session("computer")
    play(session, "e2-e4")
    session.dispatch({"action": "computer-move"})
    after_first_round = copy_position(session.position)
    notation = list(session.notation)
    play(session, "d2-d4")
    session.dispatch({"action": "computer-move"})
    view = undo(session)
    assert session.position == after_first_round
    assert view["moves"] == notation
    assert view["turn"] == "w"


def test_undo_against_the_computer_before_its_reply_takes_back_your_move() -> None:
    session = Session("computer")
    play(session, "e2-e4")
    view = undo(session)
    assert session.position == new_position()
    assert view["turn"] == "w"
    assert view["moves"] == []


def test_undo_your_checkmate_of_the_computer() -> None:
    session = Session("computer")
    start = [
        {"g1": "wK", "a1": "wR", "g8": "bK", "f7": "bP", "g7": "bP", "h7": "bP"},
        "w",
    ]
    session.position = copy_position(start)
    view = play(session, "a1-a8")
    assert view["status"] == "checkmate"
    view = undo(session)
    assert session.position == start
    assert view["status"] is None
    assert view["turn"] == "w"
    assert view["moves"] == []


def test_undo_at_the_start_against_the_computer_does_nothing() -> None:
    session = Session("computer")
    before = session.view()
    assert undo(session) == before


def test_moving_after_undo_against_the_computer() -> None:
    session = Session("computer")
    play(session, "e2-e4")
    session.dispatch({"action": "computer-move"})
    undo(session)
    view = play(session, "d2-d4")
    assert view["moves"] == ["d2-d4"]
    assert view["turn"] == "b"
    view = session.dispatch({"action": "computer-move"})
    assert len(view["moves"]) == 2
    assert view["turn"] == "w"
