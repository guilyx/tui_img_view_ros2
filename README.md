# tui_img_view

[![CI](https://github.com/guilyx/tui_img_view_ros2/actions/workflows/ci.yml/badge.svg)](https://github.com/guilyx/tui_img_view_ros2/actions/workflows/ci.yml)
[![Docs](https://github.com/guilyx/tui_img_view_ros2/actions/workflows/docs.yml/badge.svg)](https://guilyx.github.io/tui_img_view_ros2/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![ROS 2 Humble+](https://img.shields.io/badge/ROS%202-Humble%2B-22314E.svg)](https://docs.ros.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Watch an image stream **and its bounding boxes in the terminal**. No X, no GUI,
works over SSH. Built for ROS 2, but the viewer core does not know what ROS is:
a *transport* turns any message source into frames and boxes, and the ROS 2
transport is just the first one.

**Documentation:** <https://guilyx.github.io/tui_img_view_ros2/>

![The viewer playing the demo bag: topic panel, image, command panel and log](docs/assets/demo.gif)

## Quick start

```bash
git clone https://github.com/guilyx/tui_img_view_ros2.git && cd tui_img_view_ros2
pip install -e ".[bag]"

tui-img-view --image /camera/image_raw --boxes /yolo/detections        # live ROS 2
tui-img-view -t bag -o path=demo/bags/tui_demo -b /detector/detections  # demo bag, no ROS needed
tui-img-view -t fake                                                    # synthetic scene
```

## Features

- **Four render modes**, cycled with `m`: `half` (▀ blocks, 24-bit colour),
  `quadrant` (2x2 glyphs), `braille` (2x4 dithered dots), `ascii`.
- **Boxes from any number of topics at once**, drawn as box glyphs with
  `label score` / `#track_id` captions in stable per-label colours.
- **Three-column layout**: topic panel, aspect-correct image, and a sidebar
  with a command panel (buttons plus a `:` command line) over a scrolling
  log of subscriptions, topic changes and decoder errors.
- **Status bar**: resolution, encoding, fps, latency, box count, errors.
- **`--snapshot`** prints one frame as ANSI text and exits (pipes, CI, bug reports).
- **Transports**: `ros2` (rclpy), `bag` (rosbag2 MCAP files, **no ROS installed**),
  `fake` (synthetic scene or a photo), and yours via a four-method interface.
- **Custom box message types** without code: `--box-type` / `--box-types file.toml`.
- **Demo bag** with real photos and hand-annotated boxes in `demo/bags/tui_demo`.

## Install

Requirements: Python 3.10+ (Humble, Iron and Jazzy all qualify). ROS 2 is only
needed for the `ros2` transport.

```bash
pip install -e .            # viewer
pip install -e ".[bag]"     # + rosbag2 MCAP playback without ROS
pip install -e ".[dev]"     # + test and lint tools
```

As an `ament_python` package in a colcon workspace (`ros2 run tui_img_view viewer`):

```bash
cd ~/ros2_ws/src && git clone https://github.com/guilyx/tui_img_view_ros2.git
cd ~/ros2_ws && pip install textual pillow numpy
colcon build --packages-select tui_img_view && source install/setup.bash
```

`textual` has no rosdep key, hence the pip line. Full details:
[Install](https://guilyx.github.io/tui_img_view_ros2/install/).

## Usage

```bash
tui-img-view [-t ros2|bag|fake] [-i TOPIC] [-b TOPIC ...] [-m half|quadrant|braille|ascii] [options]
ros2 run tui_img_view viewer ...                # same program from a colcon workspace
ros2 bag play demo/bags/tui_demo --loop         # then view /camera/image/compressed
```

Topics are discovered on their own; `-i` and `-b` only pre-select.

| key | action | key | action |
|---|---|---|---|
| `:` | type a command | `b` | boxes on/off |
| `s` | command + log sidebar | `l` | captions on/off |
| `t` | topic panel | `c` | colour / grayscale |
| `n` | next image topic | `p` | pause |
| `m` | cycle render mode | `r` | rescan topics |
| `Esc` | back to the image | `q` | quit |

Commands (`:` then `Enter`): `mode`, `image <topic>`, `next`, `prev`,
`boxes [on|off|+topic|-topic|topic]`, `labels`, `color`, `pause`, `stale <s>`,
`fps <hz>`, `aspect <ratio>`, `rescan`, `topics`, `sidebar`, `clear`, `help`,
`quit`.

Transport options go through `-o key=value`: `ros2` takes `qos=sensor|reliable`,
`depth`, `node_name` (and `--ros-args` passes through); `bag` takes `path`,
`rate`, `loop`; `fake` takes `fps`, `width`, `height`, `objects`, `file`, `seed`.
Every flag: [Usage](https://guilyx.github.io/tui_img_view_ros2/usage/).

## Supported messages

| kind | types |
|---|---|
| images | `sensor_msgs/Image` (rgb/bgr/rgba/bgra 8-bit, mono8/16, 8UC*, 16UC1, 32FC1, 64FC1, rgb16/bgr16, yuv422, yuyv, bayer_*8), `sensor_msgs/CompressedImage` |
| boxes | `vision_msgs/Detection2DArray`, `Detection2D`, `BoundingBox2DArray` (Foxy and Humble+ layouts), `yolo_msgs/DetectionArray` |

Images are decoded without cv_bridge. Depth-like single-channel images are
min–max normalised per frame. Box coordinates are taken to be in the pixel
space of the displayed image.

Any other box message plugs in without touching the viewer:

```bash
tui-img-view -b /my/objects --box-type \
  "my_msgs/msg/Objects:items=objects,x=rect.x,y=rect.y,w=rect.w,h=rect.h,label=name,score=conf,origin=center"
```

or with `--box-types boxes.toml`, `--adapter my_pkg.adapters` (a
`@register_detection_adapter` function), or a `tui_img_view.detection_adapters`
entry point. See
[Custom box message types](https://guilyx.github.io/tui_img_view_ros2/custom-box-types/).

## Architecture

```
tui_img_view/
├── core/        Frame · BoundingBox · Detections · Transport ABC · ViewerSession · registry
├── render/      Frame + boxes → Canvas of (char, fg, bg) cells; four raster modes; ANSI output
├── transports/  fake · manual · bag (MCAP, no ROS) · ros2 (rclpy, codecs, detection adapters)
└── ui/          Textual app: image view, topic panel, command panel + log, status bar
```

Data flows one way: transport callback → `ViewerSession` (any thread) →
`snapshot()` polled by the UI → `Renderer` → `Canvas` → screen. Nothing below
`ui/` imports Textual and nothing outside `transports/ros2/transport.py`
imports `rclpy`, so the whole pipeline is tested in plain pytest. A new
transport is four methods; see
[Writing a transport](https://guilyx.github.io/tui_img_view_ros2/transports/).

## Contributing

Bug reports and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the development setup, test suite and conventions, and
[CHANGELOG.md](CHANGELOG.md) for what changed.

```bash
pip install -e ".[dev,docs]"
ruff check . && ruff format --check . && pytest -q && mkdocs build --strict
```

## License

Released under the [MIT License](LICENSE). Demo photographs are public domain
(NASA) or CC0; see [demo/README.md](demo/README.md) for credits.
