from pathlib import Path

from session import Session


def test_display_after_capture_and_new_game() -> None:
    session = Session()
    assert session.view()["captured"] == []
    session.play("e2", "e4")
    session.play("d7", "d5")
    session.play("e4", "d5")
    assert session.view()["captured"] == ["bP"]
    session.dispatch({"action": "new"})
    assert session.view()["captured"] == []


def test_undoing_a_capture_removes_it_from_the_display() -> None:
    session = Session()
    for source, target in [("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5")]:
        session.play(source, target)
    assert session.view()["captured"] == ["bP", "wP"]
    assert session.dispatch({"action": "undo"})["captured"] == ["bP"]
    assert session.dispatch({"action": "undo"})["captured"] == []


def test_undo_against_the_computer_updates_the_display() -> None:
    session = Session("computer")
    session.position = [{"e1": "wK", "e8": "bK", "d1": "wQ", "d7": "bP"}, "w"]
    session.after_move()
    before = list(session.view()["captured"])
    session.dispatch({"action": "move", "source": "d1", "target": "d7"})
    assert session.view()["captured"] != before
    session.dispatch({"action": "computer-move"})
    view = session.dispatch({"action": "undo"})
    assert view["board"]["d7"] == "bP"
    assert view["captured"] == before


def test_load_restores_the_display(tmp_path: Path) -> None:
    save_path = tmp_path / "game.save.json"
    session = Session(save_path=save_path)
    for source, target in [("e2", "e4"), ("d7", "d5"), ("e4", "d5")]:
        session.play(source, target)
    session.dispatch({"action": "save"})
    fresh = Session(save_path=save_path)
    assert fresh.dispatch({"action": "load"})["captured"] == ["bP"]
    assert fresh.dispatch({"action": "undo"})["captured"] == []
