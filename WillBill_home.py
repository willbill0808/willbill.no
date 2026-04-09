from http.server import BaseHTTPRequestHandler, HTTPServer
from jinja2 import Environment, FileSystemLoader
import os

# Load templates
env = Environment(loader=FileSystemLoader("templates"))

services = [
    {"name": "Jellyfin", "url": "http://localhost:8096"},
    {"name": "Portfolio", "url": "http://localhost:3000"},
]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            template = env.get_template("Home-page.html")
            html = template.render(doc_name="Homepage", dis_name="Main-page")

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

        else:
            self.send_response(404)
            self.end_headers()

server = HTTPServer(("0.0.0.0", 80), Handler)
print("Server running at http://localhost:80")
server.serve_forever()