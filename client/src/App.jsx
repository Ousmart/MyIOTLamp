import React, { useState, useEffect } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';

const App = () => {
  const [mode, setMode] = useState('login'); // 'login' หรือ 'signup'
  const [authData, setAuthData] = useState({ id: '', user: '', pass: '' });
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [devices, setDevices] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [deviceStatuses, setDeviceStatuses] = useState({});

  const socketUrl = 'wss://myiotlamp.onrender.com/ws';
  const apiUrl = 'https://myiotlamp.onrender.com'; // URL ของ FastAPI

  // // เปลี่ยนจาก wss://myiotlamp.onrender.com/ws เป็น local
  // const socketUrl = 'ws://127.0.0.1:8000/ws'; 

  // // เปลี่ยนจาก https://myiotlamp.onrender.com เป็น local
  // const apiUrl = 'http://127.0.0.1:8000';

  const { sendMessage, lastMessage, readyState } = useWebSocket(socketUrl, {
    shouldReconnect: () => true,
  });

  useEffect(() => {
    if (lastMessage !== null) {
      const data = JSON.parse(lastMessage.data);
      if (data.type === "auth_status") {
        if (data.status === "authorized") {
          setIsLoggedIn(true);
          if (!devices.includes(authData.id)) {
            setDevices([...devices, authData.id]);
            setSelectedId(authData.id);
          }
        } else {
          alert("Unauthorized: Wrong ID or Password");
        }
      }
      if (data.type === "telemetry") {
        setDeviceStatuses(prev => ({ ...prev, [data.id]: data.payload.LED_D0 }));
      }
    }
  }, [lastMessage]);

  // --- ฟังก์ชันสำหรับ Register (Signup) ---
  const handleSignup = async () => {
    try {
      const response = await fetch(`${apiUrl}/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: authData.user,
          esp_id: authData.id,
          password: authData.pass
        }),
      });
      const resData = await response.json();
      if (response.ok) {
        alert("Register Success! Please Login.");
        setMode('login');
      } else {
        alert(resData.detail || "Register Failed");
      }
    } catch (err) {
      alert("Error connecting to server");
    }
  };

  const handleLogin = () => {
    sendMessage(JSON.stringify({
      type: "register",
      id: authData.id,
      password: authData.pass
    }));
  };

  const toggleLED = (command) => {
    sendMessage(JSON.stringify({ target_id: selectedId, cmd: command }));
  };

  // --- UI Logic ---
  if (!isLoggedIn) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <h2>{mode === 'login' ? 'IoT Login' : 'IoT Register'}</h2>
          
          {/* ส่วนกรอกข้อมูล */}
          <input style={styles.input} placeholder="Username" onChange={e => setAuthData({...authData, user: e.target.value})} />
          <input style={styles.input} placeholder="ESP ID (e.g. ESP_01)" onChange={e => setAuthData({...authData, id: e.target.value})} />
          <input style={styles.input} type="password" placeholder="Password" onChange={e => setAuthData({...authData, pass: e.target.value})} />
          
          {mode === 'login' ? (
            <>
              <button style={styles.button} onClick={handleLogin}>Connect & Control</button>
              <p onClick={() => setMode('signup')} style={styles.link}>No account? Register here</p>
            </>
          ) : (
            <>
              <button style={{...styles.button, backgroundColor: '#2ecc71'}} onClick={handleSignup}>Create Account</button>
              <p onClick={() => setMode('login')} style={styles.link}>Back to Login</p>
            </>
          )}
          <p>Server Status: {ReadyState[readyState]}</p>
        </div>
      </div>
    );
  }

  // Dashboard (เหมือนเดิม)
  return (
    <div style={styles.container}>
      <h1>Dashboard</h1>
      <div style={styles.card}>
        <select style={styles.input} value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
          {devices.map(id => <option key={id} value={id}>{id}</option>)}
        </select>
        <button onClick={() => setIsLoggedIn(false)} style={{marginTop: '10px'}}>Add Device</button>
      </div>

      {selectedId && (
        <div style={styles.card}>
          <h3>Control: {selectedId}</h3>
          <div style={{...styles.led, backgroundColor: deviceStatuses[selectedId] === 1 ? '#2ecc71' : '#95a5a6', margin: '10px auto'}} />
          <button style={{...styles.ctrlBtn, backgroundColor: '#2ecc71'}} onClick={() => toggleLED('LED_ON')}>ON</button>
          <button style={{...styles.ctrlBtn, backgroundColor: '#e74c3c'}} onClick={() => toggleLED('LED_OFF')}>OFF</button>
        </div>
      )}
    </div>
  );
};

const styles = {
  container: { padding: '20px', textAlign: 'center', fontFamily: 'Arial', backgroundColor: '#eee', minHeight: '100vh' },
  card: { border: '1px solid #ddd', padding: '20px', margin: '0 auto', maxWidth: '350px', borderRadius: '15px', backgroundColor: '#fff', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' },
  input: { padding: '12px', margin: '8px 0', borderRadius: '8px', border: '1px solid #ccc', width: '90%' },
  button: { padding: '12px', width: '100%', backgroundColor: '#3498db', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' },
  link: { color: '#3498db', cursor: 'pointer', marginTop: '15px', textDecoration: 'underline', fontSize: '14px' },
  led: { width: '40px', height: '40px', borderRadius: '50%', transition: '0.3s' },
  ctrlBtn: { padding: '10px 20px', color: '#fff', border: 'none', borderRadius: '5px', margin: '5px', cursor: 'pointer' }
};

export default App;