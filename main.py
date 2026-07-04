import streamlit as st
import os
import json
import sqlite3
import csv
import time
from datetime import datetime
import google.generativeai as genai

# 1. 페이지 기본 설정 및 환경 세팅
st.set_page_config(page_title="동GO동樂 - 시우", page_icon="🛡️", layout="wide")

API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDQ5GBePgKYHif81I4CuXACCD4YJhObBMY")
genai.configure(api_key=API_KEY.strip())
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

# DB 및 CSV 초기화
def init_db():
    conn = sqlite3.connect('guardians.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT)')
    conn.commit()
    conn.close()

init_db()

# 세션 상태(로그인 및 채팅 데이터) 초기화
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "group_messages" not in st.session_state:
    st.session_state.group_messages = [{"sender": "AI 수호자", "text": "[단톡방에 입장하셨습니다]", "is_ai": True}]
if "ai_messages" not in st.session_state:
    st.session_state.ai_messages = []

# --- 로그인 / 회원가입 화면 ---
if not st.session_state.logged_in:
    st.title("🛡️ 학교 폭력 예방 플랫폼 '동GO동樂'")
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    
    with tab1:
        login_email = st.text_input("학교 메일 (@sen.go.kr)", key="l_email")
        login_pw = st.text_input("비밀번호", type="password", key="l_pw")
        if st.button("로그인 및 입장"):
            conn = sqlite3.connect('guardians.db')
            cursor = conn.cursor()
            cursor.execute('SELECT password FROM users WHERE email = ? AND password = ?', (login_email, login_pw))
            user = cursor.fetchone()
            conn.close()
            if user:
                st.session_state.logged_in = True
                st.session_state.user_email = login_email
                st.rerun()
            else:
                st.error("이메일 또는 비밀번호가 틀렸습니다.")
                
    with tab2:
        sign_email = st.text_input("학교 메일 (@sen.go.kr)", key="s_email")
        sign_pw = st.text_input("비밀번호", type="password", key="s_pw")
        if st.button("회원가입 하기"):
            if not sign_email or not sign_pw:
                st.warning("모든 정보를 입력해주세요.")
            else:
                try:
                    conn = sqlite3.connect('guardians.db')
                    cursor = conn.cursor()
                    cursor.execute('INSERT INTO users VALUES (?, ?)', (sign_email, sign_pw))
                    conn.commit()
                    conn.close()
                    st.success("회원가입 완료! 로그인 탭에서 로그인 해주세요.")
                except:
                    st.error("이미 존재하는 계정입니다.")

# --- 메인 채팅 화면 ---
else:
    # 상단 바 (로그아웃 및 파일 다운로드)
    col_title, col_btn1, col_btn2 = st.columns([6, 2, 2])
    with col_title:
        st.title(f"🛡️ 시우 (접속: {st.session_state.user_email.split('@')[0]})")
    with col_btn1:
        if os.path.exists('학교폭력_신고대장.csv'):
            with open('학교폭력_신고대장.csv', 'rb') as f:
                st.download_button("📊 신고대장 다운로드 (교사용)", f, file_name="학교폭력_신고대장.csv", mime="text/csv")
    with col_btn2:
        if st.button("로그아웃"):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.rerun()

    # 사이드바 메뉴 선택
    menu = st.sidebar.radio("채팅방 목록", ["👥 우리반 단체방", "🤖 AI 수호자 DM"])

    # --- 1. 우리반 단체방 ---
    if menu == "👥 우리반 단체방":
        st.subheader("우리반 단체 단톡방")
        
        # 대화 내역 출력
        for msg in st.session_state.group_messages:
            with st.chat_message("user" if not msg.get("is_ai") else "assistant"):
                st.write(f"**{msg['sender']}**: {msg['text']}")

        # 메시지 입력 처리
        if chat_input := st.chat_input("메시지를 입력하세요..."):
            bad_words = ['야', '뭐', '씨발', '존나', '눈치', '바보', '짜증', '죽어', '개새', '병신']
            
            # 폭력성 체크
            is_toxic = any(word in chat_input for word in bad_words)
            
            if is_toxic:
                # 5초 전송 제한 차단 팝업 효과 구현
                st.error("🚨 전송 차단: 상대방을 비하하거나 상처를 줄 수 있는 표현이 감지되었습니다.")
                progress_text = "부적절한 언어 검토 중... 5초간 전송이 금지됩니다."
                my_bar = st.progress(0, text=progress_text)
                for percent_complete in range(100):
                    time.sleep(0.05)
                    my_bar.progress(percent_complete + 1, text=progress_text)
                my_bar.empty()
                
                # 5초 패널티 후 강제 전송 시나리오 가동
                st.session_state.group_messages.append({"sender": st.session_state.user_email.split('@')[0], "text": chat_input})
                
                # 피해자용 보호 AI DM 자동 생성 조치
                ai_alert = f"🔴 단톡방에서 폭력 의심 대화가 감지되었습니다.\n방금 전 대화: '{chat_input}'"
                st.session_state.ai_messages.append({"sender": "AI 시스템 알림", "text": ai_alert, "trigger_msg": chat_input, "attacker": st.session_state.user_email})
                st.warning("⚠️ 메시지가 전송되었습니다. AI 수호자가 상황을 기록합니다.")
                time.sleep(1)
                st.rerun()
            else:
                st.session_state.group_messages.append({"sender": st.session_state.user_email.split('@')[0], "text": chat_input})
                st.rerun()

    # --- 2. AI 수호자 DM ---
    elif menu == "🤖 AI 수호자 DM":
        st.subheader("AI 수호자 1:1 비밀 상담방")
        
        if not st.session_state.ai_messages:
            st.info("현재 감지된 학교폭력 알림 소견이 없습니다. 안심하고 대화하셔도 좋습니다.")
        
        for msg in st.session_state.ai_messages:
            with st.chat_message("assistant"):
                st.write(f"**{msg['sender']}**")
                st.write(msg['text'])
                
                # 신고 버튼 배치 (기획안의 '피해자가 저장을 동의한 내역 저장' 기능)
                if "trigger_msg" in msg:
                    if st.button("선생님께 신고 및 대화내역 저장", key=f"rep_{msg['trigger_msg']}"):
                        # CSV 저장
                        file_path = '학교폭력_신고대장.csv'
                        file_exists = os.path.isfile(file_path)
                        with open(file_path, 'a', encoding='utf-8-sig', newline='') as f:
                            writer = csv.writer(f)
                            if not file_exists:
                                writer.writerow(['신고시간', '가해자 이메일', '피해자 이메일', '폭력 내용'])
                            writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg['attacker'], st.session_state.user_email, msg['trigger_msg']])
                        
                        # AI 위로 상담 생성
                        try:
                            prompt = f"학생이 단톡방에서 '{msg['trigger_msg']}'라는 저격성 말을 듣고 신고 대장에 등록했어. 학생의 상처받은 마음을 공감하고 위로하는 다정한 말을 해줘."
                            response = model.generate_content(prompt)
                            reply = response.text
                        except:
                            reply = "신고가 완료되어 선생님의 보호 대장에 안전하게 기록되었습니다. 너무 걱정하지 마세요."
                            
                        msg['text'] = f"✅ **교무실 신고대장 이송 완료**\n\n🤖 **AI 상담사 피드백:**\n{reply}"
                        st.rerun()
                        
