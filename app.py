import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="메디QR 주간 인사이트",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700&display=swap');
    
    * { font-family: 'Pretendard', sans-serif; }
    
    .main { background: #F7F8FC; }
    
    .metric-card {
        background: white;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border-left: 4px solid #4F6EF7;
    }
    
    .metric-card.green { border-left-color: #22C55E; }
    .metric-card.orange { border-left-color: #F97316; }
    .metric-card.purple { border-left-color: #A855F7; }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1E293B;
        line-height: 1;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
        margin-top: 6px;
        font-weight: 500;
    }
    
    .metric-delta {
        font-size: 0.85rem;
        font-weight: 600;
        margin-top: 8px;
    }
    
    .delta-up { color: #22C55E; }
    .delta-down { color: #EF4444; }
    
    .insight-box {
        background: linear-gradient(135deg, #EEF2FF 0%, #F0F9FF 100%);
        border: 1px solid #C7D2FE;
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0;
    }
    
    .insight-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #3730A3;
        margin-bottom: 12px;
    }
    
    .insight-content {
        font-size: 0.95rem;
        color: #374151;
        line-height: 1.7;
        white-space: pre-wrap;
    }
    
    .section-header {
        font-size: 1.3rem;
        font-weight: 700;
        color: #FFFFFF;
        margin: 24px 0 16px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #E2E8F0;
    }
    
    .upload-hint {
        background: #F0FDF4;
        border: 1px dashed #86EFAC;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        color: #166534;
        font-size: 0.9rem;
    }
    
    div[data-testid="stFileUploader"] {
        border: 2px dashed #C7D2FE;
        border-radius: 12px;
        padding: 8px;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #4F6EF7, #7C3AED);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 24px;
        font-weight: 600;
        font-size: 0.95rem;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 15px rgba(79, 110, 247, 0.3);
    }
    
    .week-tag {
        display: inline-block;
        background: #EEF2FF;
        color: #4F6EF7;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 6px;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
    }

    /* ── 스피너 로딩 (순수 CSS, 타이밍 문제 없음) ── */
    .mq-spinner-wrap {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 80px 0;
        gap: 20px;
        background: #F0FDF4;
        border: 1px dashed #86EFAC;
        border-radius: 12px;
    }
    .mq-spinner-label {
        font-size: 1rem;
        font-weight: 600;
        color: #166534;
        letter-spacing: 0.05em;
    }
    .mq-spinner {
        position: relative;
        width: 72px;
        height: 72px;
    }
    .mq-spinner-bar {
        position: absolute;
        width: 6px;
        height: 16px;
        border-radius: 3px;
        background: #4F6EF7;
        left: 50%;
        top: 50%;
        transform-origin: center 28px;
        animation: mq-fade 1.2s linear infinite;
    }
    @keyframes mq-fade {
        0%   { opacity: 1; }
        100% { opacity: 0.1; }
    }
</style>
""", unsafe_allow_html=True)


# ── 데이터 파싱 함수 ──────────────────────────────────────────────────────────

# 실제로 사용하는 시트만 읽음 (속도 최적화)
NEEDED_SHEETS = [
    'RAW_GA 변환',
    '★약국 - 환급자 수, 메디QR 진입, 바코드 수',
]

@st.cache_data(show_spinner=False)
def parse_excel(file) -> dict:
    """엑셀 파일 → 정제된 데이터프레임 딕셔너리 반환 (필요 시트만 로드)"""
    # 시트 이름 먼저 확인 (전체 읽기 없이)
    import openpyxl
    wb_names = openpyxl.open(file, read_only=True, data_only=True).sheetnames if False else None

    # 필요한 시트만 선택적으로 읽기
    xl = pd.read_excel(file, sheet_name=NEEDED_SHEETS, engine='openpyxl')
    result = {}

    # 1) RAW_GA 변환: 약국별 일별 유입/스캔 데이터
    if 'RAW_GA 변환' in xl:
        df = xl['RAW_GA 변환'].copy()
        # 첫 행을 컬럼명으로 — 중복/NaN 방지
        new_cols = [str(v).strip() if pd.notna(v) else f'_col_{i}' for i, v in enumerate(df.iloc[0])]
        df.columns = new_cols
        df = df.iloc[1:].reset_index(drop=True)
        # 중복 컬럼 제거 (첫 번째만 유지)
        df = df.loc[:, ~df.columns.duplicated()]
        # 필요한 컬럼만 추출
        cols = ['약국', '유입 일자', '방문 페이지', '총 사용자 수', '바코드 사용 유저', '바코드 이벤트 횟수', '유입 매체']
        available = [c for c in cols if c in df.columns]
        df = df[available].copy()
        df.columns = list(df.columns)
        df['유입 일자'] = pd.to_datetime(df['유입 일자'], errors='coerce')
        for c in ['총 사용자 수', '바코드 사용 유저', '바코드 이벤트 횟수']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        df = df.dropna(subset=['유입 일자'])
        df = df[df['약국'].astype(str).str.strip() != '약국 정보 없음']
        result['ga'] = df

    # 4) ★약국 요약 시트 — 누적 주차별 집계 파싱
    sheet_key = '★약국 - 환급자 수, 메디QR 진입, 바코드 수'
    if sheet_key in xl:
        s = xl[sheet_key].copy()
        rows = []
        for i in range(6, min(6+10, len(s))):
            label = str(s.iloc[i, 1]).strip()
            if label in ('nan', '', '변동률'):
                continue
            if not label.startswith('~'):
                continue
            try:
                rows.append({
                    '기준': label,
                    '환급이용자수': float(s.iloc[i, 2]) if str(s.iloc[i, 2]) != 'nan' else None,
                    '메디QR진입유저수': float(s.iloc[i, 3]) if str(s.iloc[i, 3]) != 'nan' else None,
                    '바코드실행유저수': float(s.iloc[i, 4]) if str(s.iloc[i, 4]) != 'nan' else None,
                    '바코드스캔횟수': float(s.iloc[i, 5]) if str(s.iloc[i, 5]) != 'nan' else None,
                })
            except Exception:
                pass
        result['weekly_summary'] = rows

        pharm_rows = []
        for i in range(12, len(s)):
            name = str(s.iloc[i, 1]).strip()
            if name in ('nan', ''):
                continue
            try:
                pharm_rows.append({
                    '약국': name,
                    '환급이용자수': float(s.iloc[i, 2]) if str(s.iloc[i, 2]) != 'nan' else 0,
                    '메디QR진입유저수': float(s.iloc[i, 3]) if str(s.iloc[i, 3]) != 'nan' else 0,
                    '바코드실행유저수': float(s.iloc[i, 4]) if str(s.iloc[i, 4]) != 'nan' else 0,
                    '바코드스캔횟수': float(s.iloc[i, 5]) if str(s.iloc[i, 5]) != 'nan' else 0,
                })
            except Exception:
                pass
        result['pharm_summary'] = pd.DataFrame(pharm_rows)

    return result


def extract_weekly_summary(data: dict) -> pd.DataFrame:
    if 'ga' not in data:
        return pd.DataFrame()
    df = data['ga'].copy()
    df['주차'] = df['유입 일자'].dt.to_period('W').astype(str)
    grp = df.groupby(['약국', '주차']).agg(
        총사용자=('총 사용자 수', 'sum'),
        바코드사용자=('바코드 사용 유저', 'sum'),
        바코드스캔=('바코드 이벤트 횟수', 'sum'),
    ).reset_index()
    return grp


def compute_wow(weekly: pd.DataFrame) -> pd.DataFrame:
    if weekly.empty:
        return pd.DataFrame()
    weeks = sorted(weekly['주차'].unique())
    if len(weeks) < 2:
        return pd.DataFrame()
    prev_w, curr_w = weeks[-2], weeks[-1]
    prev = weekly[weekly['주차'] == prev_w].set_index('약국')
    curr = weekly[weekly['주차'] == curr_w].set_index('약국')
    combined = curr.join(prev, lsuffix='_현재', rsuffix='_이전', how='outer').fillna(0)
    for col in ['총사용자', '바코드사용자', '바코드스캔']:
        combined[f'{col}_증감률'] = combined.apply(
            lambda r: (r[f'{col}_현재'] - r[f'{col}_이전']) / r[f'{col}_이전'] * 100
            if r[f'{col}_이전'] > 0 else None, axis=1
        )
    combined = combined.reset_index()
    combined.columns.name = None
    return combined, prev_w, curr_w


def generate_insights(main_df: pd.DataFrame, compare_df: pd.DataFrame = None) -> list:
    insights = []
    total_users = int(main_df['총 사용자 수'].sum())
    total_scans = int(main_df['바코드 이벤트 횟수'].sum())
    total_pharmacies = main_df['약국'].nunique()
    conv_rate = total_scans / total_users * 100 if total_users > 0 else 0

    if compare_df is not None:
        prev_users = int(compare_df['총 사용자 수'].sum())
        prev_scans = int(compare_df['바코드 이벤트 횟수'].sum())
        prev_pharmacies = compare_df['약국'].nunique()
        user_chg = (total_users - prev_users) / prev_users * 100 if prev_users > 0 else 0
        scan_chg = (total_scans - prev_scans) / prev_scans * 100 if prev_scans > 0 else 0
        pharm_chg = total_pharmacies - prev_pharmacies
        arrow_u = "▲" if user_chg >= 0 else "▼"
        arrow_s = "▲" if scan_chg >= 0 else "▼"
        color_u = "🟢" if user_chg >= 0 else "🔴"
        color_s = "🟢" if scan_chg >= 0 else "🔴"
        insights.append({
            "type": "summary",
            "title": "📊 전주 대비 전체 변화",
            "items": [
                f"{color_u} 총 방문자: {prev_users:,} → {total_users:,}명 ({arrow_u} {abs(user_chg):.1f}%)",
                f"{color_s} 바코드 스캔: {prev_scans:,} → {total_scans:,}회 ({arrow_s} {abs(scan_chg):.1f}%)",
                f"{'🟢' if pharm_chg >= 0 else '🔴'} 활성 약국: {prev_pharmacies} → {total_pharmacies}개 ({'+' if pharm_chg >= 0 else ''}{pharm_chg}개)",
            ]
        })

    if compare_df is not None:
        curr_p = main_df.groupby('약국')['총 사용자 수'].sum().reset_index(name='현재')
        prev_p = compare_df.groupby('약국')['총 사용자 수'].sum().reset_index(name='이전')
        merged = curr_p.merge(prev_p, on='약국', how='outer').fillna(0)
        merged['증감률'] = merged.apply(
            lambda r: (r['현재'] - r['이전']) / r['이전'] * 100 if r['이전'] > 0 else None, axis=1
        )
        merged = merged.dropna(subset=['증감률'])
        surge = merged[merged['증감률'] >= 30].sort_values('증감률', ascending=False).head(3)
        drop = merged[merged['증감률'] <= -30].sort_values('증감률').head(3)
        surge_items = [f"🔥 {r['약국']}: {int(r['이전'])}명 → {int(r['현재'])}명 (+{r['증감률']:.0f}%)" for _, r in surge.iterrows()]
        drop_items = [f"❄️ {r['약국']}: {int(r['이전'])}명 → {int(r['현재'])}명 ({r['증감률']:.0f}%)" for _, r in drop.iterrows()]
        if surge_items:
            insights.append({"type": "alert_up", "title": "🔥 급등 약국 (전주 대비 +30% 이상)", "items": surge_items})
        if drop_items:
            insights.append({"type": "alert_down", "title": "❄️ 급감 약국 (전주 대비 -30% 이하)", "items": drop_items})
        new_pharm = set(main_df['약국'].unique()) - set(compare_df['약국'].unique())
        lost_pharm = set(compare_df['약국'].unique()) - set(main_df['약국'].unique())
        entry_items = []
        if new_pharm:
            entry_items.append(f"🆕 신규 진입: {', '.join(sorted(new_pharm))}")
        if lost_pharm:
            entry_items.append(f"⚠️ 데이터 미집계: {', '.join(sorted(lost_pharm))}")
        if entry_items:
            insights.append({"type": "info", "title": "🏪 약국 변동", "items": entry_items})

    pharm_df = main_df.groupby('약국').agg(
        총사용자=('총 사용자 수', 'sum'),
        바코드사용자=('바코드 사용 유저', 'sum'),
    ).reset_index()
    pharm_df['전환율'] = pharm_df.apply(
        lambda r: r['바코드사용자'] / r['총사용자'] * 100 if r['총사용자'] > 0 else 0, axis=1
    )
    high_conv = pharm_df[(pharm_df['총사용자'] >= 3) & (pharm_df['전환율'] >= 20)].sort_values('전환율', ascending=False).head(3)
    zero_conv = pharm_df[(pharm_df['총사용자'] >= 5) & (pharm_df['전환율'] == 0)].sort_values('총사용자', ascending=False).head(3)
    conv_items = []
    if not high_conv.empty:
        conv_items += [f"✅ {r['약국']}: 전환율 {r['전환율']:.0f}% ({int(r['바코드사용자'])}/{int(r['총사용자'])}명)" for _, r in high_conv.iterrows()]
    if not zero_conv.empty:
        conv_items += [f"🚨 {r['약국']}: 방문자 {int(r['총사용자'])}명이지만 바코드 스캔 0회" for _, r in zero_conv.iterrows()]
    if conv_items:
        insights.append({"type": "conversion", "title": f"🎯 바코드 전환율 분석 (전체 평균: {conv_rate:.1f}%)", "items": conv_items})

    if '유입 매체' in main_df.columns:
        media_df = main_df.groupby('유입 매체').agg(
            총사용자=('총 사용자 수', 'sum'),
            바코드스캔=('바코드 이벤트 횟수', 'sum'),
        ).reset_index()
        media_df['효율'] = media_df.apply(
            lambda r: r['바코드스캔'] / r['총사용자'] * 100 if r['총사용자'] > 0 else 0, axis=1
        )
        media_df = media_df.sort_values('효율', ascending=False)
        top_media = media_df.iloc[0] if len(media_df) > 0 else None
        low_media = media_df[media_df['총사용자'] >= 5].sort_values('효율').iloc[0] if len(media_df[media_df['총사용자'] >= 5]) > 0 else None
        media_items = [f"방문자 {int(r['총사용자'])}명 / 스캔 {int(r['바코드스캔'])}회 / 효율 {r['효율']:.1f}% — {r['유입 매체']}" for _, r in media_df.iterrows()]
        if top_media is not None:
            media_items.append(f"👑 최고 효율 매체: {top_media['유입 매체']} ({top_media['효율']:.1f}%)")
        if low_media is not None:
            media_items.append(f"💡 개선 필요 매체: {low_media['유입 매체']} ({low_media['효율']:.1f}%)")
        insights.append({"type": "media", "title": "📣 유입 매체별 효율", "items": media_items})

    actions = []
    if conv_rate < 10:
        actions.append("📌 전체 바코드 전환율이 낮습니다. QR 위치 및 안내 문구 점검을 권장합니다.")
    if conv_rate >= 20:
        actions.append("📌 전체 전환율이 양호합니다. 우수 약국의 운영 방식을 다른 약국에 공유해보세요.")
    if compare_df is not None and user_chg >= 20:
        actions.append("📌 방문자가 크게 늘었습니다. 스캔 전환 유도를 강화할 좋은 시점입니다.")
    if compare_df is not None and user_chg <= -20:
        actions.append("📌 방문자가 감소했습니다. 제작물 노출 상태를 현장 점검해보세요.")
    if not zero_conv.empty:
        actions.append(f"📌 바코드 스캔이 0인 약국({len(zero_conv)}곳)에 QR 인식 테스트 및 위치 재점검이 필요합니다.")
    if not actions:
        actions.append("📌 전반적으로 안정적인 운영 중입니다. 매주 전환율 트렌드를 모니터링하세요.")
    insights.append({"type": "action", "title": "✅ 이번 주 액션 아이템", "items": actions})

    return insights


# ── UI ───────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
    <span style="font-size:2rem">💊</span>
    <div>
        <div style="font-size:1.6rem; font-weight:800; color:#FFFFFF; line-height:1.2">메디QR 주간 인사이트</div>
        <div style="font-size:0.9rem; color:#CBD5E1; margin-top:2px">엑셀 파일을 업로드하면 AI가 주간 변화를 분석해드립니다</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── session_state 초기화 ──
if 'run_analysis' not in st.session_state:
    st.session_state['run_analysis'] = False
if 'prev_file_count' not in st.session_state:
    st.session_state['prev_file_count'] = 0
if 'datasets' not in st.session_state:
    st.session_state['datasets'] = {}
if 'main_key' not in st.session_state:
    st.session_state['main_key'] = None
if 'prev_key' not in st.session_state:
    st.session_state['prev_key'] = None
if 'do_parse' not in st.session_state:
    st.session_state['do_parse'] = False

# ── 사이드바 ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 파일 업로드")
    st.markdown("이전 주차(A) + 현재 주차(B) 파일을 업로드하세요")

    uploaded_files = st.file_uploader(
        "엑셀 파일 2개 업로드",
        type=['xlsx'],
        accept_multiple_files=True,
        help="A파일(지난 주 누적) + B파일(이번 주 누적)"
    )

    curr_count = len(uploaded_files) if uploaded_files else 0

    # 파일 수 줄면 분석 상태 초기화 → 버튼 재활성화
    if curr_count < st.session_state['prev_file_count']:
        st.session_state['run_analysis'] = False
        st.session_state['datasets'] = {}
    st.session_state['prev_file_count'] = curr_count

    # 파일 2개 시 + 드롭존 숨김
    if curr_count >= 2:
        st.markdown(
            "<style>[data-testid='stFileUploaderDropzone']{display:none!important}</style>",
            unsafe_allow_html=True
        )

    # 파일 2개일 때 드롭다운 + 버튼 노출
    if curr_count >= 2:
        # 이번 주 / 지난 주 파일 선택 드롭다운 (버튼 바로 위)
        file_names = [f.name for f in uploaded_files]
        saved_main = st.session_state.get('main_key')
        saved_prev = st.session_state.get('prev_key')
        main_idx = file_names.index(saved_main) if saved_main in file_names else len(file_names)-1
        prev_idx = file_names.index(saved_prev) if saved_prev in file_names else 0
        selected_main = st.selectbox("📅 이번 주 파일", file_names, index=main_idx, key="sb_main")
        selected_prev = st.selectbox("📅 지난 주 파일", file_names, index=prev_idx, key="sb_prev")
        st.session_state['main_key'] = selected_main
        st.session_state['prev_key'] = selected_prev

        already_done = st.session_state['run_analysis']
        if already_done:
            st.button("✅ 분석 완료", type="primary", use_container_width=True, disabled=True)
        else:
            if st.button("🔍 분석 시작하기", type="primary", use_container_width=True):
                st.session_state['do_parse'] = True

    st.divider()
    st.markdown("### ⚙️ 설정")
    show_raw = st.toggle("📋 원시 데이터 보기", value=False)

    st.divider()
    st.markdown("""
    <div style="font-size:0.8rem; color:#94A3B8; line-height:1.6">
    <b>지원 시트</b><br>
    • RAW_GA 변환 (핵심)<br>
    • 제작물 리스트<br>
    • 요약 시트<br>
    • 환급 데이터
    </div>
    """, unsafe_allow_html=True)

# ── 메인 영역 ─────────────────────────────────────────────────────────────────

# 상태 1: 파일 미업로드 또는 1개만 업로드
if not uploaded_files or curr_count < 2:
    st.markdown("""
    <div class="upload-hint">
        <div style="font-size:2rem; margin-bottom:8px">📊</div>
        <div style="font-weight:600; font-size:1rem; margin-bottom:4px">왼쪽 사이드바에서 엑셀 파일 2개를 업로드하세요</div>
        <div>A파일(지난 주 누적) + B파일(이번 주 누적)</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# 상태 2: 파일 2개 업로드 완료, 버튼 미클릭 (do_parse 아닐 때만 멈춤)
if not st.session_state['run_analysis'] and not st.session_state.get('do_parse'):
    st.markdown("""
    <div class="upload-hint">
        <div style="font-size:2rem; margin-bottom:8px">📊</div>
        <div style="font-weight:600; font-size:1rem; margin-bottom:4px">왼쪽 사이드바에서 엑셀 파일 2개를 업로드하세요</div>
        <div>A파일(지난 주 누적) + B파일(이번 주 누적)</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# 상태 3: 분석 시작 버튼 눌린 직후 → 스피너 표시 후 파싱
if st.session_state.get('do_parse'):
    # CSS 스피너 즉시 렌더 (rerun으로 화면에 먼저 표시됨)
    n_bars = 12
    bars_html = ""
    for i in range(n_bars):
        angle = i * (360 / n_bars)
        delay = -(1.2 - i * (1.2 / n_bars))
        bars_html += f'<div class="mq-spinner-bar" style="transform:rotate({angle}deg) translateX(-50%);animation-delay:{delay:.2f}s"></div>'
    
    spinner_slot = st.empty()
    spinner_slot.markdown(f"""
<div class="mq-spinner-wrap">
  <div class="mq-spinner-label">분석중</div>
  <div class="mq-spinner">{bars_html}</div>
</div>
""", unsafe_allow_html=True)

    # 파싱 실행 (스피너가 화면에 표시된 상태에서)
    datasets_new = {}
    for f in uploaded_files:
        datasets_new[f.name] = parse_excel(f)
    st.session_state['datasets'] = datasets_new
    keys_list = list(datasets_new.keys())
    st.session_state['main_key'] = keys_list[-1]
    st.session_state['prev_key'] = keys_list[0] if len(keys_list) > 1 else None
    st.session_state['do_parse'] = False
    st.session_state['run_analysis'] = True
    spinner_slot.empty()
    st.rerun()

# 파싱 완료된 데이터 사용
datasets = st.session_state['datasets']
main_key = st.session_state['main_key']
prev_key = st.session_state['prev_key']

main_data = datasets[main_key]
compare_data = datasets[prev_key] if prev_key and prev_key in datasets else None

tabs = st.tabs(["📈 주간 요약", "🏪 약국별 분석", "🎯 디자인물 분석", "💡 자동 인사이트"])


# ── 탭 1: 주간 요약 ──────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown('<div class="section-header">전체 지표 요약</div>', unsafe_allow_html=True)

    if 'ga' in main_data:
        df = main_data['ga']

        def get_latest_summary(data):
            rows = data.get('weekly_summary', [])
            if rows:
                return rows[-1]
            return None

        curr_sum = get_latest_summary(main_data)
        prev_sum = get_latest_summary(compare_data) if compare_data else None

        if curr_sum and prev_sum:
            new_visitors = int((curr_sum.get('메디QR진입유저수') or 0) - (prev_sum.get('메디QR진입유저수') or 0))
            new_barcode_users = int((curr_sum.get('바코드실행유저수') or 0) - (prev_sum.get('바코드실행유저수') or 0))
            prev_visitors = int(prev_sum.get('메디QR진입유저수') or 0)
            prev_barcode = int(prev_sum.get('바코드실행유저수') or 0)
            has_compare = True
        elif curr_sum:
            new_visitors = int(curr_sum.get('메디QR진입유저수') or 0)
            new_barcode_users = int(curr_sum.get('바코드실행유저수') or 0)
            prev_visitors = 0
            prev_barcode = 0
            has_compare = False
        else:
            new_visitors = int(df['총 사용자 수'].sum())
            new_barcode_users = int(df['바코드 사용 유저'].sum())
            prev_visitors = 0
            prev_barcode = 0
            has_compare = False

        if compare_data and 'ga' in compare_data:
            prev_max_date = compare_data['ga']['유입 일자'].max()
            new_week_df = df[df['유입 일자'] > prev_max_date]
        else:
            new_week_df = df

        active_pharmacies = new_week_df[new_week_df['바코드 이벤트 횟수'] > 0]['약국'].nunique()
        new_week_visitors = int(new_week_df['총 사용자 수'].sum())
        new_week_barcode = int(new_week_df['바코드 사용 유저'].sum())
        conv_rate = new_week_barcode / new_week_visitors * 100 if new_week_visitors > 0 else 0

        def delta_tag(val, prev_val):
            if prev_val == 0 or not has_compare:
                return '<span style="color:#94A3B8; font-size:0.8rem">누적 대비 이번 주</span>'
            pct = val / prev_val * 100 if prev_val > 0 else 0
            arrow = "▲" if val >= 0 else "▼"
            cls = "delta-up" if val >= 0 else "delta-down"
            return f'<span class="{cls}">{arrow} {abs(pct):.1f}% (전주 누적 대비)</span>'

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{new_visitors:+,}</div>
                <div class="metric-label">이번 주 메디QR 신규 진입</div>
                <div class="metric-delta">{delta_tag(new_visitors, prev_visitors)}</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card green">
                <div class="metric-value">{new_barcode_users:+,}</div>
                <div class="metric-label">이번 주 바코드 실행 유저 증감</div>
                <div class="metric-delta">{delta_tag(new_barcode_users, prev_barcode)}</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card orange">
                <div class="metric-value">{conv_rate:.1f}%</div>
                <div class="metric-label">바코드 전환율</div>
                <div class="metric-delta" style="color:#94A3B8; font-size:0.8rem">이번 주 방문 → 스캔</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class="metric-card purple">
                <div class="metric-value">{active_pharmacies}</div>
                <div class="metric-label">바코드 스캔 활성 약국</div>
                <div class="metric-delta" style="color:#94A3B8; font-size:0.8rem">이번 주 스캔 발생 약국</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-header">일별 방문 트렌드</div>', unsafe_allow_html=True)

        trend_df = new_week_df if (compare_data and 'ga' in compare_data) else df
        daily = trend_df.groupby('유입 일자').agg(
            총사용자=('총 사용자 수', 'sum'),
            바코드스캔=('바코드 이벤트 횟수', 'sum')
        ).reset_index()

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=daily['유입 일자'], y=daily['총사용자'],
                             name='총 방문자', marker_color='#C7D2FE', opacity=0.8), secondary_y=False)
        fig.add_trace(go.Scatter(x=daily['유입 일자'], y=daily['바코드스캔'],
                                 name='바코드 스캔', line=dict(color='#4F6EF7', width=2.5),
                                 mode='lines+markers'), secondary_y=True)
        fig.update_layout(height=320, plot_bgcolor='white', paper_bgcolor='white',
                          margin=dict(l=0, r=0, t=20, b=0),
                          legend=dict(orientation='h', y=1.1))
        fig.update_yaxes(title_text="방문자", secondary_y=False, gridcolor='#F1F5F9')
        fig.update_yaxes(title_text="스캔", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)


# ── 탭 2: 약국별 분석 ────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown('<div class="section-header">약국별 성과</div>', unsafe_allow_html=True)

    if 'ga' in main_data:
        df = main_data['ga']
        pharmacy_df = df.groupby('약국').agg(
            총사용자=('총 사용자 수', 'sum'),
            바코드사용자=('바코드 사용 유저', 'sum'),
            바코드스캔=('바코드 이벤트 횟수', 'sum'),
            방문일수=('유입 일자', 'nunique')
        ).reset_index().sort_values('총사용자', ascending=False)

        pharmacy_df['전환율(%)'] = (pharmacy_df['바코드사용자'] / pharmacy_df['총사용자'] * 100).round(1)

        col1, col2 = st.columns([3, 2])

        with col1:
            st.markdown("**약국별 방문자 TOP 20**")
            top20 = pharmacy_df.head(20)
            fig = px.bar(top20, x='총사용자', y='약국', orientation='h',
                         color='바코드스캔', color_continuous_scale='Blues',
                         labels={'총사용자': '총 방문자', '약국': '', '바코드스캔': '스캔 횟수'})
            fig.update_layout(height=500, plot_bgcolor='white', paper_bgcolor='white',
                               margin=dict(l=0, r=0, t=10, b=0),
                               yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**바코드 전환율 TOP 10** (방문자 3명 이상)")
            top_conv = pharmacy_df[pharmacy_df['총사용자'] >= 3].nlargest(10, '전환율(%)')
            fig2 = px.bar(top_conv, x='전환율(%)', y='약국', orientation='h',
                          color='전환율(%)', color_continuous_scale='Greens')
            fig2.update_layout(height=380, plot_bgcolor='white', paper_bgcolor='white',
                                margin=dict(l=0, r=0, t=10, b=0),
                                yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)

        if compare_data and 'ga' in compare_data:
            st.markdown('<div class="section-header">전주 대비 변화</div>', unsafe_allow_html=True)

            curr_pharm = df.groupby('약국').agg(총사용자=('총 사용자 수', 'sum'), 바코드스캔=('바코드 이벤트 횟수', 'sum')).reset_index()
            prev_pharm = compare_data['ga'].groupby('약국').agg(총사용자=('총 사용자 수', 'sum'), 바코드스캔=('바코드 이벤트 횟수', 'sum')).reset_index()

            merged = curr_pharm.merge(prev_pharm, on='약국', suffixes=('_현재', '_이전'), how='outer').fillna(0)
            merged['방문자_증감'] = merged['총사용자_현재'] - merged['총사용자_이전']
            merged['스캔_증감'] = merged['바코드스캔_현재'] - merged['바코드스캔_이전']
            merged = merged.sort_values('방문자_증감', ascending=False)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**방문자 급등 TOP 5 🔥**")
                top5 = merged.head(5)[['약국', '총사용자_이전', '총사용자_현재', '방문자_증감']]
                top5.columns = ['약국', '이전', '현재', '증감']
                st.dataframe(top5, use_container_width=True, hide_index=True)
            with c2:
                st.markdown("**방문자 급감 TOP 5 ❄️**")
                bot5 = merged.tail(5)[['약국', '총사용자_이전', '총사용자_현재', '방문자_증감']]
                bot5.columns = ['약국', '이전', '현재', '증감']
                st.dataframe(bot5, use_container_width=True, hide_index=True)


# ── 탭 3: 디자인물 분석 ──────────────────────────────────────────────────────
with tabs[2]:
    st.markdown('<div class="section-header">유입 매체(디자인물)별 성과</div>', unsafe_allow_html=True)

    if 'ga' in main_data:
        df = main_data['ga']

        if '유입 매체' in df.columns:
            media_df = df.groupby('유입 매체').agg(
                총사용자=('총 사용자 수', 'sum'),
                바코드스캔=('바코드 이벤트 횟수', 'sum'),
                약국수=('약국', 'nunique')
            ).reset_index().sort_values('총사용자', ascending=False)

            c1, c2 = st.columns(2)
            with c1:
                fig = px.pie(media_df, values='총사용자', names='유입 매체',
                             title='유입 매체별 방문자 비중',
                             color_discrete_sequence=px.colors.qualitative.Set3)
                fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig2 = px.bar(media_df, x='유입 매체', y=['총사용자', '바코드스캔'],
                              barmode='group', title='매체별 방문자 vs 스캔',
                              color_discrete_map={'총사용자': '#C7D2FE', '바코드스캔': '#4F6EF7'})
                fig2.update_layout(height=350, plot_bgcolor='white', paper_bgcolor='white',
                                    margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig2, use_container_width=True)

            st.markdown("**매체별 상세 지표**")
            media_df['스캔전환율(%)'] = (media_df['바코드스캔'] / media_df['총사용자'] * 100).round(1)
            st.dataframe(media_df, use_container_width=True, hide_index=True)

        if '방문 페이지' in df.columns:
            st.markdown('<div class="section-header">방문 페이지별 분석</div>', unsafe_allow_html=True)
            page_df = df.groupby('방문 페이지').agg(
                총사용자=('총 사용자 수', 'sum'),
                바코드스캔=('바코드 이벤트 횟수', 'sum')
            ).reset_index().sort_values('총사용자', ascending=False)

            fig3 = px.bar(page_df, x='방문 페이지', y='총사용자',
                          color='바코드스캔', color_continuous_scale='Blues',
                          title='방문 페이지별 사용자 수')
            fig3.update_layout(height=300, plot_bgcolor='white', paper_bgcolor='white',
                                margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig3, use_container_width=True)


# ── 탭 4: 자동 인사이트 ───────────────────────────────────────────────────────
with tabs[3]:
    st.markdown('<div class="section-header">💡 자동 인사이트</div>', unsafe_allow_html=True)

    if 'ga' not in main_data:
        st.warning("RAW_GA 변환 시트가 없어 분석이 불가합니다.")
    else:
        compare_df_for_insight = compare_data['ga'] if compare_data and 'ga' in compare_data else None
        insights = generate_insights(main_data['ga'], compare_df_for_insight)

        style_map = {
            "summary":    ("linear-gradient(135deg,#EEF2FF,#F0F9FF)", "#C7D2FE", "#3730A3"),
            "alert_up":   ("linear-gradient(135deg,#F0FDF4,#ECFDF5)", "#86EFAC", "#166534"),
            "alert_down": ("linear-gradient(135deg,#FFF7ED,#FEF2F2)", "#FCA5A5", "#991B1B"),
            "conversion": ("linear-gradient(135deg,#FFFBEB,#FFF7ED)", "#FDE68A", "#92400E"),
            "media":      ("linear-gradient(135deg,#F5F3FF,#EFF6FF)", "#DDD6FE", "#4C1D95"),
            "action":     ("linear-gradient(135deg,#F0FDF4,#EFF6FF)", "#6EE7B7", "#065F46"),
            "info":       ("linear-gradient(135deg,#F8FAFC,#F1F5F9)", "#CBD5E1", "#334155"),
        }

        for ins in insights:
            bg, border, title_color = style_map.get(ins["type"], style_map["info"])
            items_html = "".join(f"<div style='margin:6px 0; font-size:0.95rem; color:#374151'>{item}</div>" for item in ins["items"])
            st.markdown(f"""
            <div style="background:{bg}; border:1px solid {border}; border-radius:16px; padding:20px 24px; margin:12px 0;">
                <div style="font-size:1.05rem; font-weight:700; color:{title_color}; margin-bottom:10px">{ins['title']}</div>
                {items_html}
            </div>
            """, unsafe_allow_html=True)

        if compare_df_for_insight is None:
            st.info("💡 **이전 주차 파일도 함께 업로드하면** 전주 대비 급등/급감 약국 및 주차별 변화 분석이 추가됩니다.")

# 원시 데이터
if show_raw and 'ga' in main_data:
    st.divider()
    st.markdown("**📋 원시 데이터 (GA 변환)**")
    st.dataframe(main_data['ga'].head(100), use_container_width=True)
