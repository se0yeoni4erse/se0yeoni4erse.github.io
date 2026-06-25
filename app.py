import streamlit as st
import fitz
import re

st.set_page_config(page_title="PDF 문장 정밀 대조 검수기", layout="wide")

def get_sentences(text):
    """문장 단위로 텍스트 분리"""
    # 마침표, 물음표, 느낌표 기준으로 분리
    sentences = re.split(r'[.!?]+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 5] # 너무 짧은 문장은 제외

def get_keywords(text):
    """조사 등을 제외한 핵심 단어 집합 생성"""
    words = re.findall(r'\w+', text.lower())
    return set(w for w in words if len(w) > 3) # 3글자 이상 단어만 추출

def extract_text_from_pdf(uploaded_file):
    uploaded_file.seek(0)
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [page.get_text() for page in doc]

# --- UI 및 로직 ---
st.title("📑 문장 단위 PDF 정밀 대조 검수기")
uploaded_files = st.file_uploader("두 PDF 파일을 동시에 업로드하세요.", type=["pdf"], accept_multiple_files=True)

if uploaded_files and len(uploaded_files) == 2:
    ref_filename = st.selectbox("기준 지문 PDF(2번) 선택:", [f.name for f in uploaded_files])
    
    if st.button("🚀 문장 단위 정밀 검수 시작"):
        ref_pdf = next(f for f in uploaded_files if f.name == ref_filename)
        target_pdf = next(f for f in uploaded_files if f.name != ref_filename)
        
        ref_text = " ".join(extract_text_from_pdf(ref_pdf))
        ref_keywords = get_keywords(ref_text)
        
        target_pages = extract_text_from_pdf(target_pdf)
        pages_to_delete = []
        log_data = []

        for i, page_text in enumerate(target_pages):
            page_num = i + 1
            sentences = get_sentences(page_text)
            
            # 빈 페이지 처리
            if not sentences:
                pages_to_delete.append(page_num)
                continue

            # 문장별 검사
            match_score = 0
            for s in sentences:
                if s.lower() in ref_text.lower():
                    match_score += 3 # 완벽한 문장 일치 시 높은 점수
                else:
                    # 단어 조각 일치 검사
                    s_keywords = get_keywords(s)
                    if s_keywords and len(s_keywords & ref_keywords) / len(s_keywords) > 0.5:
                        match_score += 1 # 의미 일치 시 낮은 점수
            
            if match_score < 2: # 최소한의 문장/의미 일치가 없으면 삭제
                pages_to_delete.append(page_num)
                log_data.append(f"🗑️ {page_num}페이지: 삭제 대상 (일치 문장 부족)")
            else:
                log_data.append(f"✅ {page_num}페이지: 유지 (일치 문장/의미 발견)")

        st.error(f"🗑️ 삭제 대상 페이지: {', '.join(map(str, pages_to_delete))}")
        with st.expander("🔍 상세 분석 로그"):
            for log in log_data: st.text(log)
