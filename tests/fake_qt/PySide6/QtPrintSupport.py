from . import _fake
from ._fake import *  # noqa: F401,F403

_cache = {}


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    if hasattr(_fake, name):
        return getattr(_fake, name)
    if name not in _cache:
        _cache[name] = _fake._Meta(name, (_fake.QWidget,), {})
    return _cache[name]
