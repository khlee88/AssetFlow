import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="AssetFlow", page_icon="💰", layout="wide")

st.title("💰 자산 흐름 시뮬레이터")
st.markdown(
    "초기 자산, 수입/지출, 투자 수익률을 입력하면 "
    "**연도별 자산 변화**와 **목표 자산 달성 시점**을 시뮬레이션합니다."
)

# ─────────────────────────────────────────────
# 사이드바 — 탭 입력 (자산 시나리오 / 은퇴 시나리오)
# ─────────────────────────────────────────────
# 사이드바 입력창 간격 축소 CSS
st.markdown(
    """<style>
    section[data-testid="stSidebar"] .stNumberInput {
        margin-bottom: -0.6rem;
    }
    section[data-testid="stSidebar"] .stMarkdown p {
        margin-bottom: 0.1rem;
    }
    </style>""",
    unsafe_allow_html=True,
)

with st.sidebar:
    tab_basic, tab_retire = st.tabs(["💼 자산 시나리오", "🏖️ 은퇴 시나리오"])

    # ── 탭 1: 자산 시나리오
    with tab_basic:
        st.markdown("**자산 · 수입 · 소비**")
        initial_assets = st.number_input(
            "초기 투자 자산 (만원)", min_value=0, value=30_000, step=500
        )
        col_inc, col_exp = st.columns(2)
        with col_inc:
            monthly_income = st.number_input(
                "월 수입 (만원)",
                min_value=0,
                value=400,
                step=50,
                help="세후 월 수령 금액",
            )
        with col_exp:
            monthly_expenses = st.number_input(
                "월 소비 (만원)", min_value=0, value=250, step=50
            )

        st.markdown("**투자 수익률 범위 (연)**")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            min_return_input = st.number_input(
                "최솟값 (%)",
                min_value=0.0,
                max_value=50.0,
                value=5.0,
                step=0.5,
                format="%.1f",
            )
        with col_r2:
            max_return_input = st.number_input(
                "최댓값 (%)",
                min_value=0.0,
                max_value=50.0,
                value=10.0,
                step=0.5,
                format="%.1f",
            )

        st.markdown("**기간 · 물가 · 목표**")
        sim_years = st.number_input(
            "시뮬레이션 기간 (년)", min_value=1, max_value=100, value=20, step=1
        )
        col_inf, col_ig = st.columns(2)
        with col_inf:
            inflation_rate = st.number_input(
                "물가 상승률 (%)",
                min_value=0.0,
                max_value=20.0,
                value=2.5,
                step=0.5,
                format="%.1f",
                help="매년 월 소비가 이 비율만큼 증가합니다.",
            )
        with col_ig:
            income_growth = st.number_input(
                "연봉 상승률 (%)",
                min_value=0.0,
                max_value=30.0,
                value=3.0,
                step=0.5,
                format="%.1f",
                help="매년 월 수입이 이 비율만큼 증가합니다. 은퇴 후에는 적용되지 않습니다.",
            )
        swr = st.number_input(
            "안전 인출률 / SWR (%)",
            min_value=0.5,
            max_value=10.0,
            value=4.0,
            step=0.5,
            format="%.1f",
            help=(
                "자산의 몇 %를 매년 꺼내 써도 고갈되지 않는지를 나타내는 비율.\n"
                "학계 검증된 기본값은 4% (Trinity Study 기준).\n"
                "보수적으로 보려면 3~3.5%로 낮추세요."
            ),
        )

    # min > max 자동 교체 (탭 밖에서 처리)
    min_return = min(min_return_input, max_return_input)
    max_return = max(min_return_input, max_return_input)
    if min_return_input > max_return_input:
        st.warning("⚠️ 최솟값 > 최댓값 — 자동 교체하여 계산합니다.")

    # ── 탭 2: 은퇴 시나리오
    with tab_retire:
        use_retirement = st.toggle("시나리오 켜기", value=False)

        if use_retirement:
            st.markdown("**은퇴 조건**")

            # ── session_state로 retire_year / post_retire_years 보존 ──
            # 자산 시나리오 탭의 sim_years 와 독립적으로 관리.
            if "retire_year" not in st.session_state:
                st.session_state["retire_year"] = 15
            if "post_retire_years" not in st.session_state:
                st.session_state["post_retire_years"] = 20

            col_ry, col_py = st.columns(2)
            with col_ry:
                retire_year = st.number_input(
                    "은퇴 시점 (N년차)",
                    min_value=1,
                    max_value=80,
                    step=1,
                    key="retire_year",
                    help="자산 시나리오 그래프의 중간(평균) 곡선을 보고 결정하세요.",
                )
            with col_py:
                post_retire_years = st.number_input(
                    "은퇴 이후 기간 (년)",
                    min_value=1,
                    max_value=80,
                    step=1,
                    key="post_retire_years",
                    help="은퇴 이후 자산 흐름을 추적할 기간",
                )
            retire_income = st.number_input(
                "은퇴 후 월 수입 (만원)",
                min_value=0,
                value=100,
                step=50,
                help="연금·임대·파트타임 등 투자 외 수입",
            )
            st.markdown("**인출 세금**")
            retire_tax_pct = st.number_input(
                "인출 세금률 (%)",
                min_value=0.0,
                max_value=80.0,
                value=22.0,
                step=1.0,
                format="%.1f",
                help="부족분 인출 시 적용되는 세율\n예) 해외주식 양도세 22%",
            )
            st.caption("계산 방식: 필요 순수령 ÷ (1 − 세율)")

            st.markdown("**은퇴 후 투자 수익률 범위 (연)**")
            st.caption("은퇴 후에는 안정적인 수익률로 조정하세요 (예: 3.5%~7.5%)")
            col_rr1, col_rr2 = st.columns(2)
            with col_rr1:
                min_retire_return_input = st.number_input(
                    "최솟값 (%)",
                    min_value=0.0,
                    max_value=50.0,
                    value=3.5,
                    step=0.5,
                    format="%.1f",
                    key="ret_min_return",
                )
            with col_rr2:
                max_retire_return_input = st.number_input(
                    "최댓값 (%)",
                    min_value=0.0,
                    max_value=50.0,
                    value=7.5,
                    step=0.5,
                    format="%.1f",
                    key="ret_max_return",
                )

            # 은퇴 후 수익률 min > max 자동 교체
            min_retire_return = min(min_retire_return_input, max_retire_return_input)
            max_retire_return = max(min_retire_return_input, max_retire_return_input)
            if min_retire_return_input > max_retire_return_input:
                st.warning("⚠️ 은퇴 후 수익률: 최솟값 > 최댓값 — 자동 교체합니다.")
            mid_retire_return = (min_retire_return + max_retire_return) / 2
        else:
            st.markdown(
                "<div style='color:#888; font-size:0.88rem; padding-top:8px'>"
                "토글을 켜면 은퇴 후 자산 변화를<br>그래프에서 비교할 수 있어요.</div>",
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────
# 시뮬레이션 함수
# ─────────────────────────────────────────────
def simulate(
    initial, m_income, m_exp_init, return_pct, inflation_pct, income_growth_pct, years
):
    """기본 시뮬레이션 (은퇴 없음).
    연 저축 = (월수입 − 당해 월소비) × 12 → 재투자
    월소비는 매년 inflation_pct% 상승, 월수입은 매년 income_growth_pct% 상승.
    """
    assets = [float(initial)]
    details = []
    r = return_pct / 100
    inf = inflation_pct / 100
    ig = income_growth_pct / 100

    for yr in range(1, years + 1):
        cur_monthly_exp = m_exp_init * ((1 + inf) ** yr)
        cur_monthly_income = m_income * ((1 + ig) ** yr)
        annual_exp = cur_monthly_exp * 12
        annual_savings = (cur_monthly_income - cur_monthly_exp) * 12
        annual_return = assets[-1] * r
        assets.append(assets[-1] + annual_return + annual_savings)
        details.append(
            {
                "monthly_exp": cur_monthly_exp,
                "annual_exp": annual_exp,
                "annual_savings": annual_savings,
                "annual_return": annual_return,
                "cur_income": cur_monthly_income,
                "is_retired": False,
                "gross_withdraw": 0.0,
                "tax_paid": 0.0,
            }
        )
    return assets, details


def simulate_post_retirement(
    start_assets,
    m_exp_init,
    return_pct,
    inflation_pct,
    retire_yr,
    post_years,
    m_income_post,
    tax_pct,
):
    """은퇴 단계 시뮬레이션 (은퇴 시점 이후만 계산).

    자산 시나리오의 중간 곡선이 retire_yr 시점에 도달한 자산값(start_assets)을
    초기값으로 받아, retire_yr 이후 post_years 동안의 자산 흐름을 계산.
    return_pct 별로 호출 → 한 점에서 min/mid/max 라인이 분기.

    물가상승률은 0년차부터 누적되는 절대 연도 기준으로 적용.
    (월 소비 = m_exp_init × (1+inf)^(retire_yr+k))

    은퇴 후 (월소비 > 은퇴 후 월 수입) 시:
      - 부족분을 투자 자산에서 인출
      - 세금 gross-up: 매도액 = 부족분 / (1 − tax_rate)
    은퇴 후 (월소비 ≤ 은퇴 후 월 수입) 시:
      - 잉여분 재투자, 추가 세금 없음

    반환:
      assets — 길이 post_years+1, assets[0] = start_assets
      details — 길이 post_years
    """
    assets = [float(start_assets)]
    details = []
    r = return_pct / 100
    inf = inflation_pct / 100
    tax = tax_pct / 100

    for k in range(1, post_years + 1):
        absolute_yr = retire_yr + k
        cur_monthly_exp = m_exp_init * ((1 + inf) ** absolute_yr)
        annual_exp = cur_monthly_exp * 12
        cur_income = float(m_income_post)

        monthly_deficit = cur_monthly_exp - cur_income  # 양수 → 인출 필요

        if monthly_deficit > 0 and tax < 1:
            gross_monthly = monthly_deficit / (1 - tax)
            annual_savings = -gross_monthly * 12
            tax_paid_annual = (gross_monthly - monthly_deficit) * 12
        else:
            annual_savings = (cur_income - cur_monthly_exp) * 12
            gross_monthly = max(0.0, -annual_savings / 12)
            tax_paid_annual = 0.0

        annual_return = assets[-1] * r
        assets.append(assets[-1] + annual_return + annual_savings)
        details.append(
            {
                "monthly_exp": cur_monthly_exp,
                "annual_exp": annual_exp,
                "annual_savings": annual_savings,
                "annual_return": annual_return,
                "cur_income": cur_income,
                "is_retired": True,
                "gross_withdraw": gross_monthly * 12,
                "tax_paid": tax_paid_annual,
            }
        )
    return assets, details


def calc_target_assets(m_exp_init, inflation_pct, swr_pct, years):
    """목표 자산 곡선 (안전 인출률 / SWR 기준).

    목표 자산 = 해당 연도 연간 소비 ÷ SWR
    → 이 자산의 SWR%를 매년 인출하면 소비를 영구적으로 감당 가능.
    연간 소비는 물가상승률에 따라 매년 증가 반영.
    """
    inf = inflation_pct / 100
    swr = swr_pct / 100
    return [
        (m_exp_init * ((1 + inf) ** yr) * 12 / swr) if swr > 0 else float("inf")
        for yr in range(years + 1)
    ]


def find_target_year(assets, targets):
    for i, (a, t) in enumerate(zip(assets, targets)):
        if a >= t:
            return i
    return None


def find_threshold_year(ret_assets, threshold, retire_yr):
    """은퇴 자산이 threshold 이하로 처음 떨어지는 절대 연도 반환 (없으면 None)."""
    for k, a in enumerate(ret_assets):
        if a <= threshold:
            return retire_yr + k
    return None


def fmt_man(val):
    if not np.isfinite(val):
        return "∞"
    return f"{val:,.0f}"


def fmt_eok(val):
    if not np.isfinite(val):
        return "∞"
    return f"{val / 10_000:.2f}억원"


# ─────────────────────────────────────────────
# 유효성 검사
# ─────────────────────────────────────────────
if max_return == 0:
    st.warning("투자 수익률이 0%이면 목표 자산을 계산할 수 없습니다.")
    st.stop()

# ─────────────────────────────────────────────
# 계산
# ─────────────────────────────────────────────
mid_return = (min_return + max_return) / 2

# 시뮬레이션 구간 결정
# - 은퇴 OFF: 자산 시나리오 sim_years 만큼 표시
# - 은퇴 ON: 기본 시나리오는 retire_year 까지만 (관찰용),
#           은퇴 단계가 retire_year ~ retire_year+post_retire_years 를 이어받음
if use_retirement:
    base_horizon = int(retire_year)
    total_horizon = int(retire_year) + int(post_retire_years)
else:
    base_horizon = int(sim_years)
    total_horizon = int(sim_years)

years_range = list(range(total_horizon + 1))

# 기본(자산) 시나리오 — 0 ~ base_horizon
assets_min, details_min = simulate(
    initial_assets, monthly_income, monthly_expenses,
    min_return, inflation_rate, income_growth, base_horizon,
)
assets_max, details_max = simulate(
    initial_assets, monthly_income, monthly_expenses,
    max_return, inflation_rate, income_growth, base_horizon,
)
assets_mid, details_mid = simulate(
    initial_assets, monthly_income, monthly_expenses,
    mid_return, inflation_rate, income_growth, base_horizon,
)

# 목표 자산 (SWR 기준) — 전체 구간 (은퇴 ON에서는 미사용이지만 길이 맞춤)
targets = calc_target_assets(monthly_expenses, inflation_rate, swr, total_horizon)
target_yr_min = find_target_year(assets_min, targets)
target_yr_mid = find_target_year(assets_mid, targets)
target_yr_max = find_target_year(assets_max, targets)

# 은퇴 단계 — 자산 시나리오의 mid 곡선이 retire_year에 도달한 자산값을 한 점으로 잡고
# 거기서 은퇴 min/mid/max 수익률로 분기
if use_retirement:
    retire_start_asset = assets_mid[int(retire_year)]
    ret_assets_min, ret_details_min = simulate_post_retirement(
        retire_start_asset, monthly_expenses, min_retire_return,
        inflation_rate, int(retire_year), int(post_retire_years),
        retire_income, retire_tax_pct,
    )
    ret_assets_mid, ret_details_mid = simulate_post_retirement(
        retire_start_asset, monthly_expenses, mid_retire_return,
        inflation_rate, int(retire_year), int(post_retire_years),
        retire_income, retire_tax_pct,
    )
    ret_assets_max, ret_details_max = simulate_post_retirement(
        retire_start_asset, monthly_expenses, max_retire_return,
        inflation_rate, int(retire_year), int(post_retire_years),
        retire_income, retire_tax_pct,
    )


# ─────────────────────────────────────────────
# Plotly 그래프
# ─────────────────────────────────────────────
def to_eok(lst):
    return [v / 10_000 for v in lst]


tick_interval = 1 if total_horizon <= 20 else 2
# 기본 시나리오 구간 (0 ~ base_horizon) — 은퇴 ON일 때는 retire_year까지만 그려짐
base_x = list(range(base_horizon + 1))
b_min, b_max, b_mid = assets_min, assets_max, assets_mid
b_dot_yr = [y for y in base_x if y % tick_interval == 0]
b_dot_mid = [to_eok(assets_mid)[y] for y in b_dot_yr]

fig = go.Figure()

# ── 기본 시나리오 ──────────────────────────────

# 음영 밴드
fig.add_trace(
    go.Scatter(
        x=base_x,
        y=to_eok(b_max),
        mode="lines",
        line=dict(color="rgba(100,149,237,0)", width=0),
        showlegend=False,
        hoverinfo="skip",
        name="_band_top",
    )
)
fig.add_trace(
    go.Scatter(
        x=base_x,
        y=to_eok(b_min),
        mode="lines",
        line=dict(color="rgba(100,149,237,0)", width=0),
        fill="tonexty",
        fillcolor="rgba(100,149,237,0.18)",
        showlegend=True,
        hoverinfo="skip",
        name=f"수익률 범위 ({min_return}%~{max_return}%)",
        legendrank=2,
    )
)

fig.add_trace(
    go.Scatter(
        x=base_x,
        y=to_eok(b_min),
        mode="lines",
        line=dict(color="#6495ED", width=1.5, dash="dot"),
        name=f"최소 {min_return}%",
        hovertemplate="연도: %{x}년<br>자산: %{y:.2f}억원<extra></extra>",
        showlegend=False,
    )
)
fig.add_trace(
    go.Scatter(
        x=base_x,
        y=to_eok(b_max),
        mode="lines",
        line=dict(color="#6495ED", width=1.5, dash="dot"),
        name=f"최대 {max_return}%",
        hovertemplate="연도: %{x}년<br>자산: %{y:.2f}억원<extra></extra>",
        showlegend=False,
    )
)
fig.add_trace(
    go.Scatter(
        x=base_x,
        y=to_eok(b_mid),
        mode="lines",
        line=dict(color="#1E4BCC", width=2.5),
        name=f"중간 {mid_return:.1f}%",
        hovertemplate="연도: %{x}년<br>자산: %{y:.2f}억원<extra></extra>",
        legendrank=1,
    )
)
fig.add_trace(
    go.Scatter(
        x=b_dot_yr,
        y=b_dot_mid,
        mode="markers",
        marker=dict(size=6, color="#1E4BCC", line=dict(width=1.5, color="white")),
        showlegend=False,
        hoverinfo="skip",
        name="_mid_dots",
    )
)

# 목표 자산 라인 (은퇴 시나리오 OFF일 때만 표시)
if not use_retirement:
    fig.add_trace(
        go.Scatter(
            x=years_range,
            y=to_eok(targets),
            mode="lines",
            line=dict(color="#E05A2B", width=2, dash="dash"),
            name=f"목표 자산 (SWR {swr}%)",
            hovertemplate="연도: %{x}년<br>목표: %{y:.2f}억원<extra></extra>",
            legendrank=3,
        )
    )

# ── 은퇴 시나리오 ─────────────────────────────
if use_retirement:
    # 은퇴 단계 X축: retire_year ~ retire_year + post_retire_years
    # ret_assets_*[0] = assets_mid[retire_year] (한 점에서 min/mid/max 분기)
    ret_x = list(range(int(retire_year), total_horizon + 1))
    ret_min_y = to_eok(ret_assets_min)
    ret_max_y = to_eok(ret_assets_max)
    ret_mid_y = to_eok(ret_assets_mid)

    # 은퇴 음영 밴드
    fig.add_trace(
        go.Scatter(
            x=ret_x,
            y=ret_max_y,
            mode="lines",
            line=dict(color="rgba(34,139,34,0)", width=0),
            showlegend=False,
            hoverinfo="skip",
            name="_ret_band_top",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ret_x,
            y=ret_min_y,
            mode="lines",
            line=dict(color="rgba(34,139,34,0)", width=0),
            fill="tonexty",
            fillcolor="rgba(34,139,34,0.15)",
            showlegend=True,
            hoverinfo="skip",
            name=f"은퇴 수익률 범위 ({min_retire_return}%~{max_retire_return}%)",
            legendrank=4,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ret_x,
            y=ret_min_y,
            mode="lines",
            line=dict(color="#2E8B57", width=1.5, dash="dot"),
            name=f"은퇴 최소 {min_retire_return}%",
            hovertemplate="연도: %{x}년<br>자산(은퇴): %{y:.2f}억원<extra></extra>",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ret_x,
            y=ret_max_y,
            mode="lines",
            line=dict(color="#2E8B57", width=1.5, dash="dot"),
            name=f"은퇴 최대 {max_retire_return}%",
            hovertemplate="연도: %{x}년<br>자산(은퇴): %{y:.2f}억원<extra></extra>",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ret_x,
            y=ret_mid_y,
            mode="lines+markers",
            marker=dict(size=5, color="#006400", line=dict(width=1, color="white")),
            line=dict(color="#006400", width=2.5),
            name=f"은퇴 중간 {mid_retire_return:.1f}%",
            hovertemplate="연도: %{x}년<br>자산(은퇴): %{y:.2f}억원<extra></extra>",
            legendrank=3,
        )
    )

    # 은퇴 시점 수직선
    fig.add_vline(
        x=int(retire_year),
        line=dict(color="#FF8C00", width=1.5, dash="dash"),
        annotation_text=f"🏖️ 은퇴 {int(retire_year)}년차",
        annotation_position="top right",
        annotation_font=dict(color="#FF8C00", size=12),
    )

    # ── 자산 감소 단계 경고 마커 (3개 시나리오 곡선 위에 직접 표기) ──
    rofs = int(retire_year)
    WARN_LEVELS = [
        (retire_start_asset * 0.5, "🟡", "자산 반토막 (-50%)", "#F0AD4E", 5),
        (retire_start_asset * 0.2, "🟠", "1/5 남음 (-80%)",   "#E0732B", 6),
        (0,                          "💀", "자산 고갈",         "#D9534F", 7),
    ]
    for threshold, emoji, label, color, rank in WARN_LEVELS:
        xs, ys = [], []
        for ret_assets in (ret_assets_min, ret_assets_mid, ret_assets_max):
            yr = find_threshold_year(ret_assets, threshold, rofs)
            if yr is not None:
                k = yr - rofs
                xs.append(yr)
                ys.append(ret_assets[k] / 10_000)  # 억원
        if xs:  # 적어도 한 시나리오에서 발생한 경우에만 trace + 범례 추가
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="markers+text",
                    # 투명 마커: 차트엔 이모지만 보이고, 범례에선 "Aa" 플레이스홀더 회피용
                    marker=dict(size=12, color="rgba(0,0,0,0)", line=dict(width=0)),
                    text=[emoji] * len(xs),
                    textposition="middle center",
                    textfont=dict(size=14),
                    name=f"{emoji} {label}",
                    hovertemplate=f"<b>{label}</b><br>%{{x}}년차 · %{{y:.2f}}억원<extra></extra>",
                    showlegend=True,
                    legendrank=rank,
                )
            )

