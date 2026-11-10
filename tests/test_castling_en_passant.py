"""Castling and en passant, and how they combine with undo, captures and saves.

A position may carry castling rights ("KQkq" style) and an en passant square after
the board and side to move. A position given as only [board, turn] has neither.
"""

from pathlib import Path

import pytest

from computer import choose_move
from game import Position, copy_position, legal_moves, move, new_position
from session import Session


def played(*moves: str, session: Session | None = None) -> Session:
    session = session or Session()
    for text in moves:
        source, target = text.split("-")
        session.dispatch({"action": "move", "source": source, "target": target})
    return session


# White can castle kingside after this; Black can castle kingside too.
ITALIAN = ("e2-e4", "e7-e5", "g1-f3", "b8-c6", "f1-c4", "g8-f6")


# Castling


def test_white_castles_kingside() -> None:
    session = played(*ITALIAN)
    assert "g1" in legal_moves(session.position, "e1")
    view = played("e1-g1", session=session).view()
    assert view["board"]["g1"] == "wK"
    assert view["board"]["f1"] == "wR"
    assert "e1" not in session.position[0]
    assert "h1" not in session.position[0]
    assert session.notation[-1] == "O-O"
    assert session.position[1] == "b"


def test_black_castles_kingside() -> None:
    session = played(*ITALIAN, "e1-g1", "f8-c5", "a2-a3")
    assert "g8" in legal_moves(session.position, "e8")
    played("e8-g8", session=session)
    assert session.position[0]["g8"] == "bK"
    assert session.position[0]["f8"] == "bR"
    assert session.notation[-1] == "O-O"


@pytest.mark.parametrize(
    "side,rights,king,rook,king_to,rook_to",
    [
        ("w", "Q", "e1", "a1", "c1", "d1"),
        ("b", "q", "e8", "a8", "c8", "d8"),
    ],
)
def test_queenside_castling(
    side: str, rights: str, king: str, rook: str, king_to: str, rook_to: str
) -> None:
    other_king = "h8" if side == "w" else "h1"
    other = "b" if side == "w" else "w"
    position: Position = [
        {king: side + "K", rook: side + "R", other_king: other + "K"},
        side,
        rights,
        None,
    ]
    assert king_to in legal_moves(position, king)
    assert move(position, king, king_to) == "O-O-O"
    assert position[0][king_to] == side + "K"
    assert position[0][rook_to] == side + "R"
    assert rook not in position[0]


def test_no_castling_through_pieces() -> None:
    position = new_position()
    assert legal_moves(position, "e1") == []


def test_no_castling_after_the_king_has_moved() -> None:
    session = played(*ITALIAN, "e1-e2", "a7-a6", "e2-e1", "a6-a5")
    assert "g1" not in legal_moves(session.position, "e1")


def test_no_castling_after_that_rook_has_moved() -> None:
    session = played(*ITALIAN, "h1-g1", "a7-a6", "g1-h1", "a6-a5")
    assert "g1" not in legal_moves(session.position, "e1")


def test_moving_one_rook_keeps_castling_on_the_other_side() -> None:
    position: Position = [
        {"e1": "wK", "a1": "wR", "h1": "wR", "e8": "bK"},
        "w",
        "KQ",
        None,
    ]
    move(position, "h1", "h2")
    move(position, "e8", "d8")
    assert "g1" not in legal_moves(position, "e1")
    assert "c1" in legal_moves(position, "e1")


def test_capturing_a_rook_on_its_square_removes_that_right() -> None:
    position: Position = [
        {"e1": "wK", "h1": "wR", "e8": "bK", "h8": "bR"},
        "w",
        "Kk",
        None,
    ]
    move(position, "h1", "h8")
    assert "k" not in position[2]
    assert "K" not in position[2]


def king_and_rook(attacker: str, square: str) -> Position:
    return [
        {"e1": "wK", "h1": "wR", "a1": "wR", "b8": "bK", square: "b" + attacker},
        "w",
        "KQ",
        None,
    ]


def test_no_castling_out_of_check() -> None:
    position = king_and_rook("R", "e5")
    assert "g1" not in legal_moves(position, "e1")
    assert "c1" not in legal_moves(position, "e1")


def test_no_castling_through_an_attacked_square() -> None:
    position = king_and_rook("R", "f5")
    assert "g1" not in legal_moves(position, "e1")
    assert "c1" in legal_moves(position, "e1")


def test_no_castling_into_check() -> None:
    position = king_and_rook("R", "g5")
    assert "g1" not in legal_moves(position, "e1")


def test_queenside_castling_allowed_when_only_b1_is_attacked() -> None:
    position = king_and_rook("R", "b5")
    assert "c1" in legal_moves(position, "e1")


def test_two_item_positions_have_no_castling_rights() -> None:
    position: Position = [{"e1": "wK", "h1": "wR", "e8": "bK"}, "w"]
    assert "g1" not in legal_moves(position, "e1")


def test_undo_castling_restores_king_rook_and_rights() -> None:
    session = played(*ITALIAN, "e1-g1")
    view = session.dispatch({"action": "undo"})
    assert view["board"]["e1"] == "wK"
    assert view["board"]["h1"] == "wR"
    assert "g1" not in view["board"]
    assert "g1" in legal_moves(session.position, "e1")


def test_save_and_load_keep_castling_rights(tmp_path: Path) -> None:
    save_path = tmp_path / "game.save.json"
    session = Session(save_path=save_path)
    played(*ITALIAN, "e1-e2", "a7-a6", "e2-e1", session=session)
    session.dispatch({"action": "save"})
    fresh = Session(save_path=save_path)
    fresh.dispatch({"action": "load"})
    assert fresh.position == session.position
    played("f8-e7", session=fresh)
    assert "g1" not in legal_moves(fresh.position, "e1")


