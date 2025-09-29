# app/main.py
import os, time, random, re, html
from datetime import datetime
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

# ── OpenAI 인증 점검 ─────────────────────────────────────────────────────────
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
    "4) 맥락에 맞지 않는 질문은 절대 하지 않는다. 자연스럽지 않으면 공감만 한다. "
    "5) 사용자가 '나는 ~해?'라고 물으면, 이건 자기 진술이다. 질문이 아니다. 공감만 해라. "
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

# ── 시간대별 인사 ────────────────────────────────────────────────────────────
def get_time_based_greeting() -> str:
    now = datetime.now()
    hour = now.hour
    
    if 4 <= hour < 7:
        greetings = ["벌써 일어났어?", "일찍 일어났네", "새벽부터 뭐해?"]
    elif 7 <= hour < 11:
        greetings = ["좋은 아침~ 잘 잤어?", "아침이다!", "좋은 아침이야"]
    elif 11 <= hour < 14:
        greetings = ["점심 먹었어?", "점심때네", "점심 시간이야"]
    elif 14 <= hour < 18:
        greetings = ["오후네~", "오후 시간이다", "오후에 뭐해?"]
    elif 18 <= hour < 21:
        greetings = ["저녁 먹었어?", "저녁 시간이네", "저녁은?"]
    elif 21 <= hour < 24:
        greetings = ["아직 안 잤어?", "늦은 시간이네", "밤에 뭐해?"]
    else:
        greetings = ["아직도 안 잤어?", "심야네", "무슨 일 있어?"]
    
    return random.choice(greetings)

# ── 랜덤 스타터 ──────────────────────────────────────────────────────────────
STARTER_TEMPLATES = [
    "안녕~ {suffix}", "하이루, {suffix}", "안녕, 잘 지냈어?",
    "하이~~ 왓업", "오늘 뭐 했어?", "요즘 어때?",
]
SUFFIXES = ["오늘 어땠어?", "요즘 기분은?", "바빴어?", "컨디션은 어때?"]

def generate_starter() -> str:
    if random.random() < 0.5:
        return get_time_based_greeting()
    else:
        tmpl = random.choice(STARTER_TEMPLATES)
        return tmpl.format(suffix=random.choice(SUFFIXES)) if "{suffix}" in tmpl else tmpl

if "messages" not in st.session_state:
    st.session_state.messages = [{"role":"assistant","content": generate_starter()}]

# ── 고민 트리거 ──────────────────────────────────────────────────────────────
JINWOO_WORRIES = [
    "개발자로서 급변하는 기술 트렌드에 뒤처질까 걱정돼.",
    "잦은 야근과 빡센 마감 압박이 버거울 때가 있어.",
    "클라이언트가 복잡하고 불분명한 목표를 제시할 때 방향 잡기가 힘들어.",
    "디자이너·기획자와 소통과 협업이 어긋날 때 스트레스가 쌓여.",
    "프리랜서라 수입이 불확실해서 장기 계획 세우기가 어려워.",
    "일과 사생활 경계가 흐려져서 제대로 쉬는 시간을 확보하기가 힘들어.",
    "스스로 일감을 찾고 영업·계약까지 챙겨야 해서 에너지 소모가 커.",
    "의지할 동료가 없다는 사실이 가끔 크게 느껴져.",
]

def is_ask_about_jinwoo_worry(text: str) -> bool:
    t = (text or "").strip()
    if re.search(r"(내|나|제가|내가).{0,6}(고민|걱정)", t):
        return False
    patterns = [
        r"(너|진우).*(고민|걱정)",
        r"(고민|걱정)\s*(있어|있니)",
    ]
    for p in patterns:
        if re.search(p, t, flags=re.IGNORECASE):
            return True
    return False

# ── 자기 진술 감지 (핵심 개선) ──────────────────────────────────────────────
def is_self_statement(text: str) -> bool:
    """
    '나는 ~해?' 형태는 질문이 아니라 자기 진술
    """
    t = text.strip()
    
    # "나는 ~해?" 패턴 = 자기 진술
    SELF_STATEMENT_PATTERNS = [
        r"^(나|내가|저는|제가).+\?$",
        r"^나는.+(했|됐|였|갔|있|없|일|쉬|집|회사).+\?$",
    ]
    
    for pat in SELF_STATEMENT_PATTERNS:
        if re.search(pat, t):
            return True
    
    return False

# ── 진짜 질문 감지 (개선) ───────────────────────────────────────────────────
def is_real_question(text: str) -> bool:
    """
    진짜 질문인지 확인 (상대방에게 묻는 것)
    """
    if is_self_statement(text):
        return False
    
    t = text.strip()
    
    # 진짜 질문 패턴
    REAL_QUESTION_PATTERNS = [
        r"(너|진우|넌).+\?",
        r"(어떻게|왜|뭐|어디|몇|언제).+\?",
        r".+(할까|좋을까|어때|괜찮|추천)\?",
    ]
    
    for pat in REAL_QUESTION_PATTERNS:
        if re.search(pat, t):
            return True
    
    return False