# ── 목표 달성 수직 점선 (은퇴 시나리오 OFF일 때만) ──
# 은퇴 ON이면 은퇴 시점 수직선만 남기고 목표 자산 선들은 모두 숨김
if not use_retirement:
    COLORS = {"min": "#E05A2B", "mid": "#9B59B6", "max": "#27AE60"}

    # 연도 기준 정렬 후 annotation 좌우 교차 배치 (가까운 연도 겹침 방지)
    target_items = sorted(
        [
            (yr, lbl, col)
            for yr, lbl, col in [
                (target_yr_min, f"보수적 {min_return}%", COLORS["min"]),
                (target_yr_mid, f"중간 {mid_return:.1f}%", COLORS["mid"]),
                (target_yr_max, f"낙관적 {max_return}%", COLORS["max"]),
            ]
            if yr is not None
        ],
        key=lambda x: x[0],
    )

    # 모든 annotation을 오른쪽 정렬 — 교차 배치 시 서로를 향해 뻗어 겹치는 문제 해결
    # 연도가 가까울 때는 yshift로 수직 오프셋 적용
    Y_SHIFTS = [0, -40, -80]  # 최대 3개 겹침 대비
    for i, (yr, lbl, col) in enumerate(target_items):
        fig.add_vline(
            x=yr,
            line=dict(color=col, width=1.5, dash="dot"),
            annotation_text=f"🎯 {yr}년차<br>{lbl}",
            annotation_position="top right",
            annotation_yshift=Y_SHIFTS[i],
            annotation_font=dict(color=col, size=10),
            annotation_bgcolor="rgba(255,255,255,0.88)",
            annotation_bordercolor=col,
            annotation_borderwidth=1,
        )

