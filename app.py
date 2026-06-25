import streamlit as st
import fitz  # PyMuPDF
import re

# 화면을 더 넓게 쓰도록 layout="wide" 적용
st.set_page_config(page_title="PDF 지문 대조 검수기 (정밀 분석판)", layout="wide")

def normalize_text(text):
    """공백 및 특수문자를 모두 제거하고 소문자로 변환하여 순수 문자만 남김"""
    # 1. 띄어쓰기, 줄바꿈 탭 등 모든 여백 완벽 제거
    text = re.sub(r'\s+', '', text)
    # 2. 알파벳, 숫자, 한글을 제외한 모든 기호(마침표, 쉼표, 괄호 등) 제거
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
    start = end = pages[0]
    
    for p in pages[1:]:
        if p == end + 1:
            end = p
        else:
            ranges.append(f"{start}" if start == end else f"{start}-{end}")
            start = end = p
    ranges.append(f"{start}" if start == end else f"{start}-{end}")
    return ",".join(ranges)

# --- UI 화면 구성 ---
st.title("📑 PDF 지문 대조 검수기 (정밀 분석판)")
st.markdown("기준 지문(2번)과 검사할 문제지(1번)를 **동시에 업로드**해 주세요.")

uploaded_files = st.file_uploader("여기에 두 PDF 파일을 모두 드래그 앤 드롭하세요", type=["pdf"], accept_multiple_files=True)

if uploaded_files and len(uploaded_files) == 2:
    st.divider()
    file_names = [f.name for f in uploaded_files]
    
    # 화면을 두 칸으로 나누어 세팅창을 깔끔하게 배치
    col_select, col_opt = st.columns([2, 1])
    with col_select:
        st.subheader("📌 역할 지정")
        ref_filename = st.selectbox("어느 파일이 '기준 지문(2번)' 입니까?", file_names)
    
    with col_opt:
        st.subheader("⚙️ 상세 설정")
        chunk_size = st.number_input("검사 조각 크기 (기본 15)", min_value=5, max_value=50, value=15,
                                     help="텍스트를 몇 글자 단위로 쪼개서 검사할지 정합니다.")
        min_match_count = st.number_input("최소 일치 횟수 (기본 2)", min_value=1, max_value=10, value=2,
                                          help="위 조각이 몇 번 발견되어야 합격(유지)시킬지 정합니다.")

    if st.button("🚀 정밀 대조 및 검수 시작", use_container_width=True):
        with st.spinner('문서를 꼼꼼히 분석하고 있습니다... (페이지 수에 따라 1~2분 소요)'):
            try:
                # 선택된 이름에 따라 파일 분리
                ref_pdf = next(f for f in uploaded_files if f.name == ref_filename)
                target_pdf = next(f for f in uploaded_files if f.name != ref_filename)
                
                ref_pages = extract_text_from_pdf(ref_pdf)
                target_pages = extract_text_from_pdf(target_pdf)
                
                full_ref_text = normalize_text(" ".join(ref_pages))
                
                pages_to_delete = []
                log_data = [] # 분석 과정을 기록할 리스트
                
                progress_bar = st.progress(0)
                
                for i, page_text in enumerate(target_pages):
                    page_num = i + 1
                    norm_target = normalize_text(page_text)
                    
                    # 텍스트가 너무 적은 페이지(문제 번호만 있는 빈 페이지 등)
                    if len(norm_target) < chunk_size:
                        pages_to_delete.append(page_num)
                        log_data.append(f"❌ {page_num}페이지: 텍스트 부족 (삭제 대상)")
                        continue
                        
                    match_count = 0
                    matched_chunks = []
                    step = max(1, chunk_size // 2)
                    
                    # 슬라이딩 윈도우 조각 검사
                    for j in range(0, len(norm_target) - chunk_size + 1, step):
                        chunk = norm_target[j:j+chunk_size]
                        if chunk in full_ref_text:
                            match_count += 1
                            matched_chunks.append(chunk)
                            if match_count >= min_match_count:
                                break
                                
                    # 검사 결과 기록 및 판정
                    if match_count < min_match_count:
                        pages_to_delete.append(page_num)
                        log_data.append(f"🗑️ {page_num}페이지: 지문 불일치 (발견된 조각: {match_count}개) -> 삭제 대상")
                    else:
                        # 어떤 글자 조각이 매칭되었는지 로그에 기록
                        log_data.append(f"✅ {page_num}페이지: 지문 일치 (유지) / 매칭된 텍스트 일부: '{matched_chunks[0]}'")
                        
                    progress_bar.progress(page_num / len(target_pages))
                
                final_result = format_page_ranges(pages_to_delete)
                
                st.success("✅ 모든 페이지 검수 완료!")
                
                st.markdown("### 🗑️ 최종 삭제 대상 페이지 번호")
                st.error(f"**{final_result}**")
                
                # 상세 분석 로그창 추가 (펼쳐서 확인 가능)
                st.markdown("---")
                with st.expander("🔍 페이지별 상세 분석 로그 보기 (클릭하여 펼치기)"):
                    st.markdown("각 페이지가 **왜 유지되고 왜 삭제되었는지** 확인할 수 있습니다.")
                    for log_msg in log_data:
                        st.text(log_msg)
                        
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

elif uploaded_files and len(uploaded_files) != 2:
    st.warning(f"현재 {len(uploaded_files)}개의 파일이 업로드되었습니다. 정확히 2개의 파일을 업로드해 주세요.")
