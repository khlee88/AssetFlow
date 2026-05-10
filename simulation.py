"""자산 흐름 시뮬레이션 — 순수 계산 로직 (Streamlit / Plotly 의존 없음)."""

import numpy as np


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


def monte_carlo_post_retirement(
    start_assets,
    m_exp_init,
    mu_pct,
    sigma_pct,
    inflation_pct,
    retire_yr,
    post_years,
    m_income_post,
    tax_pct,
    n_trials=10_000,
    seed=42,
):
    """은퇴 단계 Monte Carlo 시뮬레이션 — 매년 수익률 ~ N(mu, sigma²).

    μ, σ의 결정은 caller 책임 (예: min/max를 어느 신뢰구간으로 해석할지).
    인출/세금 로직은 simulate_post_retirement와 동일하지만 벡터화로 처리.

    반환:
      asset_paths — shape (n_trials, post_years+1) 자산 경로 배열.
                    asset_paths[:, 0] = start_assets (모든 trial 동일).
    """
    rng = np.random.default_rng(seed)
    inf = inflation_pct / 100
    tax = tax_pct / 100
    mu = mu_pct / 100
    sigma = sigma_pct / 100

    annual_returns = rng.normal(mu, sigma, size=(n_trials, post_years))

    asset_paths = np.zeros((n_trials, post_years + 1))
    asset_paths[:, 0] = start_assets

    for k in range(1, post_years + 1):
        absolute_yr = retire_yr + k
        cur_monthly_exp = m_exp_init * ((1 + inf) ** absolute_yr)
        deficit = cur_monthly_exp - m_income_post

        # 인출/저축은 스칼라 (모든 trial 동일)
        if deficit > 0 and tax < 1:
            annual_savings = -(deficit / (1 - tax)) * 12
        else:
            annual_savings = (m_income_post - cur_monthly_exp) * 12

        prev = asset_paths[:, k - 1]
        annual_return = prev * annual_returns[:, k - 1]
        asset_paths[:, k] = prev + annual_return + annual_savings

    return asset_paths


def compute_threshold_probabilities(asset_paths, thresholds, retire_yr):
    """각 임계값에 대해 연도별 누적 도달 확률 계산.

    "누적"의 의미: trial이 (retire_yr+k) 시점까지 한 번이라도 임계값 이하로
    떨어진 적이 있으면 그 trial은 도달한 것으로 간주.

    Args:
      asset_paths — shape (n_trials, post_years+1)
      thresholds — dict {label: threshold_value}
      retire_yr — 은퇴 시작 절대 연도

    Returns:
      dict {label: {"years": [...], "probs": [...]}} — 절대 연도 + 비율 (0~1)
    """
    n_trials, n_years_plus_1 = asset_paths.shape
    result = {}
    for label, threshold in thresholds.items():
        below = asset_paths <= threshold
        ever_below = np.cumsum(below, axis=1) > 0  # 한 번이라도 도달했으면 이후 True
        probs = ever_below.mean(axis=0).tolist()
        years = list(range(retire_yr, retire_yr + n_years_plus_1))
        result[label] = {"years": years, "probs": probs}
    return result


def fmt_man(val):
    if not np.isfinite(val):
        return "∞"
    return f"{val:,.0f}"


def fmt_eok(val):
    if not np.isfinite(val):
        return "∞"
    return f"{val / 10_000:.2f}억원"
