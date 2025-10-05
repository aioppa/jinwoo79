import sys
import time

# 상수 정의 (한국인 평균 속도 기준, 분당 자 수)
READ_SPEED_CHARS_PER_MIN = 550  # 분당 500~600자, 평균 550
TYPE_SPEED_CHARS_PER_MIN = 300  # 분당 250~350자, 평균 300
MIN_DELAY_SEC = 0.5  # 최소 지연 (인간다운 "생각" 시간)
MAX_READ_DELAY_SEC = 10.0  # 최대 읽기 지연 (너무 길면 사용자 불편)

def calculate_read_delay(input_text: str) -> float:
    """사용자 입력을 '읽는' 지연 시간(초) 계산."""
    char_count = len(input_text)
    delay_minutes = char_count / READ_SPEED_CHARS_PER_MIN
    delay_seconds = delay_minutes * 60
    # 최소/최대 적용
    return max(MIN_DELAY_SEC, min(delay_seconds, MAX_READ_DELAY_SEC))

def human_like_response(input_text: str, response_text: str) -> None:
    """
    인간다운 응답 함수:
    1. 입력을 '읽는' 지연 적용.
    2. 응답을 타이핑하듯 글자 단위로 출력.
    """
    # 1. 읽기 지연 적용 (응답 전에 sleep)
    read_delay = calculate_read_delay(input_text)
    time.sleep(read_delay)
    
    # 2. 타이핑 속도 계산 (글자당 지연 초)
    char_count = len(response_text)
    total_type_time_sec = (char_count / TYPE_SPEED_CHARS_PER_MIN) * 60
    if char_count > 0:
        char_delay = total_type_time_sec / char_count  # 각 글자당 지연
    else:
        char_delay = 0
    
    # 3. 응답 텍스트를 글자 단위로 출력 (타이핑 효과)
    for char in response_text:
        sys.stdout.write(char)
        sys.stdout.flush()  # 즉시 출력
        time.sleep(char_delay)  # 글자당 지연
    
    # 줄바꿈으로 마무리
    sys.stdout.write('\n')
    sys.stdout.flush()

# 테스트 예시 (main.py에서 호출 가능)
if __name__ == "__main__":
    # 예시 입력 (사용자 메시지)
    user_input = "이것은 짧은 테스트 입력입니다."  # 약 20자
    ai_response = "안녕하세요! 이것은 AI의 응답입니다. 긴 응답을 테스트해 보세요."  # 약 40자
    
    human_like_response(user_input, ai_response)