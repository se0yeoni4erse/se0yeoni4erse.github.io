import streamlit as st
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="PDF 지문 대조 검수기", layout="centered")

def normalize_text(text):
    """공백 및 특수문자를 모두 제거하고 소문자로 변환하여 순수 문자만 남김"""
    text = re.sub(r'[^\w가-힣]', '', text)
    return text.lower()

def extract_text_from_pdf(uploaded_file):
    """PDF 파일에서 페이지별로 텍스트를 추출"""
    uploaded_file.seek(0)
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [page.get_text() for page in doc]

def format_page_ranges(pages):
    """[1, 2, 3, 5] 형태의 배열을 '1-3,5' 형태의 문자열로 변환"""
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
st.title("📑 PDF 지문 대조 검수기 (정확도 개선판)")
st.markdown("기준 지문과 문제 PDF를 **동시에 업로드**해 주세요.")

uploaded_files = st.file_uploader("여기에 두 PDF 파일을 모두 드래그 앤 드롭하세요", type=["pdf"], accept_multiple_files=True)

if uploaded_files and len(uploaded_files) == 2:
    st.divider()
    
    file_names = [f.name for f in uploaded_files]
    
    st.subheader("📌 역할 지정")
    ref_filename = st.selectbox("어느 파일이 '기준 지문(2번)' 입니까?", file_names)
    
    # 세밀한 조정을 위한 알고리즘 민감도 설정
    col1, col2 = st.columns(2)
    with col1:
        chunk_size = st.number_input("검사 조각 크기 (글자 수)", min_value=5, max_value=50, value=15, 
                                     help="이 글자 수만큼 잘라서 비교합니다. 너무 길면 오탈자에 취약해집니다.")
    with col2:
        min_match_count = st.number_input("최소 일치 횟수", min_value=1, max_value=10, value=2, 
                                          help="위 조각이 기준 지문에서 몇 번 이상 발견되어야 같은 지문으로 인정할지 결정합니다.")

    if st.button("🚀 대조 및 검수 시작", use_container_width=True):
        with st.spinner('문서를 분석하고 있습니다. 잠시만 기다려주세요...'):
            try:
                # 선택된 이름에 따라 파일 분리
                ref_pdf = next(f for f in uploaded_files if f.name == ref_filename)
                target_pdf = next(f for f in uploaded_files if f.name != ref_filename)
                
                # 텍스트 추출 및 정규화
                ref_pages = extract_text_from_pdf(ref_pdf)
                target_pages = extract_text_from_pdf(target_pdf)
                
                # 기준 지문은 전체를 하나의 거대한 텍스트로 병합
                full_ref_text = normalize_text(" ".join(ref_pages))
                pages_to_delete = []
                
                progress_bar = st.progress(0)
                
                for i, page_text in enumerate(target_pages):
                    norm_target = normalize_text(page_text)
                    
                    # 텍스트가 너무 적은 페이지(문제 번호만 있는 빈 페이지 등)는 지문이 없는 것으로 간주(삭제 대상)
                    if len(norm_target) < chunk_size:
                        pages_to_delete.append(i + 1)
                        continue
                        
                    match_count = 0
                    # 타겟 텍스트를 절반씩 겹치게 잘라서(Sliding Window) 기준 지문 내에 존재하는지 검색
                    step = max(1, chunk_size // 2)
                    
                    for j in range(0, len(norm_target) - chunk_size + 1, step):
                        chunk = norm_target[j:j+chunk_size]
                        if chunk in full_ref_text:
                            match_count += 1
                            if match_count >= min_match_count:
                                break # 충분히 일치하면 더 이상 검사할 필요 없이 유지
                                
                    # 일치 횟수가 기준 미달이면 해당 페이지는 지문이 없는 것으로 판단 (삭제 대상)
                    if match_count < min_match_count:
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
