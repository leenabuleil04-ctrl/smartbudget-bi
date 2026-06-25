from io import StringIO
import pandas as pd
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


ALLOWED_DATE_FORMAT = '%Y-%m-%d'


def _choose_column(columns, candidates):
    cols = [c for c in columns if any(k.lower() in c.lower() for k in candidates)]
    return cols[0] if cols else None


def _normalize_amount(value):
    if pd.isna(value):
        return Decimal('0.00')
    s = str(value).strip()
    s = s.replace('\xa0', '').replace(',', '')
    # remove currency symbols and parentheses
    s = s.replace('₪', '').replace('NIS', '').replace('(', '-').replace(')', '')
    try:
        d = Decimal(s)
    except Exception:
        try:
            d = Decimal(float(s))
        except Exception:
            d = Decimal('0.00')
    return d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _normalize_date(value):
    if pd.isna(value):
        return None
    if isinstance(value, (datetime,)):
        return value.strftime(ALLOWED_DATE_FORMAT)
    s = str(value).strip()
    # try common date formats
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y', '%m/%d/%Y'):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime(ALLOWED_DATE_FORMAT)
        except Exception:
            continue
    # fallback: try pandas
    try:
        dt = pd.to_datetime(s, dayfirst=True)
        return dt.strftime(ALLOWED_DATE_FORMAT)
    except Exception:
        return None


def parse_csv(file_storage):
    """Parse uploaded CSV file (Werkzeug FileStorage) into a list of transactions.

    Each transaction is a dict with: date (YYYY-MM-DD), description, amount (Decimal), transaction_type.
    """
    content = file_storage.read()
    # ensure pointer is at end; create text stream
    try:
        text = content.decode('utf-8-sig')
    except Exception:
        text = content.decode('latin1')

    df = pd.read_csv(StringIO(text))
    cols = df.columns.tolist()

    date_col = _choose_column(cols, ['date', 'תאריך'])
    desc_col = _choose_column(cols, ['description', 'desc', 'פירוט', 'details'])
    amount_col = _choose_column(cols, ['amount', 'sum', 'סכום', 'amt'])
    type_col = _choose_column(cols, ['type', 'transaction type', 'סוג'])

    transactions = []
    for _, row in df.iterrows():
        date = _normalize_date(row[date_col]) if date_col else None
        description = str(row[desc_col]) if desc_col and not pd.isna(row[desc_col]) else ''
        amount = _normalize_amount(row[amount_col]) if amount_col else Decimal('0.00')
        transaction_type = str(row[type_col]) if type_col and not pd.isna(row[type_col]) else ''

        if date is None:
            # skip rows without parseable date
            continue

        transactions.append({
            'date': date,
            'description': description,
            'amount': float(amount),
            'transaction_type': transaction_type,
        })

    return transactions