fig.update_layout(
    title=dict(text="연도별 자산 흐름 시뮬레이션", font=dict(size=18)),
    xaxis=dict(
        title="경과 연도 (년)",
        gridcolor="#ECECEC",
        zeroline=False,
        tick0=0,
        dtick=tick_interval,
    ),
    yaxis=dict(
        title="자산 (억원)", tickformat=".1f", gridcolor="#ECECEC", zeroline=False
    ),
    hovermode="x unified",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=11),
        traceorder="normal",
    ),
    height=580,
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(t=120),
)

st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────
# 요약 카드
# ─────────────────────────────────────────────
st.subheader("📊 시뮬레이션 요약")


def render_summary(col, label, final_asset, tyr, achieved_asset, horizon_yr):
    """원본과 동일한 박스 시각화 (st.metric + success/error)."""
    with col:
        st.markdown(f"**{label}**")
        st.metric("최종 자산", fmt_eok(final_asset))
        if tyr is not None:
            st.success(
                f"🎯 목표 달성: **{tyr}년차**\n\n달성 자산: {fmt_eok(achieved_asset)}"
            )
        else:
            st.error(f"⏳ {horizon_yr}년 내 미달성\n\n최종: {fmt_eok(final_asset)}")


def _achieved(assets, tyr, offset=0):
    """tyr(절대 연도) 시점의 자산을 assets 배열에서 찾기. None이면 None 반환."""
    if tyr is None:
        return None
    idx = tyr - offset
    return assets[idx] if 0 <= idx < len(assets) else None


