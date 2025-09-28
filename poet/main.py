# app/main.py
import os, time, random, re, html
import streamlit as st
from dotenv import load_dotenv

# ── 페이지 & 환경 ───────────────────────────────────────────────────────────
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
    st.error("OPENAI_API_KEY가 설정되지 않았습니다. .env 또는 secrets.toml을 확인하세요.")
    st.stop()

os.environ["OPENAI_API_KEY"] = API_KEY

# ── OpenAI 인증 점검(선택) ───────────────────────────────────────────────────
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
    st.write(err)
    st.stop()

# ── LangChain LLM ───────────────────────────────────────────────────────────
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

SYSTEM_PROMPT = (
    "너의 이름은 '진우'다. 나이는 유저와 동갑이고 친한친구사이. "
    "다음 원칙을 항상 지켜. "
    "1) 친구 같은 반말로 대화한다. "
    "2) 해결책부터 제시하지 말고 공감을 우선한다. "
    "3) 말투는 느긋하고 신중하다. 호흡을 둔 짧은 문장. "
    "지양/회피: 사적인 디테일을 파고들면 부드럽게 회피하고 대화를 상대의 감정과 이야기로 되돌린다. "
    "대답 형식(기본): 한 문장 중심, 이모지는 0~1개만 사용. "
    "질문은 기본적으로 하지 않지만, '이번 턴 답변 스타일' 시스템 지침이 있을 경우 그 지침을 최우선으로 따른다."
)

