"""Isolated native font proof: no host Inter, application imports or network."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run():
    backend = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(backend))
    with tempfile.TemporaryDirectory(prefix="aman-font-probe-") as temp:
        root = Path(temp)
        (root / "cache").mkdir()
        config = root / "fonts.conf"
        config.write_text(
            '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">'
            '<fontconfig><dir>/usr/share/fonts/truetype/dejavu</dir>'
            f'<cachedir>{root / "cache"}</cachedir></fontconfig>'
        )
        # Must precede WeasyPrint/Pango import. The private config excludes
        # system and XDG Inter, so successful embedding cannot hide a fallback.
        os.environ.update(FONTCONFIG_FILE=str(config), FONTCONFIG_PATH=temp,
                          XDG_DATA_HOME=str(root / "data"), XDG_CACHE_HOME=str(root / "cache"))
        host = subprocess.run(["fc-match", "Inter", "-f", "%{family}"],
                              check=True, capture_output=True, text=True, timeout=5).stdout
        assert "Inter" not in host, "Probe unexpectedly has a host Inter font"

        from pypdf import PdfReader
        from weasyprint import HTML
        from weasyprint.urls import URLFetcher
        from report_fonts import FONT_DIRECTORY, INTER_SHA256, report_font_css

        fetched = []
        font_url = (FONT_DIRECTORY / "Inter.ttf").as_uri()

        class OfflineFetcher(URLFetcher):
            def fetch(self, url, *args, **kwargs):
                if not (url.startswith("data:font/ttf;base64,") or url == font_url):
                    raise AssertionError("Font probe forbids HTTP and unrelated filesystem URLs")
                fetched.append("data" if url.startswith("data:") else "pinned-file")
                return super().fetch(url, *args, **kwargs)

        css = str(report_font_css())
        contents = '<style>{css}@page{{size:A4;margin:20mm}}body{{font-family:Inter;font-size:16px}}</style>'
        contents += ''.join(f'<p style="font-weight:{weight}">AMAN 0123456789</p>' for weight in (400, 700, 800, 900))

        def render(face):
            document = HTML(string=contents.format(css=face), url_fetcher=OfflineFetcher()).render()
            boxes = [[box.text, round(box.position_x, 6), round(box.position_y, 6),
                      round(box.width, 6), round(box.height, 6)]
                     for page in document.pages for box in page._page_box.descendants()
                     if hasattr(box, "text")]
            reader = PdfReader(io.BytesIO(document.write_pdf()))
            fonts = {}
            for page in reader.pages:
                for reference in page["/Resources"]["/Font"].values():
                    font = reference.get_object()
                    name = str(font["/BaseFont"])
                    descendant = font["/DescendantFonts"][0].get_object()
                    descriptor = descendant["/FontDescriptor"].get_object()
                    stream = descriptor.get("/FontFile2") or descriptor.get("/FontFile3")
                    assert stream and len(stream.get_object().get_data()) > 0
                    assert "Inter" in name
                    fonts[name] = len(stream.get_object().get_data())
            geometry = [[round(float(page.mediabox.width), 6), round(float(page.mediabox.height), 6)]
                        for page in reader.pages]
            return {"pages": len(reader.pages), "page_geometry_pt": geometry,
                    "text_boxes": boxes, "embedded_fonts": fonts}

        embedded = render(css)
        assert fetched == ["data"]
        # Compare the data URI with exactly the same pinned font loaded from
        # an explicit local file, never an installed-font or remote baseline.
        prefix, rest = css.split('src: url("', 1)
        _, suffix = rest.split('")', 1)
        baseline = render(prefix + 'src: url("' + font_url + '")' + suffix)
        assert fetched == ["data", "pinned-file"]
        assert embedded["pages"] == 1
        assert len(embedded["embedded_fonts"]) >= 3
        assert embedded["text_boxes"] == baseline["text_boxes"]
        assert embedded["page_geometry_pt"] == baseline["page_geometry_pt"]
        return {"font_sha256": INTER_SHA256, "host_fallback_without_bundle": host,
                "http_font_requests": 0, "layout_equal_to_pinned_file": True, **embedded}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
