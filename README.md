# tui_img_view

[![CI](https://github.com/guilyx/tui_img_view_ros2/actions/workflows/ci.yml/badge.svg)](https://github.com/guilyx/tui_img_view_ros2/actions/workflows/ci.yml)
[![Docs](https://github.com/guilyx/tui_img_view_ros2/actions/workflows/docs.yml/badge.svg)](https://guilyx.github.io/tui_img_view_ros2/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![ROS 2 Humble+](https://img.shields.io/badge/ROS%202-Humble%2B-22314E.svg)](https://docs.ros.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Watch an image stream **and its bounding boxes in the terminal**. No X, no GUI,
works over SSH. Built for ROS 2, transport-agnostic by design: `ros2`, rosbag2
MCAP files with no ROS installed, or a synthetic scene.

**Docs:** <https://guilyx.github.io/tui_img_view_ros2/>

![The viewer playing the demo bag: topic panel, image, command panel and log](docs/assets/demo.gif)

## Quick start (Docker)

```bash
git clone https://github.com/guilyx/tui_img_view_ros2.git && cd tui_img_view_ros2

docker compose -f .docker/docker-compose.yml run --rm demo                        # bundled demo bag
BAG=/data/my_recording docker compose -f .docker/docker-compose.yml run --rm bag   # your own MCAP bag
docker compose -f .docker/docker-compose.yml run --rm viewer                      # live ROS 2 graph (Linux)
```

Step-by-step, including live ROS 2 setup and troubleshooting:
[Docker tutorial](https://guilyx.github.io/tui_img_view_ros2/docker/).

Without Docker: `pip install -e ".[bag]"` then `tui-img-view -t bag -o path=demo/bags/tui_demo`,
or `colcon build` it as an `ament_python` package. See
[Install](https://guilyx.github.io/tui_img_view_ros2/install/).

## Features

- Four render modes: half-block (24-bit colour), quadrant, braille, ascii.
- Boxes from any number of topics at once, with label, score and track id.
- Stackable image filters: gray, invert, sepia, blur, sharpen, edges, and more.
- Topic panel, command panel with a `:` command line, and an event log.
- `--snapshot` prints one frame as ANSI text for scripts and bug reports.
- Reads `sensor_msgs/Image` and `CompressedImage` without cv_bridge, boxes from
  `vision_msgs` and `yolo_msgs`, and any other box message via a one-line
  [field map](https://guilyx.github.io/tui_img_view_ros2/custom-box-types/).
- A [demo bag](https://guilyx.github.io/tui_img_view_ros2/demo/) with real photos
  and hand-annotated boxes, playable with `ros2 bag play` or straight from the file.

## Keys

`:` command · `s` sidebar · `t` topics · `n` next image · `m` mode · `f` filter ·
`b` boxes · `l` labels · `c` colour · `p` pause · `r` rescan · `q` quit

Everything else, from every flag and command to writing your own transport:

| | |
|---|---|
| [Usage](https://guilyx.github.io/tui_img_view_ros2/usage/) | keys, commands, flags, filters, transport options |
| [ROS 2 transport](https://guilyx.github.io/tui_img_view_ros2/ros2/) | supported encodings and detection messages, QoS |
| [Custom box types](https://guilyx.github.io/tui_img_view_ros2/custom-box-types/) | plug in your own message without code |
| [Writing a transport](https://guilyx.github.io/tui_img_view_ros2/transports/) | four methods to add a new source |
| [Architecture](https://guilyx.github.io/tui_img_view_ros2/architecture/) | how the pieces fit |

## Contributing

Issues and pull requests welcome. [CONTRIBUTING.md](CONTRIBUTING.md) has the
setup and checks; [CHANGELOG.md](CHANGELOG.md) tracks what changed.

## License

[MIT](LICENSE). Demo photographs are public domain (NASA) or CC0; credits in
[demo/README.md](demo/README.md).
