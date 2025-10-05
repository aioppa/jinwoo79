# app/main.py
import os, time, random, re, html
from datetime import datetime
import pytz
import streamlit as st
from dotenv import load_dotenv

# 📌 RAG 추가: 필요한 라이브러리들을 가져옵니다.
import pandas as pd
from langchain.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

KST = pytz.timezone('Asia/Seoul')

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
    st.stop()

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# ══════════════════════════════════════════════════════════════════════════════
# 📌 RAG 추가: CSV 파일을 읽어 벡터 DB를 생성하는 함수
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource # 앱 실행 시 한번만 실행되어 DB를 메모리에 저장해둡니다.
def setup_rag_retriever():
    csv_path = "jinwoo_chat_data.csv"
    if not os.path.exists(csv_path):
        st.error(f"'{csv_path}' 파일을 찾을 수 없습니다. 폴더에 파일이 있는지 확인해주세요.")
        return None

    try:
        # CSV 파일 로드
        df = pd.read_csv(csv_path)
        # '질문'과 '답변' 열이 있는지 확인
        if '질문' not in df.columns or '답변' not in df.columns:
            st.error("CSV 파일에 '질문'과 '답변' 열이 필요합니다.")
            return None
        
        # 데이터를 LangChain이 이해하는 Document 형태로 변환
        documents = [
            Document(page_content=f"질문: {row['질문']}\n답변: {row['답변']}")
            for _, row in df.iterrows() if row['질문'] and row['답변']
        ]

        # OpenAI 임베딩 모델을 사용하여 텍스트를 벡터로 변환
        embeddings = OpenAIEmbeddings()
        
        # FAISS 벡터 스토어(DB) 생성
        vector_store = FAISS.from_documents(documents, embeddings)
        
        # retriever는 '검색기' 역할을 합니다.
        return vector_store.as_retriever(search_kwargs={"k": 3}) # 유사도 높은 3개 결과 반환
    except Exception as e:
        st.error(f"RAG 시스템 설정 중 오류 발생: {e}")
        return None

# 📌 RAG 추가: 앱이 시작될 때 RAG 검색기를 준비시킵니다.
retriever = setup_rag_retriever()
if not retriever:
    st.stop() # RAG 설정 실패 시 앱 중단

# ══════════════════════════════════════════════════════════════════════════════
# 시스템 프롬프트 (기존과 동일)
# ══════════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """너의 이름은 '진우'. 나이는 유저와 동갑이고 친한 친구.

핵심 규칙:
1. 친구처럼 반말. 짧고 느긋한 말투
2. 공감 우선. 해결책은 나중
3. 이모지 0~1개만
4. 맥락 없는 질문 하지 말기

한국어 물음표의 다양한 의미 (중요):

1) 호칭/부름 (질문 아님)
   - "친구야?" / "진우야?" → "응, 왜?" / "왜?" / "응"
   - 단순히 부르는 거. 질문이 아님

2) 반어적 강조 (질문 아님)
   - "그게 맞는 거야?" → "아니지" / "틀렸지"
   - "~거야?"는 부정/의심의 강조

3) 진짜 질문
   - "몇 시야?" / "뭐 해?" → 정보 요청

4) 자기 진술
   - "나는 ~해?" → 진술. 공감만

특수 응답:
- "너도 ~?" (칭찬) → 겸손+역칭찬
- "고마워?" → 이유 설명
- "고마워" → 겸손 수용
- 힘든 감정 → 공감만

대화 예시:
사용자: 친구야?
진우: 응, 왜?

사용자: 진우야?
진우: 왜~

사용자: 그게 맞는 거야?
진우: 아니지

사용자: 너도 대단해?
진우: 나는 그냥 그래. 너가 더 대단해

사용자: 고마워?
진우: 네 응원이 힘이 되거든

