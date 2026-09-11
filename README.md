# tui_img_view

Watch an image stream **and its bounding boxes in the terminal**. No X, no GUI,
works over SSH. Built for ROS 2, but the viewer core does not know what ROS is:
a *transport* turns any message source into frames and boxes, and the ROS 2
transport is just the first one.

```
 /camera/image_raw  320x240 rgb8  lat 34ms  25.5 fps  mode:half  boxes:3/1t  draw 6ms
```

Example in `ascii` mode (the default `half` mode is 24-bit colour, 2 pixels per cell):

```
            !i>ilIIli>i!IIli>i!III!>>!III!>>ilII!i>ilIIli>i!            
            <>!ll!><>!ll!><>illli><illli><i!ll!><>!ll!><>!ll            
            i!!i<<<i!!i<<<>!!!><<>!!!><<<i!!i<<<i!!i<<<i!!i<            
            i>~~~>iii~~~<iii<~~<iii<~~<iii>~~~>ii>~~~>iii~~~            
            +++<>i<┌cone 0.67~>i>~++~>i><+++<i><+++<>i<~++<>            
            _~>><+_│[/xnf)│+<><~__+<>>~___~>>~___~>><+__~<><            
            <<~_--+│xYQOJv│<<+--_~<<+--_~<<+_--+<<~_--+<<~_-            
            +-??_~~│jcUCXn│_??-+~~_??-+~~+-??_~~+-??_~~+-??-            
            ]]-++_?└──────┘]?_++-]]?_++_?]?-++_?]]-++_?]]?_+            
            ┌ball 0.84_?[[]-__?][]-__-][]?__-][[?__-?[[?-__?            
            │{/\│]---][}[?--][}[?--?[}[?--?[}[]---]}}]---][}            
            └───┘??[}{}]??]}{}]??]}{}[??]}{}[???[{}[???[}{}]            
            {}]]]}{{}]]][{{{[]][{{{[]┌robot 0.84{}]]]}{{}]]]            
            [[[{11{[[[}111}[[}111}[[}│)t/1│[{11{[[[{11{[[[}1            
            }1))1}[}{))){[[{))){}[}1)│)ft)│))1}[}1))1}[}{)))            
            ((){}}1(()1}}1(((1}}{)((1└────┘){}{1((){}}1(()1}            
            (1{{)||(){{)(||){{1(||)1{1(||(1{1)||(1{{)||(){{)            
            11(\\|)11)|\\(11)|\\(11)|\\|)1)(\\|)11(\\|)11)|\            
```

## Features

- Four render modes, cycle with `m`: `half` (▀ blocks, truecolour), `quadrant`
  (2x2 glyphs), `braille` (2x4 dithered dots), `ascii` (classic ramp).
- Bounding boxes drawn as box glyphs with `label score` / `#track_id` captions,
  colour-coded per label, from **any number of box topics at once**.
- Topic discovery sidebar: pick the image topic, toggle box topics.
- Status bar with resolution, encoding, fps, latency, box count and errors.
- Aspect-ratio-correct scaling to whatever size the terminal is.
- `--snapshot` prints one frame as ANSI text and exits (pipes, CI, bug reports).
- A `fake` transport so you can try it with nothing installed.

## Install

