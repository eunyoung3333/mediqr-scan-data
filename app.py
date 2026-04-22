import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import requests
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="메디QR 주간 인사이트",
    page_icon="💊",
    layout="wide",
    color= "#FFFFFF"
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
        color: #1E293B;
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
</style>
""", unsafe_allow_html=True)


# ── 유틸 함수 ────────────────────────────────────────────────────────────────

def flatten_and_clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼명 정리: 공백 제거 / 멀티헤더 평탄화 / 중복 컬럼명 유니크 처리"""
    cols = []

    for col in df.columns:
        if isinstance(col, tuple):
            col = " ".join(
                [str(x).strip() for x in col if pd.notna(x) and str(x).strip() != ""]
            )
        else:
            col = str(col).strip()

        col = col.replace("\n", " ").replace("\r", " ")
        col = " ".join(col.split())
        cols.append(col)

    seen = {}
    unique_cols = []
    for col in cols:
        if col in seen:
            seen[col] += 1
            unique_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            unique_cols.append(col)

    df.columns = unique_cols
    return df


def make_first_row_header(df: pd.DataFrame) -> pd.DataFrame:
    """첫 행을 헤더로 승격한 뒤 컬럼 정리"""
    if df.empty:
        return df

    header = []
    for col in df.iloc[0].tolist():
        if pd.isna(col):
            header.append("")
        else:
            val = str(col).strip().replace("\n", " ").replace("\r", " ")
            val = " ".join(val.split())
            header.append(val)

    df = df.iloc[1:].reset_index(drop=True).copy()
    df.columns = header
    df = flatten_and_clean_columns(df)
    df = df.loc[:, [c != "" for c in df.columns]]
    return df


def get_first_matching_column(df: pd.DataFrame, base_name: str):
    """중복/변형 컬럼명 대응: base_name 또는 base_name_* 중 첫 번째 컬럼 반환"""
    if base_name in df.columns:
        return base_name

    candidates = [c for c in df.columns if str(c).strip().startswith(base_name)]
    return candidates[0] if candidates else None


def safe_divide(numerator, denominator):
    if denominator in [0, None] or pd.isna(denominator):
        return 0
    return numerator / denominator


# ── 데이터 파싱 함수 ──────────────────────────────────────────────────────────

def parse_excel(file) -> dict:
    """엑셀 파일 → 정제된 데이터프레임 딕셔너리 반환"""
    xl = pd.read_excel(file, sheet_name=None)
    result = {}

    # 1) RAW_GA 변환: 약국별 일별 유입/스캔 데이터
    if 'RAW_GA 변환' in xl:
        df = xl['RAW_GA 변환'].copy()
        df = make_first_row_header(df)

        # 표준 컬럼명 보정
        standard_map = {
            '약국': get_first_matching_column(df, '약국'),
            '유입 일자': get_first_matching_column(df, '유입 일자'),
            '방문 페이지': get_first_matching_column(df, '방문 페이지'),
            '총 사용자 수': get_first_matching_column(df, '총 사용자 수'),
            '바코드 사용 유저': get_first_matching_column(df, '바코드 사용 유저'),
            '바코드 이벤트 횟수': get_first_matching_column(df, '바코드 이벤트 횟수'),
            '유입 매체': get_first_matching_column(df, '유입 매체'),
        }

        for standard_name, actual_name in standard_map.items():
            if actual_name and standard_name not in df.columns:
                df[standard_name] = df[actual_name]

        cols = ['약국', '유입 일자', '방문 페이지', '총 사용자 수', '바코드 사용 유저', '바코드 이벤트 횟수', '유입 매체']
        available = [c for c in cols if c in df.columns]
        df = df[available].copy()

        if '유입 일자' in df.columns:
            df['유입 일자'] = pd.to_datetime(df['유입 일자'], errors='coerce')

        for c in ['총 사용자 수', '바코드 사용 유저', '바코드 이벤트 횟수']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

        for c in ['약국', '방문 페이지', '유입 매체']:
            if c in df.columns:
                df[c] = df[c].astype(str).str.strip()
                df[c] = df[c].replace({'nan': None, 'None': None, '': None})

        if '유입 일자' in df.columns:
            df = df.dropna(subset=['유입 일자'])

        if '약국' in df.columns:
            df = df[df['약국'].notna()]
            df = df[df['약국'] != '약국 정보 없음']

        result['ga'] = df

    # 2) 제작물 리스트
    if 'RAW_제작물 리스트(전체)' in xl:
        df = xl['RAW_제작물 리스트(전체)'].copy()
        df = flatten_and_clean_columns(df)
        result['qr_list'] = df

    # 3) 요약 시트
    if '(요청) 제작물 별 스캔 추이' in xl:
        df = xl['(요청) 제작물 별 스캔 추이'].copy()
        df = make_first_row_header(df)
        result['scan_trend'] = df

    # 4) 환급 요약
    if '★약국 - 환급자 수, 메디QR 진입, 바코드 수' in xl:
        df = xl['★약국 - 환급자 수, 메디QR 진입, 바코드 수'].copy()
        df = flatten_and_clean_columns(df)
        result['summary_raw'] = df

    return result


