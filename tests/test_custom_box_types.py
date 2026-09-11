from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from tui_img_view.cli import main
from tui_img_view.transports.ros2.detections import (
    DETECTION_ADAPTERS,
    BoxFieldMap,
    load_adapter_plugins,
    load_box_types_file,
    parse_box_type_spec,
    resolve_path,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    before = dict(DETECTION_ADAPTERS)
    yield
    DETECTION_ADAPTERS.clear()
    DETECTION_ADAPTERS.update(before)


def _msg():
    return SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace(sec=2, nanosec=0), frame_id="cam"),
        objects=[
            SimpleNamespace(
                name="cup",
                conf=0.9,
                uid=4,
                rect=SimpleNamespace(x=10.0, y=20.0, w=30.0, h=40.0),
                hyps=[SimpleNamespace(cls="mug")],
            ),
            SimpleNamespace(
                name="bottle",
                conf=0.3,
                uid=0,
                rect=SimpleNamespace(x=50.0, y=60.0, w=10.0, h=20.0),
                hyps=[SimpleNamespace(cls="flask")],
            ),
        ],
    )


def test_resolve_path_with_indexes():
    msg = _msg()
    assert resolve_path(msg, "objects[0].hyps[0].cls") == "mug"
    assert resolve_path(msg, "objects[-1].rect.w") == 10.0
    assert resolve_path(msg, "") is msg


def test_field_map_topleft_and_center():
    fm = BoxFieldMap(
        "my/msg/Objects",
        items="objects",
        x="rect.x",
        y="rect.y",
        w="rect.w",
        h="rect.h",
        label="hyps[0].cls",
        score="conf",
        id="uid",
    )
    dets = fm(_msg())
    assert dets.stamp == 2.0 and dets.frame_id == "cam" and len(dets) == 2
    a, b = dets.boxes
    assert (a.x, a.y, a.w, a.h) == (10, 20, 30, 40)
    assert a.label == "mug" and a.score == 0.9 and a.track_id == "4"
    assert b.track_id == "0"  # ids are strings, 0 is still an id
    centered = BoxFieldMap(
        "my/msg/Objects",
        items="objects",
        x="rect.x",
        y="rect.y",
        w="rect.w",
        h="rect.h",
        origin="center",
    )
    c = centered(_msg()).boxes[0]
    assert (c.x, c.y) == (-5, 0) and c.label == "" and c.score is None
    with pytest.raises(ValueError):
        BoxFieldMap("t/msg/T", x="x", y="y", w="w", h="h", origin="middle")


def test_field_map_single_message():
    fm = BoxFieldMap("my/msg/One", x="rect.x", y="rect.y", w="rect.w", h="rect.h", label="name")
    single = _msg().objects[0]
    dets = fm(single)
    assert len(dets) == 1 and dets.boxes[0].label == "cup"


def test_parse_spec_and_register():
    fm = parse_box_type_spec(
        "my_msgs/msg/Objects: items=objects, x=rect.x, y=rect.y, w=rect.w, h=rect.h, "
        "label=name, score=conf, origin=center"
    )
    assert fm.type_name == "my_msgs/msg/Objects" and fm.origin == "center" and fm.score == "conf"
    fm.register()
    assert DETECTION_ADAPTERS["my_msgs/msg/Objects"] is fm
    for bad in (
        "no-colon",
        "notatype:x=1,y=2,w=3,h=4",
        "a/msg/B:x=1,y=2,w=3",  # missing h
        "a/msg/B:x=1,y=2,w=3,h=4,bogus=5",
        "a/msg/B:x=1,y=2,w=3,h=4,label",
    ):
        with pytest.raises(ValueError):
            parse_box_type_spec(bad)


def test_load_box_types_file(tmp_path):
    pytest.importorskip("tomllib", reason="needs tomllib/tomli") if sys.version_info >= (
        3,
        11,
    ) else pytest.importorskip("tomli")
    toml = tmp_path / "boxes.toml"
    toml.write_text(
        '[[box_types]]\ntype = "my_msgs/msg/Objects"\nitems = "objects"\n'
        'x = "rect.x"\ny = "rect.y"\nw = "rect.w"\nh = "rect.h"\nlabel = "name"\n\n'
        '[[box_types]]\ntype = "my_msgs/msg/One"\n'
        'x = "rect.x"\ny = "rect.y"\nw = "rect.w"\nh = "rect.h"\n'
    )
    maps = load_box_types_file(toml)
    assert [m.type_name for m in maps] == ["my_msgs/msg/Objects", "my_msgs/msg/One"]
    assert maps[0](_msg()).boxes[1].label == "bottle"
    bad = tmp_path / "bad.toml"
    bad.write_text('[[box_types]]\nx = "a"\n')
    with pytest.raises(ValueError):
        load_box_types_file(bad)
    bad.write_text('[[box_types]]\ntype = "a/msg/B"\nx="1"\ny="2"\nw="3"\nh="4"\nnope="5"\n')
    with pytest.raises(ValueError):
        load_box_types_file(bad)


def test_load_adapter_plugins(tmp_path, monkeypatch):
    (tmp_path / "my_adapters.py").write_text(
        "from tui_img_view.transports.ros2.detections import register_detection_adapter\n"
        "from tui_img_view.core.types import Detections\n"
        "@register_detection_adapter('plug/msg/Auto')\n"
        "def auto(msg):\n    return Detections()\n"
        "def setup():\n"
        "    register_detection_adapter('plug/msg/Explicit')(lambda msg: Detections())\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    added = load_adapter_plugins(["my_adapters:setup"])
    assert added == ["plug/msg/Auto", "plug/msg/Explicit"]
    with pytest.raises(ImportError):
        load_adapter_plugins(["does_not_exist_xyz"])
    sys.modules.pop("my_adapters", None)


def test_cli_registers_custom_types(capsys):
    spec = "cli_msgs/msg/Boxes:items=boxes,x=x,y=y,w=w,h=h,label=cls"
    assert main(["-t", "fake", "--box-type", spec, "--list-topics"]) == 0
    assert "cli_msgs/msg/Boxes" in DETECTION_ADAPTERS
    with pytest.raises(SystemExit):
        main(["-t", "fake", "--box-type", "garbage", "--list-topics"])
    with pytest.raises(SystemExit):
        main(["-t", "fake", "--adapter", "nope.module", "--list-topics"])