# ── 짧은 긍정 응답 감지 ─────────────────────────────────────────────────────
def is_short_positive_reaction(text: str) -> bool:
    t = re.sub(r"[!.?~\s]+", "", (text or "").strip().lower())
    if len(t) <= 1:
        return True
    patterns = [
        r"^(응|ㅇㅇ|웅|오키|ok|알겠|알았)$",
        r"^(고마워|감사|땡큐|thx|ㄱㅅ)$",
        r"^(베프|친구|짱|최고|사랑|love)$",
        r"^(ㅋㅋ|ㅎㅎ|ㄱㄱ|ㅇㅋ)$",
    ]
    return any(re.search(p, t, flags=re.IGNORECASE) for p in patterns)

# ── 감사/애정 표현 응답 ──────────────────────────────────────────────────────
THANKS_RESPONSES = ["별말씀을~", "당연하지", "ㅎㅎ 뭘", "그럼~", "언제든지"]
AFFECTION_RESPONSES = ["나도야", "헤헤", "ㅎㅎ 고마워", "그럼 우리 베프지", "당연하지"]

# ── 안전 키워드 ──────────────────────────────────────────────────────────────
def must_lock_empathy(text: str) -> bool:
    patterns = [
        r"(퇴사|사표|번아웃)",
        r"(죽고\s?싶|자살|극단적)",
        r"(우울|불안|공황)",
        r"(학대|폭력|괴롭힘|왕따)",
    ]
    return any(re.search(p, (text or "").lower()) for p in patterns)

# ── 공감 표현 ────────────────────────────────────────────────────────────────
EMPATHY_EXPRESSIONS = [
    "그래? 그거 고민되겠다",
    "어휴, 많이 힘들었겠다",
    "맘고생이 많았겠네",
    "그랬구나",
    "많이 속상했겠다",
]

# ── 자연스러운 질문 타이밍 (대폭 개선) ─────────────────────────────────────
def should_ask_question(user_text: str, recent_messages: list) -> bool:
    """
    질문하기 좋은 자연스러운 타이밍인지 판단
    """
    t = user_text.strip()
    
    # 1. 자기 진술이면 절대 질문 안 함
    if is_self_statement(t):
        return False
    
    # 2. 너무 짧으면 질문 안 함
    if len(t) <= 10:
        return False
    
    # 3. 너무 길면 질문 안 함 (이미 충분히 설명함)
    if len(t) > 50:
        return False
    
    # 4. 힘든 감정이면 공감만
    if re.search(r"(힘들|피곤|지쳐|우울|불안|스트레스|짜증|화나|속상)", t):
        return False
    
    # 5. 최근 1턴 내에 질문했으면 안 함
    if len(recent_messages) >= 1:
        last_msg = recent_messages[-1]
        if last_msg.get("role") == "assistant" and "?" in last_msg.get("content", ""):
            return False
    
    # 6. 새로운 활동/이벤트를 짧게 언급 (질문 타이밍)
    if len(t) < 35:
        good_patterns = [
            r"(회의|미팅).+(있었|했|다녀)",
            r"(친구|동료).+(만났|봤)",
            r"(영화|책|게임).+(봤|읽|했)",
            r"(내일|다음).+(있어|할)",
        ]
        for pat in good_patterns:
            if re.search(pat, t):
                return True
    
    return False

# ── 모드 선택 (완전 개선) ───────────────────────────────────────────────────
def choose_mode(user_text: str) -> str:
    if is_short_positive_reaction(user_text):
        return "SIMPLE_ACK"
    
    if must_lock_empathy(user_text):
        return "EMPATHY"
    
    # 자기 진술이면 무조건 공감만
    if is_self_statement(user_text):
        return "EMPATHY" if len(user_text) > 15 else "SHORT_EMPATHY"
    
    recent_messages = st.session_state.get("messages", [])
    
    # 질문 타이밍 판단
    if should_ask_question(user_text, recent_messages):
        # 질문 가능
        weights = {
            "SHORT_EMPATHY": 0.10,
            "EMPATHY": 0.25,
            "REFLECT": 0.15,
            "ASK": 0.35,
            "EMPATHY_ASK": 0.15
        }
    else:
        # 공감 중심
        weights = {
            "SHORT_EMPATHY": 0.25,
            "EMPATHY": 0.45,
            "REFLECT": 0.30,
            "ASK": 0.0,
            "EMPATHY_ASK": 0.0
        }
    
    # 사용자가 진짜 질문하면 답변 모드
    if is_real_question(user_text):
        weights["EMPATHY"] = 0.7
        weights["SHORT_EMPATHY"] = 0.2
        weights["ASK"] = 0.0
        weights["EMPATHY_ASK"] = 0.0
        weights["REFLECT"] = 0.1
    
    tot = sum(max(0.01, w) for w in weights.values())
    r = random.random() * tot
    c = 0.0
    for k, w in weights.items():
        c += max(0.01, w)
        if r <= c:
            return k
    return "EMPATHY"

