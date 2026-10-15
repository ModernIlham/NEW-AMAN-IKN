"""Strict target guard shared only by disposable local tooling and tests."""
import re
from urllib.parse import urlparse


def mongo_loopback(raw):
    value = urlparse(raw)
    if (value.scheme != "mongodb" or value.username or value.password or value.fragment
            or value.path not in {"", "/"} or value.query not in {"", "directConnection=true"}
            or not re.fullmatch(r"(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?", value.netloc)):
        raise ValueError("Fixture Mongo wajib satu authority loopback tanpa credentials atau discovery options")
    try:
        port = value.port
    except ValueError:
        raise ValueError("Port Mongo fixture tidak valid") from None
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Port Mongo fixture tidak valid")
    # A single explicit driver option prevents replica-set discovery. No
    # arbitrary user query string or multi-host authority is rewritten.
    return "mongodb://" + value.netloc + "/?directConnection=true"
