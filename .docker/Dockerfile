# syntax=docker/dockerfile:1
#
# Two images from one file:
#
#   slim  - python:3.12-slim + tui_img_view[bag]. Plays MCAP bags and the fake
#           scene. No ROS. ~200 MB.
#   ros2  - ros:<distro>-ros-base + tui_img_view[bag] + vision_msgs + rosbag2
#           MCAP storage. Talks to a live ROS 2 graph (host networking) and can
#           `ros2 bag play`. ~900 MB.
#
#   docker build -f .docker/Dockerfile --target slim -t tui_img_view:slim .
#   docker build -f .docker/Dockerfile --target ros2 -t tui_img_view:ros2 .
#   docker build -f .docker/Dockerfile --target ros2 --build-arg ROS_DISTRO=humble ...
#
# Or just `docker compose -f .docker/docker-compose.yml ...` (see .docker/README.md).

ARG ROS_DISTRO=jazzy

# ---------------------------------------------------------------------------
FROM python:3.12-slim AS slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TERM=xterm-256color \
    COLORTERM=truecolor

WORKDIR /app
COPY setup.py setup.cfg package.xml README.md LICENSE ./
COPY resource ./resource
COPY tui_img_view ./tui_img_view
RUN pip install ".[bag]"
COPY demo/bags ./demo/bags

RUN useradd --create-home --uid 1000 viewer && chown -R viewer:viewer /app
USER viewer

ENTRYPOINT ["tui-img-view"]
# Default: play the bundled demo bag. Override with any tui-img-view arguments.
CMD ["-t", "bag", "-o", "path=/app/demo/bags/tui_demo", "-b", "/detector/detections"]

# ---------------------------------------------------------------------------
FROM ros:${ROS_DISTRO}-ros-base AS ros2
ARG ROS_DISTRO

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TERM=xterm-256color \
    COLORTERM=truecolor \
    ROS_DISTRO=${ROS_DISTRO}

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip \
        python3-venv \
        ros-${ROS_DISTRO}-vision-msgs \
        ros-${ROS_DISTRO}-rosbag2-storage-mcap \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY setup.py setup.cfg package.xml README.md LICENSE ./
COPY resource ./resource
COPY tui_img_view ./tui_img_view
# A venv that can still see the apt-installed rclpy / rosidl packages.
RUN python3 -m venv --system-site-packages /opt/venv \
    && /opt/venv/bin/pip install ".[bag]"
ENV PATH=/opt/venv/bin:${PATH}
COPY demo/bags ./demo/bags
COPY .docker/entrypoint.sh /entrypoint.sh

RUN useradd --create-home --uid 1000 viewer && chown -R viewer:viewer /app \
    && chmod +x /entrypoint.sh
USER viewer

ENTRYPOINT ["/entrypoint.sh"]
# Default: the viewer against the live ROS 2 graph (topics discovered on their own).
CMD []
