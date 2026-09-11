# Demo bag

The repository ships a small, real ROS 2 bag at `demo/bags/tui_demo/` (MCAP
storage, 1.9 MB): 12 seconds of slow pans and zooms over four photographs,
with hand-annotated boxes that move with the camera.

| topic | type | messages |
|---|---|---|
| `/camera/image/compressed` | `sensor_msgs/msg/CompressedImage` (jpeg, 400x300) | 120 |
| `/detector/detections` | `vision_msgs/msg/Detection2DArray` | 120 |

Every detection carries a class, a score and a track id, and is stamped 15 ms
after its image, like a real detector.

![Demo bag in the viewer](assets/demo.gif)

## Play it with ROS 2

Needs the MCAP storage plugin (`ros-<distro>-rosbag2-storage-mcap`, default
on Iron and newer).

```bash
ros2 bag info demo/bags/tui_demo
ros2 bag play demo/bags/tui_demo --loop
tui-img-view -i /camera/image/compressed -b /detector/detections
```

## Play it without ROS

The `bag` transport reads the MCAP file directly and feeds the same decoders
the live transport uses:

```bash
pip install -e ".[bag]"
tui-img-view -t bag -o path=demo/bags/tui_demo -b /detector/detections
tui-img-view -t bag -o path=demo/bags/tui_demo -o rate=0.5 -m braille
```

It works on any rosbag2 MCAP recording whose topics use the supported
message types, not just this one.

## How it was made

`demo/make_demo_bag.py` writes the bag with `mcap-ros2-support`, no ROS
required. It embeds the ROS 2 message definitions, encodes each message in
CDR, and writes a rosbag2 `metadata.yaml` so `ros2 bag info` is happy.

```bash
pip install mcap mcap-ros2-support scikit-image
python demo/make_demo_bag.py
```

Boxes are annotated once per photo in source pixels and transformed through
the same crop rectangle as the pixels, then clipped to the frame; boxes less
than 30 % visible are dropped.

## Photo credits

Shipped with scikit-image: *astronaut* (Eileen Collins, NASA, public domain),
*rocket* (SpaceX/NASA, public domain), *chelsea* (Stefan van der Walt, CC0),
*coffee* (Rachel Michetti, CC0).
