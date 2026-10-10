"""Web entry point for Vercel.

The drowsiness assistant itself runs on a laptop or a Raspberry Pi in the vehicle
(see main.py). This file only exists so the repository has a web handler that
Vercel can deploy. It uses only the Python standard library, so the deployment
stays small and does not need OpenCV or MediaPipe.
"""
from __future__ import annotations

PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Driver drowsiness detection</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 640px; margin: 48px auto; padding: 0 16px; line-height: 1.5; color: #222; }
h1 { font-size: 1.6rem; }
code { background: #f1f3f6; padding: 2px 5px; border-radius: 4px; }
</style>
</head>
<body>
<h1>Driver drowsiness detection</h1>
<p>The assistant runs on a laptop or Raspberry Pi installed in the vehicle. It watches the driver's face and raises alerts when drowsiness is detected.</p>
<p>This web page is only a placeholder. To run the assistant, follow the setup steps in the repository README, then start it with <code>python main.py</code>.</p>
</body>
</html>
"""


def handler(environ, start_response):
    """WSGI application. Vercel calls this for every request."""
    path = environ.get("PATH_INFO", "/")
    if path == "/health":
        body = b"ok"
        content_type = "text/plain; charset=utf-8"
    else:
        body = PAGE.encode("utf-8")
        content_type = "text/html; charset=utf-8"
    start_response("200 OK", [("Content-Type", content_type), ("Content-Length", str(len(body)))])
    return [body]


app = handler