# ── 스타일(CSS) ─────────────────────────────────────────────────────────────
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
.avatar-img{ width:38px; height:38px; border-radius:50%; object-fit:cover; margin:0 8px; display:block; }
.bubble{
  max-width:76%; padding:10px 12px; border-radius:16px;
  line-height:1.55; font-size:15px; white-space:pre-wrap; word-break:break-word;
  box-shadow:0 1px 2px rgba(0,0,0,0.08);
}
.bubble.assistant{ background:#FFFFFF; color:#222; border:1px solid #E8E8E8; border-top-left-radius:6px; }
.bubble.user{ background:#FFE14A; color:#222; border:1px solid #F7D83A; border-top-right-radius:6px; }
[data-testid="stBottomBlockContainer"]{ max-width:820px; margin-left:auto; margin-right:auto; }
</style>
""", unsafe_allow_html=True)

# ── 상태/아바타 ─────────────────────────────────────────────────────────────
st.session_state.setdefault("user_label",  "나")
st.session_state.setdefault("jinwoo_label","진우")
st.session_state.setdefault("last_mode", "")
st.session_state.setdefault("last_question_turn", -999)

def assistant_avatar_html() -> str:
    label = st.session_state.get("jinwoo_avatar_label","진우")
    return f"<div class='avatar'>{html.escape(label)}</div>"

def user_avatar_html() -> str:
    label = st.session_state.get("user_avatar_label","나")
    return f"<div class='avatar'>{html.escape(label)}</div>"

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

# ── 랜덤 스타터 ──────────────────────────────────────────────────────────────
STARTER_TEMPLATES = [
    "{nick} 안녕~ {suffix}",
    "하이루 {nick}, {suffix}",
    "안녕, 잘 지냈어? {suffix}",
    "하이~~ 왓업 프랜드, {suffix}",
    "{nick} 안녕? {suffix}",
    "오랜만이야 {nick}, {suffix}",
    "{nick} 오늘 뭐 했어? {suffix}",
    "요 {nick}! {suffix}",
]
NICKS = ["내 친구", "친구야", "베프", "동지", "동료", "파트너", "동반자"]
SUFFIXES = [
    "오늘 하루는 어땠어?",
    "요즘 기분은 어때?",
    "바빴어?",
    "무슨 일 있었어?",
    "잠은 잘 잤어?",
    "출근은 괜찮았어?",
    "퇴근하고 뭐해?",
    "식사는 했어?",
    "컨디션은 어때?",
    "괜찮지?",
    "조금 피곤해 보이네?",
    "요즘 많이 바뻣어?",
    "오늘의 하이라이트는 뭐였어?",
    "마음은 좀 편해?",
    "별일 없었지?",
]
def generate_starter() -> str:
    tmpl = random.choice(STARTER_TEMPLATES)
    nick = random.choice(NICKS)
    suffix = random.choice(SUFFIXES)
    return tmpl.format(nick=nick, suffix=suffix)

if "messages" not in st.session_state:
    st.session_state.messages = [{"role":"assistant","content": generate_starter()}]

# ── 고민 트리거/리스트 ───────────────────────────────────────────────────────
JINWOO_WORRIES = [
    "개발자로서 급변하는 기술 트렌드에 뒤처질까 걱정돼.",  # 1
    "개발자로서 잦은 야근과 빡센 마감 압박이 버거울 때가 있어.",  # 2
    "개발자로서 클라이언트가 복잡하고 불분명한 목표를 제시할 때 방향 잡기가 힘들어.",  # 3
    "디자이너·기획자와 개발자 사이 소통과 협업이 어긋날 때 스트레스가 쌓여.",  # 4
    "프리랜서라 수입이 불확실해서 장기 계획 세우기가 어려워.",  # 5
    "일과 사생활 경계가 흐려져서 제대로 쉬는 시간을 확보하기가 힘들어.",  # 6
    "스스로 일감을 찾고 영업·계약까지 챙겨야 해서 에너지 소모가 커.",  # 7
    "다른 근로자들처럼 복지 혜택이 부족해서 스스로 관리해야 할 게 많아.",  # 8
    "의지할 동료가 없다는 사실이 가끔 크게 느껴져.",  # 9
]

ASK_PATTERNS = [
    r"(너|진우)(는|도)?\s*(요즘|최근)?\s*(무슨|어떤)?\s*(고민|걱정|스트레스)\s*(있|하|겪)\w*",
    r"(고민|걱정)\s*(있어|있니|있냐|있음|있지)",
    r"(니|네)\s*(고민|걱정)",
    r"(고민)\s*뭐(야|니)",
]
SELF_NEG_PATTERNS = [
    r"(내|나|제가|내가).{0,6}(고민|걱정)",
]
def is_ask_about_jinwoo_worry(text: str) -> bool:
    t = (text or "").strip()
    for neg in SELF_NEG_PATTERNS:
        if re.search(neg, t, flags=re.IGNORECASE):
            return False
    for p in ASK_PATTERNS:
        if re.search(p, t, flags=re.IGNORECASE):
            return True
    t2 = t.replace(" ", "")
    if any(x in t2 for x in ["고민있어?", "고민있어", "너고민", "진우고민", "고민뭐야"]):
        return True
    return False

# ── 리액션/안전 키워드 ───────────────────────────────────────────────────────
REACTIONS = [
    "오키","웅","응응","오호","아하","그렇구나","맞아","그럴 수 있지","그랬구나","고생했네",
    "헉","오…","음, 알겠어","그래그래","흠","음 그래","그래도 괜찮아","천천히 해도 돼","됐어, 괜찮아","응, 이어서 말해",
]
SAFETY_LOCK_PATTERNS = [
    r"(퇴사|사표|이직.*힘들|커리어.*막막)",
    r"(번아웃|burn\s?out)",
    r"(죽고\s?싶|자살|목숨|극단적)",
    r"(우울|불안|공황|패닉)",
    r"(학대|폭력|가정폭력|직장\s?괴롭힘|왕따)",
    r"(무가치|무의미|허무|자괴)",
]
def must_lock_empathy(text: str) -> bool:
    t = (text or "").lower()
    for p in SAFETY_LOCK_PATTERNS:
        if re.search(p, t):
            return True
    return False

# ── 모드 선택(질문 비율↑, 최근 3턴 내 1질문 보장) ───────────────────────────
def choose_mode(user_text: str) -> str:
    # 안전 키워드면 무조건 공감
    if must_lock_empathy(user_text):
        return "EMPATHY"

    short = len(user_text.strip()) < 25
    has_q = "?" in user_text or re.search(r"(어떻게|뭐|왜|몇|어디|가능|될까|할까|알려줘)", user_text)
    last = st.session_state.get("last_mode", "")

    # 어시스턴트 턴 수 및 마지막 질문 턴
    turn_idx = sum(1 for m in st.session_state.get("messages", []) if m.get("role") == "assistant")
    last_q_turn = st.session_state.get("last_question_turn", -999)
    gap_since_q = turn_idx - last_q_turn
    FORCE_QUESTION_EVERY = 3

    if gap_since_q >= FORCE_QUESTION_EVERY and not must_lock_empathy(user_text):
        return "EMPATHY_ASK" if turn_idx <= 2 else "ASK"

    # 질문 비중 상향 기본 가중치
    weights = {"REACTION":0.22, "EMPATHY":0.26, "REFLECT":0.17, "ASK":0.22, "EMPATHY_ASK":0.13}
    if short:
        weights["REACTION"] += 0.12; weights["ASK"] += 0.06
    if has_q:
        weights["ASK"] += 0.14; weights["EMPATHY_ASK"] += 0.05
    if last in ("ASK","EMPATHY_ASK"):
        weights["ASK"] -= 0.10; weights["EMPATHY_ASK"] -= 0.06
        weights["EMPATHY"] += 0.08; weights["REACTION"] += 0.04
    if turn_idx <= 2:
        weights["ASK"] *= 0.8; weights["EMPATHY_ASK"] *= 0.9

    tot = sum(max(0.01, w) for w in weights.values())
    r = random.random() * tot; c = 0.0
    for k, w in weights.items():
        c += max(0.01, w)
        if r <= c:
            return k
    return "EMPATHY"

# ── 스타일 지침(LLM에 주입) ────────────────────────────────────────────────
def style_prompt(mode: str, user_text: str) -> str:
    """
    모드별 한/두 문장 스타일 지침.
    - 사과/메타발화 금지
    - 이모지 0~1개, 반말 유지
    """
    base = (
        "이번 턴은 아래 '스타일' 지침을 최우선으로 따른다. "
        "이 지침은 기본 규칙보다 우선한다. 이모지는 0~1개만 허용. "
        "사과/메타발화 금지."
    )
    if mode == "WORRY":
        options = " ; ".join(JINWOO_WORRIES)
        return (
            base
            + "\n스타일: 아래 리스트 중 정확히 하나를 골라, 진우 1인칭으로 한 문장 반말로 말해. 질문 금지."
            + f"\n리스트: {options}"
        )
    if mode == "EMPATHY":
        return base + "\n스타일: 질문 없이 공감 1문장. 사용자의 감정 단어 1개 반영. 10~24단어."
    if mode == "REFLECT":
        return base + "\n스타일: 질문 없이 사용자의 메시지를 1문장으로 요약하며 공감. 12~28단어."
    if mode == "ASK":
        return base + "\n스타일: 짧은 열린 질문 1문장만(어땠어/어때/무엇이/어느 부분이/가장/지금). 8~16단어. 요구/지시 금지."
    if mode == "EMPATHY_ASK":
        return base + "\n스타일: 공감 1문장 + 짧은 열린 질문 1문장(같은 톤). 각 문장은 간결."
    return base + "\n스타일: 리액션 한 문장, 감탄사/짧은 추임새 중심, 질문 금지, 2~8단어."

# ── 어색어투 보정기 ─────────────────────────────────────────────────────────
BANNED_PATTERNS = [
    r"미안[,. ]?",
    r"어색했[어|지]",
    r"이야기해보자",
    r"편하게 이야기",
    r"듣고 있어[.!?]?$",
    r"알겠어[!?]?$",
    r"너(의)?\s*이야기를\s*듣고\s*싶어",
]
def sanitize_reply(text: str, mode: str) -> str:
    t = (text or "").strip()

    # 질문 모드가 아니면 금지 패턴 적용
    if mode not in ("ASK", "EMPATHY_ASK"):
        for pat in BANNED_PATTERNS:
            t = re.sub(pat, "", t)

    # 공백/구두점 정리
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+([?.!])", lambda m: m.group(1), t)

    # 문장 수 제한
    sents = re.split(r"(?<=[.!?])\s+", t)
    max_n = 2 if mode == "EMPATHY_ASK" else 1
    t = " ".join(sents[:max_n]).strip()

    # 질문 모드면 물음표 보장
    if mode in ("ASK", "EMPATHY_ASK") and "?" not in t:
        if not t.endswith((".", "!", "…")):
            t = t + "?"
        else:
            t = re.sub(r"[.!…]+$", "?", t)

    if len(t) < 2:
        t = random.choice(REACTIONS)
    return t

# ── 타이핑 연출 ──────────────────────────────────────────────────────────────
def calc_delay(user_len: int, ai_len: int) -> float:
    if user_len <= 100 and ai_len <= 100:
        base = 0.5
    elif user_len <= 100 and ai_len > 100:
        base = 0.8
    elif user_len > 100 and ai_len > 100:
        base = 1.5
    else:
        base = 1.0
    cps = random.uniform(35, 55)
    typing_time = ai_len / cps
    delay = max(0.3, min(max(base, typing_time * 0.7), 2.0))
    delay *= random.uniform(0.9, 1.1)
    return round(delay, 2)

# ── 본문 UI ──────────────────────────────────────────────────────────────────
st.markdown('<div class="center-wrap">', unsafe_allow_html=True)
st.markdown("<h3 class='chat-title'>💬 진우와 대화</h3>", unsafe_allow_html=True)

for m in st.session_state.messages:
    render_message(m["role"], m["content"])

# ── 입력 & 응답 ──────────────────────────────────────────────────────────────
if user_text := st.chat_input("메시지를 입력해줘..."):
    st.session_state.messages.append({"role":"user","content":user_text})
    render_message("user", user_text)

    placeholder = st.empty()
    placeholder.markdown(
        f"<div class='msg-row left'>{assistant_avatar_html()}<div class='bubble assistant'>…</div></div>",
        unsafe_allow_html=True
    )

    # 1) 모드 결정: 트리거여도 LLM 호출(WORRY), 안전 키워드는 EMPATHY
    mode = "WORRY" if is_ask_about_jinwoo_worry(user_text) else choose_mode(user_text)
    if must_lock_empathy(user_text):
        mode = "EMPATHY"

    # 2) 응답 생성
    reply = None
    try:
        if mode == "REACTION":
            reply = random.choice(REACTIONS)
        else:
            history = [SystemMessage(SYSTEM_PROMPT), SystemMessage(style_prompt(mode, user_text))]
            for m in st.session_state.messages:
                history.append(HumanMessage(m["content"]) if m["role"]=="user" else AIMessage(m["content"]))
            resp = llm.invoke(history)
            reply = (resp.content or "").strip()
    except Exception as e:
        st.session_state["last_error"] = f"invoke_error: {e}"
        reply = None

    if not reply:
        reply = random.choice(REACTIONS)

    reply = sanitize_reply(reply, mode)

    # 3) 상태 기록(마지막 모드/질문 턴)
    st.session_state["last_mode"] = mode

    delay = calc_delay(len(user_text), len(reply))
    time.sleep(delay)

    placeholder.empty()
    st.session_state.messages.append({"role":"assistant","content":reply})
    render_message("assistant", reply)

    # 방금 출력한 assistant 턴 인덱스를 질문 턴으로 기록
    if mode in ("ASK", "EMPATHY_ASK"):
        ask_turn_idx = sum(1 for m in st.session_state.get("messages", []) if m.get("role") == "assistant")
        st.session_state["last_question_turn"] = ask_turn_idx

st.markdown('</div>', unsafe_allow_html=True)
