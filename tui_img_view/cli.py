"""Command line entry point.

tui-img-view --transport ros2 --image /camera/image_raw --boxes /detections
tui-img-view --transport fake
tui-img-view --transport fake --snapshot     # print one frame and exit
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from collections.abc import Sequence

from tui_img_view import __version__
from tui_img_view.core.registry import available_transports, load_transport
from tui_img_view.core.session import ViewerSession
from tui_img_view.core.transport import TransportUnavailable
from tui_img_view.render.filters import FILTER_ORDER
from tui_img_view.render.pipeline import Renderer
from tui_img_view.render.rasterize import MODE_ORDER


def strip_ros_args(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    """Split ``--ros-args ... [--]`` out of argv so argparse never sees it."""
    ours: list[str] = []
    ros: list[str] = []
    it = iter(argv)
    for arg in it:
        if arg == "--ros-args":
            ros.append(arg)
            for inner in it:
                ros.append(inner)
                if inner == "--":
                    break
            continue
        ours.append(arg)
    return ours, ros


def _parse_options(items: Sequence[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise argparse.ArgumentTypeError(f"expected key=value, got {item!r}")
        options[key.strip()] = value
    return options


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tui-img-view",
        description="View image topics and bounding boxes in the terminal.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-t",
        "--transport",
        default="ros2",
        help=f"message source (default: ros2). Available: {', '.join(available_transports())}",
    )
    parser.add_argument(
        "-o",
        "--transport-opt",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="transport-specific option, repeatable (e.g. -o qos=reliable, -o file=photo.jpg)",
    )
    parser.add_argument("-i", "--image", metavar="TOPIC", help="image topic to show first")
    parser.add_argument(
        "-b",
        "--boxes",
        metavar="TOPIC",
        action="append",
        default=[],
        help="box topic(s) to overlay",
    )
    parser.add_argument(
        "-m", "--mode", choices=MODE_ORDER, default="half", help="render mode (default: half)"
    )
    parser.add_argument("--no-color", action="store_true", help="grayscale rendering")
    parser.add_argument(
        "-F",
        "--filter",
        action="append",
        default=[],
        choices=FILTER_ORDER,
        metavar="NAME",
        help=(
            "image filter to start with, repeatable and applied in order "
            f"({', '.join(FILTER_ORDER)})"
        ),
    )
    parser.add_argument("--no-boxes", action="store_true", help="start with boxes hidden")
    parser.add_argument("--no-labels", action="store_true", help="hide box captions")
    parser.add_argument(
        "--cell-aspect",
        type=float,
        default=0.5,
        help="terminal cell width/height ratio used to keep the image aspect (default 0.5)",
    )
    parser.add_argument("--fps", type=float, default=20.0, help="UI refresh rate (default 20)")
    parser.add_argument(
        "--hide-topics", action="store_true", help="start with the topic panel hidden"
    )
    parser.add_argument(
        "--hide-sidebar", action="store_true", help="start with the command/log sidebar hidden"
    )
    parser.add_argument(
        "--stale",
        type=float,
        default=2.0,
        help="hide boxes older than this many seconds (default 2)",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="render a single frame as ANSI text to stdout and exit (no TUI)",
    )
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="seconds to wait for a frame with --snapshot"
    )
    parser.add_argument(
        "--list-topics", action="store_true", help="print discovered topics and exit"
    )
    plug = parser.add_argument_group("custom box message types")
    plug.add_argument(
        "--adapter",
        action="append",
        default=[],
        metavar="MODULE[:FUNC]",
        help="import a Python module that registers detection adapters (repeatable)",
    )
    plug.add_argument(
        "--box-type",
        action="append",
        default=[],
        metavar="SPEC",
        help=(
            "declare a box message type without code: "
            "'pkg/msg/Type:items=detections,x=bbox.x,y=bbox.y,w=bbox.w,h=bbox.h"
            "[,label=..,score=..,id=..,origin=topleft|center]' (repeatable)"
        ),
    )
    plug.add_argument(
        "--box-types", metavar="FILE.toml", help="TOML file with [[box_types]] tables (same keys)"
    )
    return parser


def register_custom_box_types(args: argparse.Namespace) -> list[str]:
    """Apply --adapter / --box-type / --box-types and entry points. Returns new type names."""
    from tui_img_view.transports.ros2 import detections as det

    added: list[str] = []
    try:
        added += det.load_entry_point_adapters()
        added += det.load_adapter_plugins(args.adapter)
        for spec in args.box_type:
            added.append(det.parse_box_type_spec(spec).register().type_name)
        if args.box_types:
            for field_map in det.load_box_types_file(args.box_types):
                added.append(field_map.register().type_name)
    except (ImportError, AttributeError, ValueError, OSError, RuntimeError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    return added


def _make_session(args: argparse.Namespace) -> ViewerSession:
    try:
        transport_cls = load_transport(args.transport)
    except KeyError as exc:
        raise SystemExit(f"error: {exc}") from exc
    try:
        transport = transport_cls.from_options(_parse_options(args.transport_opt))
    except (TransportUnavailable, ValueError, argparse.ArgumentTypeError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    return ViewerSession(transport, stale_after=args.stale)


def _make_renderer(args: argparse.Namespace) -> Renderer:
    return Renderer(
        args.mode,
        color=not args.no_color,
        show_boxes=not args.no_boxes,
        show_labels=not args.no_labels,
        cell_aspect=args.cell_aspect,
        filters=args.filter,
    )


def _apply_selection(session: ViewerSession, args: argparse.Namespace) -> None:
    if args.image:
        session.select_image(args.image)
    if args.boxes:
        session.set_box_topics(args.boxes)


def run_list_topics(session: ViewerSession, timeout: float) -> int:
    with session:
        deadline = time.monotonic() + max(0.0, timeout)
        topics = session.refresh_topics()
        while not topics and time.monotonic() < deadline:
            time.sleep(0.2)
            topics = session.refresh_topics()
    if not topics:
        print("no image or box topics found", file=sys.stderr)
        return 1
    for topic in topics:
        print(f"{topic.kind.value:6} {topic.name}  ({topic.type})")
    return 0


def run_snapshot(session: ViewerSession, renderer: Renderer, args: argparse.Namespace) -> int:
    from tui_img_view.render.ansi import canvas_to_ansi

    size = shutil.get_terminal_size((100, 30))
    cols, rows = size.columns, max(1, size.lines - 1)
    with session:
        session.refresh_topics()
        if not args.image:
            session.next_image()
        _apply_selection(session, args)
        deadline = time.monotonic() + max(0.0, args.timeout)
        snap = session.snapshot()
        while snap.frame is None and time.monotonic() < deadline:
            time.sleep(0.05)
            snap = session.snapshot()
        if snap.frame is None:
            print(f"error: no frame received on {snap.image_topic!r}", file=sys.stderr)
            if snap.error:
                print(f"error: {snap.error}", file=sys.stderr)
            return 1
        # Give detections a moment to arrive so the overlay is not empty.
        if snap.box_topics and not snap.detections:
            wait_until = time.monotonic() + min(1.0, args.timeout)
            while not snap.detections and time.monotonic() < wait_until:
                time.sleep(0.05)
                snap = session.snapshot()
        canvas = renderer.render(snap.frame, snap.detections, cols, rows)
    sys.stdout.write(canvas_to_ansi(canvas, color=True) + "\n")
    sys.stdout.flush()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    ours, ros_args = strip_ros_args(raw)
    args = build_parser().parse_args(ours)
    register_custom_box_types(args)
    session = _make_session(args)
    if ros_args and hasattr(session.transport, "_args"):
        session.transport._args = [sys.argv[0], *ros_args]  # type: ignore[attr-defined]
    renderer = _make_renderer(args)

    if args.list_topics:
        return run_list_topics(session, args.timeout)
    if args.snapshot:
        return run_snapshot(session, renderer, args)

    from tui_img_view.ui.app import ViewerApp

    app = ViewerApp(
        session,
        renderer=renderer,
        refresh_hz=args.fps,
        show_topics=not args.hide_topics,
        show_sidebar=not args.hide_sidebar,
    )
    try:
        session.start()
        _apply_selection(session, args)
        app.run()
    finally:
        session.stop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