# streamlit 기본 alert 박스 톤에 가까운 팔레트 (배경 / 테두리 / 텍스트)
ALERT_PALETTE = {
    "error":   ("rgba(255, 43, 43, 0.09)", "rgba(255, 43, 43, 0.25)", "#7A0000"),
    "warning": ("rgba(255, 170, 0, 0.10)", "rgba(255, 170, 0, 0.30)", "#7A4D00"),
    "success": ("rgba(33, 195, 84, 0.10)", "rgba(33, 195, 84, 0.30)", "#0E5F1F"),
}


def styled_alert(severity, msg_html):
    """st.error/warning/success 대체 — HTML 줄바꿈 자유롭게 사용 가능."""
    bg, bd, fg = ALERT_PALETTE[severity]
    st.markdown(
        f'<div style="background:{bg}; border:1px solid {bd}; color:{fg}; '
        f'padding:0.75rem 1rem; border-radius:0.5rem; line-height:1.7; '
        f'font-size:0.9rem; margin:0.25rem 0;">{msg_html}</div>',
        unsafe_allow_html=True,
    )


def render_retire_card(col, label, ret_assets, retire_start, retire_yr):
    """은퇴 시나리오 요약 카드 — 최종 자산 + 자산 감소 단계별 경고 시점."""
    with col:
        st.markdown(f"**{label}**")
        st.metric("최종 자산", fmt_eok(ret_assets[-1]))

        yr50 = find_threshold_year(ret_assets, retire_start * 0.5, retire_yr)
        yr20 = find_threshold_year(ret_assets, retire_start * 0.2, retire_yr)
        yr0 = find_threshold_year(ret_assets, 0, retire_yr)

        lines = []
        if yr50 is not None:
            lines.append(f"🟡 자산 반토막: <b>{yr50}년차</b>")
        if yr20 is not None:
            lines.append(f"🟠 1/5 남음: <b>{yr20}년차</b>")
        if yr0 is not None:
            lines.append(f"💀 자산 고갈: <b>{yr0}년차</b>")

        msg_html = "<br>".join(lines)
        if yr0 is not None:
            styled_alert("error", msg_html)
        elif lines:
            styled_alert("warning", msg_html)
        else:
            styled_alert("success", "✅ 안전 — 자산 유지/증가")


