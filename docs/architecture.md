# Architecture

```
tui_img_view/
├── core/        types (Frame, BoundingBox, Detections, TopicInfo)
│                Transport ABC · ViewerSession (thread-safe latest-value state)
│                registry (built-ins + `tui_img_view.transports` entry points)
├── render/      Frame + boxes → Canvas of (char, fg, bg) cells
│                raster modes · box overlay · ANSI serialiser
├── transports/  fake · manual · bag (MCAP) · ros2 (rclpy, codecs, adapters)
└── ui/          Textual app: ImageView (render_line), topic panel, command panel + log, status bar
```

## Data flow

Data flows one way and crosses one thread boundary:

1. A transport thread decodes a message into a `Frame` or `Detections` and
   calls the session's callback.
2. `ViewerSession` stores it under a lock and bumps a version counter.
3. The Textual app polls `session.snapshot()` at `--fps`. If the version
   moved (or the widget was resized) it re-renders; otherwise it only
   refreshes the status bar.
4. `Renderer` fits the image to the widget, rasterises, overlays boxes, and
   returns a `Canvas`.
5. `ImageView` turns the canvas into Textual `Strip`s once and serves them
   from `render_line`.

Nothing below `ui/` imports Textual, and nothing below `transports/ros2/`
imports `rclpy`, so the renderer and session are testable in plain pytest.

## Rendering

The renderer chooses the largest cell rectangle with the image's aspect ratio
(`--cell-aspect` is the font's cell width/height, 0.5 for most fonts), resizes
the image to `cols × px_w` by `rows × px_h` for the mode, and rasterises:

| mode | pixels per cell | colours per cell | how |
|---|---|---|---|
| `half` | 1×2 | 2 | `▀` with fg = top pixel, bg = bottom pixel |
| `quadrant` | 2×2 | 2 | split the four pixels on luminance, pick the matching quadrant glyph |
| `braille` | 2×4 | 1 | ordered (Bayer) dithering to dots, fg = block mean |
| `ascii` | 1×2 | 1 | luminance → ramp character, fg = block mean |

Boxes are drawn in cell space on top: box-drawing glyphs for the outline
(keeping the underlying background colour in modes that paint one) and a
`label score` / `#id` caption in the box's colour. Colours are a stable hash
of the label, so the same class always gets the same colour.

## Session semantics

- Switching image topic drops the old frame immediately, so a stale picture
  never shows under a new topic name.
- Detections are kept per topic and hidden once older than `--stale`
  seconds, so a dead detector's boxes disappear.
- Pause freezes the frame and boxes but keeps counting the incoming rate.
- Subscription and decode errors land in `snapshot().error` for the status
  bar rather than crashing the UI.
