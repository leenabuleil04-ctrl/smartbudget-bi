from datetime import datetime, date
import calendar
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
