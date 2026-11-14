"""Static file server for the Modal site, without stale-cache bugs.

Modal image files all carry mtime 1970-01-01, so plain http.server sends `Last-Modified: 1970` on every deploy and
answers a browser's If-Modified-Since with 304: browsers kept showing the previous deploy (L-26). This handler ignores
If-Modified-Since, drops Last-Modified, and tells browsers to revalidate every time.
"""
import functools
import http.server
import sys


class NoStaleHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        if "If-Modified-Since" in self.headers:
            del self.headers["If-Modified-Since"]
        return super().send_head()

    def send_header(self, keyword, value):
        if keyword.lower() == "last-modified":
            return
        super().send_header(keyword, value)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()


if __name__ == "__main__":
    port, directory = int(sys.argv[1]), sys.argv[2]
    handler = functools.partial(NoStaleHandler, directory=directory)
    http.server.ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()
