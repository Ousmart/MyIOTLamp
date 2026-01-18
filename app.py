from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
import os

# ดึงค่า DATABASE_URL จาก Environment Variable
# หากไม่มีค่า ให้ใช้ค่าว่าง (เพื่อไม่ให้พังตอนรัน local แต่ต้องระวัง)
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. Database Models
class UserDevice(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50))
    esp_id = Column(String(50), unique=True)
    password = Column(String(50)) 

# สร้างตารางใน Database
Base.metadata.create_all(bind=engine)

# 3. Pydantic Models สำหรับรับข้อมูลผ่าน HTTP (Signup)
class SignupRequest(BaseModel):
    username: str
    esp_id: str
    password: str

# 4. FastAPI Setup
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# เก็บการเชื่อมต่อ { "device_id": websocket_object }
active_connections = {}

# --- HTTP Routes ---

@app.get("/")
def read_root():
    return {"message": "FastAPI IoT Server is running"}

# Route สำหรับลงทะเบียนอุปกรณ์/ผู้ใช้ใหม่เข้า Database
@app.post("/signup")
def signup(data: SignupRequest):
    db = SessionLocal()
    try:
        # เช็คว่า esp_id ซ้ำไหม
        existing = db.query(UserDevice).filter(UserDevice.esp_id == data.esp_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="ESP_ID already registered")
        
        new_device = UserDevice(
            username=data.username,
            esp_id=data.esp_id,
            password=data.password
        )
        db.add(new_device)
        db.commit()
        return {"status": "success", "message": f"Device {data.esp_id} registered successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# --- WebSocket Route ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    db = SessionLocal()
    client_id = None
    
    try:
        while True:
            # รับข้อความ
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # CASE 1: การ Register (ทั้ง ESP8266 และ React ต้องส่งมาตอนเชื่อมต่อครั้งแรก)
            if message.get("type") == "register":
                input_id = message.get("id")
                input_pass = message.get("password")
                
                # ตรวจสอบกับ Database
                user_record = db.query(UserDevice).filter(
                    UserDevice.esp_id == input_id, 
                    UserDevice.password == input_pass
                ).first()
                
                if user_record:
                    client_id = input_id
                    active_connections[client_id] = websocket
                    print(f"Authorized: {client_id}")
                    await websocket.send_json({
                        "type": "auth_status",
                        "status": "authorized", 
                        "user": user_record.username
                    })
                else:
                    print(f"Unauthorized access attempt: {input_id}")
                    await websocket.send_json({
                        "type": "auth_status",
                        "status": "unauthorized"
                    })
                    await websocket.close()
                    break
            
            # CASE 2: คำสั่งควบคุม (จาก React -> ESP8266)
            elif "target_id" in message:
                target_id = message["target_id"]
                if target_id in active_connections:
                    await active_connections[target_id].send_text(json.dumps(message))
                    print(f"Command routed to {target_id}: {message.get('cmd')}")
                else:
                    print(f"Target {target_id} is offline")
                    await websocket.send_json({"type": "error", "message": "Target device is offline"})

            # CASE 3: ข้อมูลจากอุปกรณ์ (ESP8266 -> React)
            # 3. ข้อมูลจากอุปกรณ์ (ESP8266 -> React)
            elif message.get("type") == "telemetry":
                esp_id = message.get("id")
                # ค้นหาว่าใครคือเจ้าของหรือผู้ที่ควบคุม ESP_ID นี้อยู่
                # เราจะส่งกลับไปให้เฉพาะ Client ที่ลงทะเบียนด้วย ID เดียวกันเท่านั้น
                for conn_id, conn_ws in active_connections.items():
                    # เงื่อนไขสำคัญ: ส่งให้เฉพาะ socket ที่มี ID ตรงกัน แต่ไม่ใช่ตัวที่ส่งมาเอง
                    if conn_id == esp_id and conn_ws != websocket:
                        try:
                            await conn_ws.send_text(json.dumps(message))
                            print(f"Feedback sent to Controller of {esp_id}")
                        except:
                            pass

    except WebSocketDisconnect:
        if client_id in active_connections:
            del active_connections[client_id]
            print(f"Client {client_id} disconnected")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()