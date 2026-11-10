import json
import threading
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from game import new_position
from server import make_server
from session import Session

OPENING = [("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5")]


def played(save_path: Path, moves: list[tuple[str, str]]) -> Session:
    session = Session(save_path=save_path)
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})
    return session


@pytest.fixture
def save_path(tmp_path: Path) -> Path:
    return tmp_path / "game.save.json"


def test_load_restores_the_game_in_a_fresh_session(save_path: Path) -> None:
    original = played(save_path, OPENING)
    original.dispatch({"action": "save"})

    fresh = Session(save_path=save_path)
    view = fresh.dispatch({"action": "load"})

    assert view == original.view()
    assert view["board"] == original.position[0]
    assert view["turn"] == "w"
    assert view["moves"] == ["e2-e4", "d7-d5", "e4xd5", "d8xd5"]
    assert view["opponent"] == "human"
    assert fresh.moves == OPENING


def test_undo_takes_back_moves_made_before_saving(save_path: Path) -> None:
    played(save_path, OPENING).dispatch({"action": "save"})
    fresh = Session(save_path=save_path)
    fresh.dispatch({"action": "load"})

    view = fresh.dispatch({"action": "undo"})
    assert view["board"]["d5"] == "wP"
    assert view["board"]["d8"] == "bQ"
    assert view["turn"] == "b"
    assert view["moves"] == ["e2-e4", "d7-d5", "e4xd5"]
    for _ in range(3):
        view = fresh.dispatch({"action": "undo"})
    assert fresh.position == new_position()
    assert view["moves"] == []


def test_undo_against_the_computer_after_loading(save_path: Path) -> None:
    session = Session("computer", save_path=save_path)
    session.dispatch({"action": "move", "source": "e2", "target": "e4"})
    session.dispatch({"action": "computer-move"})
    session.dispatch({"action": "save"})

    fresh = Session(save_path=save_path)
    fresh.dispatch({"action": "load"})
    view = fresh.dispatch({"action": "undo"})
    assert fresh.position == new_position()
    assert view["moves"] == []
    assert view["opponent"] == "computer"


def test_save_after_undo_keeps_only_the_remaining_moves(save_path: Path) -> None:
    session = played(save_path, OPENING)
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "save"})
    fresh = Session(save_path=save_path)
    view = fresh.dispatch({"action": "load"})
    assert view == session.view()
    assert fresh.moves == OPENING[:3]


def test_loaded_game_continues(save_path: Path) -> None:
    played(save_path, OPENING).dispatch({"action": "save"})
    fresh = Session(save_path=save_path)
    fresh.dispatch({"action": "load"})
    view = fresh.dispatch({"action": "move", "source": "b1", "target": "c3"})
    assert view["moves"][-1] == "b1-c3"
    assert fresh.moves[-1] == ("b1", "c3")
    assert len(fresh.moves) == 5


def test_load_keeps_the_computer_opponent(save_path: Path) -> None:
    session = Session(save_path=save_path)
    session.dispatch({"action": "new", "opponent": "computer"})
    session.dispatch({"action": "move", "source": "e2", "target": "e4"})
    session.dispatch({"action": "save"})

    fresh = Session(save_path=save_path)
    view = fresh.dispatch({"action": "load"})
    assert view["opponent"] == "computer"
    with pytest.raises(ValueError):
        fresh.dispatch({"action": "move", "source": "e7", "target": "e5"})
    view = fresh.dispatch({"action": "computer-move"})
    assert view["turn"] == "w"
    assert len(fresh.moves) == 2


def test_load_restores_a_finished_game(save_path: Path) -> None:
    session = played(
        save_path, [("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4")]
    )
    session.dispatch({"action": "save"})
    view = Session(save_path=save_path).dispatch({"action": "load"})
    assert view["status"] == "checkmate"
    assert view["winner"] == "Black"
    assert view["moves"][-1] == "d8-h4#"


def test_load_replaces_the_current_game(save_path: Path) -> None:
    played(save_path, OPENING[:1]).dispatch({"action": "save"})
    session = Session("computer", save_path=save_path)
    session.dispatch({"action": "move", "source": "d2", "target": "d4"})
    view = session.dispatch({"action": "load"})
    assert view["opponent"] == "human"
    assert view["moves"] == ["e2-e4"]
    assert session.moves == [("e2", "e4")]


