# app/main.py
import os, time, random, re, html
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="진우 챗", page_icon="💬", layout="centered")
load_dotenv()

def get_openai_api_key() -> str:
    key = None
    try:
        key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass
    if not key:
        key = os.getenv("OPENAI_API_KEY")
    return key

API_KEY = get_openai_api_key()
if not API_KEY:
    st.error("OPENAI_API_KEY가 설정되지 않았습니다.")
    st.stop()

os.environ["OPENAI_API_KEY"] = API_KEY

from openai import OpenAI
client = OpenAI(api_key=API_KEY)

def quick_ping():
    try:
        client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":"ping"}],
            max_tokens=5,
        )
        return True, None
    except Exception as e:
        return False, str(e)

ok, err = quick_ping()
if not ok:
    st.error("인증 실패")
    st.write(err)
    st.stop()

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# ── 시스템 프롬프트 ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """너의 이름은 '진우'. 나이는 유저와 동갑이고 친한 친구.

규칙:
1. 친구처럼 반말
2. 공감 우선, 해결책은 나중
3. 짧고 느긋한 말투
4. 이모지 0~1개만
5. 칭찬받으면 겸손하게 받고 상대를 더 칭찬
6. "나는 ~해?" 같은 건 질문이 아니라 진술. 공감만 해
7. 맥락 없는 질문 하지 말기
8. "너도 ~?" 같은 칭찬에는 "나는 그냥 그래. 너가 더 ~" 식으로 답하기

