import streamlit as st
import pandas as pd
import pdfplumber
import google.generativeai as genai
import time
import re
import json
import datetime
import os

# --- 🔐 1. 비밀번호 확인 기능 ---
def check_password():
    """비밀번호가 맞으면 True를, 틀리면 False를 반환합니다."""
    # 앱의 메모리(session_state)에 비밀번호 확인 상태를 저장합니다.
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    # 비밀번호가 아직 확인되지 않았다면, 입력창을 띄웁니다.
    if not st.session_state.password_correct:
        st.header("🔒 로그인")
        password = st.text_input("비밀번호를 입력하세요", type="password")
        if st.button("로그인"):
            # 🔑 여기에 원하는 비밀번호를 설정하세요!
            if password == "skwlals25":
                st.session_state.password_correct = True
                st.rerun()  # 비밀번호가 맞으면 페이지를 새로고침합니다.
            else:
                st.error("비밀번호가 올바르지 않습니다.")
        return False
    else:
        return True

# --- 🖥️ 2. 메인 앱 실행 ---
# 비밀번호가 확인된 경우에만 아래의 앱 코드를 실행합니다.
if check_password():
    # --- 앱 기본 설정 ---
    st.set_page_config(page_title="AI 에세이 평가 플랫폼", page_icon="🤖", layout="wide")
    st.title("🤖 AI 에세이 평가 플랫폼")

    # --- 📂 데이터베이스(JSON 파일) 관리 함수 ---
    HISTORY_FILE = 'evaluation_history.json'

    def load_history():
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                try: return json.load(f)
                except json.JSONDecodeError: return []
        return []

    def save_history(history_data):
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=4)

    # --- ⚙️ API 키 설정 및 기록 불러오기 ---
    history = load_history()
    with st.sidebar:
        st.header("⚙️ 설정")
        if 'google_api_key' not in st.session_state: st.session_state.google_api_key = ""
        st.session_state.google_api_key = st.text_input("Google AI API Key", type="password", value=st.session_state.google_api_key)
        if st.session_state.google_api_key:
            try:
                genai.configure(api_key=st.session_state.google_api_key)
                st.success("API 키가 적용되었습니다.")
            except Exception as e: st.error(f"API 키 설정 중 오류: {e}")

        st.header("📚 평가 기록 불러오기")
        if history:
            history_options = {f"{item['평가명']} ({item['평가일자']})": i for i, item in enumerate(history)}
            selected_history = st.selectbox("불러올 평가를 선택하세요.", options=history_options.keys())
            if st.button("선택한 평가 기준 불러오기"):
                selected_index = history_options[selected_history]
                st.session_state.criteria_list = history[selected_index]['평가기준']
                st.success(f"'{selected_history}'의 평가 기준을 불러왔습니다.")
                st.rerun()
        else: st.info("저장된 평가 기록이 없습니다.")

    # --- 🧠 AI 응답 분석 함수 ---
    def parse_ai_response(response_text, criteria_list):
        parsed_data = {}
        try:
            summary_match = re.search(r"\[종합 평가\]\s*([\s\S]*?)\s*\[항목별 평가\]", response_text)
            parsed_data['종합 평가'] = summary_match.group(1).strip() if summary_match else "종합 평가 추출 실패"
            scores = {}
            total_score = 0
            for criterion in criteria_list:
                item_name = criterion['항목']
                max_score = criterion['배점']
                pattern = re.compile(rf"- {re.escape(item_name)}:\s*\[.*?(\d+)\s*점\]\s*([\s\S]*?)(?=\n- |\Z)")
                match = pattern.search(response_text)
                if match:
                    score = int(match.group(1))
                    reason = match.group(2).strip()
                    scores[item_name] = {"점수": score, "이유": reason, "배점": max_score}
                    total_score += score
                else:
                    scores[item_name] = {"점수": 0, "이유": "항목별 평가 추출 실패", "배점": max_score}
            parsed_data['항목별 평가'] = scores
            parsed_data['총점'] = total_score
        except Exception as e:
            return {"종합 평가": f"AI 응답 분석 실패: {e}", "항목별 평가": {}, "총점": 0}
        return parsed_data

    # --- 📝 평가 정보 입력 ---
    st.subheader("📝 1단계: 평가 정보 입력")
    eval_name = st.text_input("평가명", placeholder="예: 2025년 1학기 중간 논술 평가")
    eval_date = st.date_input("평가일자", datetime.date.today())

    # --- 📊 평가 기준 설정 ---
    with st.expander("📊 2단계: 평가 기준 설정", expanded=True):
        if 'criteria_list' not in st.session_state:
            st.session_state.criteria_list = [{"항목": "내용의 충실성", "배점": 40, "기준": "주제에 대한 이해가 깊고, 근거가 타당하며 내용이 풍부한가?"},
                                             {"항목": "논리적 구조", "배점": 30, "기준": "서론, 본론, 결론의 구조가 명확하고, 문단 간의 연결이 자연스러운가?"},
                                             {"항목": "표현의 정확성", "배점": 30, "기준": "어휘 사용이 적절하고, 문법 및 맞춤법 오류가 없는가?"}]
        for i, criterion in enumerate(st.session_state.criteria_list):
            st.markdown("---")
            col1, col2, col3 = st.columns([3, 1, 1])
            criterion['항목'] = col1.text_input(f"항목 #{i+1}", value=criterion['항목'], key=f"item_{i}")
            criterion['배점'] = col2.number_input(f"배점 #{i+1}", min_value=0, max_value=100, value=criterion['배점'], key=f"score_{i}")
            with col3:
                st.write("")
                st.write("")
                if st.button("🗑️ 삭제", key=f"delete_{i}"):
                    st.session_state.criteria_list.pop(i)
                    st.rerun()
            criterion['기준'] = st.text_area(f"세부 기준 #{i+1}", value=criterion['기준'], key=f"desc_{i}", height=100)
        if st.button("➕ 평가 항목 추가"):
            st.session_state.criteria_list.append({"항목": "", "배점": 10, "기준": ""})
            st.rerun()

    # --- 📄 에세이 업로드 및 평가 실행 ---
    st.subheader("📄 3단계: 에세이 파일 업로드 및 평가 실행")
    uploaded_essays = st.file_uploader("평가할 학생들의 에세이 PDF 파일들을 업로드하세요.", type=['pdf'], accept_multiple_files=True)

    if st.button("🚀 모든 파일 평가 시작"):
        # ... (이하 평가 로직은 이전과 동일) ...
        pass # Placeholder for brevity

    # --- 📈 평가 결과 확인 및 저장 ---
    if 'evaluation_results' in st.session_state and st.session_state['evaluation_results']:
        # ... (이하 결과 표시 로직은 이전과 동일) ...
        pass # Placeholder for brevity