def extract_weekly_summary(data: dict) -> pd.DataFrame:
    """약국별 주차별 집계"""
    if 'ga' not in data:
        return pd.DataFrame()

    df = data['ga'].copy()
    required = {'약국', '유입 일자', '총 사용자 수', '바코드 사용 유저', '바코드 이벤트 횟수'}
    if not required.issubset(set(df.columns)):
        return pd.DataFrame()

    df['주차'] = df['유입 일자'].dt.to_period('W').astype(str)
    grp = df.groupby(['약국', '주차']).agg(
        총사용자=('총 사용자 수', 'sum'),
        바코드사용자=('바코드 사용 유저', 'sum'),
        바코드스캔=('바코드 이벤트 횟수', 'sum'),
    ).reset_index()
    return grp


def compute_wow(weekly: pd.DataFrame):
    """전주 대비 증감률 계산"""
    if weekly.empty:
        return pd.DataFrame(), None, None

    weeks = sorted(weekly['주차'].unique())
    if len(weeks) < 2:
        return pd.DataFrame(), None, None

    prev_w, curr_w = weeks[-2], weeks[-1]
    prev = weekly[weekly['주차'] == prev_w].set_index('약국')
    curr = weekly[weekly['주차'] == curr_w].set_index('약국')
    combined = curr.join(prev, lsuffix='_현재', rsuffix='_이전', how='outer').fillna(0)

    for col in ['총사용자', '바코드사용자', '바코드스캔']:
        combined[f'{col}_증감률'] = combined.apply(
            lambda r: (r[f'{col}_현재'] - r[f'{col}_이전']) / r[f'{col}_이전'] * 100
            if r[f'{col}_이전'] > 0 else None,
            axis=1
        )

    combined = combined.reset_index()
    combined.columns.name = None
    return combined, prev_w, curr_w


def call_claude_api(prompt: str) -> str:
    """Claude API 호출"""
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "system": "당신은 약국 QR 마케팅 데이터 분석 전문가입니다. 데이터를 보고 실무적으로 유의미한 인사이트를 한국어로 명확하고 간결하게 제공하세요. 불릿 포인트로 3~5개 핵심 인사이트를 제공하세요.",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        data = response.json()
        return data['content'][0]['text']
    except Exception as e:
        return f"⚠️ AI 분석 오류: {str(e)}"


# ── UI ───────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
    <span style="font-size:2rem">💊</span>
    <div>
        <div style="font-size:1.6rem; font-weight:800; color:#1E293B; line-height:1.2">메디QR 주간 인사이트</div>
        <div style="font-size:0.9rem; color:#64748B; margin-top:2px">엑셀 파일을 업로드하면 AI가 주간 변화를 분석해드립니다</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

with st.sidebar:
    st.markdown("### 📂 파일 업로드")
    st.markdown("매주 새로운 엑셀 파일을 업로드하세요")

    uploaded_files = st.file_uploader(
        "엑셀 파일 (최대 2개)",
        type=['xlsx'],
        accept_multiple_files=True,
        help="이전 주 + 현재 주 파일을 함께 올리거나, 1개만 올려도 됩니다"
    )

    st.divider()
    st.markdown("### ⚙️ 분석 설정")
    ai_enabled = st.toggle("🤖 AI 인사이트 생성", value=True)
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

