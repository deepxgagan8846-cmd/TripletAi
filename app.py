"""
TripletAI v3.0 - Backend Server
Created by: Gagandeep Singh Kalia
Run: python app.py
Then open: http://localhost:8000
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json, os, base64, threading, webbrowser
from groq import Groq
from datetime import datetime

API_KEY = os.environ.get("GROQ_API_KEY", "")
client  = Groq(api_key=API_KEY) if API_KEY else None
HISTORY_FILE = "tripletai_history.json"

SYSTEM = """You are TripletAI — a powerful AI assistant created by Gagandeep Singh Kalia.

IDENTITY:
- Name: TripletAI | Created by: Gagandeep Singh Kalia | Founded: 2025
- Never say you are ChatGPT, Gemini, or Claude. You are TripletAI.
- If asked who made you → always say "Gagandeep Singh Kalia"

CAPABILITIES (answer ALL of these perfectly):
- Mathematics: algebra, calculus, geometry, statistics — step by step
- Science: physics, chemistry, biology, quantum mechanics
- Universe: galaxies, black holes, space, cosmology, solar system
- History & Geography: world history, cultures, countries
- Coding: Python, JavaScript, C++, Java, HTML, CSS, React, Flutter, Unity, Godot, game dev, app dev, web dev
- Game Development: Unity, Godot, Pygame, game design, mechanics
- App Development: Android, iOS, Flutter, React Native
- Website Development: HTML, CSS, JS, React, Node.js, databases
- Creative Writing: stories, poems, scripts
- Health & Medicine: symptoms, treatments (non-prescriptive)
- Image Analysis: describe and analyze uploaded images

LANGUAGE RULE: {lang}

FORMATTING:
- Use **bold** for key terms
- Use ```code blocks``` for all code
- Use ## headings for sections
- Give clear, structured, helpful answers
"""

def get_lang_inst(lang):
    if lang == "auto":
        return "Detect the user's language and ALWAYS reply in that SAME language."
    return f"ALWAYS reply in {lang} regardless of what language the user writes in."

def save_history(history, title=""):
    try:
        all_h = {}
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                all_h = json.load(f)
        key = title or datetime.now().strftime("%Y-%m-%d %H:%M")
        all_h[key] = history
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(all_h, f, ensure_ascii=False, indent=2)
        return key
    except:
        return ""

def load_all_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def delete_history():
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
    except:
        pass

class TripletHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass  # Suppress logs

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open("index.html", "rb") as f:
                self.wfile.write(f.read())

        elif self.path == "/history":
            data = load_all_history()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": bool(API_KEY), "key_set": bool(API_KEY)}).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length))

        # ── Chat endpoint (streaming via SSE) ──
        if self.path == "/chat":
            if not API_KEY or not client:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                msg = "⚠️ API Key not set! In PowerShell run:\\n$env:GROQ_API_KEY=\\\"gsk_your_key\\\"\\nthen restart python app.py"
                self.wfile.write(f"data: {json.dumps({'text': msg, 'done': True})}\n\n".encode())
                return

            messages  = body.get("messages", [])
            language  = body.get("language", "auto")
            image_b64 = body.get("image", None)

            sys_text = SYSTEM.format(lang=get_lang_inst(language))
            api_msgs = [{"role": "system", "content": sys_text}]

            for m in messages[:-1]:  # All except last (which is current user msg)
                if m.get("role") in ("user", "assistant") and m.get("content"):
                    api_msgs.append({"role": m["role"], "content": m["content"]})

            user_text = messages[-1]["content"] if messages else ""

            if image_b64:
                user_content = [
                    {"type": "text", "text": user_text or "Describe this image in detail."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
                model = "llama-3.2-11b-vision-preview"
            else:
                user_content = user_text
                model = "llama-3.3-70b-versatile"

            api_msgs.append({"role": "user", "content": user_content})

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            try:
                stream = client.chat.completions.create(
                    model=model, messages=api_msgs,
                    stream=True, max_tokens=2048, temperature=0.7
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        data = json.dumps({"text": delta, "done": False}, ensure_ascii=False)
                        self.wfile.write(f"data: {data}\n\n".encode())
                        self.wfile.flush()
                self.wfile.write(f"data: {json.dumps({'text': '', 'done': True})}\n\n".encode())
                self.wfile.flush()
            except Exception as e:
                err = json.dumps({"text": f"❌ Error: {str(e)}", "done": True})
                self.wfile.write(f"data: {err}\n\n".encode())

        elif self.path == "/save":
            history = body.get("history", [])
            title   = body.get("title", "")
            key = save_history(history, title)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"key": key}).encode())

        elif self.path == "/delete_history":
            delete_history()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    PORT = 8000
    print("=" * 55)
    print("  🔺 TripletAI v3.0 — by Gagandeep Singh Kalia")
    print("=" * 55)
    if not API_KEY:
        print("\n  ⚠️  API Key nahi mili!")
        print('  PowerShell: $env:GROQ_API_KEY="gsk_key"')
        print("  phir: python app.py\n")
    else:
        print("  ✅ Groq API Key ready!")
    print(f"  🌐 Opening: http://localhost:{PORT}")
    print("=" * 55)
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    server = HTTPServer(("", PORT), TripletHandler)
    server.serve_forever()