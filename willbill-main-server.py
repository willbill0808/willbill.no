import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, unquote
from jinja2 import Environment, FileSystemLoader
import os
import shutil
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta, UTC
from http.cookies import SimpleCookie
import sqlite3
import bcrypt
import mimetypes

load_dotenv() 
secret = os.getenv("SECRET_KEY")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}

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
    data_return = cursor.execute("SELECT * FROM users WHERE username=?", (rec_user,))
    print("data_return:", data_return)

    for data in data_return:
        print(rec_user, rec_pass)
        print(data)
        if data[1] == rec_user and data[2] == rec_pass:
            print(data)
            return data[3]

        

def first_image_in_dir(path):
    if not os.path.isdir(path):
        return None
    for name in sorted(os.listdir(path)):
        if name.startswith('.'):
            continue
        full_path = os.path.join(path, name)
        if os.path.isfile(full_path) and os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS:
            return name
    return None


def parse_content_disposition(value):
    items = {}
    for part in value.split(";"):
        part = part.strip()
        if "=" in part:
            key, val = part.split("=", 1)
            val = val.strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            items[key.strip().lower()] = val
        else:
            items[part.lower()] = None
    return items


def parse_multipart_form_data(content_type, body_bytes):
    if "multipart/form-data" not in content_type:
        return []

    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part.split("=", 1)[1]
            if boundary.startswith('"') and boundary.endswith('"'):
                boundary = boundary[1:-1]
            break

    if not boundary:
        return []

    boundary_bytes = ("--" + boundary).encode("utf-8")
    sections = body_bytes.split(boundary_bytes)
    fields = []

    for section in sections:
        section = section.strip(b"\r\n")
        if not section or section == b"--":
            continue

        header_block, sep, value = section.partition(b"\r\n\r\n")
        if not sep:
            continue

        header_lines = header_block.split(b"\r\n")
        headers = {}
        for line in header_lines:
            if b":" not in line:
                continue
            key, val = line.split(b":", 1)
            headers[key.decode("utf-8").strip().lower()] = val.decode("utf-8", errors="replace").strip()

        disposition = headers.get("content-disposition", "")
        disposition_params = parse_content_disposition(disposition)
        field_name = disposition_params.get("name")
        filename = disposition_params.get("filename")
        content_type = headers.get("content-type")

        if value.endswith(b"\r\n"):
            value = value[:-2]

        fields.append({
            "name": field_name,
            "filename": filename,
            "content_type": content_type,
            "data": value,
        })

    return fields


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

