import streamlit as st
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="PDF 지문 스스로 검수기 (AI Heuristic)", layout="wide")

def extract_english_sentences(text):
    """
    한국어 및 불필요한 기호를 배제하고 순수 영어 문장 단위로 분리하여 추출
    """
    # 1. 한글 및 특수기호 제거 (영어, 숫자, 기본 문장부호만 남김)
    text = re.sub(r'[가-힣]', ' ', text)
    # 2. 문장 부호(. ! ?)를 기준으로 텍스트 분할
    raw_sentences = re.split(r'[.!?]+', text)
    
    sentences = []
    for s in raw_sentences:
        # 순수 영어 단어(알파벳)만 추출
        words = re.findall(r'[a-zA-Z]{2,}', s.lower())
        if len(words) >= 4: # 영어 단어가 4개 이상인 의미 있는 문장만 취급
            sentences.append({
                "original": s.strip().replace('\n', ' '),
                "words": set(words)
            })
    return sentences

def extract_text_from_pdf(uploaded_file):
    """PDF에서 페이지별 텍스트 추출"""
    uploaded_file.seek(0)
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [page.get_text() for page in doc]

def format_page_ranges(pages):
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

# --- UI 세팅 ---
st.title("🧠 PDF 지문 독립 판단 검수기 (영어 문장 기반)")
st.markdown("한국어 해설과 문제 번호를 무시하고, **오직 영어 지문의 문맥을 스스로 파악하여** 검수합니다.")

uploaded_files = st.file_uploader("여기에 두 PDF 파일을 모두 드래그 앤 드롭하세요.", type=["pdf"], accept_multiple_files=True)

if uploaded_files and len(uploaded_files) == 2:
    st.divider()
    file_names = [f.name for f in uploaded_files]
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📌 기준 문서 설정")
        ref_filename = st.selectbox("어느 파일이 '기준 지문(2번 PDF)' 입니까?", file_names)
    
    with col2:
        st.subheader("⚙️ AI 판단 민감도")
        similarity_threshold = st.slider("문장 일치 판단 기준 (%)", min_value=30, max_value=100, value=60,
                                         help="변형 문제의 (a), (b) 기호 추가를 감안하여 두 문장의 핵심 영어 단어가 몇 % 일치하면 같은 문장으로 볼지 결정합니다.")
        min_sentences_to_pass = st.number_input("페이지 합격 최소 문장 수", min_value=1, max_value=10, value=2,
                                                help="한 페이지 안에서 위 기준을 통과한 문장이 이 숫자만큼 발견되면, 해당 지문이 포함된 문제로 최종 판단합니다.")

    if st.button("🚀 문맥 기반 검수 시작", use_container_width=True):
        with st.spinner('영어 문맥을 스스로 분석하며 페이지를 판별 중입니다...'):
            try:
                # 1. 파일 구분 및 텍스트 추출
                ref_pdf = next(f for f in uploaded_files if f.name == ref_filename)
                target_pdf = next(f for f in uploaded_files if f.name != ref_filename)
                
                ref_pages_text = extract_text_from_pdf(ref_pdf)
                target_pages_text = extract_text_from_pdf(target_pdf)
                
                # 2. 기준 지문의 전체 영어 문장 풀(Pool) 생성
                combined_ref_text = " ".join(ref_pages_text)
                ref_sentences = extract_english_sentences(combined_ref_text)
                
                pages_to_delete = []
                log_data = []
                progress_bar = st.progress(0)
                
                # 3. 타겟(문제지) 페이지별 독립 분석
                for i, page_text in enumerate(target_pages_text):
                    page_num = i + 1
                    target_sentences = extract_english_sentences(page_text)
                    
                    if not target_sentences:
                        pages_to_delete.append(page_num)
                        log_data.append(f"❌ {page_num}페이지: 영어 지문 없음 (삭제 대상)")
                        continue
                    
                    matched_count = 0
                    page_log = []
                    
                    # 해당 페이지의 각 영어 문장이 기준 지문에 존재하는지 검사
                    for t_sent in target_sentences:
                        best_match_ratio = 0
                        best_ref_sent = ""
                        
                        for r_sent in ref_sentences:
                            # 두 문장의 단어 교집합 비율 계산 (Jaccard Similarity 활용)
                            intersection = t_sent['words'].intersection(r_sent['words'])
                            if len(t_sent['words']) == 0: continue
                            
                            ratio = (len(intersection) / len(t_sent['words'])) * 100
                            if ratio > best_match_ratio:
                                best_match_ratio = ratio
                                best_ref_sent = r_sent['original']
                        
                        # 설정된 민감도(%)를 넘으면 일치하는 문장으로 '스스로 판단'
                        if best_match_ratio >= similarity_threshold:
                            matched_count += 1
                            page_log.append(f"   - [일치율 {best_match_ratio:.0f}%] 문제: {t_sent['original'][:40]}... -> 기준: {best_ref_sent[:40]}...")
                    
                    # 최종 결론 도출: 일치하는 문장이 기준치 이상인가?
                    if matched_count >= min_sentences_to_pass:
                        log_data.append(f"✅ {page_num}페이지: 유지 (일치 문장 {matched_count}개 발견)")
                        log_data.extend(page_log) # 어떤 문장들이 일치했는지 근거 로그에 추가
                    else:
                        pages_to_delete.append(page_num)
                        log_data.append(f"🗑️ {page_num}페이지: 삭제 대상 (일치 문장 {matched_count}개 부족)")
                    
                    progress_bar.progress(page_num / len(target_pages_text))
                
                # 4. 결과 출력
                final_result = format_page_ranges(pages_to_delete)
                
                st.success("✅ 문맥 기반 검수 완료!")
                st.markdown("### 🗑️ 최종 삭제 대상 페이지")
                st.error(f"**{final_result}**")
                
                st.markdown("---")
                with st.expander("🔍 AI 문맥 판단 근거 (상세 로그 보기)"):
                    st.markdown("코드가 어떤 영어 문장을 보고 같은 지문이라고 '생각'했는지 확인해 보세요.")
                    for log_msg in log_data:
                        st.text(log_msg)
                        
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

elif uploaded_files and len(uploaded_files) != 2:
    st.warning(f"현재 {len(uploaded_files)}개의 파일이 업로드되었습니다. 정확히 2개의 파일을 업로드해 주세요.")
