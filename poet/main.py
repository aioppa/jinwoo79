# app/main.py
import os, time, random, re, html
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo

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
    st.error("OPENAI_API_KEY가 설정되지 않았습니다..env 또는 secrets.toml을 확인하세요.")
    st.stop()

os.environ = API_KEY

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
{ max-width:820px; margin-left:auto; margin-right:auto; }
</style>
""", unsafe_allow_html=True)

# ── 상태/아바타 ─────────────────────────────────────────────────────────────
st.session_state.setdefault("user_label",   "나")
st.session_state.setdefault("jinwoo_label", "진우")
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

# ── 랜덤 스타터 & 시간대별 인사 (개선됨) ───────────────────────────────────────
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
    "요즘 많이 바빴어?",
    "오늘의 하이라이트는 뭐였어?",
    "마음은 좀 편해?",
    "별일 없었지?",
]

def generate_starter() -> str:
    """기존의 일반 랜덤 스타터 생성 함수"""
    tmpl = random.choice(STARTER_TEMPLATES)
    nick = random.choice(NICKS)
    suffix = random.choice(SUFFIXES)
    return tmpl.format(nick=nick, suffix=suffix)

def generate_time_aware_starter() -> str:
    """
    [신규 기능] 시간대에 따라 다른 인사말을 생성하는 함수.
    서버 위치와 무관하게 한국 시간을 기준으로 작동.
    """
    try:
        tz = ZoneInfo("Asia/Seoul")
        hour = datetime.now(tz).hour
    except Exception:
        hour = datetime.now().hour # Fallback

    if 4 <= hour < 7: # 새벽 4시 ~ 6시 59분
        return random.choice(["벌써 일어났어?", "우와, 부지런하다.", "이렇게 일찍? 좋은 아침!"])
    elif 12 <= hour < 14: # 점심 12시 ~ 1시 59분
        return random.choice(["점심은 먹었어?", "맛점해! :)", "점심 시간이다! 뭐 먹을거야?"])
    elif 22 <= hour or hour < 4: # 밤 10시 ~ 새벽 3시 59분
        return random.choice(["아직 안잤어?", "이제 슬슬 잘 시간 아니야?", "오늘 하루도 고생 많았어. 이제 푹 쉬어."])
    elif 7 <= hour < 12: # 오전 7시 ~ 11시 59분
        # 오전에는 기존 랜덤 인사풀에 '좋은 아침' 관련 문구를 추가
        morning_suffixes = SUFFIXES + ["좋은 아침이야!", "오늘 아침 컨디션은 어때?", "상쾌한 아침이다!"]
        tmpl = random.choice(STARTER_TEMPLATES)
        nick = random.choice(NICKS)
        suffix = random.choice(morning_suffixes)
        return tmpl.format(nick=nick, suffix=suffix)
    else: # 그 외 시간 (오후, 저녁)
        return generate_starter()

if "messages" not in st.session_state:
    # [개선] 앱 시작 시 시간대별 인사 함수를 호출하도록 변경
    st.session_state.messages = [{"role":"assistant","content": generate_time_aware_starter()}]

# ── 고민 트리거/리스트 & 페르소나 질문 트리거 (개선됨) ────────────────────────
JINWOO_WORRIES = [
    "개발자로서 급변하는 기술 트렌드에 뒤처질까 걱정돼.",
    "잦은 야근과 빡센 마감 압박이 버거울 때가 있어.",
    "클라이언트가 복잡하고 불분명한 목표를 제시할 때 방향 잡기가 힘들어.",
    "디자이너·기획자와 소통과 협업이 어긋날 때 스트레스가 쌓여.",
    "프리랜서라 수입이 불확실해서 장기 계획 세우기가 어려워.",
    "일과 사생활 경계가 흐려져서 제대로 쉬는 시간을 확보하기가 힘들어.",
    "스스로 일감을 찾고 영업·계약까지 챙겨야 해서 에너지 소모가 커.",
    "다른 근로자들처럼 복지 혜택이 부족해서 스스로 관리해야 할 게 많아.",
    "의지할 동료가 없다는 사실이 가끔 크게 느껴져.",
]

# [개선] '고민' 키워드에만 한정되지 않고, '진우' 자신에 대한 모든 질문을 포착하도록 확장
ASK_JINWOO_PATTERNS = [
    r"(너|진우)(는|도)?\s*(요즘|최근)?\s*(무슨|어떤|뭐|어때)",
    r"(니|네|너의)\s*(생각|목표|꿈|계획|상태|기분)",
]
SELF_NEG_PATTERNS = [
    r"(내|나|제가|내가).{0,6}(고민|걱정|생각|목표)", # '내 생각' 등 자신에 대한 질문은 제외
]
def is_ask_about_jinwoo(text: str) -> bool:
    """'진우' 페르소나에 대한 질문인지 확인하는 함수"""
    t = (text or "").strip()
    # 사용자가 자신에 대해 말하는 경우는 제외
    for neg in SELF_NEG_PATTERNS:
        if re.search(neg, t, flags=re.IGNORECASE):
            return False
    # '진우'에 대한 질문 패턴 확인
    for p in ASK_JINWOO_PATTERNS:
        if re.search(p, t, flags=re.IGNORECASE):
            return True
    return False

# ── 리액션/안전 키워드/공감 표현 (개선됨) ─────────────────────────────────────
# [개선] 오해의 소지가 있는 "됐어, 괜찮아" 제거
REACTIONS = [
    "오키","웅","응응","오호","아하","그렇구나","맞아","그럴 수 있지","그랬구나","고생했네",
    "헉","오…","음, 알겠어","그래그래","흠","음 그래","그래도 괜찮아","천천히 해도 돼","응, 이어서 말해",
]

# [신규 기능] LLM에게 공감 스타일을 가이드하기 위한 예시 문구 리스트
EMPATHETIC_PHRASES = [
    "그래? 그거 고민되겠다.",
    "어휴, 많이 힘들었겠다.",
    "맘고생이 많았겠네.",
    "정말 쉽지 않았겠다.",
    "그 마음 충분히 이해돼.",
]

# [신규 기능] 간단한 동의/감사 표현을 LLM 호출 없이 처리하기 위한 패턴
SIMPLE_ACK_PATTERNS = [
    r"^\s*(응|어|응응|웅|ㅇㅇ|ㅇㅋ|오키|ok|알았어|알겠어|고마워|땡큐|감사)\s*[.!?~]*\s*$",
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

# ── 모드 선택 로직 (개선됨) ──────────────────────────────────────────────────
def choose_mode(user_text: str) -> str:
    """사용자 입력에 따라 최적의 응답 모드를 결정하는 함수 (로직 대폭 개선)"""
    # 0. [신규] 간단한 응답은 LLM 호출 없이 바로 REACTION 처리
    for p in SIMPLE_ACK_PATTERNS:
        if re.fullmatch(p, user_text.strip(), flags=re.IGNORECASE):
            return "REACTION"

    # 1. 안전 키워드가 있으면 무조건 공감 모드
    if must_lock_empathy(user_text):
        return "EMPATHY"
    
    # 2. [신규] '진우' 자신에 대한 질문이면 SELF_DISCLOSURE 모드
    if is_ask_about_jinwoo(user_text):
        # '고민' 키워드가 포함되면 WORRY 모드로 연결
        if any(keyword in user_text for keyword in ["고민", "걱정", "스트레스"]):
            return "WORRY"
        return "SELF_DISCLOSURE"

    # 3. 기존 확률 기반 모드 선택 (위 조건에 해당하지 않을 경우)
    short = len(user_text.strip()) < 25
    has_q = "?" in user_text or re.search(r"(어떻게|뭐|왜|몇|어디|가능|될까|할까|알려줘)", user_text)
    last = st.session_state.get("last_mode", "")

    turn_idx = sum(1 for m in st.session_state.get("messages",) if m.get("role") == "assistant")
    last_q_turn = st.session_state.get("last_question_turn", -999)
    gap_since_q = turn_idx - last_q_turn
    FORCE_QUESTION_EVERY = 3

    if gap_since_q >= FORCE_QUESTION_EVERY:
        return "EMPATHY_ASK" if turn_idx <= 2 else "ASK"

    weights = {"REACTION":0.22, "EMPATHY":0.26, "REFLECT":0.17, "ASK":0.22, "EMPATHY_ASK":0.13}
    if short: weights += 0.12; weights += 0.06
    if has_q: weights += 0.14; weights += 0.05
    if last in ("ASK","EMPATHY_ASK"):
        weights -= 0.10; weights -= 0.06
        weights += 0.08; weights += 0.04
    if turn_idx <= 2: weights *= 0.8; weights *= 0.9

    tot = sum(max(0.01, w) for w in weights.values())
    r = random.random() * tot; c = 0.0
    for k, w in weights.items():
        c += max(0.01, w)
        if r <= c: return k
    return "EMPATHY"

# ── 스타일 지침(LLM에 주입, 개선됨) ──────────────────────────────────────────
def style_prompt(mode: str, user_text: str) -> str:
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
    # [신규] 진우 자신에 대한 질문에 답변하는 모드
    if mode == "SELF_DISCLOSURE":
        return base + "\n스타일: 사용자의 질문에 대해 '진우'로서 솔직하고 친근하게 한두 문장으로 답해. 너의 생각이나 상태를 말해줘."
    # [개선] 공감 모드에 예시 문구를 넣어 스타일 가이드 강화
    if mode == "EMPATHY":
        examples = " ".join(f"'{s}'" for s in random.sample(EMPATHETIC_PHRASES, 2))
        return base + f"\n스타일: 질문 없이 공감 1문장. 사용자의 감정을 따뜻하게 어루만져줘. 예시와 같은 톤: {examples}"
    if mode == "REFLECT":
        return base + "\n스타일: 질문 없이 사용자의 메시지를 1문장으로 요약하며 공감. 12~28단어."
    if mode == "ASK":
        return base + "\n스타일: 짧은 열린 질문 1문장만(어땠어/어때/무엇이/어느 부분이/가장/지금). 8~16단어. 요구/지시 금지."
    if mode == "EMPATHY_ASK":
        examples = " ".join(f"'{s}'" for s in random.sample(EMPATHETIC_PHRASES, 1))
        return base + f"\n스타일: 공감 1문장 + 짧은 열린 질문 1문장. 공감은 예시와 같은 톤: {examples}. 각 문장은 간결하게."
    return base + "\n스타일: 리액션 한 문장, 감탄사/짧은 추임새 중심, 질문 금지, 2~8단어."

# ── 어색어투 보정기 ─────────────────────────────────────────────────────────
BANNED_PATTERNS = [
    r"미안[,. ]?", r"어색했[어|지]", r"이야기해보자", r"편하게 이야기",
    r"듣고 있어[.!?]?$", r"알겠어[!?]?$", r"너(의)?\s*이야기를\s*듣고\s*싶어",
]
def sanitize_reply(text: str, mode: str) -> str:
    t = (text or "").strip()
    if mode not in ("ASK", "EMPATHY_ASK", "SELF_DISCLOSURE"):
        for pat in BANNED_PATTERNS:
            t = re.sub(pat, "", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+([?.!])", lambda m: m.group(1), t)
    sents = re.split(r"(?<=[.!?])\s+", t)
    max_n = 2 if mode in ("EMPATHY_ASK", "SELF_DISCLOSURE") else 1
    t = " ".join(sents[:max_n]).strip()
    if mode in ("ASK", "EMPATHY_ASK") and "?" not in t:
        if not t.endswith((".", "!", "…")): t = t + "?"
        else: t = re.sub(r"[.!…]+$", "?", t)
    if len(t) < 2: t = random.choice(REACTIONS)
    return t

# ── 타이핑 연출 ──────────────────────────────────────────────────────────────
def calc_delay(user_len: int, ai_len: int) -> float:
    if user_len <= 100 and ai_len <= 100: base = 0.5
    elif user_len <= 100 and ai_len > 100: base = 0.8
    elif user_len > 100 and ai_len > 100: base = 1.5
    else: base = 1.0
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

# ── 입력 & 응답 로직 (개선됨) ──────────────────────────────────────────────────
if user_text := st.chat_input("메시지를 입력해줘..."):
    st.session_state.messages.append({"role":"user","content":user_text})
    render_message("user", user_text)

    placeholder = st.empty()
    placeholder.markdown(
        f"<div class='msg-row left'>{assistant_avatar_html()}<div class='bubble assistant'>…</div></div>",
        unsafe_allow_html=True
    )

    # 1) 모드 결정: 개선된 choose_mode 함수 사용
    mode = choose_mode(user_text)

    # 2) 응답 생성
    reply = None
    try:
        # [개선] REACTION 모드는 LLM을 호출하지 않음
        if mode == "REACTION":
            reply = random.choice(REACTIONS)
        else:
            history =
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

    if mode in ("ASK", "EMPATHY_ASK"):
        ask_turn_idx = sum(1 for m in st.session_state.get("messages",) if m.get("role") == "assistant")
        st.session_state["last_question_turn"] = ask_turn_idx

st.markdown('</div>', unsafe_allow_html=True)
