"""
Bank Hapoalim PDF statement parser.

Statement column layout: תאריך | פעולה | חובה | זכות | יתרה בש"ח
  תאריך  – date, format DD/MM/YYYY → converted to YYYY-MM-DD
  פעולה  – transaction description
  חובה   – debit  amount (expense) → stored as negative
  זכות   – credit amount (income)  → stored as positive
  יתרה   – running balance → ignored

Strategy: use pdfplumber's word-level extraction (extract_words) so
each token carries an x-coordinate.  The centre x of the חובה / זכות
header words is used as a column anchor; every numeric token in a data
row is then classified as debit or credit by proximity to those anchors.
The last numeric token on a data row is always the running balance and
is discarded.
"""
import io
import re
import pdfplumber


_DATE_RE = re.compile(r'^(\d{2})/(\d{2})/(\d{4})$')


def _clean_amount(text):
    """Strip ₪, commas, whitespace; return float or None."""
    if not text:
        return None
    s = re.sub(r'[₪,\s]', '', str(text))
    try:
        return float(s)
    except ValueError:
        return None


def _is_number(text):
    """True if text is a numeric amount (after stripping ₪ / commas)."""
    cleaned = re.sub(r'[₪,\s]', '', text or '')
    return bool(re.fullmatch(r'\d+(\.\d+)?', cleaned))


def _date_to_iso(text):
    """DD/MM/YYYY → YYYY-MM-DD, or None if the format doesn't match."""
    m = _DATE_RE.match((text or '').strip())
    if not m:
        return None
    d, mo, y = m.groups()
    return f'{y}-{mo}-{d}'


def parse_pdf(file_storage):
    """Parse a Bank Hapoalim PDF bank statement.

    Returns a list of dicts with keys: date, description, amount,
    transaction_type.
    """
    content = file_storage.read()
    transactions = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        # Column-header anchors; refreshed on every page that contains headers.
        hova_cx = None   # centre-x of the חובה (debit) header
        zchut_cx = None  # centre-x of the זכות (credit) header

        for page in pdf.pages:
            words = page.extract_words(x_tolerance=4, y_tolerance=4)
            if not words:
                continue

            # Detect column header positions on this page
            for w in words:
                t = w['text']
                if 'חובה' in t:
                    hova_cx = (w['x0'] + w['x1']) / 2
                elif 'זכות' in t:
                    zchut_cx = (w['x0'] + w['x1']) / 2

            # Bucket words into text rows by y-position (2 px tolerance)
            lines: dict = {}
            for w in words:
                key = round(w['top'] / 2) * 2
                lines.setdefault(key, []).append(w)

            for top in sorted(lines):
                row = sorted(lines[top], key=lambda w: w['x0'])

                # Skip rows that don't begin with a DD/MM/YYYY date
                date_idx = None
                for i, w in enumerate(row):
                    if _DATE_RE.match(w['text']):
                        date_idx = i
                        break
                if date_idx is None:
                    continue

                dt = _date_to_iso(row[date_idx]['text'])
                if not dt:
                    continue

                # Tokens after the date → split into description and numbers
                desc_parts = []
                amount_words = []

                for w in row[date_idx + 1:]:
                    if _is_number(w['text']):
                        amount_words.append(w)
                    elif not amount_words:
                        # Still in the description zone (no numbers seen yet)
                        desc_parts.append(w['text'])

                description = ' '.join(desc_parts).strip()

                # Last numeric token is the running balance (יתרה) — discard it
                value_words = amount_words[:-1] if len(amount_words) > 1 else amount_words
                if not value_words:
                    continue

                # Classify each remaining token as debit or credit
                debit_val = None
                credit_val = None

                for vw in value_words:
                    val = _clean_amount(vw['text'])
                    if not val:
                        continue
                    cx = (vw['x0'] + vw['x1']) / 2

                    if hova_cx is not None and zchut_cx is not None:
                        if abs(cx - hova_cx) <= abs(cx - zchut_cx):
                            debit_val = val
                        else:
                            credit_val = val
                    else:
                        # Fallback when headers were not found:
                        # assume left half = debit, right half = credit
                        if cx <= page.width / 2:
                            debit_val = val
                        else:
                            credit_val = val

                if debit_val is not None:
                    amount = -round(debit_val, 2)
                elif credit_val is not None:
                    amount = round(credit_val, 2)
                else:
                    continue

                transactions.append({
                    'date':             dt,
                    'description':      description,
                    'amount':           amount,
                    'transaction_type': '',
                })

    return transactions
