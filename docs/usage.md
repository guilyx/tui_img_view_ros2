# Usage

```bash
tui-img-view [-t TRANSPORT] [-i TOPIC] [-b TOPIC ...] [-m MODE] [options]
ros2 run tui_img_view viewer ...      # same program, from a colcon workspace
```

The viewer discovers image and box topics on its own. `-i` and `-b` only
pre-select; you can switch in the sidebar at any time.

## Layout

```
┌ status bar ─────────────────────────────────────────────────────────┐
│ topics      │ image                              │ commands          │
│ (t)         │                                    │ [Mode][Boxes]...  │
│             │                                    │ : command line    │
│             │                                    ├───────────────────┤
│             │                                    │ log               │
│             │                                    │ 12:00:01 subscr…  │
└ footer ─────────────────────────────────────────────────────────────┘
```

The topic panel (++t++) and the sidebar (++s++) can each be hidden; the image
takes whatever is left, keeping its aspect ratio.

## Keys

| key | action |
|---|---|
| ++colon++ | focus the command line (opens the sidebar if hidden) |
| ++s++ | show / hide the command + log sidebar |
| ++t++ | show / hide the topic panel |
| ++n++ | next image topic |
| ++m++ | cycle render mode: half → quadrant → braille → ascii |
| ++b++ | boxes on / off |
| ++l++ | captions on / off |
| ++c++ | colour / grayscale |
| ++f++ | cycle image filter (none → each filter alone → none) |
| ++p++ | pause |
| ++r++ | rescan topics |
| ++q++ | quit |

In the panel, ++enter++ on an image topic shows it and ++space++ on a box topic
toggles its overlay. Any number of box topics can be on at once. ++esc++
returns focus to the image from anywhere.

## Commands

Press ++colon++, type, ++enter++. Buttons in the command panel run the same
commands. Every command's outcome is written to the log.

| command | effect |
|---|---|
| `mode [name]` | set or cycle the render mode |
| `image <topic>`, `next`, `prev` | choose the image topic |
| `boxes [on\|off]` | draw boxes or not |
| `boxes +<topic>`, `boxes -<topic>`, `boxes <topic>` | add, remove, toggle a box topic |
| `filter <name>`, `filter +<name>`, `filter -<name>` | toggle, add, remove a filter |
| `filter`, `filter next`, `filter off`, `filters` | show active, cycle, clear, list available |
| `labels [on\|off]`, `color [on\|off]`, `pause [on\|off]` | toggles |
| `stale <seconds>` | hide boxes older than this |
| `fps <hz>` | UI refresh rate |
| `aspect <ratio>` | cell width/height used for aspect-correct fitting |
| `rescan` | re-discover topics |
| `topics`, `sidebar` | show / hide panels |
| `clear` | clear the log |
| `help`, `quit` | |

## Filters

Filters are applied to the image after it is scaled to the terminal and
before it is rasterised, so they cost the same whatever the camera
resolution. They **stack in the order you enable them**: `:filter gray` then
`:filter edges` gives edges of the grayscale image. The status bar shows the
stack as `flt:gray+edges`, and the buttons in the command panel light up for
active filters. Boxes are unaffected.

| filter | effect |
|---|---|
| `gray` | grayscale |
| `invert` | negative |
| `sepia` | warm sepia tone |
| `blur` | Gaussian blur, radius 1.5 |
| `sharpen` | unsharp mask |
| `edges` | edge detection |
| `emboss` | emboss relief |
| `threshold` | black and white at 50 % luminance |
| `posterize` | 3 bits per channel |
| `contrast` | stretch contrast (autocontrast, 1 % cutoff) |
| `equalize` | histogram equalisation |

Start with filters from the command line: `--filter invert --filter blur`.

## Log

The log panel shows timestamped events from the viewer and its transports:
subscriptions, topic switches, topics appearing or disappearing, decoder and
subscription errors, bag loops, command results. It is fed from the standard
`tui_img_view` Python logger, so a transport only has to call
`logging.getLogger(__name__).info(...)` to appear there.

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
| `-F, --filter NAME` | image filter to start with, repeatable, applied in order |
| `--cell-aspect 0.5` | your font's cell width/height, if the image looks stretched |
| `--fps 20` | UI refresh rate |
| `--stale 2.0` | hide boxes older than N seconds |
| `--hide-topics`, `--hide-sidebar` | start with that panel hidden |
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
