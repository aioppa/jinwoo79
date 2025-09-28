import os, time, re, random, html
import streamlit as st
from dotenv import load_dotenv

# ---- 페이지 & 환경 ----
st.set_page_config(page_title="진우 챗", page_icon="💬", layout="centered")
load_dotenv()  # .env 로컬용

def get_openai_api_key() -> str:
    # 우선순위: Streamlit secrets → 환경변수 → (이미 load_dotenv 적용)
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
    st.error("OPENAI_API_KEY가 설정되지 않았습니다. .env 또는 secrets.toml을 확인하세요.")
    st.stop()

# 환경변수로만 주입(하드코딩 금지, 인자 전달 금지)
os.environ["OPENAI_API_KEY"] = API_KEY

# ---- 최소 인증 테스트 (OpenAI 공식 클라이언트) ----
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
    st.error("인증 테스트 실패: 키/프로젝트/모델 권한을 확인하세요.")
    st.write(err)  # 원문 에러 노출로 원인 파악
    st.stop()

# ---- LangChain (키 인자 제거!) ----
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

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
-유저가 많은 이야기를 할수 있게 들어주는 자세를 유지한다.
1문장, 이모지 과다 사용 금지, 말끝에 ~야/~지? 등 반말 자연스럽게.
-"~~ 정말 이해해." 이렇게 말하지 않기.
"""

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)  # api_key 인자 제거

# 예시 호출 (개발용 버튼)
#if st.button("테스트 응답 보기"):
    resp = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content="요즘 마음이 복잡해."),
    ])
    st.write(resp.content)


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
STARTERS = [
    "안녕, 잘 지냈어? 오늘 하루는 어땟어?",
    "하이~~ 왓업 프랜드, 뭔일 있어?",
    "내 친구 안녕~ 잘 지냈어?",
    "하이루, 오늘 기분은 어때?",
    "내 친구 안녕~, 무슨일 있어?",
    "안녕하세용~ 오늘 바뻣어?",
    "아...기다리고 있었어...오늘 어때?"
]
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role":"assistant","content": random.choice(STARTERS)}
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


# ── 고민 랜덤 응답 로직 ──────────────────────────────────────────────────────
JINWOO_WORRIES = [
    "개발자로서 급변하는 기술 트렌드에 뒤처질까 걱정돼.",  # 1. 급변 트렌드
    "개발자로서 잦은 야근과 빡센 마감 압박이 버거울 때가 있어.",  # 2. 야근/마감 압박
    "개발자로서 클라이언트가 복잡하고 불분명한 목표를 제시할 때 방향 잡기가 힘들어.",  # 3. 불분명 목표
    "디자이너·기획자와 개발자 사이 소통과 협업이 어긋날 때 스트레스가 쌓여.",  # 4. 협업 문제
    "프리랜서라 수입이 불확실해서 장기 계획 세우기가 어려워.",  # 5. 수입 불확실성
    "일과 사생활 경계가 흐려져서 제대로 쉬는 시간을 확보하기가 힘들어.",  # 6. 휴식 확보 어려움
    "스스로 일감을 찾고 영업·계약까지 챙겨야 해서 에너지 소모가 커.",  # 7. 영업/계약
    "다른 근로자들처럼 복지 혜택이 부족해서 스스로 관리해야 할 게 많아.특히 4대보험이 없는게 힘들어",  # 8. 복지 부재
    "의지할 동료가 없다는 사실이 가끔 크게 느껴져.",  # 9. 의지할 동료 부재
]

ASK_PATTERNS = [
    r"(너|진우)(는|도)?\s*(요즘|최근)?\s*(무슨|어떤)?\s*(고민|걱정|스트레스)\s*(있|하|겪)\w*",
    r"(고민|걱정)\s*(있어|있니|있냐|있음|있지)",
    r"(니|네)\s*(고민|걱정)",
    r"(고민)\s*뭐(야|니)",
]
SELF_NEG_PATTERNS = [
    r"(내|나|제가|내가).{0,6}(고민|걱정)",  # 사용자가 자신의 고민을 말하는 경우는 제외
]

def is_ask_about_jinwoo_worry(text: str) -> bool:
    t = (text or "").strip()
    for neg in SELF_NEG_PATTERNS:
        if re.search(neg, t, flags=re.IGNORECASE):
            return False
    for p in ASK_PATTERNS:
        if re.search(p, t, flags=re.IGNORECASE):
            return True
    # 공백 제거 형태 간단 체크
    t2 = t.replace(" ", "")
    if any(x in t2 for x in ["고민있어?", "고민있어", "너고민", "진우고민", "고민뭐야"]):
        return True
    return False


# ── 입력 & 응답 ───────────────────────────────────────────────────────────────

def calc_delay(user_len: int, ai_len: int) -> float:
    # 4가지 규칙 기반 베이스
    if user_len <= 100 and ai_len <= 100:
        base = 0.5
    elif user_len <= 100 and ai_len > 100:
        base = 0.8
    elif user_len > 100 and ai_len > 100:
        base = 1.5
    else:  # user>100, ai<=100
        base = 1.0

    # 타자속도 보정(문자/초)
    cps = random.uniform(35, 55)
    typing_time = ai_len / cps

    # 스무딩(0.3s~2.0s) + 약간의 지터
    delay = max(0.3, min(max(base, typing_time * 0.7), 2.0))
    delay *= random.uniform(0.9, 1.1)
    return round(delay, 2)


if user_text := st.chat_input("메시지를 입력해줘..."):
    st.session_state.messages.append({"role":"user","content":user_text})
    render_message("user", user_text)

    # 시스템 프롬프트 + 히스토리
    history = [SystemMessage(SYSTEM_PROMPT)]
    for m in st.session_state.messages:
        history.append(HumanMessage(m["content"]) if m["role"]=="user" else AIMessage(m["content"]))

    # 자리표시자 즉시 출력(호출 전 sleep 금지)
    placeholder = st.empty()
    placeholder.markdown(
        f"<div class='msg-row left'>{assistant_avatar_html()}<div class='bubble assistant'>…</div></div>",
        unsafe_allow_html=True
    )

    # 트리거 문구면 LLM을 호출하지 않고 랜덤 고민으로 응답
    if is_ask_about_jinwoo_worry(user_text):
        reply = random.choice(JINWOO_WORRIES)
    else:
        # 모델 즉시 호출
        reply = llm.invoke(history).content

    # 응답 길이 기반 연출 지연
    delay = calc_delay(len(user_text), len(reply))
    time.sleep(delay)

    # 결과 렌더
    placeholder.empty()
    st.session_state.messages.append({"role":"assistant","content":reply})
    render_message("assistant", reply)

st.markdown('</div>', unsafe_allow_html=True)