def test_save_file_is_versioned_json(save_path: Path) -> None:
    played(save_path, OPENING[:2]).dispatch({"action": "save"})
    data = json.loads(save_path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["opponent"] == "human"
    assert data["turn"] == "w"
    assert data["notation"] == ["e2-e4", "d7-d5"]
    assert data["moves"] == [["e2", "e4"], ["d7", "d5"]]
    assert data["board"]["e4"] == "wP"


def test_save_overwrites_the_previous_save(save_path: Path) -> None:
    session = played(save_path, OPENING[:1])
    session.dispatch({"action": "save"})
    session.dispatch({"action": "move", "source": "d7", "target": "d5"})
    session.dispatch({"action": "save"})
    view = Session(save_path=save_path).dispatch({"action": "load"})
    assert view["moves"] == ["e2-e4", "d7-d5"]


def test_new_game_can_still_save(save_path: Path) -> None:
    session = Session(save_path=save_path)
    session.dispatch({"action": "new", "opponent": "computer"})
    session.dispatch({"action": "save"})
    assert Session(save_path=save_path).dispatch({"action": "load"})["opponent"] == (
        "computer"
    )


def test_save_and_load_need_a_configured_file() -> None:
    session = Session()
    for action in ("save", "load"):
        with pytest.raises(ValueError):
            session.dispatch({"action": action})


def test_load_without_a_save_leaves_the_game(save_path: Path) -> None:
    session = played(save_path, OPENING[:1])
    before = session.view()
    with pytest.raises(ValueError, match="No saved game"):
        session.dispatch({"action": "load"})
    assert session.view() == before
    assert session.moves == OPENING[:1]


def corrupt(data: dict[str, Any], change: str) -> None:
    if change == "version":
        data["version"] = 99
    elif change == "opponent":
        data["opponent"] = "robot"
    elif change == "illegal-history":
        data["moves"][1] = ["e7", "e4"]
    elif change == "malformed-history":
        data["moves"] = [["e2"]]
    elif change == "board":
        data["board"]["a1"] = "wQ"
    elif change == "turn":
        data["turn"] = "b"
    elif change == "notation":
        data["notation"][0] = "e2-e3"
    elif change == "missing":
        del data["moves"]


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "opponent",
        "illegal-history",
        "malformed-history",
        "board",
        "turn",
        "notation",
        "missing",
    ],
)
def test_load_rejects_an_inconsistent_save(save_path: Path, change: str) -> None:
    played(save_path, OPENING).dispatch({"action": "save"})
    data = json.loads(save_path.read_text(encoding="utf-8"))
    corrupt(data, change)
    save_path.write_text(json.dumps(data), encoding="utf-8")

    session = played(save_path, OPENING[:1])
    before = session.view()
    with pytest.raises(ValueError):
        session.dispatch({"action": "load"})
    assert session.view() == before
    assert session.moves == OPENING[:1]


@pytest.mark.parametrize("content", [b"not json", b"[]", b"\xff\xfe"])
def test_load_rejects_an_unreadable_save(save_path: Path, content: bytes) -> None:
    save_path.write_bytes(content)
    with pytest.raises(ValueError):
        Session(save_path=save_path).dispatch({"action": "load"})


@pytest.fixture
def serve(save_path: Path) -> Iterator[Callable[[], str]]:
    """Start servers that share a save file, as a restarted server would."""
    servers = []

    def start() -> str:
        server = make_server(0, save_path)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_port}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def post(base: str, action: dict[str, str]) -> Any:
    request = urllib.request.Request(
        base + "/api/action",
        data=json.dumps(action).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def test_server_loads_a_save_after_restart(serve: Callable[[], str]) -> None:
    first = serve()
    post(first, {"action": "new", "opponent": "computer"})
    post(first, {"action": "move", "source": "e2", "target": "e4"})
    post(first, {"action": "computer-move"})
    saved = post(first, {"action": "save"})

    second = serve()
    with urllib.request.urlopen(second + "/api/state") as response:
        assert json.load(response)["moves"] == []
    loaded = post(second, {"action": "load"})
    assert loaded == saved
    assert loaded["opponent"] == "computer"
    assert len(loaded["moves"]) == 2
