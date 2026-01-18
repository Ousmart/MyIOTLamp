import React, { useEffect, useState } from 'react';
import useWebSocket from 'react-use-websocket';

function App() {
  const [currentValue, setCurrentValue] = useState(0);
  
  // เปลี่ยน URL เป็นของ Render เมื่อ Deploy แล้ว (เช่น wss://your-app.onrender.com/ws)
  // ตอนทดสอบ Local ให้ใช้ ws://127.0.0.1:8000/ws
  const socketUrl = 'wss://myiotlamp.onrender.com/ws';

  const { lastJsonMessage, readyState } = useWebSocket(socketUrl, {
    onOpen: () => console.log('Connected to FastAPI'),
    shouldReconnect: (closeEvent) => true, // ให้ต่อใหม่โดยอัตโนมัติถ้าหลุด
  });

  // อัปเดตค่าเมื่อมีข้อมูลใหม่ส่งมา
  useEffect(() => {
    if (lastJsonMessage !== null) {
      setCurrentValue(lastJsonMessage.value);
    }
  }, [lastJsonMessage]);

  const connectionStatus = {
    0: 'Connecting',
    1: 'Open',
    2: 'Closing',
    3: 'Closed',
  }[readyState];

  return (
    <div style={{ textAlign: 'center', marginTop: '50px' }}>
      <h1>Real-time Random Value</h1>
      <p>Status: <strong>{connectionStatus}</strong></p>
      <div style={{ fontSize: '72px', color: '#646cff' }}>
        {currentValue}
      </div>
    </div>
  );
}

export default App;