"""Redo: restore what undo took back.

Expected outcomes, agreed before implementing:

- Redo restores the most recently undone move; repeated redo replays the undone
  moves in order. With nothing to redo, redo does nothing.
- A redone capture or promotion is restored exactly: the same piece chosen, the same
  notation, and the same captured-pieces display.
- Playing any move after undo discards the redo continuation.
- Against the computer, one undo takes back a round, and one redo restores that same
  round: your move and the identical computer reply. The reply is never chosen again.
  When an undo took back only your move, redo restores only that move.
- New game (and the promotion setup) clears both undo and redo.
- Save keeps the redo continuation, so undo, save, load, redo works. A save without
  redo (version 1) loads with nothing to redo; a damaged continuation is refused.
- The view's can_redo says whether there is anything to redo.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from game import Position, copy_position, new_position
from session import Session

OPENING = ["e2-e4", "d7-d5", "e4-d5", "d8-d5"]


def play(session: Session, *moves: str) -> dict[str, Any]:
    view: dict[str, Any] = {}
    for text in moves:
        source, target = text.split("-")
        view = session.dispatch({"action": "move", "source": source, "target": target})
    return view


def undo(session: Session) -> dict[str, Any]:
    return session.dispatch({"action": "undo"})


def redo(session: Session) -> dict[str, Any]:
    return session.dispatch({"action": "redo"})


def underpromoted(save_path: Path | None = None) -> Session:
    """After the promotion setup, White plays b7xa8=N, capturing a rook."""
    session = Session(save_path=save_path)
    session.dispatch({"action": "promotion-setup"})
    session.dispatch(
        {"action": "move", "source": "b7", "target": "a8", "promotion": "N"}
    )
    return session


def test_redo_restores_the_undone_move() -> None:
    session = Session()
    after = play(session, "e2-e4")
    assert undo(session)["can_redo"] is True
    view = redo(session)
    assert view == after
    assert view["can_redo"] is False
    assert session.position[1] == "b"


def test_redo_with_nothing_undone_does_nothing() -> None:
    session = Session()
    assert redo(session) == session.view()
    assert session.view()["can_redo"] is False
    before = play(session, "e2-e4")
    assert redo(session) == before


def test_redo_restores_a_capture_and_its_display() -> None:
    session = Session()
    after = play(session, *OPENING)
    assert after["captured"] == ["bP", "wP"]
    assert undo(session)["captured"] == ["bP"]
    assert undo(session)["captured"] == []
    assert redo(session)["captured"] == ["bP"]
    view = redo(session)
    assert view == after
    assert view["board"]["d5"] == "bQ"
    assert view["moves"] == ["e2-e4", "d7-d5", "e4xd5", "d8xd5"]


def test_redo_restores_the_chosen_promotion() -> None:
    session = underpromoted()
    after = session.view()
    view = undo(session)
    assert view["board"]["a8"] == "bR"
    view = redo(session)
    assert view == after
    assert view["board"]["a8"] == "wN"
    assert view["moves"][-1] == "b7xa8=N"
    assert view["captured"] == ["bP", "bR", "wP"]


def test_repeated_undo_then_redo_returns_to_the_end() -> None:
    session = Session()
    after = play(session, *OPENING)
    for _ in range(4):
        undo(session)
    assert session.position == new_position()
    for _ in range(4):
        view = redo(session)
    assert view == after
    assert redo(session) == after


def test_a_different_move_discards_redo() -> None:
    session = Session()
    play(session, "e2-e4", "e7-e5")
    undo(session)
    view = play(session, "c7-c5")
    assert view["can_redo"] is False
    assert redo(session) == view
    assert view["moves"] == ["e2-e4", "c7-c5"]


def test_the_same_move_after_undo_also_discards_redo() -> None:
    # Playing is not redoing: the rest of the continuation is gone either way.
    session = Session()
    play(session, "e2-e4", "e7-e5")
    undo(session)
    undo(session)
    view = play(session, "e2-e4")
    assert view["can_redo"] is False


def test_new_game_clears_undo_and_redo() -> None:
    session = Session()
    play(session, "e2-e4", "e7-e5")
    undo(session)
    view = session.dispatch({"action": "new"})
    assert view["can_redo"] is False
    assert redo(session) == view
    assert undo(session) == view
    assert session.position == new_position()


def test_promotion_setup_clears_redo() -> None:
    session = Session()
    play(session, "e2-e4")
    undo(session)
    view = session.dispatch({"action": "promotion-setup"})
    assert view["can_redo"] is False


def test_redo_against_the_computer_restores_the_same_round() -> None:
    session = Session("computer")
    play(session, "e2-e4")
    session.dispatch({"action": "computer-move"})
    play(session, "d2-d4")
    after = session.dispatch({"action": "computer-move"})
    undo(session)
    view = undo(session)
    assert session.position == new_position()
    view = redo(session)
    assert view["moves"] == after["moves"][:2]
    assert view["turn"] == "w"
    view = redo(session)
    assert view == after
    assert view["can_redo"] is False


def test_redo_against_the_computer_never_rechooses_its_reply() -> None:
    for _ in range(10):
        session = Session("computer")
        play(session, "e2-e4")
        after = session.dispatch({"action": "computer-move"})
        undo(session)
        assert redo(session) == after
        with pytest.raises(ValueError):
            session.dispatch({"action": "computer-move"})


def test_redo_your_checkmate_of_the_computer() -> None:
    session = Session("computer")
    start: Position = [
        {"g1": "wK", "a1": "wR", "g8": "bK", "f7": "bP", "g7": "bP", "h7": "bP"},
        "w",
    ]
    session.position = copy_position(start)
    after = play(session, "a1-a8")
    undo(session)
    assert session.position == start
    view = redo(session)
    assert view == after
    assert view["status"] == "checkmate"


def test_a_new_move_against_the_computer_discards_redo() -> None:
    session = Session("computer")
    play(session, "e2-e4")
    session.dispatch({"action": "computer-move"})
    undo(session)
    view = play(session, "d2-d4")
    assert view["can_redo"] is False
    view = session.dispatch({"action": "computer-move"})
    assert view["can_redo"] is False
    assert view["moves"][0] == "d2-d4"


@pytest.fixture
def save_path(tmp_path: Path) -> Path:
    return tmp_path / "game.save.json"


def save_and_load(session: Session, save_path: Path) -> Session:
    session.dispatch({"action": "save"})
    fresh = Session(save_path=save_path)
    fresh.dispatch({"action": "load"})
    return fresh


def test_undo_save_load_redo(save_path: Path) -> None:
    session = Session(save_path=save_path)
    after = play(session, *OPENING)
    undo(session)
    undo(session)
    fresh = save_and_load(session, save_path)
    assert fresh.view() == session.view()
    assert fresh.view()["can_redo"] is True
    redo(fresh)
    assert redo(fresh) == after


def test_undo_save_load_redo_keeps_the_promotion(save_path: Path) -> None:
    session = underpromoted(save_path)
    after = session.view()
    undo(session)
    fresh = save_and_load(session, save_path)
    view = redo(fresh)
    assert view == after
    assert view["board"]["a8"] == "wN"


def test_undo_save_load_redo_against_the_computer(save_path: Path) -> None:
    session = Session("computer", save_path=save_path)
    play(session, "e2-e4")
    after = session.dispatch({"action": "computer-move"})
    undo(session)
    fresh = save_and_load(session, save_path)
    assert fresh.view()["opponent"] == "computer"
    assert redo(fresh) == after


def test_save_lists_the_redo_continuation_in_order(save_path: Path) -> None:
    session = underpromoted(save_path)
    undo(session)
    undo(session)
    session.dispatch({"action": "save"})
    data = json.loads(save_path.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert data["redo"] == [["h3", "g2"], ["b7", "a8", "N"]]


def test_a_save_without_redo_still_loads(save_path: Path) -> None:
    session = Session(save_path=save_path)
    play(session, "e2-e4")
    session.dispatch({"action": "save"})
    data = json.loads(save_path.read_text(encoding="utf-8"))
    data["version"] = 1
    del data["redo"]
    save_path.write_text(json.dumps(data), encoding="utf-8")
    view = Session(save_path=save_path).dispatch({"action": "load"})
    assert view["moves"] == ["e2-e4"]
    assert view["can_redo"] is False


@pytest.mark.parametrize(
    "redo_list", [[["e2", "e5"]], [["e2"]], "e2-e4", None, [["b7", "a8", "K"]]]
)
def test_load_rejects_a_damaged_redo(save_path: Path, redo_list: object) -> None:
    session = Session(save_path=save_path)
    play(session, "e2-e4")
    undo(session)
    session.dispatch({"action": "save"})
    data = json.loads(save_path.read_text(encoding="utf-8"))
    data["redo"] = redo_list
    save_path.write_text(json.dumps(data), encoding="utf-8")

    current = Session(save_path=save_path)
    before = play(current, "d2-d4")
    with pytest.raises(ValueError):
        current.dispatch({"action": "load"})
    assert current.view() == before
