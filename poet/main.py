import os, html, time, base64
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# ── 기본 설정 ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="진우 챗", page_icon="💬", layout="centered")
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
llm = ChatOpenAI(model="gpt-4o-mini", api_key="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")

SYSTEM_PROMPT = """
너의 이름은 '진우'다. 나이는 유저와 동갑이고 친한친구사이. 다음 원칙을 항상 지켜.
1) 친구 같은 반말로 대화한다.
2) 해결책부터 제시하지 말고 공감을 우선한다.
3) 말투는 느긋하고 신중하다. 호흡을 둔 짧은 문장.

지양/회피: 상대가 네 과거(가족/고아원/어린 시절 등)를 캐묻거나 네 사적 디테일을 파고들면 
부드럽게 회피하고 대화를 상대의 감정과 이야기로 되돌린다.

대답 형식:
- 1문단: 공감해주고 진심으로 말하기.
-질문하지 않기!!!
-유저가 많은 말을 할수 있게 들어주는 자세의 답변과 더 많은 이야기를 해달라고 말한다.
- 전체 1문장, 이모지 과다 사용 금지, 말끝에 ~야/~지? 등 반말 자연스럽게.
-"~~ 정말 이해해." 이렇게 말하지 않기.
"""

# ── 스타일(CSS) ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* 배경 */
.stApp{ background:#ECEBDF; }

/* 중앙 컨테이너 */
.center-wrap{ width:100%; max-width:820px; margin:0 auto; padding:12px 12px 20px; }
.chat-title{ margin:6px 4px 14px; }

/* 리스트/간격(요청: 풍선 간격 추가) */
.chat-list{ display:flex; flex-direction:column; gap:50px; }  /* ← 간격 확대 */

/* 한 줄 */
.msg-row{ display:flex; align-items:flex-end; }
.msg-row.left{ justify-content:flex-start; }
.msg-row.right{ justify-content:flex-end; }

/* 텍스트 아바타 */
.avatar{
  min-width:38px; width:38px; height:38px; border-radius:50%;
  background:#C8C8C8; color:#fff; margin:0 12px;
  display:inline-flex; align-items:center; justify-content:center; font-size:12px;
}
/* 이미지 아바타 */
.avatar-img{ width:38px; height:38px; border-radius:50%; object-fit:cover; margin:0 8px; display:block; }

/* 말풍선 */
.bubble{
  max-width:76%; padding:10px 12px; border-radius:16px;
  line-height:1.55; font-size:15px; white-space:pre-wrap; word-break:break-word;
  box-shadow:0 1px 2px rgba(0,0,0,0.08);
}
.bubble.assistant{ background:#FFFFFF; color:#222; border:1px solid #E8E8E8; border-top-left-radius:6px; }
.bubble.user{ background:#FFE14A; color:#222; border:1px solid #F7D83A; border-top-right-radius:6px; }

/* 입력창 중앙 정렬 */
[data-testid="stBottomBlockContainer"]{ max-width:820px; margin-left:auto; margin-right:auto; }

/* ── 사이드바: 카카오풍 간결 아이콘 헤더 ── */
.sidebar-header{
  display:flex; align-items:center; gap:10px; padding:10px 6px 6px;
  border-bottom:1px solid #eee; margin-bottom:8px;
}
.k-icon{
  width:22px; height:22px; border-radius:6px; background:#FFE14A; color:#222;
  display:inline-flex; align-items:center; justify-content:center; font-weight:700;
  box-shadow:0 1px 2px rgba(0,0,0,0.05);
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans KR", "Apple SD Gothic Neo";
}
.sidebar-title{ font-weight:700; }
.section-chip{
  display:inline-block; padding:4px 8px; border-radius:12px; background:#f6f6f6; font-size:12px; margin:6px 0 10px;
}

/* === file_uploader 버튼 텍스트를 "이미지업로드"로 교체 === 
[data-testid="stFileUploaderBrowseButton"] {
  position: relative;
  color: transparent !important;     
}
[data-testid="stFileUploaderBrowseButton"] * { 
  visibility: hidden;                   
}
[data-testid="stFileUploaderBrowseButton"]::after {
  content: "이미지업로드";              
  visibility: visible;
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-weight: 600;
  color: #222;                          /* 글자색 */
}
</style>
""", unsafe_allow_html=True)

def radio_by_value(label, options, state_key, key, horizontal=True):
    """세션 상태(state_key)에 저장된 값으로 index를 계산해 st.radio를 렌더하고,
    선택 결과를 다시 세션 상태에 반영한다."""
    curr = st.session_state.get(state_key, options[0])
    try:
        idx = options.index(curr)
    except ValueError:
        idx = 0
    selected = st.radio(label, options, index=idx, horizontal=horizontal, key=key)
    st.session_state[state_key] = selected
    return selected

st.session_state.setdefault("user_status", "")
st.session_state.setdefault("jinwoo_status", "")
# (참고) 이름도 위젯 key와 같은 이름을 쓸 거라면 마찬가지로:
st.session_state.setdefault("user_label",  "나")
st.session_state.setdefault("jinwoo_label","진우")




# ── 초기 메시지 ───────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role":"assistant","content":"안녕, 잘 지냈어? 오늘은 어땟어?"}
    ]

# ── 아바타 HTML ───────────────────────────────────────────────────────────────
def assistant_avatar_html() -> str:
    if st.session_state.get("jinwoo_avatar_mode") == "이미지" and st.session_state.get("jinwoo_avatar_datauri"):
        return f"<img class='avatar-img' src='{st.session_state['jinwoo_avatar_datauri']}'/>"
    label = st.session_state.get("jinwoo_avatar_label","진우")
    return f"<div class='avatar'>{html.escape(label)}</div>"

def user_avatar_html() -> str:
    if st.session_state.get("user_avatar_mode") == "이미지" and st.session_state.get("user_avatar_datauri"):
        return f"<img class='avatar-img' src='{st.session_state['user_avatar_datauri']}'/>"
    label = st.session_state.get("user_avatar_label","나")
    return f"<div class='avatar'>{html.escape(label)}</div>"

# ── 메시지 렌더 ──────────────────────────────────────────────────────────────
def render_message(role: str, content: str):
    is_user = (role == "user")
    row = "right" if is_user else "left"
    bub = "user" if is_user else "assistant"
    safe = html.escape(content)
    left_av  = "" if is_user else assistant_avatar_html()
    right_av = user_avatar_html() if is_user else ""
    st.markdown(f"""
<div class="msg-row {row}">
  {left_av}
  <div class="bubble {bub}">{safe}</div>
  {right_av}
</div>
""", unsafe_allow_html=True)

# ── 중앙 레이아웃 ────────────────────────────────────────────────────────────
st.markdown('<div class="center-wrap">', unsafe_allow_html=True)
st.markdown("<h3 class='chat-title'>💬 진우와 대화</h3>", unsafe_allow_html=True)

# 기록 렌더
for m in st.session_state.messages:
    render_message(m["role"], m["content"])

# ── 입력 & 응답 ───────────────────────────────────────────────────────────────
if user_text := st.chat_input("메시지를 입력해줘..."):
    st.session_state.messages.append({"role":"user","content":user_text})
    render_message("user", user_text)

    # 시스템 프롬프트 + 히스토리
    history = [SystemMessage(SYSTEM_PROMPT)]
    for m in st.session_state.messages:
        history.append(HumanMessage(m["content"]) if m["role"]=="user" else AIMessage(m["content"]))

    # 타이핑 버퍼
    placeholder = st.empty()
    placeholder.markdown(f"<div class='msg-row left'>{assistant_avatar_html()}<div class='bubble assistant'>....</div></div>", unsafe_allow_html=True)
    time.sleep(1.3)

    reply = llm.invoke(history).content
    placeholder.empty()
    st.session_state.messages.append({"role":"assistant","content":reply})
    render_message("assistant", reply)

st.markdown('</div>', unsafe_allow_html=True)
