# ROS 2 transport

`--transport ros2` (the default) spins an `rclpy` node in a background thread
and subscribes on demand. It needs a sourced ROS 2 environment; if `rclpy` is
not importable it says so and exits.

## Images

`sensor_msgs/msg/Image` is decoded without cv_bridge, straight from the byte
buffer, honouring `step` padding and `is_bigendian`:

| encodings | handling |
|---|---|
| `rgb8 bgr8 rgba8 bgra8 8UC3 8UC4` | channel reorder |
| `mono8 8UC1 8SC1` | replicated to RGB |
| `mono16 16UC1 16SC1 32FC1 64FC1` | min–max normalised per frame (depth images look right) |
| `rgb16 bgr16 rgba16 bgra16 16UC3` | high byte |
| `yuv422` (UYVY), `yuv422_yuy2` (YUYV) | converted |
| `bayer_rggb8 bayer_bggr8 bayer_gbrg8 bayer_grbg8` | half-resolution demosaic |

`sensor_msgs/msg/CompressedImage` goes through Pillow (jpeg, png, ...). The
`"... compressed bgr8"` format convention from `image_transport` is respected.

Unsupported encodings are reported in the status bar; the viewer keeps running.

## Boxes

Built-in adapters:

| type | notes |
|---|---|
| `vision_msgs/msg/Detection2DArray` | Foxy (`center.x`, `results[].id`) and Humble+ (`center.position.x`, `results[].hypothesis.class_id`) layouts |
| `vision_msgs/msg/Detection2D` | single detection |
| `vision_msgs/msg/BoundingBox2DArray` | boxes only, no labels |
| `yolo_msgs/msg/DetectionArray` | yolo_ros: `class_name`, `score`, `id` |

The best-scoring hypothesis becomes the caption. Box coordinates are assumed
to be in the pixel space of the displayed image.

Anything else: [Custom box message types](custom-box-types.md).

## QoS

Subscriptions default to sensor-data QoS (best effort, keep last 1), which is
compatible with both reliable and best-effort publishers. Use
`-o qos=reliable` if you need every message, and `-o depth=N` for history.

## Topic type resolution

Types come from the ROS graph. If you pre-select a topic before its publisher
exists, the transport assumes `sensor_msgs/msg/Image` (or `CompressedImage`
when the name ends in `/compressed`) and `vision_msgs/msg/Detection2DArray`.
