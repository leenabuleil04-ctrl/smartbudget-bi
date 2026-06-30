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
        print(f'[PDF DEBUG] opened PDF — {len(pdf.pages)} page(s)', flush=True)

        # Column-header anchors; refreshed on every page that contains headers.
        hova_cx = None   # centre-x of the חובה (debit) header
        zchut_cx = None  # centre-x of the זכות (credit) header

        for page_num, page in enumerate(pdf.pages, start=1):
            # ── Raw text dump (visible in Railway logs) ──────────────────────
            raw_text = page.extract_text() or ''
            print(f'[PDF DEBUG] ── page {page_num} raw text ──', flush=True)
            for line in raw_text.splitlines():
                print(f'[PDF DEBUG]   {line!r}', flush=True)

            words = page.extract_words(x_tolerance=4, y_tolerance=4)
            print(
                f'[PDF DEBUG] page {page_num}: {len(words)} word tokens extracted',
                flush=True,
            )
            if not words:
                print(f'[PDF DEBUG] page {page_num}: no words — skipping', flush=True)
                continue

            # ── Print all tokens with their x-positions ───────────────────
            print(f'[PDF DEBUG] page {page_num} word list (text | x0 | top):', flush=True)
            for w in words:
                print(
                    f'[PDF DEBUG]   {w["text"]!r:30s}  x0={w["x0"]:6.1f}  top={w["top"]:6.1f}',
                    flush=True,
                )

            # Detect column header positions on this page
            prev_hova_cx, prev_zchut_cx = hova_cx, zchut_cx
            for w in words:
                t = w['text']
                if 'חובה' in t:
                    hova_cx = (w['x0'] + w['x1']) / 2
                elif 'זכות' in t:
                    zchut_cx = (w['x0'] + w['x1']) / 2

            if hova_cx != prev_hova_cx or zchut_cx != prev_zchut_cx:
                print(
                    f'[PDF DEBUG] page {page_num}: column anchors updated — '
                    f'חובה cx={hova_cx}  זכות cx={zchut_cx}',
                    flush=True,
                )
            else:
                print(
                    f'[PDF DEBUG] page {page_num}: column anchors unchanged — '
                    f'חובה cx={hova_cx}  זכות cx={zchut_cx}',
                    flush=True,
                )

            # Bucket words into text rows by y-position (2 px tolerance)
            lines: dict = {}
            for w in words:
                key = round(w['top'] / 2) * 2
                lines.setdefault(key, []).append(w)

            print(
                f'[PDF DEBUG] page {page_num}: {len(lines)} distinct row(s) after bucketing',
                flush=True,
            )

            for top in sorted(lines):
                row = sorted(lines[top], key=lambda w: w['x0'])
                row_texts = [w['text'] for w in row]

                # Skip rows that don't contain a DD/MM/YYYY date
                date_idx = None
                for i, w in enumerate(row):
                    if _DATE_RE.match(w['text']):
                        date_idx = i
                        break

                if date_idx is None:
                    # Log non-data rows at lower verbosity
                    print(
                        f'[PDF DEBUG]   row y={top}: no date match — tokens: {row_texts}',
                        flush=True,
                    )
                    continue

                print(
                    f'[PDF DEBUG]   row y={top}: DATE MATCHED {row[date_idx]["text"]!r} '
                    f'at index {date_idx} — full row: {row_texts}',
                    flush=True,
                )

                dt = _date_to_iso(row[date_idx]['text'])
                if not dt:
                    print(f'[PDF DEBUG]   row y={top}: _date_to_iso failed', flush=True)
                    continue

                # Tokens after the date → split into description and numbers
                desc_parts = []
                amount_words = []

                for w in row[date_idx + 1:]:
                    if _is_number(w['text']):
                        amount_words.append(w)
                    elif not amount_words:
                        desc_parts.append(w['text'])

                description = ' '.join(desc_parts).strip()
                amount_texts = [w['text'] for w in amount_words]
                print(
                    f'[PDF DEBUG]   desc={description!r}  amounts={amount_texts}',
                    flush=True,
                )

                # Last numeric token is the running balance (יתרה) — discard it
                value_words = amount_words[:-1] if len(amount_words) > 1 else amount_words
                if not value_words:
                    print(
                        f'[PDF DEBUG]   no value tokens after dropping balance — skipping row',
                        flush=True,
                    )
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
                        dist_h = abs(cx - hova_cx)
                        dist_z = abs(cx - zchut_cx)
                        verdict = 'חובה(debit)' if dist_h <= dist_z else 'זכות(credit)'
                        print(
                            f'[PDF DEBUG]   amount {vw["text"]!r} cx={cx:.1f} '
                            f'→ dist_חובה={dist_h:.1f} dist_זכות={dist_z:.1f} '
                            f'→ classified as {verdict}',
                            flush=True,
                        )
                        if dist_h <= dist_z:
                            debit_val = val
                        else:
                            credit_val = val
                    else:
                        verdict = 'debit(fallback-left)' if cx <= page.width / 2 else 'credit(fallback-right)'
                        print(
                            f'[PDF DEBUG]   amount {vw["text"]!r} cx={cx:.1f} '
                            f'page_width={page.width:.1f} — no headers, {verdict}',
                            flush=True,
                        )
                        if cx <= page.width / 2:
                            debit_val = val
                        else:
                            credit_val = val

                if debit_val is not None:
                    amount = -round(debit_val, 2)
                elif credit_val is not None:
                    amount = round(credit_val, 2)
                else:
                    print(f'[PDF DEBUG]   no debit or credit resolved — skipping row', flush=True)
                    continue

                print(
                    f'[PDF DEBUG]   → TRANSACTION: date={dt}  desc={description!r}  amount={amount}',
                    flush=True,
                )
                transactions.append({
                    'date':             dt,
                    'description':      description,
                    'amount':           amount,
                    'transaction_type': '',
                })

    print(f'[PDF DEBUG] parse complete — {len(transactions)} transaction(s) found', flush=True)
    return transactions
