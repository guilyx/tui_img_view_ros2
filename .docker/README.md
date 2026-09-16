# Docker

Two images are built from `.docker/Dockerfile`:

| target | base | what it can do | size |
|---|---|---|---|
| `slim` | `python:3.12-slim` | `bag` and `fake` transports, `--snapshot` | ~200 MB |
| `ros2` | `ros:jazzy-ros-base` (`ROS_DISTRO` build arg) | everything, including the live `ros2` transport and `ros2 bag play` | ~900 MB |

All commands below are run from the repository root.

## Try it in one command (no ROS on the host)

```bash
docker compose -f .docker/docker-compose.yml run --rm demo
```

builds the slim image and plays the bundled demo bag with boxes. Any
`tui-img-view` arguments can follow, for example `demo -m braille --filter edges`.

## Play your own bag

```bash
BAG=/data/my_recording docker compose -f .docker/docker-compose.yml run --rm bag -b /detections
```

`BAG` may be a rosbag2 directory or a single `.mcap` file; it is mounted
read-only at `/bag`. `RATE=0.5` slows playback.

## View a live ROS 2 graph

```bash
docker compose -f .docker/docker-compose.yml run --rm viewer
docker compose -f .docker/docker-compose.yml run --rm viewer -i /camera/image_raw -b /yolo/detections
ROS_DOMAIN_ID=7 docker compose -f .docker/docker-compose.yml run --rm viewer
```

The `viewer` service uses the host network and IPC namespace so DDS discovery
sees the nodes on your machine. Set `ROS_DOMAIN_ID`, `ROS_LOCALHOST_ONLY` and
`RMW_IMPLEMENTATION` to match your host. Pick another distro with
`ROS_DISTRO=humble docker compose -f .docker/docker-compose.yml build viewer`.

To try the ROS path with no camera around, play the demo bag into the graph
from a second terminal:

```bash
docker compose -f .docker/docker-compose.yml --profile ros-demo run --rm bag-play
docker compose -f .docker/docker-compose.yml run --rm viewer -i /camera/image/compressed -b /detector/detections
```

## Plain docker

```bash
docker build -f .docker/Dockerfile --target slim -t tui_img_view:slim .
docker run --rm -it tui_img_view:slim                       # demo bag
docker run --rm -it tui_img_view:slim -t fake -m ascii      # synthetic scene
docker run --rm tui_img_view:slim -t fake --snapshot        # one frame to stdout

docker build -f .docker/Dockerfile --target ros2 -t tui_img_view:ros2 .
docker run --rm -it --network host --ipc host tui_img_view:ros2
docker run --rm -it --network host --ipc host tui_img_view:ros2 ros2 topic list
```

The `ros2` image's entrypoint sources ROS and runs `tui-img-view` when the
first argument starts with `-` (or there are none); any other command runs
as-is.

## Notes

- The images run as the unprivileged `viewer` user (uid 1000).
- `TERM=xterm-256color`, `COLORTERM=truecolor` and a UTF-8 locale are set so
  the block glyphs and 24-bit colour work; keep `-it` (compose `run` does).
- The Python package is installed from the build context, so rebuild after
  code changes. `.dockerignore` keeps caches, the docs site and git out of the
  context.
