"""
Bank Hapoalim PDF statement parser.

Statement column layout (visual RTL order): תאריך | פעולה | חובה | זכות | יתרה בש"ח

pdfplumber returns words sorted by x0 (left→right in PDF coords).
Because the statement is RTL, that order is the REVERSE of the visual reading order:

  row[0]   = יתרה (balance)  — starts with ₪, e.g. '₪.60'   ← skip
  row[1]   = amount           — x0 ≈ 160-280                  ← classify by x0
  row[2:-1]= פעולה tokens    — Hebrew words in reverse order  ← reverse to read
  row[-1]  = תאריך (date)    — DD/MM/YYYY                     ← anchor

Debit / credit is determined by the amount token's x0:
  160 ≤ x0 ≤ 220  →  זכות  (credit) → positive amount
  220 < x0 ≤ 280  →  חובה  (debit)  → negative amount
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
    """True if text is a numeric amount after stripping ₪ / commas."""
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

        for page_num, page in enumerate(pdf.pages, start=1):
            raw_text = page.extract_text() or ''
            print(f'[PDF DEBUG] ── page {page_num} raw text ──', flush=True)
            for line in raw_text.splitlines():
                print(f'[PDF DEBUG]   {line!r}', flush=True)

            words = page.extract_words(x_tolerance=4, y_tolerance=4)
            print(
                f'[PDF DEBUG] page {page_num}: {len(words)} word token(s)',
                flush=True,
            )
            if not words:
                continue

            print(f'[PDF DEBUG] page {page_num} word list (text | x0 | top):', flush=True)
            for w in words:
                print(
                    f'[PDF DEBUG]   {w["text"]!r:30s}  x0={w["x0"]:6.1f}  top={w["top"]:6.1f}',
                    flush=True,
                )

            # Bucket words into rows by y-position (2 px tolerance)
            lines: dict = {}
            for w in words:
                key = round(w['top'] / 2) * 2
                lines.setdefault(key, []).append(w)

            print(
                f'[PDF DEBUG] page {page_num}: {len(lines)} row bucket(s)',
                flush=True,
            )

            for top in sorted(lines):
                # Sort left→right by x0 (RTL PDF: balance first, date last)
                row = sorted(lines[top], key=lambda w: w['x0'])
                row_texts = [w['text'] for w in row]

                # ── 1. Date = last token matching DD/MM/YYYY ─────────────
                date_word = None
                for w in reversed(row):
                    if _DATE_RE.match(w['text']):
                        date_word = w
                        break

                if date_word is None:
                    print(
                        f'[PDF DEBUG]   row y={top}: no date — skipping {row_texts}',
                        flush=True,
                    )
                    continue

                dt = _date_to_iso(date_word['text'])
                if not dt:
                    continue

                # ── 2. Balance = first token starting with ₪ ─────────────
                balance_word = next(
                    (w for w in row if w['text'].startswith('₪')), None
                )

                # ── 3. Collect remaining tokens ───────────────────────────
                skip_ids = {id(date_word)}
                if balance_word:
                    skip_ids.add(id(balance_word))
                other = [w for w in row if id(w) not in skip_ids]

                # ── 4. Amount = first numeric token in remaining ──────────
                amount_word = None
                desc_tokens = []
                for w in other:
                    if amount_word is None and _is_number(w['text']):
                        amount_word = w
                    else:
                        desc_tokens.append(w)

                print(
                    f'[PDF DEBUG]   row y={top}: DATE={date_word["text"]!r}  '
                    f'balance={balance_word["text"] if balance_word else "none"!r}  '
                    f'amount_word={amount_word["text"] if amount_word else "none"!r}  '
                    f'desc_tokens={[w["text"] for w in desc_tokens]}',
                    flush=True,
                )

                if amount_word is None:
                    print(f'[PDF DEBUG]   no amount token — skipping', flush=True)
                    continue

                val = _clean_amount(amount_word['text'])
                if not val:
                    print(
                        f'[PDF DEBUG]   _clean_amount({amount_word["text"]!r}) returned None — skipping',
                        flush=True,
                    )
                    continue

                # ── 5. Classify by x0 position ────────────────────────────
                ax0 = amount_word['x0']
                if 160 <= ax0 <= 220:
                    amount = round(val, 2)    # זכות (credit) → positive
                    kind = 'זכות/credit'
                elif 220 < ax0 <= 280:
                    amount = -round(val, 2)   # חובה (debit) → negative
                    kind = 'חובה/debit'
                else:
                    # Outside mapped ranges — treat as debit and flag in logs
                    amount = -round(val, 2)
                    kind = f'unknown-x0={ax0:.1f}→debit'

                print(
                    f'[PDF DEBUG]   amount {amount_word["text"]!r} x0={ax0:.1f} '
                    f'→ {kind} → {amount}',
                    flush=True,
                )

                # ── 6. Description = tokens reversed (RTL → LTR) ─────────
                description = ' '.join(w['text'] for w in reversed(desc_tokens)).strip()

                print(
                    f'[PDF DEBUG]   → TRANSACTION: {dt}  {description!r}  {amount}',
                    flush=True,
                )
                transactions.append({
                    'date':             dt,
                    'description':      description,
                    'amount':           amount,
                    'transaction_type': '',
                })

    print(
        f'[PDF DEBUG] parse complete — {len(transactions)} transaction(s)',
        flush=True,
    )
    return transactions
