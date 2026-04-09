import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from jinja2 import Environment, FileSystemLoader
import os
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta, UTC
from http.cookies import SimpleCookie


load_dotenv() 
secret = os.getenv("SECRET_KEY")


# Setup Jinja2
env = Environment(loader=FileSystemLoader("templates"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def respond_html(self, html):
    self.send_response(200)
    self.send_header("Content-Type", "text/html")
    self.end_headers()
    self.wfile.write(html.encode())
    self.log_custom(200)

def nav_tier(tier):
    if tier == "friend":
        return [
            {"name": "Home", "url": "/home"},
            {"name": "Log-inn", "url": "/log-inn"},
            {"name": "Portfolio", "url": "/portfolio"},
            {"name": "Services", "url": "/services"},
        ]

    return [
        {"name": "Home", "url": "/home"},
        {"name": "Log-inn", "url": "/log-inn"},
        {"name": "Portfolio", "url": "/portfolio"},
    ]  

def autherise(rec_user, rec_pass):
    friend_user = os.getenv("USERNAME")
    friend_pass = os.getenv("USERPASS")
    friend_tier = os.getenv("USERTIER")
    if rec_user == friend_user and rec_pass == friend_pass:
        return friend_tier

def authenticate(self, secret):
    cookie_header = self.headers.get("Cookie")

    if not cookie_header:
        return None

    cookie = SimpleCookie()
    cookie.load(cookie_header)

    token = cookie.get("jwt")

    if not token:
        return None

    try:
        # Validate JWT
        decoded = jwt.decode(
            token.value,
            secret,
            algorithms=["HS256"]
        )
        return decoded

    except jwt.ExpiredSignatureError:
        
        self.send_response(302)
        self.send_header("Location", "/login")
        self.send_header(
            "Set-Cookie",
            "jwt=; Path=/; Max-Age=0"
        )
        self.end_headers()
        return None

    except jwt.InvalidTokenError:
        
        self.send_response(302)
        self.send_header("Location", "/login")
        self.send_header(
            "Set-Cookie",
            "jwt=; Path=/; Max-Age=0"
        )
        self.end_headers()
        return None

class Handler(BaseHTTPRequestHandler):


    def log_custom(self, code=200):
        """Logs request info in aligned format"""
        msg = f"{self.client_address[0]:15} | {self.command:6} | {self.path:20} | {code}\n"
        if code >= 500:
            logging.error(msg)
        elif code >= 400:
            logging.warning(msg)
        else:
            logging.info(msg)

    def do_GET(self):
        decoded = authenticate(self, secret)

        tier = decoded.get("tier") if decoded else None
        try:
            # Serve static files
            if self.path.startswith("/static/"):
                file_path = "." + self.path
                if os.path.exists(file_path):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/css")
                    self.end_headers()
                    with open(file_path, "rb") as f:
                        self.wfile.write(f.read())
                    self.log_custom(200)
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.log_custom(404)
                return

            # Serve routes
            if self.path == "/" or self.path == "/home":
                template = env.get_template("Home-page.html")
                html = template.render(nav_items=nav_tier(tier), dis_name="Home-Page", doc_name="Home")
                respond_html(self, html)

            elif self.path == "/log-inn":
                template = env.get_template("Log-inn-page.html")
                html = template.render(nav_items=nav_tier(tier), dis_name="Log-inn-Page", doc_name="Log inn")
                respond_html(self, html)
            
            elif self.path == "/portfolio":
                template = env.get_template("Portfolio-page.html")
                html = template.render(nav_items=nav_tier(tier), dis_name="Portfolio", doc_name="Portfolio")
                respond_html(self, html)

            elif self.path == "/services":
                if tier == "friend":
                    template = env.get_template("Services-page.html")
                    html = template.render(nav_items=nav_tier(tier), dis_name="Services", doc_name="Services")
                    respond_html(self, html)
                else:
                    template = env.get_template("Home-page.html")
                    html = template.render(nav_items=nav_tier(tier), dis_name="Home-Page", doc_name="Home")
                    respond_html(self, html)

            else:
                self.send_response(404)
                self.end_headers()
                self.log_custom(404)

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.log_custom(500)
            logging.exception("Unhandled exception:")
    
    def do_POST(self):
        decoded = authenticate(self, secret)

        tier = decoded.get("tier") if decoded else None
        try:
            if self.path == "/auth":
                # Get content length
                content_length = int(self.headers.get('Content-Length', 0))

                # Read raw POST data
                post_data = self.rfile.read(content_length).decode('utf-8')

                # Parse form data
                data = parse_qs(post_data)

                # Extract values
                username = data.get("username", [""])[0]
                password = data.get("password", [""])[0]

                # Print to console

                tier = autherise(username, password)

                if tier:
                    payload = {
                        "user": username,
                        "tier": tier,
                        "exp": datetime.now(UTC) + timedelta(hours=1)
                    }
                    token = jwt.encode(payload, secret, algorithm="HS256")

                # Respond to browser
                template = env.get_template("Log-inn-page.html")
                html = template.render(nav_items=nav_tier(tier), dis_name="Log-inn-Page", doc_name="Log inn")
                
                self.send_response(200)
                if tier: self.send_header("Set-Cookie", f"jwt={token}; Path=/; HttpOnly")
                self.send_header("Content-Type", "text/html") 
                self.end_headers()
                self.wfile.write(html.encode())
                self.log_custom(200)


        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.log_custom(500)
            logging.exception("Unhandled exception:")


# Run server
server_address = ("0.0.0.0", 8000)
httpd = HTTPServer(server_address, Handler)
logging.info(f"Server running at http://{server_address[0]}:{server_address[1]}")
httpd.serve_forever()