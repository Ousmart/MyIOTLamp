import os
import json
import pymysql
import pymysql.cursors
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from urllib.parse import urlparse # ใช้ตัวนี้แกะ URL จะปลอดภัยกว่า split เอง

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Connection Function (เวอร์ชันปลอดภัย) ---
def get_db_connection():
    url_str = os.getenv("DATABASE_URL")
    if not url_str:
        raise ValueError("DATABASE_URL is not set in environment variables")
    
    # ลบส่วนโปรโตคอลออกเพื่อให้ urlparse ทำงานได้ถูกต้อง
    clean_url = url_str.replace("mysql+pymysql://", "http://") 
    result = urlparse(clean_url)
    
    return pymysql.connect(
        host=result.hostname,
        user=result.username,
        password=result.password,
        database=result.path.lstrip('/'),
        port=result.port or 3306,
        ssl={'ssl_mode': 'REQUIRED'},
        cursorclass=pymysql.cursors.DictCursor
    )

# --- นอกนั้นใช้โค้ดเดิมได้เลย ---

def init_db():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50),
                    esp_id VARCHAR(50) UNIQUE,
                    password VARCHAR(50)
                )
            """)
        conn.commit()
        conn.close()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ DB Init Error: {e}")

# เรียกใช้งานตอนเริ่ม
init_db()

# ... (ส่วน Signup และ WebSocket คงเดิม) ...

# --- Models ---
class SignupRequest(BaseModel):
    username: str
    esp_id: str
    password: str

active_connections = {}

# --- Routes ---

@app.get("/")
def home():
    return "Hello"

@app.post("/signup")
def signup(data: SignupRequest):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # เช็คว่ามี ID นี้หรือยัง
            cursor.execute("SELECT id FROM devices WHERE esp_id = %s", (data.esp_id,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="ESP_ID already registered")
            
            # เพิ่มข้อมูลใหม่
            sql = "INSERT INTO devices (username, esp_id, password) VALUES (%s, %s, %s)"
            cursor.execute(sql, (data.username, data.esp_id, data.password))
        conn.commit()
        return {"status": "success", "message": f"Device {data.esp_id} registered"}
    finally:
        conn.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = None
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "register":
                input_id = message.get("id")
                input_pass = message.get("password")
                
                # ตรวจสอบกับ Database โดยตรง
                conn = get_db_connection()
                user_record = None
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "SELECT username FROM devices WHERE esp_id = %s AND password = %s",
                            (input_id, input_pass)
                        )
                        user_record = cursor.fetchone()
                finally:
                    conn.close()

                if user_record:
                    client_id = input_id
                    active_connections[client_id] = websocket
                    await websocket.send_json({
                        "type": "auth_status", 
                        "status": "authorized", 
                        "user": user_record['username']
                    })
                else:
                    await websocket.send_json({"type": "auth_status", "status": "unauthorized"})
                    await websocket.close()
                    break

            elif "target_id" in message:
                print(f"Received command for {message['target_id']}: {message['cmd']}")
                target_id = message["target_id"]
                if target_id in active_connections:
                    await active_connections[target_id].send_text(json.dumps(message))
            
            elif message.get("type") == "telemetry":
                esp_id = message.get("id")
                for conn_id, conn_ws in active_connections.items():
                    if conn_id == esp_id and conn_ws != websocket:
                        await conn_ws.send_text(json.dumps(message))

    except WebSocketDisconnect:
        if client_id in active_connections:
            del active_connections[client_id]