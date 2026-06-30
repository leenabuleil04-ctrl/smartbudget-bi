import io
from decimal import Decimal
import pdfplumber
from services.csv_parser import _normalize_date, _normalize_amount


def parse_pdf(file_storage):
    """Parse an uploaded bank statement PDF using pdfplumber.

    Extracts tables from each page, treats first row as header, then reuses
    the same column-detection and normalisation logic as the CSV parser.
    Returns a list of dicts with keys: date, description, amount, transaction_type.
    """
    content = file_storage.read()
    rows = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                rows.extend(table)

    if len(rows) < 2:
        return []

    # First row is the header
    raw_headers = rows[0]
    headers = [str(h).strip().lower() if h else '' for h in raw_headers]

    date_candidates    = ['date', 'תאריך']
    desc_candidates    = ['description', 'desc', 'פירוט', 'details']
    amount_candidates  = ['amount', 'sum', 'סכום', 'amt']
    type_candidates    = ['type', 'transaction type', 'סוג']

    def find_col(candidates):
        for i, h in enumerate(headers):
            if any(k in h for k in candidates):
                return i
        return None

    date_idx   = find_col(date_candidates)
    desc_idx   = find_col(desc_candidates)
    amount_idx = find_col(amount_candidates)
    type_idx   = find_col(type_candidates)

    transactions = []
    for row in rows[1:]:
        if not row or all(cell is None or str(cell).strip() == '' for cell in row):
            continue

        def cell(idx):
            if idx is None or idx >= len(row):
                return None
            return row[idx]

        dt = _normalize_date(cell(date_idx)) if date_idx is not None else None
        if dt is None:
            continue

        desc   = str(cell(desc_idx)).strip() if cell(desc_idx) is not None else ''
        amt    = _normalize_amount(cell(amount_idx)) if amount_idx is not None else Decimal('0.00')
        tx_typ = str(cell(type_idx)).strip() if cell(type_idx) is not None else ''

        transactions.append({
            'date':             dt,
            'description':      desc,
            'amount':           float(amt),
            'transaction_type': tx_typ,
        })

    return transactions