if not use_retirement:
    c1, c2, c3 = st.columns(3)
    render_summary(
        c1, f"최소 {min_return}%",
        assets_min[-1], target_yr_min, _achieved(assets_min, target_yr_min), total_horizon,
    )
    render_summary(
        c2, f"중간 {mid_return:.1f}%",
        assets_mid[-1], target_yr_mid, _achieved(assets_mid, target_yr_mid), total_horizon,
    )
    render_summary(
        c3, f"최대 {max_return}%",
        assets_max[-1], target_yr_max, _achieved(assets_max, target_yr_max), total_horizon,
    )
else:
    st.markdown(
        f"##### 🏖️ 은퇴 후 {int(post_retire_years)}년 시점 자산 "
        f"(은퇴 시작 자산: {fmt_eok(retire_start_asset)})"
    )
    r1, r2, r3 = st.columns(3)
    rofs = int(retire_year)
    render_retire_card(r1, f"은퇴 최소 {min_retire_return}%", ret_assets_min, retire_start_asset, rofs)
    render_retire_card(r2, f"은퇴 중간 {mid_retire_return:.1f}%", ret_assets_mid, retire_start_asset, rofs)
    render_retire_card(r3, f"은퇴 최대 {max_retire_return}%", ret_assets_max, retire_start_asset, rofs)