def test_save_and_load_a_castled_game(tmp_path: Path) -> None:
    save_path = tmp_path / "game.save.json"
    session = Session(save_path=save_path)
    played(*ITALIAN, "e1-g1", session=session)
    session.dispatch({"action": "save"})
    fresh = Session(save_path=save_path)
    view = fresh.dispatch({"action": "load"})
    assert view["moves"][-1] == "O-O"
    assert view["board"]["f1"] == "wR"


# En passant


def test_white_captures_en_passant() -> None:
    session = played("e2-e4", "a7-a6", "e4-e5", "d7-d5")
    assert "d6" in legal_moves(session.position, "e5")
    view = played("e5-d6", session=session).view()
    assert view["board"]["d6"] == "wP"
    assert "d5" not in view["board"]
    assert "e5" not in view["board"]
    assert view["moves"][-1] == "e5xd6"
    assert view["captured"] == ["bP"]


def test_black_captures_en_passant() -> None:
    session = played("a2-a3", "d7-d5", "a3-a4", "d5-d4", "e2-e4")
    assert "e3" in legal_moves(session.position, "d4")
    played("d4-e3", session=session)
    assert session.position[0]["e3"] == "bP"
    assert "e4" not in session.position[0]
    assert session.view()["captured"] == ["wP"]


def test_en_passant_only_on_the_next_move() -> None:
    session = played("e2-e4", "a7-a6", "e4-e5", "d7-d5", "h2-h3", "h7-h6")
    assert "d6" not in legal_moves(session.position, "e5")


def test_no_en_passant_after_two_single_steps() -> None:
    session = played("e2-e4", "d7-d6", "e4-e5", "d6-d5")
    assert "d6" not in legal_moves(session.position, "e5")


def test_no_en_passant_that_exposes_the_king() -> None:
    position: Position = [
        {"a5": "wK", "b5": "wP", "c7": "bP", "h5": "bR", "e8": "bK"},
        "b",
        "",
        None,
    ]
    move(position, "c7", "c5")
    assert "c6" not in legal_moves(position, "b5")


def test_undo_en_passant_restores_the_pawn_and_the_chance() -> None:
    session = played("e2-e4", "a7-a6", "e4-e5", "d7-d5", "e5-d6")
    view = session.dispatch({"action": "undo"})
    assert view["board"]["d5"] == "bP"
    assert view["board"]["e5"] == "wP"
    assert view["captured"] == []
    assert "d6" in legal_moves(session.position, "e5")


def test_save_and_load_keep_the_en_passant_chance(tmp_path: Path) -> None:
    save_path = tmp_path / "game.save.json"
    session = Session(save_path=save_path)
    played("e2-e4", "a7-a6", "e4-e5", "d7-d5", session=session)
    session.dispatch({"action": "save"})
    fresh = Session(save_path=save_path)
    fresh.dispatch({"action": "load"})
    assert "d6" in legal_moves(fresh.position, "e5")
    played("e5-d6", session=fresh)
    assert fresh.view()["captured"] == ["bP"]


def test_computer_captures_en_passant() -> None:
    session = Session("computer")
    start: Position = [{"a1": "wK", "h8": "bK", "e2": "wP", "d4": "bP"}, "w"]
    session.position = copy_position(start)
    played("e2-e4", session=session)
    assert choose_move(session.position) == ("d4", "e3")
    view = session.dispatch({"action": "computer-move"})
    assert view["board"]["e3"] == "bP"
    assert "e4" not in view["board"]


# Redo


def test_redo_castling_moves_the_rook_again() -> None:
    session = played(*ITALIAN, "e1-g1")
    session.dispatch({"action": "undo"})
    view = session.dispatch({"action": "redo"})
    assert view["board"]["g1"] == "wK"
    assert view["board"]["f1"] == "wR"
    assert view["moves"][-1] == "O-O"
    assert "k" in session.position[2]
    assert "K" not in session.position[2]


def test_redo_en_passant_takes_the_pawn_again() -> None:
    session = played("e2-e4", "a7-a6", "e4-e5", "d7-d5", "e5-d6")
    session.dispatch({"action": "undo"})
    view = session.dispatch({"action": "redo"})
    assert view["board"]["d6"] == "wP"
    assert "d5" not in view["board"]
    assert view["moves"][-1] == "e5xd6"
    assert view["captured"] == ["bP"]


def test_redo_through_a_double_step_restores_the_en_passant_chance() -> None:
    session = played("e2-e4", "a7-a6", "e4-e5", "d7-d5")
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "redo"})
    assert "d6" in legal_moves(session.position, "e5")


def test_redo_castling_after_save_and_load(tmp_path: Path) -> None:
    save_path = tmp_path / "game.save.json"
    session = Session(save_path=save_path)
    played(*ITALIAN, "e1-g1", session=session)
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "save"})
    fresh = Session(save_path=save_path)
    view = fresh.dispatch({"action": "load"})
    assert view["can_redo"]
    assert "g1" in legal_moves(fresh.position, "e1")
    view = fresh.dispatch({"action": "redo"})
    assert view["moves"][-1] == "O-O"
    assert view["board"]["f1"] == "wR"


def test_redo_against_the_computer_restores_its_en_passant_capture() -> None:
    session = Session("computer")
    session.position = [{"a1": "wK", "h8": "bK", "e2": "wP", "d4": "bP"}, "w"]
    played("e2-e4", session=session)
    session.dispatch({"action": "computer-move"})
    after_round = copy_position(session.position)
    session.dispatch({"action": "undo"})
    view = session.dispatch({"action": "redo"})
    assert session.position == after_round
    assert view["moves"] == ["e2-e4", "d4xe3"]
