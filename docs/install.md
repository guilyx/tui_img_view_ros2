# Install

Python 3.10 or newer. Every supported ROS 2 distro's Python works (Humble 3.10,
Iron 3.10, Jazzy 3.12).

## pip

```bash
git clone https://github.com/guilyx/tui_img_view_ros2.git
cd tui_img_view_ros2
pip install -e .
```

Extras:

| extra | adds | for |
|---|---|---|
| `bag` | `mcap`, `mcap-ros2-support` | the `bag` transport (play MCAP bags with no ROS) |
| `docs` | `mkdocs-material`, `mkdocstrings` | building this site |
| `dev` | pytest, ruff, the bag deps | running the test suite |

```bash
pip install -e ".[bag,dev]"
```

## colcon workspace

The repository is an `ament_python` package, so `ros2 run` works:

```bash
cd ~/ros2_ws/src && git clone https://github.com/guilyx/tui_img_view_ros2.git
cd ~/ros2_ws && pip install textual pillow numpy
colcon build --packages-select tui_img_view
source install/setup.bash
ros2 run tui_img_view viewer --help
```

!!! note "Why the extra pip line"
    `textual` has no rosdep key, so it is installed with pip. `numpy` and
    `pillow` resolve through rosdep (`python3-numpy`, `python3-pil`) but the
    pip line covers non-rosdep setups too.

## Check it works

```bash
tui-img-view -t fake --snapshot -b /detector/detections
```

prints one coloured frame with boxes and exits. If you see it, the renderer,
the fake transport and your terminal's colour support are all fine.
