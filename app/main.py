import json, sqlite3, datetime
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import jwt

# Config
SECRET_KEY = "supersecretkey"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
DB_PATH = "app/db.sqlite3"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --------------------
# DB Helpers
# --------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            last_address TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY,
            name TEXT,
            price REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            items TEXT,
            total REAL,
            timestamp DATETIME
        )
    """)
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

init_db()

# --------------------
# JWT Auth
# --------------------
def create_token():
    return jwt.encode({"admin": True}, SECRET_KEY, algorithm="HS256")

def verify_token(token: str = ""):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("admin") != True:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# --------------------
# Routes
# --------------------
@app.get("/")
def home():
    return FileResponse("app/static/index.html")

@app.get("/api/menu")
def get_menu():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id,name,price FROM menu")
    rows = c.fetchall()
    menu = [dict(row) for row in rows]
    conn.close()
    return menu

@app.post("/api/order")
def post_order(phone: str = Form(...), address: str = Form(...), items: str = Form(...)):
    conn = get_db()
    c = conn.cursor()
    # Save/update user
    c.execute("INSERT OR REPLACE INTO users(phone,last_address) VALUES (?,?)", (phone,address))
    # Calculate total
    order_items = json.loads(items)
    total = sum(i["price"]*i["qty"] for i in order_items)
    # Save order
    c.execute("INSERT INTO orders(phone,items,total,timestamp) VALUES (?,?,?,?)",
              (phone, json.dumps(order_items), total, datetime.datetime.now()))
    conn.commit()
    conn.close()
    return {"success": True, "total": total}

@app.get("/api/user/{phone}")
def get_user(phone: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT last_address FROM users WHERE phone=?", (phone,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"last_address": row["last_address"]}
    return {"last_address": ""}

# --------------------
# Admin endpoints
# --------------------
@app.post("/api/admin/login")
def admin_login(user: str = Form(...), password: str = Form(...)):
    if user == ADMIN_USER and password == ADMIN_PASS:
        token = create_token()
        return {"token": token}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/admin/orders")
def admin_orders(token: str = Form(...)):
    verify_token(token)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/menu")
def admin_menu(menu: list, token: str = Form(...)):
    verify_token(token)
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM menu")
    for item in menu:
        c.execute("INSERT INTO menu(id,name,price) VALUES (?,?,?)", (item["id"], item["name"], item["price"]))
    conn.commit()
    conn.close()
    return {"success": True}