# ── 스타일 지침 ──────────────────────────────────────────────────────────────
def style_prompt(mode: str, user_text: str) -> str:
    base = (
        "이번 턴은 아래 '스타일' 지침을 최우선으로 따른다. "
        "이모지는 0~1개만. 사과/메타발화 금지. 맥락 고려."
    )
    
    if mode == "WORRY":
        options = " ; ".join(JINWOO_WORRIES)
        return base + f"\n스타일: 아래 중 하나를 골라 진우 1인칭 한 문장 반말. 질문 금지.\n리스트: {options}"
    
    if mode == "SIMPLE_ACK":
        return base + "\n스타일: 짧은 긍정 리액션 1개. 질문 절대 금지. 2~5단어."
    
    if mode == "SHORT_EMPATHY":
        return base + "\n스타일: 짧은 공감 1문장. 질문 없음. 5~12단어."
    
    if mode == "EMPATHY":
        return base + "\n스타일: 공감 1~2문장. 질문 절대 금지. 10~24단어."
    
    if mode == "REFLECT":
        return base + "\n스타일: 사용자 메시지 요약하며 공감 1문장. 질문 금지. 12~28단어."
    
    if mode == "ASK":
        return base + "\n스타일: 짧은 열린 질문 1문장. '어땠어?', '어때?', '어떤?' 같은 자연스러운 질문만. 8~16단어."
    
    if mode == "EMPATHY_ASK":
        return base + "\n스타일: 공감 1문장 + 짧은 질문 1문장."
    
    return base + "\n스타일: 자연스럽게 짧게 1문장."

# ── 어색어투 보정기 ──────────────────────────────────────────────────────────
def sanitize_reply(text: str, mode: str) -> str:
    t = (text or "").strip()
    
    # 금지 패턴
    banned = [r"미안", r"이야기해보자", r"편하게", r"듣고 있어", r"친구니까\?", r"미워하지\s*않아"]
    for pat in banned:
        t = re.sub(pat, "", t)
    
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = re.sub(r"\s+([?.!])", lambda m: m.group(1), t)
    
    # 문장 수 제한
    sents = re.split(r"(?<=[.!?])\s+", t)
    max_n = 2 if mode == "EMPATHY_ASK" else 1
    t = " ".join(sents[:max_n]).strip()
    
    # 질문 모드면 물음표 보장
    if mode in ("ASK", "EMPATHY_ASK") and len(t) > 3:
        if "?" not in t:
            t = t.rstrip(".!…") + "?"
    
    # 너무 짧으면 대체
    if len(t) < 2:
        if mode == "SIMPLE_ACK":
            t = random.choice(THANKS_RESPONSES)
        else:
            t = random.choice(EMPATHY_EXPRESSIONS)
    
    return t

# ── 타이핑 연출 ──────────────────────────────────────────────────────────────
def calc_delay(user_len: int, ai_len: int) -> float:
    if user_len <= 100 and ai_len <= 100:
        base = 0.5
    elif user_len <= 100 and ai_len > 100:
        base = 0.8
    else:
        base = 1.0
    delay = max(0.3, min(base, 2.0)) * random.uniform(0.9, 1.1)
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

    # 짧은 긍정 응답 처리
    if is_short_positive_reaction(user_text):
        if re.search(r"(고마워|감사|땡큐|thanks|thx)", user_text, flags=re.IGNORECASE):
            reply = random.choice(THANKS_RESPONSES)
        elif re.search(r"(베프|친구|짱|최고|사랑|love)", user_text, flags=re.IGNORECASE):
            reply = random.choice(AFFECTION_RESPONSES)
        else:
            reply = random.choice(["응응", "웅", "ㅇㅇ", "그래", "오키"])
        mode = "SIMPLE_ACK"
    else:
        mode = "WORRY" if is_ask_about_jinwoo_worry(user_text) else choose_mode(user_text)
        if must_lock_empathy(user_text):
            mode = "EMPATHY"

        reply = None
        try:
            history = [SystemMessage(SYSTEM_PROMPT), SystemMessage(style_prompt(mode, user_text))]
            for m in st.session_state.messages:
                history.append(HumanMessage(m["content"]) if m["role"]=="user" else AIMessage(m["content"]))
            resp = llm.invoke(history)
            reply = (resp.content or "").strip()
        except Exception as e:
            st.session_state["last_error"] = f"invoke_error: {e}"
            reply = None

        if not reply:
            reply = random.choice(EMPATHY_EXPRESSIONS)

        reply = sanitize_reply(reply, mode)

    st.session_state["last_mode"] = mode

    delay = calc_delay(len(user_text), len(reply))
    time.sleep(delay)

    placeholder.empty()
    st.session_state.messages.append({"role":"assistant","content":reply})
    render_message("assistant", reply)

st.markdown('</div>', unsafe_allow_html=True)
