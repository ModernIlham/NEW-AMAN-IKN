"""Trusted release font shared by report previews and WeasyPrint PDFs.

The original OFL font travels with the release. A single cached data URI
works in authenticated HTML previews and PDF workers without a public font
route, host font installation, filesystem URLs or external font requests.
"""

import base64
from functools import lru_cache
import hashlib
from pathlib import Path

from markupsafe import Markup

FONT_DIRECTORY = Path(__file__).resolve().parent / "assets" / "fonts"
INTER_SHA256 = "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031"
INTER_LICENSE_SHA256 = "5b9321a4298cfeb6b34354164a1c3afc3db114569984c502b9b35d988fd58c57"


@lru_cache(maxsize=1)
def report_font_css() -> Markup:
    """Load and verify fixed release files once, never accept a user font URL."""
    font = (FONT_DIRECTORY / "Inter.ttf").read_bytes()
    license_text = (FONT_DIRECTORY / "OFL.txt").read_bytes()
    if hashlib.sha256(font).hexdigest() != INTER_SHA256:
        raise RuntimeError("Bundled report font failed its release checksum")
    if hashlib.sha256(license_text).hexdigest() != INTER_LICENSE_SHA256:
        raise RuntimeError("Bundled report font license failed its release checksum")
    encoded = base64.b64encode(font).decode("ascii")
    # Inter is a variable font: browsers use the weight range; Pango reads
    # the original font's wght axis when shaping WeasyPrint text.
    return Markup(
        "@font-face { font-family: 'Inter'; font-style: normal; "
        "font-weight: 100 900; font-display: swap; "
        'src: url("data:font/ttf;base64,' + encoded + '") format("truetype"); }'
    )