Plain Python (any ROS 2 distro's Python works, 3.10+):

```bash
pip install -e .
```

In a colcon workspace (ament_python package, so `ros2 run` works):

```bash
cd ~/ros2_ws/src && git clone https://github.com/guilyx/tui_img_view_ros2.git
cd ~/ros2_ws && pip install textual pillow numpy && colcon build --packages-select tui_img_view
source install/setup.bash
```

`textual` is not a rosdep key, hence the extra pip line.

## Use

```bash
# ROS 2 (default transport). Discovers topics on its own; these just pre-select.
tui-img-view --image /camera/image_raw --boxes /yolo/detections
ros2 run tui_img_view viewer -i /camera/image_raw/compressed -b /detections -b /tracks

# No ROS? Try the synthetic scene, or a photo with a scanning box.
tui-img-view -t fake
tui-img-view -t fake -o file=photo.jpg

# One frame to stdout, no TUI.
tui-img-view -t fake --snapshot -b /detector/detections
tui-img-view --list-topics
```

Keys:

| key | action                          |
|-----|---------------------------------|
| `t` | show/hide the topic panel       |
| `n` | next image topic                |
| `m` | cycle render mode               |
| `b` | boxes on/off                    |
| `l` | captions on/off                 |
| `c` | colour / grayscale              |
| `p` | pause                           |
| `r` | rescan topics                   |
| `q` | quit                            |

In the panel: `Enter` on an image topic to view it, `Space` on a box topic to
toggle its overlay.

Useful flags: `-m ascii|half|quadrant|braille`, `--no-color`, `--no-labels`,
`--stale 2.0` (hide boxes older than N seconds), `--cell-aspect 0.5` (tune if
your font is not 1:2), `--fps 20` (UI refresh), `-o key=value` (transport
options, repeatable).

ROS 2 transport options: `-o qos=sensor|reliable`, `-o depth=1`,
`-o node_name=tui_img_view`. Standard `--ros-args` are passed through.

## What the ROS 2 transport understands

Images, decoded without cv_bridge:

- `sensor_msgs/msg/Image`: `rgb8 bgr8 rgba8 bgra8 mono8 mono16 8UC1 8UC3 8UC4
  16UC1 16SC1 32FC1 64FC1 rgb16 bgr16 yuv422 yuv422_yuy2 bayer_*8`. 16-bit and
  float single-channel images (depth) are min-max normalised per frame; Bayer
  is demosaiced at half resolution.
- `sensor_msgs/msg/CompressedImage`: anything Pillow can open (jpeg, png), with
  the `"... compressed bgr8"` channel-order convention respected.

Boxes:

- `vision_msgs/msg/Detection2DArray`, `Detection2D`, `BoundingBox2DArray`
  (Foxy and Humble+ layouts).
- `yolo_msgs/msg/DetectionArray` (yolo_ros).

Box coordinates are assumed to be in the pixel space of the displayed image.

Add another message type in one function:

```python
from tui_img_view.transports.ros2.detections import register_detection_adapter
from tui_img_view import BoundingBox, Detections

@register_detection_adapter("my_msgs/msg/Objects")
def my_objects(msg):
    return Detections(BoundingBox(o.x, o.y, o.w, o.h, label=o.name) for o in msg.objects)
```

## Architecture

```
tui_img_view/
├── core/        types (Frame, BoundingBox, Detections, TopicInfo)
│                Transport ABC · ViewerSession (thread-safe latest-value state)
│                registry (built-ins + `tui_img_view.transports` entry points)
├── render/      Frame + boxes → Canvas of (char, fg, bg) cells
│                raster modes · box overlay · ANSI serialiser
├── transports/  fake · manual (push by hand) · ros2 (rclpy, codecs, adapters)
└── ui/          Textual app: ImageView (render_line), topic panel, status bar
```

Data flows one way: transport callback → `ViewerSession` (any thread) →
`snapshot()` polled by the UI at `--fps` → `Renderer` → `Canvas` → screen. The
session only re-renders when its version counter moves.

### Writing a transport

Implement four methods and you are done; nothing else changes.

```python
from tui_img_view import Transport, Frame, Detections, TopicInfo, TopicKind

class ZmqTransport(Transport):
    name = "zmq"

    @classmethod
    def from_options(cls, options):        # -o key=value from the CLI
        return cls(options.get("endpoint", "tcp://localhost:5555"))

    def start(self): ...                   # connect, spawn a receive thread
    def stop(self): ...
    def list_topics(self) -> list[TopicInfo]: ...
    def subscribe_image(self, topic, callback):   # callback(Frame) from any thread
        ...; return subscription           # anything with .close()
    def subscribe_boxes(self, topic, callback):   # callback(Detections)
        ...
```

Register it via `tui_img_view.core.registry.register_transport(ZmqTransport)`
or, from another package, with an entry point in the `tui_img_view.transports`
group, and select it with `--transport zmq`.

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest -q
```

The test suite runs without ROS: the ROS 2 codecs and detection adapters are
duck-typed and tested against stub messages, and the Textual app is driven
headlessly against the fake transport.

## License

MIT
