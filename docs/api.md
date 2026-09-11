# Python API

The public surface for embedding the viewer or writing plugins.

## Types

::: tui_img_view.core.types
    options:
      members: [Frame, BoundingBox, Detections, TopicInfo, TopicKind]

## Transport interface

::: tui_img_view.core.transport
    options:
      members: [Transport, Subscription, CallbackSubscription, TransportUnavailable]

## Registry

::: tui_img_view.core.registry
    options:
      members: [load_transport, register_transport, available_transports]

## Session

::: tui_img_view.core.session
    options:
      members: [ViewerSession, Snapshot]

## Renderer

::: tui_img_view.render.pipeline
    options:
      members: [Renderer, Placement, fit_image]

::: tui_img_view.render.canvas
    options:
      members: [Canvas]

## Detection adapters

::: tui_img_view.transports.ros2.detections
    options:
      members: [register_detection_adapter, BoxFieldMap, parse_box_type_spec, load_box_types_file, load_adapter_plugins, resolve_path]

## Image codecs

::: tui_img_view.transports.ros2.codecs
    options:
      members: [decode_image, decode_compressed]

## Transports

::: tui_img_view.transports.bag
    options:
      members: [McapTransport]

::: tui_img_view.transports.manual
    options:
      members: [ManualTransport]
