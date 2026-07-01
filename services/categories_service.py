"""
Category service for SmartBudget BI.

This file reads category metadata from the Supabase `categories` table.
If Supabase is unavailable, it falls back to the default category list
so the app will not break.
"""

DEFAULT_CATEGORIES = [
    {"name": "Food", "icon": "🍔", "color": "#10B981"},
    {"name": "Rent", "icon": "🏠", "color": "#3B82F6"},
    {"name": "Transport", "icon": "🚌", "color": "#F59E0B"},
    {"name": "Entertainment", "icon": "🎬", "color": "#8B5CF6"},
    {"name": "Education", "icon": "📚", "color": "#06B6D4"},
    {"name": "Health", "icon": "💊", "color": "#EF4444"},
    {"name": "Shopping", "icon": "🛍️", "color": "#EC4899"},
    {"name": "Other", "icon": "📦", "color": "#94A3B8"},
]


def get_categories(supabase):
    """
    Return category rows from Supabase.

    Each category contains:
    - name
    - icon
    - color

    If the database query fails, return DEFAULT_CATEGORIES.
    """
    try:
        if supabase is None:
            return DEFAULT_CATEGORIES

        response = (
            supabase
            .table("categories")
            .select("name, icon, color")
            .order("id")
            .execute()
        )

        rows = response.data or []

        if rows:
            return rows

        return DEFAULT_CATEGORIES

    except Exception:
        return DEFAULT_CATEGORIES


def get_category_names(supabase):
    """
    Return only the category names.
    """
    return [category["name"] for category in get_categories(supabase)]