# Contributing

Thanks for helping out. This page is the short version; the
[docs](https://guilyx.github.io/tui_img_view_ros2/) cover the design.

## Set up

```bash
git clone https://github.com/guilyx/tui_img_view_ros2.git && cd tui_img_view_ros2
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,docs]"
```

No ROS is needed for development. The ROS 2 codecs and detection adapters are
duck-typed and tested against stub messages, the `bag` transport exercises
them on real CDR data from `demo/bags/tui_demo`, and the Textual app is driven
headlessly.

## Before you push

```bash
ruff check . && ruff format .      # lint and format (CI runs --check)
pytest -q                          # 70+ tests, ~20 s
mkdocs build --strict              # docs must build without warnings
tui-img-view -t fake --snapshot    # eyeball one frame
```

CI runs the same on Python 3.10 and 3.12.

## Where things go

| change | where |
|---|---|
| a new message source | `tui_img_view/transports/<name>.py`, register it in `core/registry.py` or as an entry point |
| a new box message type | an adapter in `transports/ros2/detections.py`, or document a `--box-type` field map |
| a new image encoding | `transports/ros2/codecs.py` + a test in `tests/test_codecs.py` |
| a render mode | `render/rasterize.py` (`RasterMode` subclass) + `tests/test_rasterize.py` |
| a key or command | `ui/app.py` bindings and `ui/commands.py`; update `docs/usage.md` and the README table |

Keep `render/` and `core/` free of Textual imports and everything outside
`transports/ros2/transport.py` free of `rclpy` imports; the tests rely on it.

## Pull requests

- One topic per PR, with tests for behaviour changes.
- Update `CHANGELOG.md` under *Unreleased*.
- Regenerate the demo bag with `python demo/make_demo_bag.py` only if you
  changed it on purpose, and say so.
- Commit messages: a short imperative summary line, then the why.

## Releasing

Bump the version in `setup.py` and `package.xml`, move the *Unreleased*
section of `CHANGELOG.md` under the new version, tag `vX.Y.Z`.

## License

By contributing you agree that your contributions are licensed under the
[MIT License](https://guilyx.github.io/tui_img_view_ros2/license/) (the `LICENSE` file at the repository root).
