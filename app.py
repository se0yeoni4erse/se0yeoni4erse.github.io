import streamlit as st
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="PDF 문장/단어 복합 정밀 검수기", layout="wide")

def clean_text(text):
    """최소한의 가공만 거친 텍스트 정제 (소문자화 및 불필요 공백 제거)"""
    return " ".join(text.lower().split())

def split_into_sentences(text):
    """주어진 문장부호(.,!?)를 기준으로 정확하게 문장을 분리"""
    # 문장부호 뒤에 공백이 있거나 없는 경우 모두 대응하여 분리
    sentences = re.split(r'[.!?]+', text)
    valid_sentences = []
    for s in sentences:
        cleaned = s.strip()
        # 의미를 가질 수 있는 최소 글자 수 (띄어쓰기 포함 8글자 이상) 설정
        if len(cleaned) >= 8:
            valid_sentences.append(cleaned.lower())
    return valid_sentences

def extract_keywords(text):
    """텍스트에서 기호를 빼고 순수 단축 토큰(단어) 집합을 생성"""
    # 텍스트 내 알파벳과 숫자가 섞인 단어 단위 추출
    words = re.findall(r'[a-zA-Z0-9가-힣]+', text.lower())
    # 너무 짧은 단어(1~2글자의 관사/조사 등)는 제외하여 핵심 단어만 추출
    return set(w for w in words if len(w) >= 2)

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
st.title("📑 문장 & 단어 복합 정밀 대조 검수기")
st.markdown("기준 지문과 문제 PDF를 대조하여, **지문이 포함되지 않은 문제 페이지 번호**를 엄격하게 추출합니다.")

uploaded_files = st.file_uploader("여기에 두 PDF 파일을 모두 드래그 앤 드롭하세요.", type=["pdf"], accept_multiple_files=True)

if uploaded_files and len(uploaded_files) == 2:
    st.divider()
    file_names = [f.name for f in uploaded_files]
    
    col_select, col_opt = st.columns([2, 1])
    with col_select:
        st.subheader("📌 역할 지정")
        ref_filename = st.selectbox("어느 파일이 '기준 지문(2번 PDF)' 입니까?", file_names)
    
    with col_opt:
        st.subheader("⚙️ 알고리즘 민감도 세팅")
        # 단어 일치 기준 비율 설정
        word_match_rate = st.slider("단어 매칭 인정 기준 비율 (%)", min_value=10, max_value=90, value=30,
                                    help="문장이 완벽히 일치하지 않아도, 문장 내 단어가 이 비율 이상 기준 지문에 존재하면 일치로 인정합니다. 필수 페이지가 빠진다면 이 값을 더 낮춰보세요.")

    if st.button("🚀 복합 정밀 대조 검수 시작", use_container_width=True):
        with st.spinner('문장 분할 및 단어 토큰 교차 분석을 정밀하게 진행 중입니다...'):
            try:
                # 1. 파일 구분
                ref_pdf = next(f for f in uploaded_files if f.name == ref_filename)
                target_pdf = next(f for f in uploaded_files if f.name != ref_filename)
                
                # 2. 텍스트 추출
                ref_pages = extract_text_from_pdf(ref_pdf)
                target_pages = extract_text_from_pdf(target_pdf)
                
                # 3. 기준 지문 전체의 문장 및 단어 풀(Pool) 생성
                combined_ref_text = " ".join(ref_pages)
                normalized_ref_text = clean_text(combined_ref_text)
                ref_keywords_pool = extract_keywords(combined_ref_text)
                
                pages_to_delete = []
                log_data = []
                
                progress_bar = st.progress(0)
                
                # 4. 검사 대상 문제지 페이지별 정밀 분석
                for i, page_text in enumerate(target_pages):
                    page_num = i + 1
                    sentences = split_into_sentences(page_text)
                    
                    # 텍스트나 문장 구분이 안 되는 완전 빈 페이지 처리
                    if not sentences:
                        pages_to_delete.append(page_num)
                        log_data.append(f"❌ {page_num}페이지: 추출된 유효 문장 없음 (삭제 대상)")
                        continue
                    
                    page_matched = False
                    reason = ""
                    
                    for s in sentences:
                        # [1단계 검증] 문장 전체가 통째로 기준 지문에 포함되는지 확인 (완벽 일치)
                        if s in normalized_ref_text:
                            page_matched = True
                            reason = f"문장 완벽 일치 발견 -> '{s[:30]}...'"
                            break
                        
                        # [2단계 검증] 변형 문제나 OCR 오류 극복을 위한 단어 토큰 단위 분석
                        s_keywords = extract_keywords(s)
                        if s_keywords:
                            # 현재 문장의 단어 중 기준 지문 전체 단어 풀과 겹치는 단어 계산
                            intersect_words = s_keywords & ref_keywords_pool
                            match_ratio = len(intersect_words) / len(s_keywords)
                            
                            # 설정한 단어 인정 비율(기본 30%)을 넘으면 지문이 존재한다고 판단
                            if match_ratio >= (word_match_rate / 100.0):
                                page_matched = True
                                reason = f"단어 복합 매칭 성공 (일치율: {match_ratio*100:.1f}%) -> 핵심단어 포함"
                                break
                    
                    # 판정 결과 저장
                    if page_matched:
                        log_data.append(f"✅ {page_num}페이지: 유지 [{reason}]")
                    else:
                        pages_to_delete.append(page_num)
                        log_data.append(f"🗑️ {page_num}페이지: 지문 불일치 -> 삭제 대상")
                        
                    progress_bar.progress(page_num / len(target_pages))
                
                # 5. 최종 결과 출력
                final_result = format_page_ranges(pages_to_delete)
                
                st.success("✅ 정밀 복합 대조 완료!")
                st.markdown("### 🗑️ 최종 삭제 대상 페이지")
                st.error(f"**{final_result}**")
                
                st.markdown("---")
                with st.expander("🔍 페이지별 알고리즘 판정 세부 로그 보기"):
                    for log_msg in log_data:
                        st.text(log_msg)
                        
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

elif uploaded_files and len(uploaded_files) != 2:
    st.warning(f"현재 {len(uploaded_files)}개의 파일이 업로드되었습니다. 정확히 2개의 파일을 업로드해 주세요.")
