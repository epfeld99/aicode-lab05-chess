"""Promotion combined with undo, captured pieces, and save/load."""

import json
from pathlib import Path

import pytest

from game import Position, copy_position, new_position
from session import Session


def promoted(save_path: Path | None = None) -> Session:
    """After the promotion setup, White plays b7xa8=Q."""
    session = Session(save_path=save_path)
    session.dispatch({"action": "promotion-setup"})
    session.dispatch(
        {"action": "move", "source": "b7", "target": "a8", "promotion": "Q"}
    )
    return session


def test_undo_takes_back_a_promotion() -> None:
    session = promoted()
    assert session.notation[-1] == "b7xa8=Q"
    view = session.dispatch({"action": "undo"})
    assert view["board"]["b7"] == "wP"
    assert view["board"]["a8"] == "bR"
    assert view["turn"] == "w"
    assert "b7xa8=Q" not in view["moves"]


def test_repeated_undo_after_promotion_reaches_the_start() -> None:
    session = promoted()
    for _ in range(9):
        session.dispatch({"action": "undo"})
    assert session.position == new_position()
    assert session.view()["captured"] == []


def test_undo_against_the_computer_takes_back_its_promotion() -> None:
    session = Session("computer")
    start: Position = [{"a8": "wK", "e8": "bK", "a2": "wP", "h2": "bP"}, "w"]
    session.position = copy_position(start)
    session.dispatch({"action": "move", "source": "a2", "target": "a3"})
    view = session.dispatch({"action": "computer-move"})
    assert view["board"].get("h1") == "bQ"
    view = session.dispatch({"action": "undo"})
    assert session.position == start
    assert view["moves"] == []


def test_promotion_alone_is_not_a_capture() -> None:
    session = Session()
    session.position = [{"a1": "wK", "h6": "bK", "d7": "wP"}, "w"]
    view = session.dispatch(
        {"action": "move", "source": "d7", "target": "d8", "promotion": "Q"}
    )
    assert view["captured"] == []


def test_captured_display_after_a_capturing_promotion() -> None:
    # The setup captured a black pawn (a6xb7) and a white pawn (h3xg2).
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    assert session.view()["captured"] == ["bP", "wP"]
    assert promoted().view()["captured"] == ["bP", "bR", "wP"]


def test_a_captured_promoted_piece_shows_its_type_at_capture() -> None:
    session = Session()
    session.position = [{"a1": "wK", "h8": "bK", "b7": "wP", "c8": "bR"}, "w"]
    session.dispatch(
        {"action": "move", "source": "b7", "target": "b8", "promotion": "Q"}
    )
    view = session.dispatch({"action": "move", "source": "c8", "target": "b8"})
    assert view["captured"] == ["wQ"]
    view = session.dispatch({"action": "undo"})
    assert view["captured"] == []


def test_undoing_a_capturing_promotion_restores_the_display() -> None:
    session = promoted()
    view = session.dispatch({"action": "undo"})
    assert view["captured"] == ["bP", "wP"]


def test_save_and_load_keep_a_promotion(tmp_path: Path) -> None:
    save_path = tmp_path / "game.save.json"
    session = promoted(save_path)
    session.dispatch({"action": "save"})
    fresh = Session(save_path=save_path)
    view = fresh.dispatch({"action": "load"})
    assert view["board"]["a8"] == "wQ"
    assert view["moves"] == session.notation
    assert view["captured"] == ["bP", "bR", "wP"]
    view = fresh.dispatch({"action": "undo"})
    assert view["board"]["b7"] == "wP"
    assert view["board"]["a8"] == "bR"


def test_load_rejects_a_damaged_promotion_choice(tmp_path: Path) -> None:
    save_path = tmp_path / "game.save.json"
    promoted(save_path).dispatch({"action": "save"})
    data = json.loads(save_path.read_text(encoding="utf-8"))
    data["moves"][-1][2] = "K"
    save_path.write_text(json.dumps(data), encoding="utf-8")
    fresh = Session(save_path=save_path)
    with pytest.raises(ValueError):
        fresh.dispatch({"action": "load"})
    assert fresh.position == new_position()
