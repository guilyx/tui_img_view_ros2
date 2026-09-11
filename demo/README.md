# Demo bag

`bags/tui_demo/` is a real ROS 2 bag in MCAP storage:

| topic | type | messages |
|---|---|---|
| `/camera/image/compressed` | `sensor_msgs/msg/CompressedImage` (jpeg, 400x300) | 120 |
| `/detector/detections` | `vision_msgs/msg/Detection2DArray` | 120 |

12 seconds at 10 fps: slow pans and zooms over four photographs, with
hand-annotated boxes (person, shuttle, helmet, flag, eyes, nose, cup, saucer,
spoon, rocket, towers) that move with the camera. Track ids and scores are
filled in, and the detector runs 15 ms behind the camera, like a real one.

## Play it

With ROS 2 (Humble or newer, `ros2-<distro>-rosbag2-storage-mcap` installed):

```bash
ros2 bag play demo/bags/tui_demo --loop
tui-img-view -i /camera/image/compressed -b /detector/detections
```

Without ROS at all, through the viewer's `bag` transport:

```bash
pip install "tui_img_view[bag]"
tui-img-view -t bag -o path=demo/bags/tui_demo -b /detector/detections
```

## Regenerate

```bash
pip install mcap mcap-ros2-support scikit-image
python demo/make_demo_bag.py
```

`make_demo_bag.py` writes the CDR messages itself (no ROS needed), so the
message definitions it embeds are the ones `ros2 bag play` publishes.

## Photo credits

Shipped with scikit-image: *astronaut* (Eileen Collins, NASA, public domain),
*rocket* (SpaceX/NASA, public domain), *chelsea* (Stefan van der Walt, CC0),
*coffee* (Rachel Michetti, CC0).
