import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from jinja2 import Environment, FileSystemLoader
import os
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta, UTC
from http.cookies import SimpleCookie
import sqlite3
import bcrypt
import mimetypes

load_dotenv() 
secret = os.getenv("SECRET_KEY")

connection = sqlite3.connect("users.db")
cursor = connection.cursor()

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
    if tier is None:
        tier = 0    

    nav_items = [
        {"name": "Home", "url": "/home", "id": "home"},
        {"name": "Log-inn", "url": "/log-inn", "id": "log-inn"},
        {"name": "Portfolio", "url": "/portfolio", "id": "portfolio"},
    ]  

    if tier >= 1: 
        nav_items.append({"name": "Services", "url": "/services", "id": "services"})
    
    if tier >= 2: 
        nav_items.append({"name": "Admin-Services", "url": "/admin-services", "id": "admin-services"})

    return nav_items

def autherise(rec_user, rec_pass):
    data_return = cursor.execute("SELECT * FROM users")

    for data in data_return:
        print(rec_user, rec_pass)
        print(data)
        if data[1] == rec_user and data[2] == rec_pass:
            print(data)
            return data[3]

        

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

def tier_routing(self, tier, min_tier, page, dis_name, doc_name):
    if tier is None:
        tier = 0

    if tier >= min_tier:
        template = env.get_template(page)
        html = template.render(nav_items=nav_tier(tier), dis_name=dis_name, doc_name=doc_name)
        respond_html(self, html)
    else:
        template = env.get_template("not-auth.html")
        html = template.render(nav_items=nav_tier(tier), dis_name="Un-Autherised", doc_name="Un-Autherised")
        respond_html(self, html)


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

        print(decoded)

        tier = decoded.get("tier") if decoded else None
        try:
            # Serve static files
            if self.path.startswith("/static/"):
                print(self.path)
                file_path = "." + self.path

                if os.path.exists(file_path):
                    self.send_response(200)

                    mime_type, _ = mimetypes.guess_type(file_path)
                    if mime_type is None:
                        mime_type = "application/octet-stream"

                    self.send_header("Content-Type", mime_type)
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
                tier_routing(self, tier, 0, "Home-page.html", "Home", "Home")

            elif self.path == "/log-inn":
                tier_routing(self, tier, 0, "Log-inn-page.html", "Log-inn", "Log inn")
            
            elif self.path == "/Create-User":
                tier_routing(self, tier, 0, "Create-User.html", "Create-User", "Lag Bruker")
            
            elif self.path == "/portfolio":
                tier_routing(self, tier, 0, "Portfolio-page.html", "Portfolio", "Portfolio")

            elif self.path == "/services":
                tier_routing(self, tier, 1, "Services-page.html", "Services", "Services")
            
            elif self.path == "/admin-services":
                tier_routing(self, tier, 2, "Admin-Services-page.html", "Admin-Services", "Admin-Services")
            
            elif self.path == "/filserver":
                tier_routing(self, tier, 2, "filserver.html", "Filserver", "Filserver")            
            
            else:
                tier_routing(self, tier, 0, "404.html", "404", "404")

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
            
            if self.path == "/make":
                # Get content length
                content_length = int(self.headers.get('Content-Length', 0))

                # Read raw POST data
                post_data = self.rfile.read(content_length).decode('utf-8')

                # Parse form data
                data = parse_qs(post_data)

                # Extract values
                username = data.get("username", [""])[0]
                password = data.get("password", [""])[0]
                password2 = data.get("password2", [""])[0]

                print(username)
                print(password)
                print(password2)

                # Respond to browser
                template = env.get_template("Create-user.html")
                html = template.render(nav_items=nav_tier(tier), dis_name="Create-User", doc_name="Lag Bruker")
                
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