# ─────────────────────────────────────────────
# 연도별 상세 표
# ─────────────────────────────────────────────
st.subheader("📅 연도별 상세 내역")

DASH = "—"

# ── 자산 시나리오 상세 표 (항상 표시, 0 ~ base_horizon) ──
col_min = f"자산({min_return}%)"
col_mid = f"자산({mid_return:.1f}%)"
col_max = f"자산({max_return}%)"

with st.expander("💼 자산 시나리오 상세 내역 펼치기"):
    rows = []
    for yr in range(base_horizon + 1):
        if yr == 0:
            m_exp = float(monthly_expenses)
            annual_exp = m_exp * 12
            cur_inc = float(monthly_income)
            reinvest = (cur_inc - m_exp) * 12
            yr_ret_min = initial_assets * (min_return / 100)
            yr_ret_mid = initial_assets * (mid_return / 100)
            yr_ret_max = initial_assets * (max_return / 100)
        else:
            d = details_mid[yr - 1]
            m_exp = d["monthly_exp"]
            annual_exp = d["annual_exp"]
            reinvest = d["annual_savings"]
            cur_inc = d["cur_income"]
            yr_ret_min = details_min[yr - 1]["annual_return"]
            yr_ret_mid = details_mid[yr - 1]["annual_return"]
            yr_ret_max = details_max[yr - 1]["annual_return"]

        row = {
            "연도": f"{yr}년차",
            "월 수입 (만원)": fmt_man(cur_inc),
            "월 소비 (만원)": fmt_man(m_exp),
            "연 소비 (만원)": fmt_man(annual_exp),
            "재투자 (만원)": fmt_man(reinvest),
            f"연수익({min_return}%)": fmt_man(yr_ret_min),
            f"연수익({mid_return:.1f}%)": fmt_man(yr_ret_mid),
            f"연수익({max_return}%)": fmt_man(yr_ret_max),
            col_min: fmt_eok(assets_min[yr]),
            col_mid: fmt_eok(assets_mid[yr]),
            col_max: fmt_eok(assets_max[yr]),
        }
        if not use_retirement:
            row[f"목표 자산 (SWR {swr}%)"] = fmt_eok(targets[yr])
        rows.append(row)

    df_basic = pd.DataFrame(rows)
    st.dataframe(df_basic, hide_index=True, use_container_width=True)

