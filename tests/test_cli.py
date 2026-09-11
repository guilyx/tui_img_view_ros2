from __future__ import annotations

from tui_img_view.cli import build_parser, main, strip_ros_args


def test_strip_ros_args():
    ours, ros = strip_ros_args(["-t", "ros2", "--ros-args", "-r", "a:=b", "--", "--mode", "ascii"])
    assert ours == ["-t", "ros2", "--mode", "ascii"]
    assert ros == ["--ros-args", "-r", "a:=b", "--"]
    assert strip_ros_args(["--ros-args", "-p", "x:=1"]) == ([], ["--ros-args", "-p", "x:=1"])


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.transport == "ros2" and args.mode == "half" and args.boxes == []


def test_snapshot_and_list_topics(capsys):
    assert main(["-t", "fake", "-o", "width=40", "-o", "height=20", "--list-topics"]) == 0
    out = capsys.readouterr().out
    assert "/camera/image_raw" in out and "boxes" in out
    assert main(["-t", "fake", "--snapshot", "-b", "/detector/detections", "-m", "ascii"]) == 0
    out = capsys.readouterr().out
    assert "\x1b[38;2;" in out and "┌" in out


def test_unknown_transport_exits():
    import pytest

    with pytest.raises(SystemExit):
        main(["-t", "nope", "--snapshot"])
