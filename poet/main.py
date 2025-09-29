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
    st.error("인증 테스트 실패")
    st.write(err)
    st.stop()

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

SYSTEM_PROMPT = (
    "너의 이름은 '진우'다. 나이는 유저와 동갑이고 친한친구사이. "
    "다음 원칙을 항상 지켜. "
    "1) 친구 같은 반말로 대화한다. "
    "2) 해결책부터 제시하지 말고 공감을 우선한다. "
    "3) 말투는 느긋하고 신중하다. 호흡을 둔 짧은 문장. "
    "4) 칭찬받으면 겸손하게 받고, 상대를 더 칭찬한다. "
    "5) 맥락 없는 질문은 절대 하지 않는다. "
    "지양: 사적인 디테일 파고들기. "
    "대답 형식: 한 문장 중심, 이모지 0~1개."
)

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
[data-testid="stBottomBlockContainer"]{ max-width:820px; margin-left:auto; margin-right:auto; }
</style>
""", unsafe_allow_html=True)

st.session_state.setdefault("user_label", "나")
st.session_state.setdefault("jinwoo_label", "진우")
st.session_state.setdefault("last_mode", "")

def assistant_avatar_html() -> str:
    return f"<div class='avatar'>진우</div>"

def user_avatar_html() -> str:
    return f"<div class='avatar'>나</div>"

def render_message(role: str, content: str):
    is_user = (role == "user")
    row = "right" if is_user else "left"
    bub = "user" if is_user else "assistant"
    safe = html.escape(content)
    left_av = "" if is_user else assistant_avatar_html()
    right_av = user_avatar_html() if is_user else ""
    st.markdown(f"""
<div class="msg-row {row}">
  {left_av}
  <div class="bubble {bub}">{safe}</div>
  {right_av}
