# tui_img_view

Watch an image stream **and its bounding boxes in the terminal**. No X, no GUI,
works over SSH. Built for ROS 2, but the viewer core does not know what ROS is:
a *transport* turns any message source into frames and boxes.

![Demo: the viewer playing the demo bag](assets/demo.gif)

## In one minute

=== "Docker (recommended)"

    ```bash
    git clone https://github.com/guilyx/tui_img_view_ros2.git && cd tui_img_view_ros2
    docker compose -f .docker/docker-compose.yml run --rm demo          # demo bag, no ROS
    BAG=/data/rec docker compose -f .docker/docker-compose.yml run --rm bag   # your bag
    docker compose -f .docker/docker-compose.yml run --rm viewer        # live ROS 2 graph
    ```

    Step by step: [Docker tutorial](docker.md).

=== "pip, with ROS 2"

    ```bash
    pip install -e .
    tui-img-view --image /camera/image_raw --boxes /yolo/detections
    ```

=== "pip, demo bag"

    ```bash
    pip install -e ".[bag]"
    tui-img-view -t bag -o path=demo/bags/tui_demo -b /detector/detections
    ```

## What you get

- **Four render modes**, cycled with ++m++: `half` (▀ blocks, 24-bit colour),
  `quadrant`, `braille` (dithered dots), `ascii`.
- **Boxes from any number of topics at once**, drawn as box glyphs with
  `label score` / `#track_id` captions in stable per-label colours.
- **Topic panel**: pick the image topic, toggle box topics.
- **Command panel and log**: buttons and a `:` command line, with a scrolling
  log of subscriptions, topic changes and decoder errors.
- **Image filters** that stack: grayscale, invert, sepia, blur, sharpen, edges,
  emboss, threshold, posterize, autocontrast, equalize.
- **Status bar**: resolution, encoding, fps, latency, box count, decoder errors.
- **`--snapshot`**: one frame as ANSI text to stdout, for pipes and bug reports.
- **Custom message types** without code, see
  [Custom box message types](custom-box-types.md).
- **Pluggable transports**: `ros2`, `bag` (MCAP, no ROS), `fake`, and yours.

## Where next

- [Docker tutorial](docker.md) is the fastest path; [Install](install.md)
  for pip and colcon; [Usage](usage.md) for every key, command and flag.
- [Demo bag](demo.md) to see it on real photos.
- [Architecture](architecture.md) for how the pieces fit.
- [Contributing](contributing.md), [Changelog](changelog.md) and the
  [MIT License](license.md).
