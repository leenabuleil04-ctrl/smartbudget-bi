from typing import List

ALLOWED_CATEGORIES = [
    'Food', 'Rent', 'Transport', 'Entertainment', 'Education', 'Health', 'Shopping', 'Other'
]

# Simple Hebrew keyword map to categories
CATEGORY_KEYWORDS = {
    'שופרסל': 'Food',
    'סופר': 'Food',
    'רכבת': 'Transport',
    'מטרו': 'Transport',
    'אוטובוס': 'Transport',
    'תחבורה': 'Transport',
    'סופר פארם': 'Health',
    'פארם': 'Health',
    'בתי ספר': 'Education',
    'אוניברסיטה': 'Education',
    'שכר דירה': 'Rent',
    'חנות': 'Shopping',
    'מקדונלדס': 'Food',
    'פיצה': 'Food',
    'קולנוע': 'Entertainment',
}


def categorize_description(description: str) -> str:
    if not description:
        return 'Other'
    text = description.lower()
    for kw, cat in CATEGORY_KEYWORDS.items():
        if kw in text:
            return cat
    return 'Other'


def categorize_transactions(transactions: List[dict]) -> List[dict]:
    for t in transactions:
        desc = t.get('description', '')
        t['category'] = categorize_description(desc)
    return transactions
