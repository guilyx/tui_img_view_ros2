# Custom box message types

Any message with a list of boxes can be plugged in without touching the
viewer. Pick whichever fits.

## No code: a field map

Describe where the fields live, relative to one item of the list. Paths are
dotted attributes with optional indexes; `origin` says whether `x`/`y` is the
top-left corner (default) or the centre.

```bash
tui-img-view -b /my/objects --box-type \
  "my_msgs/msg/Objects:items=objects,x=rect.x,y=rect.y,w=rect.w,h=rect.h,label=hyps[0].cls,score=conf,id=uid,origin=center"
```

| key | required | meaning |
|---|---|---|
| `items` | no | path to the sequence of detections; omit if the message *is* one box |
| `x`, `y`, `w`, `h` | yes | box geometry |
| `label`, `score`, `id` | no | caption fields |
| `origin` | no | `topleft` (default) or `center` |

The same keys in a TOML file, one table per type:

```toml
# boxes.toml
[[box_types]]
type   = "my_msgs/msg/Objects"
items  = "objects"
x      = "rect.x"
y      = "rect.y"
w      = "rect.w"
h      = "rect.h"
label  = "hyps[0].cls"
score  = "conf"
id     = "uid"
origin = "center"
```

```bash
tui-img-view --box-types boxes.toml -b /my/objects
```

## Python: an adapter function

The message is duck-typed, so the same function works on live `rclpy`
messages, on MCAP-decoded messages from the `bag` transport, and on stubs in
tests.

```python
# my_pkg/adapters.py
from tui_img_view import BoundingBox, Detections
from tui_img_view.transports.ros2.detections import register_detection_adapter


@register_detection_adapter("my_msgs/msg/Objects")
def my_objects(msg):
    return Detections(BoundingBox(o.x, o.y, o.w, o.h, label=o.name) for o in msg.objects)
```

```bash
tui-img-view --adapter my_pkg.adapters -b /my/objects
tui-img-view --adapter my_pkg.adapters:setup   # call setup() after import
```

## Packaged: an entry point

Expose the module or a setup function under the
`tui_img_view.detection_adapters` group and it loads on every start:

```ini
# setup.cfg of your package
[options.entry_points]
tui_img_view.detection_adapters =
    my_objects = my_pkg.adapters
```

## Checking

Registered types join topic discovery like the built-ins:

```bash
tui-img-view --box-type "..." --list-topics
```