if not uploaded_files:
    st.markdown("""
    <div class="upload-hint">
        <div style="font-size:2rem; margin-bottom:8px">📊</div>
        <div style="font-weight:600; font-size:1rem; margin-bottom:4px">왼쪽 사이드바에서 엑셀 파일을 업로드하세요</div>
        <div>1개 파일: 최신 주차 분석 | 2개 파일: 주차 간 비교 분석</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

datasets = {}
for f in uploaded_files:
    parsed = parse_excel(f)
    datasets[f.name] = parsed

st.success(f"✅ {len(uploaded_files)}개 파일 로드 완료: {', '.join([f.name for f in uploaded_files])}")

if len(datasets) == 1:
    main_key = list(datasets.keys())[0]
    prev_key = None
    main_data = datasets[main_key]
    compare_data = None
else:
    keys = list(datasets.keys())
    col1, col2 = st.columns(2)
    with col1:
        main_key = st.selectbox("📅 현재 주차 파일", keys, index=len(keys)-1)
    with col2:
        prev_key = st.selectbox("📅 이전 주차 파일", keys, index=0)
    main_data = datasets[main_key]
    compare_data = datasets[prev_key]

tabs = st.tabs(["📈 주간 요약", "🏪 약국별 분석", "🎯 디자인물 분석", "🤖 AI 인사이트"])


# ── 탭 1: 주간 요약 ──────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown('<div class="section-header">전체 지표 요약</div>', unsafe_allow_html=True)

    if 'ga' in main_data and not main_data['ga'].empty:
        df = main_data['ga'].copy()

        required_cols = {'유입 일자', '총 사용자 수', '바코드 사용 유저', '바코드 이벤트 횟수', '약국'}
        if not required_cols.issubset(set(df.columns)):
            st.warning("필수 컬럼이 일부 누락되어 주간 요약을 표시할 수 없습니다.")
        else:
            df['주차'] = df['유입 일자'].dt.to_period('W').astype(str)
            weeks = sorted(df['주차'].dropna().unique())

            if not weeks:
                st.warning("주차 데이터가 없습니다.")
            else:
                curr_w = weeks[-1]
                curr_df = df[df['주차'] == curr_w]
                prev_df = df[df['주차'] == weeks[-2]] if len(weeks) >= 2 else pd.DataFrame()

                curr_users = int(curr_df['총 사용자 수'].sum())
                curr_barcode_users = int(curr_df['바코드 사용 유저'].sum())
                curr_scans = int(curr_df['바코드 이벤트 횟수'].sum())
                curr_pharmacies = curr_df['약국'].nunique()

                prev_users = int(prev_df['총 사용자 수'].sum()) if not prev_df.empty else 0
                prev_scans = int(prev_df['바코드 이벤트 횟수'].sum()) if not prev_df.empty else 0

                def delta_str(curr, prev):
                    if prev == 0:
                        return ""
                    pct = (curr - prev) / prev * 100
                    arrow = "▲" if pct > 0 else "▼"
                    cls = "delta-up" if pct > 0 else "delta-down"
                    return f'<span class="{cls}">{arrow} {abs(pct):.1f}%</span>'

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{curr_users:,}</div>
                        <div class="metric-label">총 방문자 수</div>
                        <div class="metric-delta">{delta_str(curr_users, prev_users)} 전주 대비</div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""
                    <div class="metric-card green">
                        <div class="metric-value">{curr_scans:,}</div>
                        <div class="metric-label">바코드 스캔 횟수</div>
                        <div class="metric-delta">{delta_str(curr_scans, prev_scans)} 전주 대비</div>
                    </div>""", unsafe_allow_html=True)
                with c3:
                    conv_rate = safe_divide(curr_barcode_users, curr_users) * 100 if curr_users > 0 else 0
                    st.markdown(f"""
                    <div class="metric-card orange">
                        <div class="metric-value">{conv_rate:.1f}%</div>
                        <div class="metric-label">바코드 전환율</div>
                        <div class="metric-delta" style="color:#64748B">방문 → 스캔</div>
                    </div>""", unsafe_allow_html=True)
                with c4:
                    st.markdown(f"""
                    <div class="metric-card purple">
                        <div class="metric-value">{curr_pharmacies}</div>
                        <div class="metric-label">활성 약국 수</div>
                        <div class="metric-delta" style="color:#64748B">이번 주 기준</div>
                    </div>""", unsafe_allow_html=True)

                st.markdown('<div class="section-header">일별 방문 트렌드</div>', unsafe_allow_html=True)

                daily = df.groupby('유입 일자').agg(
                    총사용자=('총 사용자 수', 'sum'),
                    바코드스캔=('바코드 이벤트 횟수', 'sum')
                ).reset_index()

                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(
                    go.Bar(
                        x=daily['유입 일자'],
                        y=daily['총사용자'],
                        name='총 방문자',
                        marker_color='#C7D2FE',
                        opacity=0.8
                    ),
                    secondary_y=False
                )
                fig.add_trace(
                    go.Scatter(
                        x=daily['유입 일자'],
                        y=daily['바코드스캔'],
                        name='바코드 스캔',
                        line=dict(color='#4F6EF7', width=2.5),
                        mode='lines+markers'
                    ),
                    secondary_y=True
                )
                fig.update_layout(
                    height=320,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    margin=dict(l=0, r=0, t=20, b=0),
                    legend=dict(orientation='h', y=1.1)
                )
                fig.update_yaxes(title_text="방문자", secondary_y=False, gridcolor='#F1F5F9')
                fig.update_yaxes(title_text="스캔", secondary_y=True)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("RAW_GA 변환 시트가 없어 주간 요약을 표시할 수 없습니다.")