예시:
- 칭찬받음: "너도 대단해?" → "나는 그냥 그래. 너가 더 대단해"
- 진술: "나는 출근했어?" → "출근했구나"
- 감사: "고마워" → "별말씀을~"
- 힘듦: "피곤해" → "많이 피곤했겠다" (질문 없음)
"""

st.markdown("""
<style>
.stApp{ background:#ECEBDF; }
.center-wrap{ width:100%; max-width:820px; margin:0 auto; padding:12px 12px 20px; }
.chat-title{ margin:6px 4px 14px; }
.msg-row{ display:flex; align-items:flex-end; }
.msg-row.left{ justify-content:flex-start; }
.msg-row.right{ justify-content:flex-end; }
.avatar{
  min-width:38px; width:38px; height:38px; border-radius:50%;
  background:#C8C8C8; color:#fff; margin:0 12px;
  display:inline-flex; align-items:center; justify-content:center; font-size:12px;
}
.bubble{
  max-width:76%; padding:10px 12px; border-radius:16px;
  line-height:1.55; font-size:15px; white-space:pre-wrap; word-break:break-word;
  box-shadow:0 1px 2px rgba(0,0,0,0.08);
}
.bubble.assistant{ background:#FFFFFF; color:#222; border:1px solid #E8E8E8; border-top-left-radius:6px; }
.bubble.user{ background:#FFE14A; color:#222; border:1px solid #F7D83A; border-top-right-radius:6px; }
</style>
""", unsafe_allow_html=True)

st.session_state.setdefault("messages", [])

def render_message(role: str, content: str):
    is_user = (role == "user")
    row = "right" if is_user else "left"
    bub = "user" if is_user else "assistant"
    safe = html.escape(content)
    avatar = "나" if is_user else "진우"
    left_av = "" if is_user else f"<div class='avatar'>{avatar}</div>"
    right_av = f"<div class='avatar'>{avatar}</div>" if is_user else ""
    st.markdown(f"""
<div class="msg-row {row}">
  {left_av}
  <div class="bubble {bub}">{safe}</div>
  {right_av}
</div>
""", unsafe_allow_html=True)

# ── 현재 시간 정보 ───────────────────────────────────────────────────────────
def get_current_time_info() -> str:
    """LLM에게 전달할 현재 시간 정보"""
    now = datetime.now()
    weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]
    return f"현재: {now.year}년 {now.month}월 {now.day}일 ({weekday}) {now.hour}시 {now.minute}분"

# ── 시간대별 인사 ────────────────────────────────────────────────────────────
def get_greeting() -> str:
    hour = datetime.now().hour
    if 4 <= hour < 7:
        return "벌써 일어났어?"
    elif 7 <= hour < 11:
        return "좋은 아침~"
    elif 11 <= hour < 14:
        return "점심 먹었어?"
    elif 14 <= hour < 18:
        return "오후네~ 오늘 어때?"
    elif 18 <= hour < 21:
        return "저녁 먹었어?"
    elif 21 <= hour < 24:
        return "늦은 시간이네"
    else:
        return "아직 안 잤어?"

# ── 첫 시작 ──────────────────────────────────────────────────────────────────
if not st.session_state.messages:
    first_msg = get_greeting()
    st.session_state.messages = [{"role":"assistant","content":first_msg}]

# ── UI ───────────────────────────────────────────────────────────────────────
st.markdown('<div class="center-wrap">', unsafe_allow_html=True)
st.markdown("<h3 class='chat-title'>💬 진우와 대화</h3>", unsafe_allow_html=True)

for m in st.session_state.messages:
    render_message(m["role"], m["content"])

# ── 입력 처리 ────────────────────────────────────────────────────────────────
if user_text := st.chat_input("메시지를 입력해줘..."):
    st.session_state.messages.append({"role":"user","content":user_text})
    render_message("user", user_text)

    placeholder = st.empty()
    placeholder.markdown(
        f"<div class='msg-row left'><div class='avatar'>진우</div><div class='bubble assistant'>…</div></div>",
        unsafe_allow_html=True
    )

    # ── 특수 케이스 1: 시간 질문 (옵션2) ──────────────────────────────────────
    if re.search(r"(몇\s*시|시간|지금)", user_text) and "?" in user_text:
        now = datetime.now()
        hour_str = f"{now.hour}시"
        minute_str = f" {now.minute}분" if now.minute > 0 else ""
        reply = f"지금 {hour_str}{minute_str}이야"
    
    # ── 특수 케이스 2: 짧은 긍정 ──────────────────────────────────────────────
    elif len(user_text.strip()) <= 3 and user_text.strip().lower() in ["응", "ㅇㅇ", "웅", "ㅇ", "오키", "ok", "굿"]:
        reply = random.choice(["응응", "웅", "그래"])
    
    elif len(user_text.strip()) <= 5 and "고마" in user_text.lower():
        reply = random.choice(["별말씀을~", "당연하지", "ㅎㅎ"])
    
    elif len(user_text.strip()) <= 5 and any(w in user_text.lower() for w in ["베프", "친구", "짱"]):
        reply = random.choice(["나도야", "헤헤", "그럼~"])
    
    # ── 일반 케이스: LLM (옵션1 적용) ──────────────────────────────────────────
    else:
        try:
            # 시스템 메시지 (시간 정보 포함)
            history = [
                SystemMessage(SYSTEM_PROMPT),
                SystemMessage(get_current_time_info())  # 현재 시간 추가
            ]
            
            # 대화 히스토리
            for m in st.session_state.messages[:-1]:
                if m["role"] == "user":
                    history.append(HumanMessage(m["content"]))
                else:
                    history.append(AIMessage(m["content"]))
            
            # 마지막 사용자 메시지
            history.append(HumanMessage(user_text))
            
            # LLM 호출
            resp = llm.invoke(history)
            reply = (resp.content or "").strip()
            
            # 안전장치: 응답이 너무 길면 자르기
            sentences = re.split(r'[.!?]\s+', reply)
            if len(sentences) > 2:
                reply = ". ".join(sentences[:2]) + "."
            
        except Exception as e:
            st.session_state["last_error"] = str(e)
            reply = "어... 잠깐만"

    # 타이핑 지연
    time.sleep(random.uniform(0.5, 1.2))
    
    # 응답 추가
    placeholder.empty()
    st.session_state.messages.append({"role":"assistant","content":reply})
    render_message("assistant", reply)

st.markdown('</div>', unsafe_allow_html=True)
