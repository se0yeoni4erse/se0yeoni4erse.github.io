import streamlit as st
import fitz  # PyMuPDF 라이브러리
import re
from difflib import SequenceMatcher

st.set_page_config(page_title="PDF 지문 대조 검수기", layout="centered")

def normalize_text(text):
    text = re.sub(r'[^\w가-힣]', '', text)
    return text.lower()

def extract_text_from_pdf(uploaded_file):
    # 파일 포인터를 처음으로 되돌림 (재검수 시 오류 방지)
    uploaded_file.seek(0) 
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [page.get_text() for page in doc]

def format_page_ranges(pages):
    if not pages:
        return "삭제 대상 없음"
    pages = sorted(list(set(pages)))
    ranges = []
    start = pages[0]
    end = pages[0]
    for p in pages[1:]:
        if p == end + 1:
            end = p
        else:
            ranges.append(f"{start}" if start == end else f"{start}-{end}")
            start = end = p
    ranges.append(f"{start}" if start == end else f"{start}-{end}")
    return ",".join(ranges)

# --- UI 화면 구성 ---
st.title("📑 PDF 지문 대조 검수기")
st.markdown("기준 지문과 문제 PDF를 **아래 한 곳에 동시에 업로드**해 주세요.")

# 1. 단일 업로드 창 (accept_multiple_files=True 로 여러 파일 허용)
uploaded_files = st.file_uploader("여기에 두 PDF 파일을 모두 드래그 앤 드롭하세요", type=["pdf"], accept_multiple_files=True)

# 두 개의 파일이 정상적으로 업로드되었을 때만 다음 단계 표시
if uploaded_files and len(uploaded_files) == 2:
    st.divider()
    
    # 파일 이름 목록 추출
    file_names = [f.name for f in uploaded_files]
    
    # 2. 어떤 파일이 기준 지문인지 사용자가 선택
    st.subheader("📌 역할 지정")
    ref_filename = st.selectbox("어느 파일이 '기준 지문(2번)' 입니까?", file_names)
    
    threshold = st.slider("최소 일치 글자 수 (기본값: 30)", min_value=10, max_value=100, value=30, 
                          help="이 글자 수만큼 연속으로 일치해야 같은 지문으로 인정합니다.")

    if st.button("🚀 대조 및 검수 시작", use_container_width=True):
        with st.spinner('문서를 분석하고 있습니다...'):
            try:
                # 선택된 이름에 따라 파일 변수 분리
                ref_pdf = next(f for f in uploaded_files if f.name == ref_filename)
                target_pdf = next(f for f in uploaded_files if f.name != ref_filename)
                
                # 텍스트 추출 및 정규화
                ref_pages = extract_text_from_pdf(ref_pdf)
                target_pages = extract_text_from_pdf(target_pdf)
                
                full_ref_text = normalize_text(" ".join(ref_pages))
                pages_to_delete = []
                
                progress_bar = st.progress(0)
                for i, page_text in enumerate(target_pages):
                    norm_target = normalize_text(page_text)
                    
                    if len(norm_target) < threshold:
                        pages_to_delete.append(i + 1)
                        continue
                        
                    matcher = SequenceMatcher(None, norm_target, full_ref_text)
                    match = matcher.find_longest_match(0, len(norm_target), 0, len(full_ref_text))
                    
                    if match.size < threshold:
                        pages_to_delete.append(i + 1)
                        
                    progress_bar.progress((i + 1) / len(target_pages))
                
                final_result = format_page_ranges(pages_to_delete)
                
                st.success("✅ 검수 완료!")
                st.markdown("### 🗑️ 삭제 대상 페이지")
                st.info(f"**{final_result}**")
                
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

elif uploaded_files and len(uploaded_files) != 2:
    st.warning(f"현재 {len(uploaded_files)}개의 파일이 업로드되었습니다. 정확히 2개의 파일을 업로드해 주세요.")
