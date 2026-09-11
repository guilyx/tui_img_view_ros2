# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-11

### Added

- Terminal viewer for image topics with bounding box overlays, built on
  Textual. Four render modes (`half`, `quadrant`, `braille`, `ascii`), boxes
  from any number of topics at once, captions with label, score and track id.
- Three-column layout: topic panel, aspect-correct image, and a sidebar with a
  command panel (buttons and a `:` command line) over a timestamped log.
- Transport-agnostic core: `Frame`, `BoundingBox`, `Detections`, a
  four-method `Transport` interface, a thread-safe `ViewerSession`, and a
  registry with `tui_img_view.transports` entry-point discovery.
- `ros2` transport (rclpy) decoding `sensor_msgs/Image` without cv_bridge
  (8/16-bit colour and mono, float depth, yuv422, Bayer) and
  `sensor_msgs/CompressedImage`; detection adapters for
  `vision_msgs/Detection2DArray`, `Detection2D`, `BoundingBox2DArray` and
  `yolo_msgs/DetectionArray`.
- `bag` transport playing rosbag2 MCAP files with no ROS installed.
- `fake` transport with a synthetic scene or a user photo.
- Custom box message types without code: `--box-type` field maps,
  `--box-types file.toml`, `--adapter module`, and a
  `tui_img_view.detection_adapters` entry-point group.
- `--snapshot` and `--list-topics` modes for scripts and bug reports.
- Demo bag `demo/bags/tui_demo` (real photographs, hand-annotated boxes) and
  the `demo/make_demo_bag.py` generator.
- MkDocs Material documentation deployed to GitHub Pages; CI on Python 3.10
  and 3.12 with ruff, pytest, snapshot smoke tests and a strict docs build.
- Packaging for pip and colcon (`ament_python`).

[Unreleased]: https://github.com/guilyx/tui_img_view_ros2/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/guilyx/tui_img_view_ros2/releases/tag/v0.1.0
