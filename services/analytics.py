from datetime import datetime, date
import calendar
from collections import defaultdict
from decimal import Decimal

CATEGORY_ORDER = ['Food', 'Rent', 'Transport', 'Entertainment', 'Education', 'Health', 'Shopping', 'Other']


def compute_metrics(transactions, month=None):
    """Compute totals and category breakdowns from a list of transactions.

    transactions : list of dicts with keys: date (YYYY-MM-DD), amount (float), category
    month        : 'YYYY-MM' of the viewed month — needed for correct projection when
                   viewing a past month (past → projection equals actual spend, no extrapolation)
    Returns dict with totals and data for charts.
    """
    total_income = 0.0
    total_expenses = 0.0
    by_category = {c: 0.0 for c in CATEGORY_ORDER}

    net = 0.0
    dates = []

    for t in transactions:
        try:
            amt = float(t.get('amount', 0) or 0)
        except Exception:
            amt = 0.0
        # positive amounts treated as income, negative as expense
        if amt >= 0:
            total_income += amt
        else:
            total_expenses += -amt
            cat = t.get('category', 'Other')
            if cat not in by_category:
                cat = 'Other'
            by_category[cat] += -amt

        net += amt
        d = t.get('date')
        if d:
            try:
                dates.append(datetime.strptime(d, '%Y-%m-%d').date())
            except Exception:
                pass

    balance = total_income - total_expenses

    # ── End-of-month projection ──
    today = date.today()
    cur_y, cur_m = today.year, today.month

    # Resolve which month is being viewed
    view_y, view_m = cur_y, cur_m
    if month:
        try:
            view_y, view_m = map(int, month.split('-'))
        except Exception:
            pass

    days_in_month = calendar.monthrange(view_y, view_m)[1]

    if (view_y, view_m) < (cur_y, cur_m):
        # Past month is already complete — projection IS the actual spend
        days_elapsed = days_in_month
        projection   = total_expenses
    else:
        # Current month — use today's real day, clamped to valid range
        days_elapsed  = max(1, min(today.day, days_in_month))
        avg_daily_net = net / days_elapsed
        projection    = balance + avg_daily_net * (days_in_month - days_elapsed)

    print(
        f'[projection] month={month or f"{cur_y}-{cur_m:02d}"} '
        f'days_elapsed={days_elapsed} days_in_month={days_in_month} '
        f'total_spent={total_expenses:.2f} projection={projection:.2f}',
        flush=True,
    )

    # round outputs to 2 decimals
    def r(v):
        return float(Decimal(v).quantize(Decimal('0.01')))

    metrics = {
        'total_income': r(total_income),
        'total_expenses': r(total_expenses),
        'balance': r(balance),
        'by_category': {k: r(v) for k, v in by_category.items()},
        'projection': r(projection),
    }
    return metrics


def compute_monthly_trend(transactions):
    """Return (labels, values) for total expenses over the last 6 calendar months."""
    monthly = defaultdict(float)
    for t in transactions:
        try:
            amt = float(t.get('amount', 0) or 0)
        except Exception:
            amt = 0.0
        if amt >= 0:
            continue
        d = t.get('date', '')
        if d and len(d) >= 7:
            monthly[d[:7]] += -amt  # store as positive expense total

    today = date.today()
    labels, values = [], []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        key = f'{y:04d}-{m:02d}'
        labels.append(datetime(y, m, 1).strftime('%b %Y'))
        values.append(round(monthly.get(key, 0.0), 2))
    return labels, values