# ── 은퇴 시나리오 상세 표 (토글 ON일 때만, retire_year ~ total_horizon) ──
if use_retirement:
    col_ret_min = f"은퇴자산({min_retire_return}%)"
    col_ret_mid = f"은퇴자산({mid_retire_return:.1f}%)"
    col_ret_max = f"은퇴자산({max_retire_return}%)"

    with st.expander("🏖️ 은퇴 시나리오 상세 내역 펼치기"):
        rows = []
        for yr in range(int(retire_year), total_horizon + 1):
            k = yr - int(retire_year)
            if k == 0:
                # 시작점 — 자산 시나리오 mid 곡선이 도달한 한 점에서 분기
                row = {
                    "연도": f"{yr}년차 (시작)",
                    "월 수입 (만원)": DASH,
                    "월 소비 (만원)": DASH,
                    "연 소비 (만원)": DASH,
                    "예상 세금 (만원)": DASH,
                    f"연수익({min_retire_return}%)": DASH,
                    f"연수익({mid_retire_return:.1f}%)": DASH,
                    f"연수익({max_retire_return}%)": DASH,
                    col_ret_min: fmt_eok(retire_start_asset),
                    col_ret_mid: fmt_eok(retire_start_asset),
                    col_ret_max: fmt_eok(retire_start_asset),
                    "총 인출 (만원)": DASH,
                }
            else:
                rd = ret_details_mid[k - 1]
                row = {
                    "연도": f"{yr}년차",
                    "월 수입 (만원)": fmt_man(rd["cur_income"]),
                    "월 소비 (만원)": fmt_man(rd["monthly_exp"]),
                    "연 소비 (만원)": fmt_man(rd["annual_exp"]),
                    "예상 세금 (만원)": fmt_man(rd["tax_paid"]),
                    f"연수익({min_retire_return}%)": fmt_man(ret_details_min[k - 1]["annual_return"]),
                    f"연수익({mid_retire_return:.1f}%)": fmt_man(ret_details_mid[k - 1]["annual_return"]),
                    f"연수익({max_retire_return}%)": fmt_man(ret_details_max[k - 1]["annual_return"]),
                    col_ret_min: fmt_eok(ret_assets_min[k]),
                    col_ret_mid: fmt_eok(ret_assets_mid[k]),
                    col_ret_max: fmt_eok(ret_assets_max[k]),
                    "총 인출 (만원)": fmt_man(rd["gross_withdraw"]),
                }
            rows.append(row)

        df_retire = pd.DataFrame(rows)
        st.dataframe(df_retire, hide_index=True, use_container_width=True)

