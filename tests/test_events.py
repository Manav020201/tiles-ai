import json

from tiles_ai.api import format_sse
from tiles_ai.events import Event, EventBus


def test_bus_fans_out_to_subscribers():
    bus = EventBus()
    a = bus.subscribe()
    b = bus.subscribe()
    bus.publish(Event(type="tile.activated", tile_id="t1"))
    assert a.get_nowait().type == "tile.activated"
    assert b.get_nowait().tile_id == "t1"


def test_publish_stamps_timestamp():
    bus = EventBus()
    q = bus.subscribe()
    bus.publish(Event(type="x"))
    assert q.get_nowait().ts is not None


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)
    bus.publish(Event(type="x"))
    assert bus.subscriber_count == 0
    assert q.empty()


def test_format_sse_frame():
    frame = format_sse(
        Event(type="action.queued", tile_id="reply-drafter", data={"tool": "send_message"}, ts=1.0)
    )
    assert frame.startswith("event: action.queued\n")
    body = frame.split("data: ", 1)[1].split("\n\n")[0]
    parsed = json.loads(body)
    assert parsed["type"] == "action.queued"
    assert parsed["data"]["tool"] == "send_message"
    assert frame.endswith("\n\n")