def generate_insights(spending_by_category, cbs_benchmarks, budget_goals):
    """Return a list of insight dicts: {type, icon, text}.

    spending_by_category : {category: float}         — expenses this month (positive)
    cbs_benchmarks       : list of dicts from Supabase, keys: category, avg_monthly_ils
    budget_goals         : list of dicts from Supabase, keys: category, monthly_limit_ils
    """
    # Average multiple rows per category (table may contain duplicates)
    cbs_sums: dict = {}
    cbs_counts: dict = {}
    for row in (cbs_benchmarks or []):
        cat = row.get('category')
        val = float(row.get('avg_monthly_ils') or 0)
        if cat and val > 0:
            cbs_sums[cat]   = cbs_sums.get(cat, 0.0)  + val
            cbs_counts[cat] = cbs_counts.get(cat, 0)   + 1
    cbs_map = {cat: cbs_sums[cat] / cbs_counts[cat] for cat in cbs_sums}

    goals_map = {
        row['category']: float(row.get('monthly_limit_ils') or 0)
        for row in (budget_goals or [])
        if row.get('category')
    }

    insights = []

    # highest spending category — info, 📊
    categories_with_spend = {c: v for c, v in spending_by_category.items() if v > 0}
    if categories_with_spend:
        top_cat = max(categories_with_spend, key=categories_with_spend.get)
        top_amt = categories_with_spend[top_cat]
        insights.append({
            'type': 'info',
            'icon': '📊',
            'text': f'Your biggest expense this month is {top_cat} at ₪{top_amt:,.0f}.',
        })

    for cat in CATEGORY_ORDER:
        spent = spending_by_category.get(cat, 0.0)
        benchmark = cbs_map.get(cat, 0.0)
        goal = goals_map.get(cat, 0.0)

        # exceeded budget goal — danger, 💸
        if goal > 0 and spent > goal:
            over_pct = round((spent / goal - 1) * 100)
            insights.append({
                'type': 'danger',
                'icon': '💸',
                'text': f'You exceeded your {cat} budget by {over_pct}% (₪{spent:,.0f} vs ₪{goal:,.0f} limit).',
            })

        if benchmark > 0 and spent > 0:
            ratio = spent / benchmark
            if ratio >= 2.0:
                # 2x+ CBS average — danger, 🚨
                insights.append({
                    'type': 'danger',
                    'icon': '🚨',
                    'text': f'You spent {ratio:.1f}× the national average on {cat} (₪{spent:,.0f} vs ₪{benchmark:,.0f} avg).',
                })
            elif ratio >= 1.2:
                # 1.2x–2x CBS average — warning, ⚠️
                pct_over = round((ratio - 1) * 100)
                insights.append({
                    'type': 'warning',
                    'icon': '⚠️',
                    'text': f'You spent {pct_over}% above the national average on {cat} (₪{spent:,.0f} vs ₪{benchmark:,.0f} avg).',
                })
            elif ratio <= 0.7:
                # ≤70% of CBS average — good, ✅
                saving_pct = round((1 - ratio) * 100)
                insights.append({
                    'type': 'good',
                    'icon': '✅',
                    'text': f'Great job on {cat}! You spent {saving_pct}% less than the national average.',
                })

    return insights


def compute_spending_alerts(transactions):
    """Return list of alert strings for categories that rose >20% vs last month."""
    today = date.today()
    this_key = f'{today.year:04d}-{today.month:02d}'
    lm, ly = today.month - 1, today.year
    if lm <= 0:
        lm, ly = 12, ly - 1
    last_key = f'{ly:04d}-{lm:02d}'

    this_month: dict = defaultdict(float)
    last_month: dict = defaultdict(float)

    for t in transactions:
        try:
            amt = float(t.get('amount', 0) or 0)
        except Exception:
            amt = 0.0
        if amt >= 0:
            continue
        d = t.get('date', '')
        if not d or len(d) < 7:
            continue
        cat = t.get('category', 'Other')
        mk = d[:7]
        if mk == this_key:
            this_month[cat] += -amt
        elif mk == last_key:
            last_month[cat] += -amt

    alerts = []
    for cat in CATEGORY_ORDER:
        cur = this_month.get(cat, 0.0)
        prev = last_month.get(cat, 0.0)
        if prev > 0 and cur > prev * 1.2:
            pct = round((cur / prev - 1) * 100)
            alerts.append(f'You spent {pct}% more on {cat} than last month.')
    return alerts
