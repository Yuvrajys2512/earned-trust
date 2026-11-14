"""B8: serve the review pages + signed evidence (out/site/, built by `uv run et site`) at a public Modal URL.

    uv run et site && uv run modal deploy deploy/modal_app.py

Static only: every page embeds its record; prediction, reveal and signing run in the viewer's browser.
Nothing is uploaded back. Signed records are downloaded by the reviewer, not stored here.
"""
from pathlib import Path

import modal

SITE = Path(__file__).resolve().parents[1] / "out" / "site"

image = (modal.Image.debian_slim(python_version="3.12")
         .add_local_file(str(Path(__file__).with_name("serve.py")), "/serve.py")
         .add_local_dir(str(SITE), "/site"))
app = modal.App("earned-trust-receipts", image=image)


@app.function(min_containers=0, scaledown_window=300)
@modal.concurrent(max_inputs=50)
@modal.web_server(port=8000, startup_timeout=60)
def site():
    import subprocess
    subprocess.Popen(["python", "/serve.py", "8000", "/site"])  # no-cache, no 1970 Last-Modified (L-26)
