#!/usr/bin/env bash
# Source ROS 2, then run the viewer unless a different command was given.
#   docker run ... tui_img_view:ros2                    -> tui-img-view
#   docker run ... tui_img_view:ros2 -i /cam -b /dets   -> tui-img-view -i /cam -b /dets
#   docker run ... tui_img_view:ros2 ros2 topic list    -> ros2 topic list
set -e
# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO}/setup.bash"
if [ "$#" -eq 0 ] || [ "${1#-}" != "$1" ]; then
    exec tui-img-view "$@"
fi
exec "$@"