def tier_routing(self, tier, min_tier, page, dis_name, doc_name, extra=None):
    if tier is None:
        tier = 0

    if tier >= min_tier:
        template = env.get_template(page)
        context = {
            "nav_items": nav_tier(tier),
            "dis_name": dis_name,
            "doc_name": doc_name,
        }
        if extra:
            context.update(extra)
        html = template.render(**context)
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
            if self.path.startswith("/filserver"):
                self.handle_filserver_request(self.path, tier)
                return

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
            
            else:
                tier_routing(self, tier, 0, "404.html", "404", "404")

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.log_custom(500)
            logging.exception("Unhandled exception:")

    def handle_filserver_request(self, request_path, tier, status_message=None):
        if tier is None or tier < 0:
            tier_routing(self, tier, 0, "not-auth.html", "Un-Autherised", "Un-Autherised")
            return

        base_dir = os.path.join(os.getcwd(), "filserver")
        rel_path = request_path[len("/filserver"):].lstrip("/")
        rel_path = unquote(rel_path)
        abs_path = os.path.normpath(os.path.join(base_dir, rel_path))
        base_norm = os.path.normpath(base_dir)

        if abs_path != base_norm and not abs_path.startswith(base_norm + os.sep):
            self.send_response(404)
            self.end_headers()
            self.log_custom(404)
            return

        if os.path.isdir(abs_path):
            entries = []
            for name in sorted(os.listdir(abs_path)):
                if name.startswith('.'):
                    continue
                full_path = os.path.join(abs_path, name)
                entry_type = "directory" if os.path.isdir(full_path) else "file"
                item_path = os.path.join(rel_path, name) if rel_path else name
                url = "/filserver/" + quote(item_path.replace(os.sep, "/"))
                preview = None
                if entry_type == "directory":
                    image_name = first_image_in_dir(full_path)
                    if image_name:
                        preview_path = os.path.join(item_path, image_name)
                        preview = "/filserver/" + quote(preview_path.replace(os.sep, "/"))
                else:
                    ext = os.path.splitext(name)[1].lower()
                    if ext in IMAGE_EXTENSIONS:
                        preview = url

                entries.append({
                    "name": name,
                    "type": entry_type,
                    "url": url,
                    "preview": preview
                })

            if rel_path:
                parent_path = "/filserver"
                parent_parts = rel_path.split("/")[:-1]
                if parent_parts:
                    parent_path = "/filserver/" + quote("/".join(parent_parts))
            else:
                parent_path = None

            extra = {
                "entries": entries,
                "current_folder": rel_path,
                "path_parts": rel_path.split("/") if rel_path else [],
                "parent_path": parent_path,
                "status_message": status_message
            }
            tier_routing(self, tier, 2, "filserver.html", "Filserver", "Filserver", extra=extra)
            return

        if os.path.isfile(abs_path):
            if os.path.exists(abs_path):
                self.send_response(200)
                mime_type, _ = mimetypes.guess_type(abs_path)
                if mime_type is None:
                    mime_type = "application/octet-stream"
                self.send_header("Content-Type", mime_type)
                self.end_headers()
                with open(abs_path, "rb") as f:
                    self.wfile.write(f.read())
                self.log_custom(200)
                return

        self.send_response(404)
        self.end_headers()
        self.log_custom(404)

    def handle_filserver_post(self, request_path, tier):
        if tier is None or tier < 0:
            tier_routing(self, tier, 2, "not-auth.html", "Un-Autherised", "Un-Autherised")
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(content_length)
        fields = parse_multipart_form_data(self.headers.get('Content-Type', ''), body_bytes)

        def get_value(name):
            for field in fields:
                if field.get('name') == name and field.get('filename') is None:
                    return field.get('data', b"").decode('utf-8', errors='replace')
            return ""

        def get_file(name):
            for field in fields:
                if field.get('name') == name and field.get('filename'):
                    return field
            return None

        action = get_value("action")
        current_folder = get_value("current_folder") or ""
        rel_path = current_folder.strip("/")

        base_dir = os.path.join(os.getcwd(), "filserver")
        base_norm = os.path.normpath(base_dir)
        target_dir = os.path.normpath(os.path.join(base_dir, rel_path))

        if target_dir != base_norm and not target_dir.startswith(base_norm + os.sep):
            self.send_response(400)
            self.end_headers()
            self.log_custom(400)
            return

        status_message = ""

        if action == "create_folder":
            folder_name = get_value("new_folder_name").strip()
            if not folder_name:
                status_message = "Enter a valid folder name."
            else:
                folder_name = os.path.basename(folder_name)
                if folder_name in {"", ".", ".."} or os.sep in folder_name or "/" in folder_name:
                    status_message = "Folder name may not include slashes."
                else:
                    new_folder_path = os.path.join(target_dir, folder_name)
                    if os.path.exists(new_folder_path):
                        status_message = f"Folder '{folder_name}' already exists."
                    else:
                        os.makedirs(new_folder_path, exist_ok=True)
                        status_message = f"Folder '{folder_name}' created."

        elif action == "upload_file":
            file_item = get_file("upload_file")
            if not file_item:
                status_message = "No file selected for upload."
            else:
                filename = os.path.basename(file_item.get('filename', '') or '')
                if not filename:
                    status_message = "No file selected for upload."
                else:
                    filename = filename.replace('/', '_').replace('\\', '_')
                    dest_path = os.path.normpath(os.path.join(target_dir, filename))
                    if dest_path != base_norm and not dest_path.startswith(base_norm + os.sep):
                        status_message = "Invalid upload path."
                    else:
                        try:
                            with open(dest_path, "wb") as out_file:
                                out_file.write(file_item.get('data', b""))
                            status_message = f"Uploaded '{filename}'."
                        except Exception:
                            status_message = "Upload failed. Please try again."

        else:
            status_message = "Unknown filserver action."

        request_path = "/filserver/" + quote(rel_path) if rel_path else "/filserver"
        self.handle_filserver_request(request_path, tier, status_message=status_message)

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

                tier = autherise(username, password)

                if tier:
                    payload = {
                        "user": username,
                        "tier": tier,
                        "exp": datetime.now(UTC) + timedelta(hours=1)
                    }
                    token = jwt.encode(payload, secret, algorithm="HS256")

                template = env.get_template("Log-inn-page.html")
                html = template.render(nav_items=nav_tier(tier), dis_name="Log-inn-Page", doc_name="Log inn")
                
                self.send_response(200)
                if tier: self.send_header("Set-Cookie", f"jwt={token}; Path=/; HttpOnly")
                self.send_header("Content-Type", "text/html") 
                self.end_headers()
                self.wfile.write(html.encode())
                self.log_custom(200)

            elif self.path == "/make":
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

            elif self.path.startswith("/filserver"):
                self.handle_filserver_post(self.path, tier)

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