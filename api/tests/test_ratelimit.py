from app.services.ratelimit import SlidingWindowLimiter


def test_allows_up_to_limit_then_blocks():
    lim = SlidingWindowLimiter(max_events=3, window_seconds=60)
    t = 1000.0
    assert lim.allow("ip", now=t)
    assert lim.allow("ip", now=t + 1)
    assert lim.allow("ip", now=t + 2)
    assert not lim.allow("ip", now=t + 3)  # 4th within window -> blocked


def test_window_slides():
    lim = SlidingWindowLimiter(max_events=2, window_seconds=60)
    assert lim.allow("ip", now=0)
    assert lim.allow("ip", now=1)
    assert not lim.allow("ip", now=2)
    # once the window passes, the early hits expire
    assert lim.allow("ip", now=61)


def test_keys_are_independent():
    lim = SlidingWindowLimiter(max_events=1, window_seconds=60)
    assert lim.allow("a", now=0)
    assert lim.allow("b", now=0)
    assert not lim.allow("a", now=1)
