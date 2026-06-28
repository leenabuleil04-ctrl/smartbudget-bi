from datetime import datetime, date
import calendar
from collections import defaultdict
from decimal import Decimal

CATEGORY_ORDER = ['Food', 'Rent', 'Transport', 'Entertainment', 'Education', 'Health', 'Shopping', 'Other']


def compute_metrics(transactions):
    """Compute totals and category breakdowns from a list of transactions.

    transactions: list of dicts with keys: date (YYYY-MM-DD), amount (float), category
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

    # projection to end of month: average daily net * remaining days + balance
    today = date.today()
    first = today.replace(day=1)
    total_days = calendar.monthrange(today.year, today.month)[1]
    days_passed = (today - first).days + 1
    days_passed = max(1, days_passed)
    avg_daily_net = net / days_passed if days_passed else 0
    remaining_days = total_days - days_passed
    projection = balance + avg_daily_net * remaining_days

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
