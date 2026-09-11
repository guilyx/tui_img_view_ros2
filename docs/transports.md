# Writing a transport

A transport is the only part of the viewer that knows where frames come from.
Implement four methods and nothing else changes: the session, renderer and UI
only ever see `Frame` and `Detections`.

```python
from tui_img_view import Transport, Frame, Detections, TopicInfo, TopicKind


class ZmqTransport(Transport):
    name = "zmq"                                   # --transport zmq

    @classmethod
    def from_options(cls, options):                # -o key=value from the CLI
        return cls(options.get("endpoint", "tcp://localhost:5555"))

    def start(self):
        """Connect and spawn a receive thread."""

    def stop(self):
        """Tear down. Must be safe to call twice."""

    def list_topics(self) -> list[TopicInfo]:
        return [TopicInfo("/cam", "zmq/jpeg", TopicKind.IMAGE)]

    def subscribe_image(self, topic, callback):
        """Call callback(Frame) from any thread; return an object with .close()."""

    def subscribe_boxes(self, topic, callback):
        """Same, with callback(Detections)."""
```

## The contract

- `Frame.pixels` is an `HxWx3` `uint8` RGB array. The constructor normalises
  grayscale and other dtypes for you.
- `BoundingBox` is top-left `x, y, w, h` in source-image pixels;
  `BoundingBox.from_center(...)` for centre-based formats.
- Callbacks may run on any thread. `ViewerSession` locks around the latest
  frame and detections, so transports do not need to.
- Set `self.last_error` to a short string when a message fails to decode; the
  status bar shows it. Never let an exception escape a callback.
- `stop()` must be idempotent and must join your threads.

`tui_img_view.transports.manual.ManualTransport` is a ready-made callback
registry with `push_frame` / `push_boxes`; both the `fake` and `bag`
transports wrap it rather than re-implementing subscription bookkeeping.

## Registering

In-process:

```python
from tui_img_view.core.registry import register_transport
register_transport(ZmqTransport)
```

From another package, an entry point in the `tui_img_view.transports` group:

```ini
[options.entry_points]
tui_img_view.transports =
    zmq = my_pkg.zmq_transport:ZmqTransport
```

Then `tui-img-view --transport zmq -o endpoint=tcp://robot:5555`.

## Testing without a UI

`ViewerSession` is enough to exercise a transport end to end:

```python
from tui_img_view.core.session import ViewerSession

with ViewerSession(ZmqTransport("tcp://localhost:5555")) as s:
    s.refresh_topics()
    s.select_image("/cam")
    snap = s.snapshot()          # .frame, .detections, .fps, .error
```
