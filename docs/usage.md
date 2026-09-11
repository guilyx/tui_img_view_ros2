# Usage

```bash
tui-img-view [-t TRANSPORT] [-i TOPIC] [-b TOPIC ...] [-m MODE] [options]
ros2 run tui_img_view viewer ...      # same program, from a colcon workspace
```

The viewer discovers image and box topics on its own. `-i` and `-b` only
pre-select; you can switch in the sidebar at any time.

## Keys

| key | action |
|---|---|
| ++t++ | show / hide the topic panel |
| ++n++ | next image topic |
| ++m++ | cycle render mode: half → quadrant → braille → ascii |
| ++b++ | boxes on / off |
| ++l++ | captions on / off |
| ++c++ | colour / grayscale |
| ++p++ | pause |
| ++r++ | rescan topics |
| ++q++ | quit |

In the panel, ++enter++ on an image topic shows it and ++space++ on a box topic
toggles its overlay. Any number of box topics can be on at once.

## Status bar

```
/camera/image_raw  640x480 rgb8  lat 34ms  25.5 fps  mode:half  boxes:3/1t  draw 6ms
```

Topic, resolution and encoding, wall-clock latency (only when the stamp looks
like wall time), frame rate, render mode, boxes drawn / box topics enabled,
render time. Decoder or subscription errors appear at the end on a red bar.

## Flags

| flag | meaning |
|---|---|
| `-t, --transport NAME` | `ros2` (default), `bag`, `fake`, or a registered plugin |
| `-o, --transport-opt KEY=VALUE` | transport option, repeatable |
| `-i, --image TOPIC` | image topic to show first |
| `-b, --boxes TOPIC` | box topic to overlay, repeatable |
| `-m, --mode MODE` | `half`, `quadrant`, `braille`, `ascii` |
| `--no-color`, `--no-boxes`, `--no-labels` | start with that feature off |
| `--cell-aspect 0.5` | your font's cell width/height, if the image looks stretched |
| `--fps 20` | UI refresh rate |
| `--stale 2.0` | hide boxes older than N seconds |
| `--hide-topics` | start with the panel hidden |
| `--snapshot` | print one frame as ANSI text and exit |
| `--list-topics` | print discovered topics and exit |
| `--adapter`, `--box-type`, `--box-types` | see [Custom box message types](custom-box-types.md) |

### Transport options

=== "ros2"

    | option | default | |
    |---|---|---|
    | `qos` | `sensor` | `sensor` (best effort, matches any publisher) or `reliable` |
    | `depth` | `1` | history depth |
    | `node_name` | `tui_img_view` | |

    Standard `--ros-args` (remaps, parameters) pass straight through.

=== "bag"

    | option | default | |
    |---|---|---|
    | `path` | required | an `.mcap` file or a rosbag2 directory |
    | `rate` | `1.0` | playback speed |
    | `loop` | `true` | |

=== "fake"

    | option | default | |
    |---|---|---|
    | `fps` | `15` | |
    | `width`, `height` | `320`, `240` | |
    | `objects` | `3` | bouncing objects |
    | `file` | | show this image with a scanning box instead |
    | `seed` | `0` | |

## Snapshot mode

```bash
tui-img-view -t bag -o path=demo/bags/tui_demo -b /detector/detections --snapshot > frame.txt
cat frame.txt
```

Renders at the current terminal size and exits. Useful in scripts, over slow
links, and when reporting rendering issues.