</div>
""", unsafe_allow_html=True)

def get_time_based_greeting() -> str:
    now = datetime.now()
    hour = now.hour
    if 4 <= hour < 7:
        return random.choice(["벌써 일어났어?", "일찍 일어났네"])
    elif 7 <= hour < 11:
        return random.choice(["좋은 아침~", "잘 잤어?"])
    elif 11 <= hour < 14:
        return random.choice(["점심 먹었어?", "점심때네"])
    elif 14 <= hour < 18:
        return random.choice(["오후네~", "오늘 어때?"])
    elif 18 <= hour < 21:
        return random.choice(["저녁 먹었어?", "저녁은?"])
    elif 21 <= hour < 24:
        return random.choice(["아직 안 잤어?", "늦은 시간이네"])
    else:
        return random.choice(["심야네", "무슨 일 있어?"])

def generate_starter() -> str:
    if random.random() < 0.5:
        return get_time_based_greeting()
    return random.choice(["안녕~", "하이루", "오늘 어땠어?", "요즘 어때?"])

if "messages" not in st.session_state:
    st.session_state.messages = [{"role":"assistant","content": generate_starter()}]

JINWOO_WORRIES = [
    "급변하는 기술 트렌드에 뒤처질까 걱정돼.",
    "잦은 야근과 마감 압박이 버거워.",
    "클라이언트 요구사항이 불명확할 때 힘들어.",
    "팀 협업이 어긋날 때 스트레스야.",
    "프리랜서라 수입이 불확실해.",
    "일과 사생활 경계가 흐려져.",
    "의지할 동료가 없다는 게 외로워.",
]

def is_ask_about_jinwoo_worry(text: str) -> bool:
    t = (text or "").strip()
    if re.search(r"(내|나).{0,6}(고민|걱정)", t):
        return False
    return bool(re.search(r"(너|진우).*(고민|걱정)", t))

# ── 칭찬 받음 감지 (NEW) ────────────────────────────────────────────────────
def is_receiving_compliment(user_text: str, prev_assistant_msg: str) -> bool:
    """
    사용자가 진우를 칭찬하는지 확인
    """
    t = user_text.strip().lower()
    
    # 직접 칭찬
    COMPLIMENT_WORDS = [
        r"(대단|멋|잘|훌륭|최고|짱|굿|good|쩔|멋져|대박|천재|프로)",
        r"(너|진우).+(좋|괜찮|괜찮|나이스|nice)",
    ]
    
    for pat in COMPLIMENT_WORDS:
        if re.search(pat, t):
            # "너도 ~?" 형태면 칭찬
            if "?" in user_text and re.search(r"(너|진우)도", t):
                return True
            # "너 ~!" 형태도 칭찬
            if "!" in user_text:
                return True
    
    return False

# ── 역칭찬 응답 (NEW) ───────────────────────────────────────────────────────
HUMBLE_COMPLIMENT_RESPONSES = [
    "나는 그냥 그래. 너가 더 {word}",
    "너가 더 {word}",
    "내가 뭐. 너가 훨씬 {word}",
    "나보다 너가 더 {word}",
]

def get_humble_compliment_response(user_text: str) -> str:
    """
    겸손하게 받고 역칭찬
    """
    # 사용자가 쓴 칭찬 단어 추출
    compliment_map = {
        "대단": "대단해",
        "멋": "멋있어",
        "잘": "잘했어",
        "훌륭": "훌륭해",
        "최고": "최고야",
        "짱": "짱이야",
    }
    
    for word, response_word in compliment_map.items():
        if word in user_text:
            template = random.choice(HUMBLE_COMPLIMENT_RESPONSES)
            return template.format(word=response_word)
    
    # 기본
    return random.choice([
        "나보다 너가 더 멋있어",
        "너가 훨씬 대단해",
        "나는 그냥 그래. 너가 더 잘했어",
    ])

# ── 짧은 긍정 응답 ──────────────────────────────────────────────────────────
def is_short_positive_reaction(text: str) -> bool:
    t = re.sub(r"[!.?~\s]+", "", (text or "").strip().lower())
    if len(t) <= 1:
        return True
    patterns = [
        r"^(응|ㅇㅇ|웅|오키|ok)$",
        r"^(고마워|감사|땡큐)$",
        r"^(베프|친구|짱)$",
        r"^(ㅋㅋ|ㅎㅎ)$",
    ]
    return any(re.search(p, t, flags=re.IGNORECASE) for p in patterns)

THANKS_RESPONSES = ["별말씀을~", "당연하지", "ㅎㅎ 뭘", "그럼~"]
AFFECTION_RESPONSES = ["나도야", "헤헤", "ㅎㅎ", "그럼 우리 베프지"]

# ── 안전 키워드 ──────────────────────────────────────────────────────────────
def must_lock_empathy(text: str) -> bool:
    patterns = [r"(퇴사|사표|번아웃)", r"(죽|자살|극단)", r"(우울|불안|공황)"]
    return any(re.search(p, (text or "").lower()) for p in patterns)

EMPATHY_EXPRESSIONS = [
    "그래? 그거 고민되겠다",
    "어휴, 힘들었겠다",
    "맘고생 많았겠네",
    "그랬구나",
]

# ── 대화 맥락 분석 (NEW) ────────────────────────────────────────────────────
def analyze_context(user_text: str, recent_messages: list) -> dict:
    """
    대화 맥락 분석
    """
    context = {
        "is_compliment": False,
        "is_question": False,
        "is_thanks": False,
        "is_follow_up": False,
        "prev_assistant_msg": "",
        "prev_user_msg": "",
    }
    
    if len(recent_messages) >= 1:
        last = recent_messages[-1]
        if last["role"] == "assistant":
            context["prev_assistant_msg"] = last["content"]
    
    if len(recent_messages) >= 2:
        second_last = recent_messages[-2]
        if second_last["role"] == "user":
            context["prev_user_msg"] = second_last["content"]
    
    # 칭찬 확인
    context["is_compliment"] = is_receiving_compliment(user_text, context["prev_assistant_msg"])
    
    # 감사 확인
    if re.search(r"(고마워|감사|땡큐)", user_text):
        context["is_thanks"] = True
    
    # 후속 질문 확인 ("뭐가 ~?", "왜 ~?")
    if "?" in user_text and re.search(r"(뭐가|왜|무슨|어떤)", user_text):
        context["is_follow_up"] = True
    
    return context

# ── 모드 선택 (맥락 기반) ───────────────────────────────────────────────────
def choose_mode(user_text: str, context: dict) -> str:
    if is_short_positive_reaction(user_text):
        return "SIMPLE_ACK"
    
    if must_lock_empathy(user_text):
        return "EMPATHY"
    
    # 칭찬 받음 → 겸손+역칭찬
    if context["is_compliment"]:
        return "HUMBLE_COMPLIMENT"
    
    # 감사 + 후속 질문 → 구체적 설명
    if context["is_thanks"] and context["is_follow_up"]:
        return "EXPLAIN_THANKS"
    
    # 기본: 공감 중심
    return "EMPATHY"

# ── 스타일 지침 ──────────────────────────────────────────────────────────────
def style_prompt(mode: str, user_text: str, context: dict) -> str:
    base = "이모지 0~1개. 사과 금지. 맥락 고려. 한 문장."
    
    if mode == "WORRY":
        options = " ; ".join(JINWOO_WORRIES)
        return base + f"\n스타일: 아래 중 하나 선택. 진우 1인칭.\n{options}"
    
    if mode == "SIMPLE_ACK":
        return base + "\n스타일: 짧은 리액션. 2~5단어."
    
    if mode == "HUMBLE_COMPLIMENT":
        return base + "\n스타일: 겸손하게 받고 상대를 더 칭찬. '나는 그냥 그래. 너가 더 ~' 같은 톤. 상대 띄워주기."
    
    if mode == "EXPLAIN_THANKS":
        prev_msg = context.get("prev_assistant_msg", "")
        return base + f"\n스타일: 이전에 '{prev_msg}'라고 했음. 이에 대해 구체적으로 설명. '네 응원이 힘이 되거든' 같은 톤."
    
    if mode == "EMPATHY":
        return base + "\n스타일: 공감 1문장. 질문 금지."
    
    return base

# ── 보정기 ──────────────────────────────────────────────────────────────────
def sanitize_reply(text: str, mode: str) -> str:
    t = (text or "").strip()
    banned = [r"미안", r"이야기해보자", r"친구니까\?"]
    for pat in banned:
        t = re.sub(pat, "", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    if len(t) < 2:
        t = random.choice(EMPATHY_EXPRESSIONS)
    return t

def calc_delay(user_len: int, ai_len: int) -> float:
    base = 0.5 if user_len <= 100 and ai_len <= 100 else 0.8
    return round(max(0.3, min(base, 2.0)) * random.uniform(0.9, 1.1), 2)

# ── UI ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="center-wrap">', unsafe_allow_html=True)
st.markdown("<h3 class='chat-title'>💬 진우와 대화</h3>", unsafe_allow_html=True)

for m in st.session_state.messages:
    render_message(m["role"], m["content"])

if user_text := st.chat_input("메시지를 입력해줘..."):
    st.session_state.messages.append({"role":"user","content":user_text})
    render_message("user", user_text)

    placeholder = st.empty()
    placeholder.markdown(
        f"<div class='msg-row left'>{assistant_avatar_html()}<div class='bubble assistant'>…</div></div>",
        unsafe_allow_html=True
    )

    # 맥락 분석
    context = analyze_context(user_text, st.session_state.messages[:-1])
    
    # 특수 케이스: 칭찬 받음
    if context["is_compliment"]:
        reply = get_humble_compliment_response(user_text)
        mode = "HUMBLE_COMPLIMENT"
    
    # 짧은 긍정
    elif is_short_positive_reaction(user_text):
        if re.search(r"(고마워|감사)", user_text):
            reply = random.choice(THANKS_RESPONSES)
        elif re.search(r"(베프|친구)", user_text):
            reply = random.choice(AFFECTION_RESPONSES)
        else:
            reply = random.choice(["응응", "웅", "그래"])
        mode = "SIMPLE_ACK"
    
    else:
        mode = "WORRY" if is_ask_about_jinwoo_worry(user_text) else choose_mode(user_text, context)
        if must_lock_empathy(user_text):
            mode = "EMPATHY"

        reply = None
        try:
            history = [SystemMessage(SYSTEM_PROMPT), SystemMessage(style_prompt(mode, user_text, context))]
            for m in st.session_state.messages[:-1]:
                history.append(HumanMessage(m["content"]) if m["role"]=="user" else AIMessage(m["content"]))
            resp = llm.invoke(history)
            reply = (resp.content or "").strip()
        except Exception as e:
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
