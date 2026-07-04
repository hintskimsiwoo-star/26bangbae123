import os
import json
import sqlite3
import csv
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import google.generativeai as genai
from werkzeug.security import generate_password_hash, check_password_hash 

app = Flask(__name__)
# 보안 비밀키 설정 (세션 및 소켓 암호화용)
app.config['SECRET_KEY'] = 'siwoo_school_violence_prevention_secret'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

# API KEY 설정
API_KEY = "AIzaSyDQ5GBePgKYHif81I4CuXACCD4YJhObBMY"
genai.configure(api_key=API_KEY.strip())
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

# HTML UI 정의 (Single File 형태 유지를 위해 내장 변수로 처리)
HTML_UI = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>동GO동樂 - 상용화 플랫폼</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        :root { --kakao-yellow: #FEE500; --side-bar: #423630; --list-bg: #FFFFFF; --chat-bg: #abc1d1; }
        body { margin: 0; display: flex; height: 100vh; font-family: 'Malgun Gothic', sans-serif; overflow: hidden; }
        
        .sidebar { width: 70px; background: var(--side-bar); display: flex; flex-direction: column; align-items: center; padding-top: 30px; gap: 25px; }
        .side-icon { color: #888; font-size: 24px; cursor: pointer; }
        .side-icon.active { color: white; }

        .room-list { width: 300px; background: var(--list-bg); border-right: 1px solid #ddd; }
        .room-header { padding: 25px 20px; font-size: 20px; font-weight: bold; }
        .room-item { padding: 15px 20px; cursor: pointer; display: flex; gap: 12px; align-items: center; }
        .room-item.active { background: #f2f2f2; }
        .profile-img { width: 45px; height: 45px; border-radius: 15px; background: #eee; display: flex; align-items: center; justify-content: center; font-size: 20px;}

        .chat-pane { flex: 1; display: flex; flex-direction: column; background: var(--chat-bg); position: relative; }
        .chat-header { height: 60px; background: white; display: flex; align-items: center; padding: 0 20px; font-weight: bold; border-bottom: 1px solid #ddd;}
        .chat-content { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        
        .msg { max-width: 60%; padding: 10px 14px; border-radius: 10px; font-size: 14px; word-break: break-all; line-height: 1.4; }
        .msg.me { background: var(--kakao-yellow); align-self: flex-end; border-top-right-radius: 0; }
        .msg.other { background: white; align-self: flex-start; border-top-left-radius: 0; }
        .msg.ai { background: #e0f7fa; color: #006064; border: 2px solid #00acc1; align-self: flex-start; font-weight: bold; border-top-left-radius: 0; }

        .input-area { height: 120px; background: white; padding: 15px; display: flex; flex-direction: column; position: relative; }
        #text-in { flex: 1; border: none; outline: none; resize: none; font-size: 14px; }
        .btn-send { align-self: flex-end; background: var(--kakao-yellow); border: 1px solid #e5d000; padding: 6px 25px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        #typing-indicator { position: absolute; top: -30px; left: 10px; font-size: 13px; color: #000; background: rgba(255, 255, 255, 0.8); padding: 5px 10px; border-radius: 5px; display: none; font-weight: bold; }

        /* 모달 및 로그인 화면 */
        .overlay { position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.7); z-index: 1000; display: none; justify-content: center; align-items: center; }
        .modal { background: white; padding: 30px; border-radius: 20px; width: 320px; text-align: center; }
        .timer { font-size: 40px; font-weight: bold; color: #ff4d4d; margin: 15px 0; }
        
        #login-layer { position: fixed; top:0; left:0; width:100%; height:100%; background: var(--kakao-yellow); z-index: 2000; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .login-box { background: white; padding: 40px; border-radius: 20px; width: 320px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
        .login-box input { width: 100%; padding: 12px; margin-bottom: 10px; box-sizing: border-box; border: 1px solid #ddd; border-radius: 5px; }
        .btn-auth { width: 100%; padding: 12px; background: var(--side-bar); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; margin-bottom: 10px; }
        
        .tab-group { display: flex; margin-bottom: 20px; border-bottom: 2px solid #eee; }
        .tab { flex: 1; padding: 10px; cursor: pointer; font-weight: bold; color: #aaa; }
        .tab.active { color: var(--side-bar); border-bottom: 3px solid var(--side-bar); }
    </style>
</head>
<body>

    <div id="login-layer">
        <h1 style="color: var(--side-bar); margin-bottom: 30px;">🛡️ 동GO동樂</h1>
        <div class="login-box">
            <div class="tab-group">
                <div class="tab active" id="tab-login" onclick="setMode('login')">로그인</div>
                <div class="tab" id="tab-signup" onclick="setMode('signup')">회원가입</div>
            </div>
            <input type="text" id="email" placeholder="학교 메일 (@sen.go.kr)">
            <input type="password" id="pw" placeholder="비밀번호">
            <button class="btn-auth" id="btn-submit" onclick="auth('login')">로그인 및 입장</button>
        </div>
    </div>

    <div id="nudge-overlay" class="overlay">
        <div class="modal">
            <h3 style="color:#d32f2f; margin-top:0;">🚨 전송 차단</h3>
            <p id="nudge-text" style="color:#666; line-height:1.5;"></p>
            <div class="timer" id="timer-val">5</div>
            <button id="btn-force" disabled onclick="forceSend()" style="width:100%; padding:12px; background:#ff4d4d; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold; margin-bottom:10px;">강제 전송</button>
            <button onclick="closeModal()" style="width:100%; border:none; background:#eee; color:#333; padding:12px; border-radius:8px; cursor:pointer; font-weight:bold;">취소하기</button>
        </div>
    </div>

    <div class="sidebar">
        <div class="side-icon active">💬</div>
    </div>

    <div class="room-list">
        <div class="room-header">채팅방</div>
        <div class="room-item active" onclick="switchRoom('group')" id="room-tab-group">
            <div class="profile-img" style="background:#ffcc00;">👥</div>
            <div><strong>우리반 단체방</strong></div>
        </div>
        <div class="room-item" onclick="switchRoom('ai')" id="room-tab-ai">
            <div class="profile-img" style="background:#00acc1;">🛡️</div>
            <div><strong>AI 수호자 DM</strong><br><small style="color:#ff4d4d; font-weight:bold;" id="ai-badge"></small></div>
        </div>
    </div>

    <div class="chat-pane">
        <div class="chat-header" id="current-room-name">우리반 단체방</div>
        
        <div class="chat-content" id="chat-group">
            <div class="msg ai" style="align-self: center; background: rgba(0,0,0,0.1); border: none; color: #555;">[단톡방에 입장하셨습니다]</div>
        </div>
        
        <div class="chat-content" id="chat-ai" style="display: none;"></div>
        
        <div class="input-area">
            <div id="typing-indicator">🤖 AI 스캔 중...</div>
            <textarea id="text-in" placeholder="메시지 입력 후 엔터..." onkeydown="if(event.keyCode==13 && !event.shiftKey) { event.preventDefault(); attemptSend(); }"></textarea>
            <button class="btn-send" onclick="attemptSend()">전송</button>
        </div>
    </div>

    <script>
        const socket = io(); 
        let myEmail = "";
        let activeRoom = 'group';
        let pendingMsg = "";
        let typingTimer;
        let isBlocked = false;
        let currentMode = 'login';

        function setMode(mode) {
            currentMode = mode;
            document.getElementById('tab-login').className = 'tab' + (mode === 'login' ? ' active' : '');
            document.getElementById('tab-signup').className = 'tab' + (mode === 'signup' ? ' active' : '');
            document.getElementById('btn-submit').innerText = mode === 'login' ? '로그인 및 입장' : '회원가입하기';
            document.getElementById('btn-submit').onclick = () => auth(mode);
        }

        async function auth(mode) {
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('pw').value.trim();

            if(!email || !password) return alert("이메일과 비밀번호를 모두 입력해주세요.");

            try {
                const res = await fetch('/api/auth', {
                    method: 'POST', 
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email, password, mode})
                });
                
                if (!res.ok) throw new Error("서버 응답 오류");

                const data = await res.json();
                
                if(data.status === 'success') {
                    if(mode === 'signup') {
                        alert(data.msg); 
                        setMode('login'); 
                    } else {
                        myEmail = email;
                        document.getElementById('login-layer').style.display = 'none';
                        socket.emit('join', {email: myEmail});
                    }
                } else { 
                    alert(data.msg); 
                }
            } catch (error) {
                alert("🚨 파이썬 서버가 꺼져 있거나 연결 오류입니다.");
            }
        }

        const inputEl = document.getElementById('text-in');
        const indicator = document.getElementById('typing-indicator');

        inputEl.addEventListener('input', () => {
            clearTimeout(typingTimer);
            indicator.style.display = 'block';
            if (inputEl.value.trim().length > 0) {
                typingTimer = setTimeout(checkWhileTyping, 1200);
            } else { indicator.style.display = 'none'; }
        });

        async function checkWhileTyping() {
            indicator.style.display = 'none';
            const text = inputEl.value.trim();
            if(!text) return;
            try {
                const res = await fetch('/api/analyze', {
                    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message: text})
                });
                const data = await res.json();
                if(data.is_toxic) triggerPopup(text, data.nudge);
            } catch(e) {}
        }

        async function attemptSend() {
            if(activeRoom !== 'group' || isBlocked) return;
            const text = inputEl.value.trim();
            if(!text) return;
            clearTimeout(typingTimer);
            indicator.style.display = 'none';

            try {
                const res = await fetch('/api/analyze', {
                    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message: text})
                });
                const data = await res.json();

                if(data.is_toxic) {
                    triggerPopup(text, data.nudge);
                } else {
                    sendFinal(text, false);
                    inputEl.value = '';
                }
            } catch(e) {
                sendFinal(text, false);
                inputEl.value = '';
            }
        }

        function triggerPopup(text, nudgeMsg) {
            isBlocked = true; pendingMsg = text;
            inputEl.blur(); inputEl.disabled = true;
            document.getElementById('nudge-text').innerText = nudgeMsg;
            document.getElementById('nudge-overlay').style.display = 'flex';
            
            let count = 5;
            const btn = document.getElementById('btn-force');
            const val = document.getElementById('timer-val');
            btn.disabled = true; val.innerText = count;
            
            const itv = setInterval(() => {
                count--; val.innerText = count;
                if(count <= 0) { clearInterval(itv); btn.disabled = false; }
            }, 1000);
        }

        function closeModal() {
            document.getElementById('nudge-overlay').style.display = 'none';
            isBlocked = false; inputEl.disabled = false; inputEl.focus(); pendingMsg = "";
        }

        function forceSend() {
            closeModal(); sendFinal(pendingMsg, true);
            inputEl.value = ''; pendingMsg = "";
        }

        function sendFinal(msg, isToxic) {
            socket.emit('chat', {sender: myEmail, message: msg, is_toxic: isToxic});
        }

        socket.on('broadcast_chat', (data) => {
            const type = (data.sender === myEmail) ? 'me' : 'other';
            renderMsg('chat-group', `${data.sender.split('@')[0]}: ${data.message}`, type);
            
            if(data.is_toxic && data.sender !== myEmail) {
                document.getElementById('ai-badge').innerText = "🔴 치료 알림";
                const alertHtml = `
                    단톡방의 <b>\${data.sender.split('@')[0]}</b>님이 보낸 메시지로 상처받으셨나요?<br><br>
                    <button onclick="doReport('\${data.sender}', '\${data.message}')" 
                    style="background:#ff4d4d; color:white; border:none; padding:8px; border-radius:4px; cursor:pointer;">
                    선생님께 신고하기</button>
                `;
                renderMsg('chat-ai', alertHtml, 'ai');
            }
        });

        async function doReport(attacker, msg) {
            document.getElementById('ai-badge').innerText = "";
            const res = await fetch('/api/report', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({attacker, msg, victim: myEmail})
            });
            const data = await res.json();
            renderMsg('chat-ai', `[신고 접수 완료]\\n\\n\${data.counseling}`, 'ai');
        }

        function switchRoom(room) {
            activeRoom = room;
            document.getElementById('current-room-name').innerText = (room === 'group' ? "우리반 단체방" : "AI 수호자 DM 방");
            document.getElementById('room-tab-group').className = 'room-item' + (room === 'group' ? ' active' : '');
            document.getElementById('room-tab-ai').className = 'room-item' + (room === 'ai' ? ' active' : '');
            document.getElementById('chat-group').style.display = (room === 'group' ? 'flex' : 'none');
            document.getElementById('chat-ai').style.display = (room === 'ai' ? 'flex' : 'none');
        }

        function renderMsg(targetId, text, type) {
            const box = document.getElementById(targetId);
            const d = document.createElement('div');
            d.className = `msg \${type}`;
            d.innerHTML = text;
            box.appendChild(d);
            box.scrollTop = box.scrollHeight;
        }
    </script>
</body>
</html>
"""

def init_db():
    conn = sqlite3.connect('guardians.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password_hash TEXT)')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template_string(HTML_UI)

@app.route('/api/auth', methods=['POST'])
def auth():
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    mode = data.get('mode')

    conn = sqlite3.connect('guardians.db')
    cursor = conn.cursor()
    
    if mode == 'signup':
        hashed = generate_password_hash(password)
        try:
            cursor.execute('INSERT INTO users VALUES (?, ?)', (email, hashed))
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "msg": "회원가입 완료! 로그인 탭에서 입장하세요."})
        except:
            conn.close()
            return jsonify({"status": "fail", "msg": "이미 존재하는 계정입니다."})
    else:
        cursor.execute('SELECT password_hash FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[0], password):
            return jsonify({"status": "success"})
        return jsonify({"status": "fail", "msg": "비밀번호가 틀렸습니다."})

@app.route('/api/analyze', methods=['POST'])
def analyze():
    text = request.json.get('message', '')
    if not text:
        return jsonify({"is_toxic": False, "nudge": ""})
    
    bad_words = ['야', '뭐', '씨발', '존나', '눈치', '바보', '짜증', '죽어', '개새', '병신']
    if any(word in text for word in bad_words):
        return jsonify({"is_toxic": True, "nudge": "상대방을 존중하지 않는 언어(가스라이팅, 비하 등)가 감지되었습니다. 정말 전송하시겠습니까?"})

    prompt = f"너는 학폭 감지 AI야. '{text}'가 욕설, 비하, 가스라이팅인지 깐깐하게 판단해 JSON으로 답해: {{\"is_toxic\": true/false, \"nudge\": \"경고 멘트\"}}"
    try:
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
        response = model.generate_content(prompt, safety_settings=safety_settings)
        json_res = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return jsonify(json.loads(json_res))
    except Exception as e:
        return jsonify({"is_toxic": True, "nudge": "부적절한 언어가 감지되었습니다. 5초 후 전송 가능합니다."})

@app.route('/api/report', methods=['POST'])
def report():
    data = request.json
    attacker = data.get('attacker', '알수없음')
    victim = data.get('victim', '알수없음')
    msg = data.get('msg', '내용없음')
    
    try:
        file_path = '학교폭력_신고대장.csv'
        file_exists = os.path.isfile(file_path)
        with open(file_path, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['신고시간', '가해자 이메일', '피해자 이메일', '폭력 내용'])
            writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), attacker, victim, msg])
    except Exception as e:
        print(f"❌ 엑셀 에러: {e}")

    counsel_prompt = f"피해자({victim})가 '{msg}'라는 말을 듣고 신고했어. 다정하게 위로하면서 기분이 어떤지 물어봐줘."
    try:
        response = model.generate_content(counsel_prompt)
        return jsonify({"status": "success", "counseling": response.text})
    except:
    return jsonify({"status": "success", "msg": "회원가입 완료! 로그인 탭에서 입장하세요."})
