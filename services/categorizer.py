from typing import List

ALLOWED_CATEGORIES = [
    'Food', 'Rent', 'Transport', 'Entertainment', 'Education', 'Health', 'Shopping', 'Other'
]

# Keywords ordered most-specific → least-specific within each category.
# Checked against BOTH the original description and a char-reversed version
# (pdfplumber on some Hebrew PDFs returns characters within each word in
# visual/reversed order, e.g. 'טקריד רבטצמל' = reversed 'דירקט למצטבר').
CATEGORY_KEYWORDS = {
    # ── Food ─────────────────────────────────────────────────────────────
    'שופרסל': 'Food',
    'רמי לוי': 'Food',
    'יוחננוף': 'Food',
    'ויקטורי': 'Food',
    'מגה בול': 'Food',
    'מגה': 'Food',
    'טיב טעם': 'Food',
    'קינג סטור': 'Food',
    'AM:PM': 'Food',
    'am:pm': 'Food',
    'מסעדה': 'Food',
    'מאפייה': 'Food',
    'קפה גרג': 'Food',
    'גרג': 'Food',
    'ארומה': 'Food',
    'קפה': 'Food',
    'פיצה': 'Food',
    'פלאפל': 'Food',
    'שווארמה': 'Food',
    'שניצל': 'Food',
    'סושי': 'Food',
    'המבורגר': 'Food',
    'בורגר קינג': 'Food',
    'מקדונלד': 'Food',
    'KFC': 'Food',
    'kfc': 'Food',
    'דומינוס': 'Food',
    'אוכל': 'Food',
    'מזון': 'Food',
    'מכולת': 'Food',
    'ירקות': 'Food',
    'קצביה': 'Food',
    'מאפה': 'Food',
    'עוגה': 'Food',
    'גלידה': 'Food',

    # ── Rent ─────────────────────────────────────────────────────────────
    'שכר דירה': 'Rent',
    'שכירות': 'Rent',
    'דמי שכירות': 'Rent',
    'ועד בית': 'Rent',
    'ועד הבית': 'Rent',
    'משכנתא': 'Rent',
    'ארנונה': 'Rent',
    'שכד': 'Rent',

    # ── Transport ────────────────────────────────────────────────────────
    'רכבת ישראל': 'Transport',
    'רכבת': 'Transport',
    'רב קו': 'Transport',
    'רב-קו': 'Transport',
    'אגד': 'Transport',
    'דן באר': 'Transport',
    'מטרו': 'Transport',
    'אוטובוס': 'Transport',
    'תחבורה': 'Transport',
    'חניה': 'Transport',
    'פרקינג': 'Transport',
    'parking': 'Transport',
    'דלק': 'Transport',
    'בנזין': 'Transport',
    'פז': 'Transport',
    'סונול': 'Transport',
    'דור אלון': 'Transport',
    'yellow': 'Transport',
    'גט': 'Transport',
    'אובר': 'Transport',
    'uber': 'Transport',
    'מוניות': 'Transport',
    'מונית': 'Transport',
    'הסעה': 'Transport',
    'טיסה': 'Transport',
    'אל על': 'Transport',
    'ויזאייר': 'Transport',
    'ריינאייר': 'Transport',
    'wolt': 'Transport',     # Wolt is also a delivery service — listed under Transport, not Food

    # ── Entertainment ────────────────────────────────────────────────────
    'קולנוע': 'Entertainment',
    'סינמה': 'Entertainment',
    'יס': 'Entertainment',
    'הוט': 'Entertainment',
    'netflix': 'Entertainment',
    'נטפליקס': 'Entertainment',
    'spotify': 'Entertainment',
    'ספוטיפיי': 'Entertainment',
    'apple': 'Entertainment',
    'youtube': 'Entertainment',
    'disney': 'Entertainment',
    'hbo': 'Entertainment',
    'תיאטרון': 'Entertainment',
    'מוזיאון': 'Entertainment',
    'בידור': 'Entertainment',
    'כרטיס': 'Entertainment',
    'הופעה': 'Entertainment',
    'ספורט': 'Entertainment',
    'כדורגל': 'Entertainment',
    'steam': 'Entertainment',
    'gaming': 'Entertainment',
    'playstation': 'Entertainment',
    'xbox': 'Entertainment',

    # ── Education ────────────────────────────────────────────────────────
    'אוניברסיטה': 'Education',
    'האוניברסיטה': 'Education',
    'טכניון': 'Education',
    'מכללה': 'Education',
    'בית ספר': 'Education',
    'בית-ספר': 'Education',
    'שכר לימוד': 'Education',
    'שכ"ל': 'Education',
    'לימוד': 'Education',
    'קורס': 'Education',
    'udemy': 'Education',
    'coursera': 'Education',
    'ספרי לימוד': 'Education',

    # ── Health ───────────────────────────────────────────────────────────
    'סופר פארם': 'Health',
    'super-pharm': 'Health',
    'super pharm': 'Health',
    'פארם': 'Health',
    'בית חולים': 'Health',
    'מרפאה': 'Health',
    'רופא': 'Health',
    'תרופות': 'Health',
    'מכבי': 'Health',
    'כללית': 'Health',
    'מאוחדת': 'Health',
    'לאומית': 'Health',
    'קופת חולים': 'Health',
    'ביטוח בריאות': 'Health',
    'אופטיקה': 'Health',
    'שיניים': 'Health',
    'פיזיותרפיה': 'Health',
    'בריאות': 'Health',

    # ── Shopping ─────────────────────────────────────────────────────────
    'amazon': 'Shopping',
    'אמזון': 'Shopping',
    'aliexpress': 'Shopping',
    'ebay': 'Shopping',
    'ikea': 'Shopping',
    'איקאה': 'Shopping',
    'זארה': 'Shopping',
    'H&M': 'Shopping',
    'h&m': 'Shopping',
    'קסטרו': 'Shopping',
    'רנואר': 'Shopping',
    'אדידס': 'Shopping',
    'נייק': 'Shopping',
    'פוקס': 'Shopping',
    'הום סנטר': 'Shopping',
    'homecenter': 'Shopping',
    'אקסטרא': 'Shopping',
    'extra': 'Shopping',
    'bug': 'Shopping',
    'מחשב': 'Shopping',
    'טלפון': 'Shopping',
    'קניות': 'Shopping',
    'חנות': 'Shopping',
}

# Keyword list also checked in reverse-character order for RTL PDF encoding issues
# (e.g. 'טקריד' in PDF = 'דירקט' in logical Hebrew, reversed per word by pdfplumber)
_KW_LOWER = {k.lower(): v for k, v in CATEGORY_KEYWORDS.items()}


def _reverse_words(text: str) -> str:
    """Reverse characters within each whitespace-separated token.

    Handles PDFs where pdfplumber returns Hebrew in visual (right-to-left byte)
    order rather than Unicode logical order, e.g. 'טקריד' → 'דירקט'.
    """
    return ' '.join(word[::-1] for word in text.split())


def categorize_description(description: str) -> str:
    if not description:
        return 'Other'

    text     = description.lower()
    text_rev = _reverse_words(text)   # char-reversed version for RTL PDFs

    for kw, cat in _KW_LOWER.items():
        if kw in text:
            return cat
        # Only apply char-reversal check for keywords ≥ 3 chars — 2-char Hebrew
        # fragments are too likely to appear as substrings in unrelated reversed words.
        if len(kw) >= 3 and kw in text_rev:
            return cat

    return 'Other'


def categorize_transactions(transactions: List[dict]) -> List[dict]:
    for t in transactions:
        t['category'] = categorize_description(t.get('description', ''))
    return transactions