# ─────────────────────────────────────────────
# 계산 가정 안내
# ─────────────────────────────────────────────
with st.expander("📐 계산 가정 및 공식 안내"):
    st.markdown(
        f"""
**자산 성장 공식 (매년 반복)**
```
자산(n+1) = 자산(n) × (1 + 수익률) + 연 저축액
연 저축액  = (월 수입 − 해당 연도 월 소비) × 12
월 소비    = 초기 월 소비 × (1 + 물가상승률)^n
```

**목표 자산 공식 (SWR 기반)**
```
목표 자산 = 해당 연도 연간 소비 ÷ 안전 인출률(SWR)
현재 설정  = 연간 소비 ÷ SWR({swr}%)
```
> SWR {swr}% 의미: 이 자산에서 매년 {swr}%씩 꺼내 써도 장기적으로 고갈되지 않는 수준.  
> Trinity Study 기준 권장값은 **4%** (30년 기준 약 95% 생존율).  
> 보수적으로 보려면 3~3.5%로 낮추고, 세금 부담을 반영하려면 `SWR ÷ 1.세금비율` 로 조정하세요.  
> 예) 인출 시 세금 20% 증가 고려 → 4% ÷ 1.2 ≈ 3.3%

**은퇴 시나리오 인출 공식 (세금 gross-up)**
```
필요 매도액 = 월 부족분 ÷ (1 − 세율)
연간 자산 차감 = 필요 매도액 × 12
```
> 예) 월 부족분 200만원, 세율 22% → 매도액 = 200 ÷ 0.78 ≈ 256만원 (세금 56만원 포함)

**주요 가정**
- 수익은 매년 말 정산 후 재투자 (연 복리)
- 물가상승률은 월 소비에만 적용 (수입 불변, 단 연봉 상승률 별도 적용)
- 연봉 상승률은 은퇴 전 월 수입에만 적용
- 세금은 은퇴 후 자산 인출 시에만 반영 (gross-up 방식)
- 음수 자산(파산) 이후에도 계산은 계속됨 (참고용)
""",
        unsafe_allow_html=False,
    )
