from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random

app = FastAPI()

# ตั้งค่า CORS เพื่อให้ React เชื่อมต่อได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # สุ่มตัวเลข 0-100
            random_value = random.randint(0, 100)
            # ส่งค่าไปยัง Client (React/ESP8266)
            await websocket.send_json({"value": random_value})
            # หน่วงเวลา 0.1 วินาที (ส่งรัวๆ 10 ครั้งต่อวินาที)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        print("Client disconnected")