# ── 탭 2: 약국별 분석 ────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown('<div class="section-header">약국별 성과</div>', unsafe_allow_html=True)

    if 'ga' in main_data and not main_data['ga'].empty:
        df = main_data['ga'].copy()

        required_cols = {'약국', '총 사용자 수', '바코드 사용 유저', '바코드 이벤트 횟수', '유입 일자'}
        if not required_cols.issubset(set(df.columns)):
            st.warning("필수 컬럼이 일부 누락되어 약국별 분석을 표시할 수 없습니다.")
        else:
            pharmacy_df = df.groupby('약국').agg(
                총사용자=('총 사용자 수', 'sum'),
                바코드사용자=('바코드 사용 유저', 'sum'),
                바코드스캔=('바코드 이벤트 횟수', 'sum'),
                방문일수=('유입 일자', 'nunique')
            ).reset_index().sort_values('총사용자', ascending=False)

            pharmacy_df['전환율(%)'] = (
                pharmacy_df.apply(
                    lambda r: round(safe_divide(r['바코드사용자'], r['총사용자']) * 100, 1),
                    axis=1
                )
            )

            col1, col2 = st.columns([3, 2])

            with col1:
                st.markdown("**약국별 방문자 TOP 20**")
                top20 = pharmacy_df.head(20)
                fig = px.bar(
                    top20,
                    x='총사용자',
                    y='약국',
                    orientation='h',
                    color='바코드스캔',
                    color_continuous_scale='Blues',
                    labels={'총사용자': '총 방문자', '약국': '', '바코드스캔': '스캔 횟수'}
                )
                fig.update_layout(
                    height=500,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    margin=dict(l=0, r=0, t=10, b=0),
                    yaxis={'categoryorder': 'total ascending'}
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("**바코드 전환율 TOP 10** (방문자 3명 이상)")
                top_conv = pharmacy_df[pharmacy_df['총사용자'] >= 3].nlargest(10, '전환율(%)')
                fig2 = px.bar(
                    top_conv,
                    x='전환율(%)',
                    y='약국',
                    orientation='h',
                    color='전환율(%)',
                    color_continuous_scale='Greens'
                )
                fig2.update_layout(
                    height=380,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    margin=dict(l=0, r=0, t=10, b=0),
                    yaxis={'categoryorder': 'total ascending'}
                )
                st.plotly_chart(fig2, use_container_width=True)

            if compare_data and 'ga' in compare_data and not compare_data['ga'].empty:
                st.markdown('<div class="section-header">전주 대비 변화</div>', unsafe_allow_html=True)

                prev_ga = compare_data['ga'].copy()

                curr_pharm = df.groupby('약국').agg(
                    총사용자=('총 사용자 수', 'sum'),
                    바코드스캔=('바코드 이벤트 횟수', 'sum')
                ).reset_index()

                prev_pharm = prev_ga.groupby('약국').agg(
                    총사용자=('총 사용자 수', 'sum'),
                    바코드스캔=('바코드 이벤트 횟수', 'sum')
                ).reset_index()

                merged = curr_pharm.merge(
                    prev_pharm,
                    on='약국',
                    suffixes=('_현재', '_이전'),
                    how='outer'
                ).fillna(0)

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
    else:
        st.warning("RAW_GA 변환 시트가 없어 약국별 분석을 표시할 수 없습니다.")


# ── 탭 3: 디자인물 분석 ──────────────────────────────────────────────────────
with tabs[2]:
    st.markdown('<div class="section-header">유입 매체(디자인물)별 성과</div>', unsafe_allow_html=True)

    if 'ga' in main_data and not main_data['ga'].empty:
        df = main_data['ga'].copy()

        if '유입 매체' in df.columns:
            media_base = df.copy()
            media_base = media_base.loc[:, ~media_base.columns.duplicated()]
            media_base = media_base[media_base['유입 매체'].notna()]
            media_base = media_base[media_base['유입 매체'].astype(str).str.strip() != ""]

            if not media_base.empty:
                media_df = media_base.groupby('유입 매체').agg(
                    총사용자=('총 사용자 수', 'sum'),
                    바코드스캔=('바코드 이벤트 횟수', 'sum'),
                    약국수=('약국', 'nunique')
                ).reset_index().sort_values('총사용자', ascending=False)

                c1, c2 = st.columns(2)
                with c1:
                    fig = px.pie(
                        media_df,
                        values='총사용자',
                        names='유입 매체',
                        title='유입 매체별 방문자 비중',
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
                    st.plotly_chart(fig, use_container_width=True)

                with c2:
                    fig2 = px.bar(
                        media_df,
                        x='유입 매체',
                        y=['총사용자', '바코드스캔'],
                        barmode='group',
                        title='매체별 방문자 vs 스캔',
                        color_discrete_map={'총사용자': '#C7D2FE', '바코드스캔': '#4F6EF7'}
                    )
                    fig2.update_layout(
                        height=350,
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        margin=dict(l=0, r=0, t=40, b=0)
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                st.markdown("**매체별 상세 지표**")
                media_df['스캔전환율(%)'] = media_df.apply(
                    lambda r: round(safe_divide(r['바코드스캔'], r['총사용자']) * 100, 1),
                    axis=1
                )
                st.dataframe(media_df, use_container_width=True, hide_index=True)

        if '방문 페이지' in df.columns:
            st.markdown('<div class="section-header">방문 페이지별 분석</div>', unsafe_allow_html=True)

            page_base = df.copy()
            page_base = page_base.loc[:, ~page_base.columns.duplicated()]
            page_base = page_base[page_base['방문 페이지'].notna()]
            page_base = page_base[page_base['방문 페이지'].astype(str).str.strip() != ""]

            if not page_base.empty:
                page_df = page_base.groupby('방문 페이지', dropna=False).agg(
                    총사용자=('총 사용자 수', 'sum'),
                    바코드스캔=('바코드 이벤트 횟수', 'sum')
                ).reset_index().sort_values('총사용자', ascending=False)

                fig3 = px.bar(
                    page_df,
                    x='방문 페이지',
                    y='총사용자',
                    color='바코드스캔',
                    color_continuous_scale='Blues',
                    title='방문 페이지별 사용자 수'
                )
                fig3.update_layout(
                    height=300,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    margin=dict(l=0, r=0, t=40, b=0)
                )
                st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning("RAW_GA 변환 시트가 없어 디자인물 분석을 표시할 수 없습니다.")


# ── 탭 4: AI 인사이트 ─────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown('<div class="section-header">🤖 AI 인사이트 분석</div>', unsafe_allow_html=True)

    if not ai_enabled:
        st.info("사이드바에서 'AI 인사이트 생성'을 켜주세요.")
    elif 'ga' not in main_data or main_data['ga'].empty:
        st.warning("RAW_GA 변환 시트가 없어 분석이 불가합니다.")
    else:
        df = main_data['ga'].copy()

        required_cols = {'유입 일자', '약국', '총 사용자 수', '바코드 이벤트 횟수'}
        if not required_cols.issubset(set(df.columns)):
            st.warning("AI 분석에 필요한 컬럼이 일부 누락되어 있습니다.")
        else:
            weeks = sorted(df['유입 일자'].dt.to_period('W').astype(str).unique())
            curr_w = weeks[-1] if weeks else None
            curr_df = df[df['유입 일자'].dt.to_period('W').astype(str) == curr_w] if curr_w else df.copy()

            pharm_summary = df.groupby('약국').agg(
                총사용자=('총 사용자 수', 'sum'),
                바코드스캔=('바코드 이벤트 횟수', 'sum')
            ).sort_values('총사용자', ascending=False).head(10)

            if '유입 매체' in df.columns:
                media_summary = df.groupby('유입 매체').agg(
                    총사용자=('총 사용자 수', 'sum'),
                    바코드스캔=('바코드 이벤트 횟수', 'sum')
                ).to_dict()
            else:
                media_summary = {}

            total_users = int(df['총 사용자 수'].sum())
            total_scans = int(df['바코드 이벤트 횟수'].sum())
            total_pharmacies = df['약국'].nunique()
            conv_rate = safe_divide(total_scans, total_users) * 100 if total_users > 0 else 0

            prompt = f"""다음은 메디QR 서비스의 약국 QR 마케팅 데이터입니다.

【전체 요약】
- 총 방문자: {total_users:,}명
- 바코드 스캔: {total_scans:,}회
- 전환율: {conv_rate:.1f}%
- 활성 약국: {total_pharmacies}개
- 분석 기간: {df['유입 일자'].min().date()} ~ {df['유입 일자'].max().date()}

【방문자 TOP 10 약국】
{pharm_summary.to_string()}

【유입 매체별 현황】
{json.dumps(media_summary, ensure_ascii=False, indent=2)}

위 데이터를 분석하여:
1. 가장 주목할 만한 성과 약국과 그 특징
2. 유입 매체별 효율성 비교 및 개선점
3. 바코드 전환율 관련 인사이트
4. 다음 주 액션 아이템 추천

을 실무자가 바로 활용할 수 있는 형태로 분석해주세요."""

            if st.button("🔍 AI 분석 실행", type="primary"):
                with st.spinner("AI가 데이터를 분석 중입니다..."):
                    insight = call_claude_api(prompt)

                st.markdown(f"""
                <div class="insight-box">
                    <div class="insight-title">📊 이번 주 핵심 인사이트</div>
                    <div class="insight-content">{insight}</div>
                </div>
                """, unsafe_allow_html=True)

            if compare_data and 'ga' in compare_data and not compare_data['ga'].empty:
                st.divider()
                st.markdown("**📅 주차 간 변화 분석**")

                if st.button("🔄 전주 대비 변화 분석", type="primary"):
                    prev_df = compare_data['ga'].copy()
                    curr_total = int(df['총 사용자 수'].sum())
                    prev_total = int(prev_df['총 사용자 수'].sum())
                    curr_scan = int(df['바코드 이벤트 횟수'].sum())
                    prev_scan = int(prev_df['바코드 이벤트 횟수'].sum())

                    curr_pharm = set(df['약국'].dropna().unique())
                    prev_pharm = set(prev_df['약국'].dropna().unique())
                    new_pharm = curr_pharm - prev_pharm
                    dropped = prev_pharm - curr_pharm

                    visit_change_pct = ((curr_total - prev_total) / prev_total * 100) if prev_total > 0 else 0
                    scan_change_pct = ((curr_scan - prev_scan) / prev_scan * 100) if prev_scan > 0 else 0

                    wow_prompt = f"""메디QR 서비스의 주차 간 데이터 변화를 분석해주세요.

【이전 주】
- 파일명: {prev_key}
- 방문자: {prev_total:,}명, 바코드 스캔: {prev_scan:,}회, 약국수: {len(prev_pharm)}개

【현재 주】
- 파일명: {main_key}
- 방문자: {curr_total:,}명, 바코드 스캔: {curr_scan:,}회, 약국수: {len(curr_pharm)}개

【변화】
- 방문자 증감: {curr_total - prev_total:+,}명 ({visit_change_pct:+.1f}%)
- 스캔 증감: {curr_scan - prev_scan:+,}회 ({scan_change_pct:+.1f}%)
- 신규 진입 약국: {list(new_pharm)[:5]}
- 이탈 약국: {list(dropped)[:5]}

주간 변화의 핵심 원인과 다음 주 개선 방향을 분석해주세요."""

                    with st.spinner("전주 대비 분석 중..."):
                        wow_insight = call_claude_api(wow_prompt)

                    st.markdown(f"""
                    <div class="insight-box">
                        <div class="insight-title">📅 전주 대비 변화 인사이트</div>
                        <div class="insight-content">{wow_insight}</div>
                    </div>
                    """, unsafe_allow_html=True)

if show_raw and 'ga' in main_data:
    st.divider()
    st.markdown("**📋 원시 데이터 (GA 변환)**")
    st.dataframe(main_data['ga'].head(100), use_container_width=True)