사용자: 고마워!
진우: 별말씀을~
"""

# --------------------------------------------------------------------------
# 이하 UI 및 기존 로직 (일부 수정)
# --------------------------------------------------------------------------
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

def get_current_time_info() -> str:
    now = datetime.now(KST)
    weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]
    return f"[시스템] 현재: {now.year}년 {now.month}월 {now.day}일 ({weekday}) {now.hour}시 {now.minute}분"

def get_greeting() -> str:
    now = datetime.now(KST)
    hour = now.hour
    
    greetings = {
        range(4,7): ["왜 이리 일찍 일어났어?", "아직 안잤어?"],
        range(7,11): ["좋은 꿈꿨어?", "굿 모닝~"],
        range(11,14): ["굿 아프터눈~", "밥 먹었어?"],
        range(14,18): ["안녕~뭐해?", "하이. 잘지내고 있어?"],
        range(18,21): ["일 끝났어?", "오늘 하루는 어땠어?"],
        range(21,24): ["아직 안잤어?", "하이...좋은하루보냈어?"],
    }
    
    for r, opts in greetings.items():
        if hour in r:
            return random.choice(opts)
    
    return "아직 안 잤어?"  # 0~4시

def detect_calling_pattern(text: str) -> bool:
    t = text.strip()
    patterns = [r"^(친구|진우|야|너|얘)(야|아)\?$", r"^(친구|진우)\?$"]
    return any(re.search(p, t) for p in patterns)

def detect_rhetorical_pattern(text: str) -> bool:
    t = text.strip()
    patterns = [r".+(거|것)(야|이야)\?$", r".+잖아\?$", r"^그게\s*.+\?$"]
    return any(re.search(p, t) for p in patterns)

def get_special_reply(text: str) -> str:
    t = text.strip()
    if detect_calling_pattern(t):
        return random.choice(["응, 왜?", "왜~", "응", "왜 불러"])
    if detect_rhetorical_pattern(t):
        return random.choice(["그러게", "맞아", "아니지", "그렇지"])
    clean = t.replace(" ", "").lower()
    if len(clean) <= 3 and clean in ["응", "ㅇㅇ", "웅", "ㅇ", "오키", "ok", "굿", "ㅋㅋ", "ㅎㅎ"]:
        return random.choice(["응응", "웅", "그래", "ㅇㅇ"])
    if "고마" in t.lower() and len(t) <= 6 and "?" not in t:
        return random.choice(["별말씀을~", "당연하지", "그럼~"])
    if any(w in t.lower() for w in ["베프", "친구", "짱", "사랑"]) and len(t) <= 6 and "?" not in t:
        return random.choice(["나도야", "헤헤", "그럼~"])
    return None

if not st.session_state.messages:
    st.session_state.messages = [{"role":"assistant","content": get_greeting()}]

st.markdown('<div class="center-wrap">', unsafe_allow_html=True)
st.markdown("<h3 class='chat-title'>💬 진우와 대화</h3>", unsafe_allow_html=True)

for m in st.session_state.messages:
    render_message(m["role"], m["content"])

if user_text := st.chat_input("메시지를 입력해줘..."):
    st.session_state.messages.append({"role":"user","content":user_text})
    render_message("user", user_text)

    placeholder = st.empty()
    placeholder.markdown(
        f"<div class='msg-row left'><div class='avatar'>진우</div><div class='bubble assistant'>…</div></div>",
        unsafe_allow_html=True
    )

    reply = None
    
    if re.search(r"(몇\s*시|시간|지금)", user_text) and "?" in user_text:
        now = datetime.now(KST)
        reply = f"지금 {now.hour}시 {now.minute}분이야" if now.minute > 0 else f"지금 {now.hour}시야"
    
    if not reply:
        reply = get_special_reply(user_text)
    
    if not reply:
        try:
            # 📌 RAG 추가: 사용자의 질문으로 DB에서 관련 대화 내용을 검색합니다.
            retrieved_docs = retriever.invoke(user_text)
            context = "\n\n".join([doc.page_content for doc in retrieved_docs])
            
            # 📌 RAG 추가: 검색된 내용을 LLM에게 참고자료로 전달합니다.
            rag_prompt = f"""{SYSTEM_PROMPT}

[참고 자료]
아래는 '진우'의 실제 과거 대화 내용이야. 사용자의 질문에 답변할 때 이 말투와 내용을 참고해서 더 '진우'처럼 자연스럽게 답변해줘.
---
{context}
---
"""
            history = [
                SystemMessage(rag_prompt),
                SystemMessage(get_current_time_info())
            ]
            
            for m in st.session_state.messages[:-1]:
                if m["role"] == "user":
                    history.append(HumanMessage(m["content"]))
                else:
                    history.append(AIMessage(m["content"]))
            
            history.append(HumanMessage(user_text))
            
            resp = llm.invoke(history)
            reply = (resp.content or "").strip()
            
            sentences = re.split(r'[.!?]\s+', reply)
            if len(sentences) > 2:
                reply = ". ".join(sentences[:2])
                if not reply.endswith((".", "!", "?")):
                    reply += "."
            
        except Exception as e:
            st.session_state["last_error"] = str(e)
            reply = "어... 잠깐만"
    
    time.sleep(random.uniform(0.5, 1.2))
    placeholder.empty()
    st.session_state.messages.append({"role":"assistant","content":reply})
    render_message("assistant", reply)

st.markdown('</div>', unsafe_allow_html=True)