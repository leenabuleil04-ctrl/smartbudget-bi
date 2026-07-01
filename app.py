import io
import os
import calendar
from datetime import date
from html import escape as _xe
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import config
from supabase_auth.errors import AuthApiError
from models.supabase_client import get_supabase_client
from services.csv_parser import parse_csv
from services.categorizer import categorize_transactions, categorize_description, ALLOWED_CATEGORIES
from services.analytics import compute_metrics, compute_monthly_trend, compute_spending_alerts, generate_insights, CATEGORY_ORDER

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY or os.urandom(24)

supabase = None
try:
    supabase = get_supabase_client()
except Exception:
    supabase = None

# ── CBS benchmark seed data (Feature 2) ──
CBS_BENCHMARK_DATA = [
    {'category': 'Food',          'monthly_avg': 1200},
    {'category': 'Rent',          'monthly_avg': 2800},
    {'category': 'Transport',     'monthly_avg': 600},
    {'category': 'Entertainment', 'monthly_avg': 400},
    {'category': 'Education',     'monthly_avg': 500},
    {'category': 'Health',        'monthly_avg': 300},
    {'category': 'Shopping',      'monthly_avg': 800},
    {'category': 'Other',         'monthly_avg': 400},
]


def seed_cbs_benchmarks():
    if supabase is None:
        return
    try:
        supabase.table('cbs_benchmarks').upsert(
            CBS_BENCHMARK_DATA, on_conflict='category'
        ).execute()
    except Exception:
        pass


seed_cbs_benchmarks()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    user = session.get('user')
    if not user:
        flash('Please log in to view the dashboard', 'error')
        return redirect(url_for('login'))

    # Feature 3: month filter from query param, default to current month
    selected_month = request.args.get('month', '').strip()
    if not selected_month:
        selected_month = date.today().strftime('%Y-%m')

    # Fetch all transactions to build available-months list
    all_transactions = []
    try:
        res = supabase.table('transactions').select('*').eq('student_id', user['id']).execute()
        if not getattr(res, 'error', None):
            all_transactions = res.data or []
    except Exception:
        all_transactions = []

    # Available months for the selector dropdown (falls back to date[:7] if month column absent)
    available_months = sorted(set(
        t.get('month') or t.get('date', '')[:7]
        for t in all_transactions
        if t.get('date')
    ), reverse=True)
    if not available_months:
        available_months = [selected_month]
    if selected_month not in available_months:
        available_months.insert(0, selected_month)

    # Filter to selected month
    transactions = [
        t for t in all_transactions
        if (t.get('month') or t.get('date', '')[:7]) == selected_month
    ]

    metrics = compute_metrics(transactions)

    cat_labels = CATEGORY_ORDER
    cat_values = [metrics['by_category'].get(c, 0) for c in cat_labels]

    # Monthly trend uses all transactions (not month-filtered) for 6-month view
    trend_labels, trend_values = compute_monthly_trend(all_transactions)
    alerts = compute_spending_alerts(all_transactions)

    cbs_benchmarks_raw = []
    cbs_by_category = {}
    try:
        res = supabase.table('cbs_benchmarks').select('category,monthly_avg').execute()
        if not getattr(res, 'error', None) and res.data:
            cbs_benchmarks_raw = res.data
            # Average multiple rows per category before building chart values
            _cbs_sums: dict = {}
            _cbs_counts: dict = {}
            for row in res.data:
                cat = (row.get('category') or '').strip()
                val = float(row.get('monthly_avg', 0) or 0)
                if cat and val > 0:
                    _cbs_sums[cat]   = _cbs_sums.get(cat, 0.0) + val
                    _cbs_counts[cat] = _cbs_counts.get(cat, 0)  + 1
            cbs_by_category = {
                cat: _cbs_sums[cat] / _cbs_counts[cat]
                for cat in _cbs_sums
            }
    except Exception:
        pass
    cbs_values = [cbs_by_category.get(c, 0) for c in cat_labels]

    budget_goals_raw = []
    budget_breakdown = {}
    try:
        res = supabase.table('budget_goals').select('category,monthly_limit_ils') \
            .eq('student_id', user['id']).execute()
        if not getattr(res, 'error', None) and res.data:
            budget_goals_raw = res.data
            for row in res.data:
                cat = row.get('category')
                goal = float(row.get('monthly_limit_ils') or 0)
                if cat and goal > 0:
                    spent = metrics['by_category'].get(cat, 0.0)
                    pct = min(round((spent / goal) * 100, 1), 999)
                    budget_breakdown[cat] = {'goal': goal, 'spent': spent, 'pct': pct}
    except Exception:
        pass

    insights = generate_insights(metrics['by_category'], cbs_benchmarks_raw, budget_goals_raw)

    return render_template(
        'dashboard.html',
        metrics=metrics,
        cat_labels=cat_labels,
        cat_values=cat_values,
        cbs_values=cbs_values,
        budget_breakdown=budget_breakdown,
        trend_labels=trend_labels,
        trend_values=trend_values,
        alerts=alerts,
        transactions=transactions,
        insights=insights,
        selected_month=selected_month,
        available_months=available_months,
    )


@app.route('/export')
def export_pdf():
    user = session.get('user')
    if not user:
        flash('Please log in', 'error')
        return redirect(url_for('login'))

    selected_month = request.args.get('month', date.today().strftime('%Y-%m')).strip()

    # ── Fetch data (same logic as dashboard route) ─────────────────────
    transactions = []
    try:
        res = supabase.table('transactions').select('*').eq('student_id', user['id']).execute()
        if not getattr(res, 'error', None):
            transactions = [
                t for t in (res.data or [])
                if (t.get('month') or t.get('date', '')[:7]) == selected_month
            ]
    except Exception:
        pass

    metrics = compute_metrics(transactions)

    cbs_benchmarks_raw, cbs_by_category = [], {}
    try:
        res = supabase.table('cbs_benchmarks').select('category,monthly_avg').execute()
        if not getattr(res, 'error', None) and res.data:
            cbs_benchmarks_raw = res.data
            _s, _c = {}, {}
            for row in cbs_benchmarks_raw:
                cat = row['category']
                val = float(row.get('monthly_avg', 0) or 0)
                if val > 0:
                    _s[cat] = _s.get(cat, 0.0) + val
                    _c[cat] = _c.get(cat, 0) + 1
            cbs_by_category = {cat: _s[cat] / _c[cat] for cat in _s}
    except Exception:
        pass

    budget_goals_raw = []
    try:
        res = (supabase.table('budget_goals')
               .select('category,monthly_limit_ils')
               .eq('student_id', user['id']).execute())
        if not getattr(res, 'error', None) and res.data:
            budget_goals_raw = res.data
    except Exception:
        pass

    insights = generate_insights(metrics['by_category'], cbs_benchmarks_raw, budget_goals_raw)

    # ── Build PDF ───────────────────────────────────────────────────────
    buf = io.BytesIO()
    W   = A4[0] - 4 * cm   # usable content width
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=2*cm,
                            leftMargin=2*cm,  rightMargin=2*cm)

    TEAL   = colors.HexColor('#005c55')
    TEAL_L = colors.HexColor('#e8f5f4')
    GREY   = colors.HexColor('#6e7977')
    RED    = colors.HexColor('#b00020')
    GREEN  = colors.HexColor('#166534')
    BORDER = colors.HexColor('#bdd8d5')
    ss     = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, parent=ss['Normal'], **kw)

    story = []

    # 1. Header banner ──────────────────────────────────────────────────
    user_name = _xe(user.get('name') or user.get('email', ''))
    banner = Table(
        [[
            Paragraph('SmartBudget BI<br/>'
                      '<font size="10">Monthly Financial Report</font>',
                      ps('bh', fontSize=18, fontName='Helvetica-Bold',
                         textColor=colors.white, leading=26)),
            Paragraph(f'<b>{user_name}</b><br/>'
                      f'<font size="10">{selected_month}</font>',
                      ps('br', fontSize=13, fontName='Helvetica',
                         textColor=colors.white, leading=20, alignment=TA_RIGHT)),
        ]],
        colWidths=[W * 0.65, W * 0.35],
    )
    banner.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), TEAL),
        ('LEFTPADDING',   (0, 0), (-1, -1), 20),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 20),
        ('TOPPADDING',    (0, 0), (-1, -1), 22),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 22),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(banner)
    story.append(Spacer(1, 0.6 * cm))

    # 2. KPI row ────────────────────────────────────────────────────────
    bal_color = GREEN if metrics['balance'] >= 0 else RED
    kpi = Table(
        [[
            Paragraph(f'<b>ILS {metrics["total_income"]:,.2f}</b>',
                      ps('ki',  fontSize=16, fontName='Helvetica-Bold', textColor=GREEN,  alignment=TA_CENTER)),
            Paragraph(f'<b>ILS {metrics["total_expenses"]:,.2f}</b>',
                      ps('ke',  fontSize=16, fontName='Helvetica-Bold', textColor=RED,    alignment=TA_CENTER)),
            Paragraph(f'<b>ILS {metrics["balance"]:,.2f}</b>',
                      ps('kb',  fontSize=16, fontName='Helvetica-Bold', textColor=bal_color, alignment=TA_CENTER)),
        ], [
            Paragraph('Total Income',   ps('kli', fontSize=9, fontName='Helvetica', textColor=GREY, alignment=TA_CENTER)),
            Paragraph('Total Expenses', ps('kle', fontSize=9, fontName='Helvetica', textColor=GREY, alignment=TA_CENTER)),
            Paragraph('Net Balance',    ps('klb', fontSize=9, fontName='Helvetica', textColor=GREY, alignment=TA_CENTER)),
        ]],
        colWidths=[W / 3, W / 3, W / 3],
    )
    kpi.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), TEAL_L),
        ('TOPPADDING',    (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('LINEAFTER',     (0, 0), (1, -1),  1, BORDER),
    ]))
    story.append(kpi)
    story.append(Spacer(1, 0.6 * cm))

    # 3. Category spending table ────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=1, color=BORDER, spaceAfter=4))
    story.append(Paragraph('SPENDING BY CATEGORY',
                            ps('sh', fontSize=9, fontName='Helvetica-Bold',
                               textColor=TEAL, spaceBefore=2, spaceAfter=6)))

    total_exp = metrics['total_expenses']
    cat_rows = []
    for cat in CATEGORY_ORDER:
        spent = metrics['by_category'].get(cat, 0.0)
        if spent <= 0:
            continue
        pct   = f'{spent / total_exp * 100:.1f}%' if total_exp > 0 else '-'
        cbs_v = cbs_by_category.get(cat, 0.0)
        cat_rows.append([cat, f'ILS {spent:,.2f}', pct, f'ILS {cbs_v:,.0f}' if cbs_v > 0 else '-'])

    if not cat_rows:
        cat_rows = [['No expenses recorded this month', '', '', '']]

    TH = ps('th', fontSize=9, fontName='Helvetica-Bold', textColor=colors.white)
    TD = ps('td', fontSize=9, fontName='Helvetica',      textColor=colors.HexColor('#1a1e1d'))
    ct = Table(
        [[Paragraph(h, TH) for h in ['Category', 'Amount (ILS)', '% of Total', 'CBS Avg (ILS)']],
         *[[Paragraph(r[0], TD), r[1], r[2], r[3]] for r in cat_rows]],
        colWidths=[W * 0.35, W * 0.25, W * 0.20, W * 0.20],
    )
    ct.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0),  TEAL),
        ('TOPPADDING',     (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 7),
        ('LEFTPADDING',    (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 10),
        ('FONTNAME',       (1, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',       (1, 1), (-1, -1), 9),
        ('ALIGN',          (1, 0), (-1, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, TEAL_L]),
        ('LINEBELOW',      (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(ct)
    story.append(Spacer(1, 0.6 * cm))

    # 4. Top 3 insights ─────────────────────────────────────────────────
    top_ins = insights[:3]
    if top_ins:
        story.append(HRFlowable(width='100%', thickness=1, color=BORDER, spaceAfter=4))
        story.append(Paragraph('TOP INSIGHTS',
                                ps('ih', fontSize=9, fontName='Helvetica-Bold',
                                   textColor=TEAL, spaceBefore=2, spaceAfter=6)))
        TYPE_ACCENT = {
            'danger':  (colors.HexColor('#fff1f2'), colors.HexColor('#ef4444')),
            'warning': (colors.HexColor('#fffbeb'), colors.HexColor('#f59e0b')),
            'good':    (colors.HexColor('#f0fdf4'), colors.HexColor('#22c55e')),
            'info':    (colors.HexColor('#eff6ff'), colors.HexColor('#3b82f6')),
        }
        for idx, ins in enumerate(top_ins):
            bg, accent = TYPE_ACCENT.get(ins['type'], (TEAL_L, TEAL))
            it = Table(
                [[Paragraph(_xe(ins['text']),
                            ps(f'it{idx}', fontSize=9, fontName='Helvetica',
                               textColor=colors.HexColor('#1a1e1d'), leading=15))]],
                colWidths=[W],
            )
            it.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (-1, -1), bg),
                ('LEFTPADDING',   (0, 0), (-1, -1), 14),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 14),
                ('TOPPADDING',    (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LINEBEFORE',    (0, 0), (0,  -1), 4, accent),
            ]))
            story.append(it)
            story.append(Spacer(1, 0.2 * cm))

    # 5. Footer ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GREY))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(
        f'Generated {date.today().strftime("%B %d, %Y")}  |  SmartBudget BI',
        ps('ft', fontSize=8, fontName='Helvetica', textColor=GREY, alignment=TA_CENTER),
    ))

    doc.build(story)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=f'smartbudget_{selected_month}.pdf',
        mimetype='application/pdf',
    )


@app.route('/api/chat', methods=['POST'])
def api_chat():
    user = session.get('user')
    if not user:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    month    = (data.get('month')    or date.today().strftime('%Y-%m')).strip()

    if not question:
        return jsonify({'reply': 'Please ask a question.'}), 200

    # ── Fetch this month's transactions ──
    all_tx = []
    try:
        res = supabase.table('transactions').select('*').eq('student_id', user['id']).execute()
        all_tx = res.data or []
    except Exception:
        pass

    month_tx = [
        t for t in all_tx
        if (t.get('month') or t.get('date', '')[:7]) == month
    ]
    metrics = compute_metrics(month_tx)

    # ── Fetch budget goals ──
    goals_map = {}
    try:
        res = supabase.table('budget_goals').select('category,monthly_limit_ils') \
            .eq('student_id', user['id']).execute()
        for row in (res.data or []):
            cat  = row.get('category')
            goal = float(row.get('monthly_limit_ils') or 0)
            if cat and goal > 0:
                goals_map[cat] = goal
    except Exception:
        pass

    # ── Build plain-text financial context ──
    try:
        from datetime import datetime as _dt
        month_label = _dt.strptime(month, '%Y-%m').strftime('%B %Y')
    except Exception:
        month_label = month

    cat_lines = []
    for cat in CATEGORY_ORDER:
        spent = metrics['by_category'].get(cat, 0.0)
        goal  = goals_map.get(cat, 0.0)
        if spent == 0 and goal == 0:
            continue
        if goal > 0:
            status = 'over budget' if spent > goal else 'within budget'
            cat_lines.append(
                f'  {cat}: spent ₪{spent:,.0f} of ₪{goal:,.0f} limit ({status})'
            )
        else:
            cat_lines.append(f'  {cat}: spent ₪{spent:,.0f} (no budget set)')

    cat_section = '\n'.join(cat_lines) if cat_lines else '  No spending recorded yet.'

    system_prompt = (
        f'You are SmartBudget BI, a friendly personal finance assistant for Israeli students.\n'
        f'The user is asking about their finances for {month_label}.\n\n'
        f'FINANCIAL SUMMARY FOR {month_label}:\n'
        f'  Total income:   ₪{metrics["total_income"]:,.0f}\n'
        f'  Total expenses: ₪{metrics["total_expenses"]:,.0f}\n'
        f'  Balance:        ₪{metrics["balance"]:,.0f}\n\n'
        f'SPENDING BY CATEGORY:\n'
        f'{cat_section}\n\n'
        f'INSTRUCTIONS:\n'
        f'- Answer only using the data above. If asked about something not in this data, '
        f'say "I don\'t have that information."\n'
        f'- Be concise: 2–4 sentences unless the user explicitly asks for detail.\n'
        f'- Use ₪ for all currency amounts.\n'
        f'- Be encouraging and constructive, never judgmental.\n'
        f'- Do not fabricate data or reference external sources.\n'
    )

    # ── Call OpenAI ──
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not api_key:
        return jsonify({'reply': "Sorry, I can't answer right now — the AI service isn't configured."}), 200

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': question},
            ],
            max_tokens=300,
            temperature=0.4,
        )
        reply = completion.choices[0].message.content.strip()
    except Exception:
        reply = "Sorry, I can't answer right now. Please try again later."

    return jsonify({'reply': reply}), 200


@app.route('/recategorize', methods=['POST'])
def recategorize():
    """Re-run keyword categorization on every transaction for the logged-in user.

    Useful after the keyword list is updated to fix previously imported
    transactions that were miscategorized.  Only updates rows where the
    category actually changes so the DB write count stays low.
    """
    user = session.get('user')
    if not user:
        flash('Please log in', 'error')
        return redirect(url_for('login'))

    try:
        res = supabase.table('transactions').select('id,description,category') \
            .eq('student_id', user['id']).execute()
        rows = res.data or []
    except Exception as e:
        flash(f'Could not fetch transactions: {e}', 'error')
        return redirect(url_for('transactions_page'))

    updated = 0
    errors  = 0
    for row in rows:
        new_cat = categorize_description(row.get('description', ''))
        if new_cat == row.get('category'):
            continue
        try:
            supabase.table('transactions') \
                .update({'category': new_cat}) \
                .eq('id', row['id']).execute()
            updated += 1
        except Exception:
            errors += 1

    if errors:
        flash(f'Re-categorized {updated} transaction(s) — {errors} error(s).', 'warning')
    else:
        flash(f'Re-categorized {updated} transaction(s) successfully.', 'success')
    return redirect(url_for('transactions_page'))


@app.route('/import', methods=['GET', 'POST'])
def import_page():
    user = session.get('user')
    if not user:
        flash('Please log in to import transactions', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('No file uploaded', 'error')
            return redirect(url_for('import_page'))

        # Feature 3: month selected on the import form
        selected_month = request.form.get('month', date.today().strftime('%Y-%m')).strip()

        try:
            # Feature 4: detect PDF vs CSV by file extension
            filename = (file.filename or '').lower()
            if filename.endswith('.pdf'):
                from services.pdf_parser import parse_pdf
                transactions = parse_pdf(file)
            else:
                transactions = parse_csv(file)
            transactions = categorize_transactions(transactions)

            # Feature 1: build dedup set from all existing transactions for this student
            existing = set()
            try:
                res = supabase.table('transactions').select('date,description,amount') \
                    .eq('student_id', user['id']).execute()
                for row in (res.data or []):
                    existing.add((
                        row.get('date', ''),
                        row.get('description', ''),
                        float(row.get('amount', 0)),
                    ))
            except Exception:
                pass

            records = []
            skipped = 0
            for t in transactions:
                amt = round(float(t.get('amount', 0)), 2)
                desc = t.get('description', '')
                dt = t['date']
                if (dt, desc, amt) in existing:
                    skipped += 1
                    continue
                records.append({
                    'student_id': user['id'],
                    'date': dt,
                    'description': desc,
                    'amount': amt,
                    'category': t.get('category', 'Other'),
                    'month': dt[:7],  # Feature 3: tag from transaction date
                })

            if records:
                try:
                    res = supabase.table('transactions').insert(records).execute()
                    err = getattr(res, 'error', None)
                    if err:
                        flash(f'Error saving transactions: {getattr(err, "message", str(err))}', 'error')
                        return redirect(url_for('import_page'))
                    msg = f'Imported {len(records)} transaction{"s" if len(records) != 1 else ""}'
                    if skipped:
                        msg += f' · {skipped} duplicate{"s" if skipped != 1 else ""} skipped'
                    flash(msg, 'success')
                except Exception as e:
                    flash(f'Unexpected DB error: {e}', 'error')
                    return redirect(url_for('import_page'))
            else:
                if skipped:
                    flash(
                        f'All {skipped} transaction{"s" if skipped != 1 else ""} already imported — '
                        'no duplicates added', 'info'
                    )
                else:
                    flash('No transactions found in file', 'info')
                return redirect(url_for('dashboard', month=selected_month))

        except Exception as e:
            flash(f'Failed to parse file: {e}', 'error')
            return redirect(url_for('import_page'))

        return redirect(url_for('dashboard', month=selected_month))

    # GET: build month grid data
    try:
        selected_year = int(request.args.get('year', ''))
    except (ValueError, TypeError):
        selected_year = date.today().year

    monthly_totals = {}
    try:
        res = supabase.table('transactions') \
            .select('month,date,amount') \
            .eq('student_id', user['id']) \
            .execute()
        for row in (res.data or []):
            m = row.get('month') or (row.get('date', '') or '')[:7]
            try:
                amt = float(row.get('amount', 0) or 0)
            except Exception:
                amt = 0.0
            if m and amt < 0:
                monthly_totals[m] = round(monthly_totals.get(m, 0.0) + (-amt), 2)
    except Exception:
        pass

    months_info = [
        {
            'num': i,
            'name': calendar.month_abbr[i],
            'full_name': calendar.month_name[i],
            'ym': f'{selected_year}-{i:02d}',
            'total': monthly_totals.get(f'{selected_year}-{i:02d}'),
        }
        for i in range(1, 13)
    ]

    default_month = date.today().strftime('%Y-%m')
    current_year = date.today().year

    return render_template(
        'import.html',
        default_month=default_month,
        months_info=months_info,
        selected_year=selected_year,
        current_year=current_year,
    )


@app.route('/transactions')
def transactions_page():
    user = session.get('user')
    if not user:
        flash('Please log in to view transactions', 'error')
        return redirect(url_for('login'))

    f_category  = request.args.get('category', '').strip()
    f_date_from = request.args.get('date_from', '').strip()
    f_date_to   = request.args.get('date_to', '').strip()
    f_search    = request.args.get('search', '').strip()

    transactions = []
    try:
        q = supabase.table('transactions').select('*').eq('student_id', user['id'])
        if f_category:
            q = q.eq('category', f_category)
        if f_date_from:
            q = q.gte('date', f_date_from)
        if f_date_to:
            q = q.lte('date', f_date_to)
        if f_search:
            q = q.ilike('description', f'%{f_search}%')
        res = q.order('date', desc=True).execute()
        if not getattr(res, 'error', None):
            transactions = res.data or []
    except Exception:
        transactions = []

    now_month = date.today().strftime('%Y-%m')

    return render_template(
        'transactions.html',
        transactions=transactions,
        categories=ALLOWED_CATEGORIES,
        f_category=f_category,
        f_date_from=f_date_from,
        f_date_to=f_date_to,
        f_search=f_search,
        now_month=now_month,
    )


# Feature 5: delete a single transaction
@app.route('/transactions/<tx_id>/delete', methods=['POST'])
def delete_transaction(tx_id):
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    try:
        supabase.table('transactions') \
            .delete() \
            .eq('id', tx_id) \
            .eq('student_id', user['id']) \
            .execute()
        flash('Transaction deleted', 'info')
    except Exception as e:
        flash(f'Error deleting transaction: {e}', 'error')
    return redirect(url_for('transactions_page'))


# Feature 5: delete all transactions for a given month
@app.route('/transactions/delete-month', methods=['POST'])
def delete_month_transactions():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    month = request.form.get('month', '').strip()
    if not month:
        flash('No month specified', 'error')
        return redirect(url_for('transactions_page'))
    try:
        year, mon = map(int, month.split('-'))
        last_day = calendar.monthrange(year, mon)[1]
        first = f'{month}-01'
        last  = f'{month}-{last_day:02d}'
        supabase.table('transactions') \
            .delete() \
            .eq('student_id', user['id']) \
            .gte('date', first) \
            .lte('date', last) \
            .execute()
        flash(f'All transactions for {month} have been deleted', 'info')
    except Exception as e:
        flash(f'Error deleting transactions: {e}', 'error')
    return redirect(url_for('transactions_page'))


@app.route('/transactions/delete-all', methods=['POST'])
def delete_all_transactions():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    if request.form.get('confirm', '').strip() != 'DELETE':
        flash('Type DELETE in the confirmation box to wipe all transactions.', 'error')
        return redirect(url_for('transactions_page'))
    try:
        supabase.table('transactions').delete().eq('student_id', user['id']).execute()
        flash('All your transactions have been permanently deleted.', 'info')
    except Exception as e:
        flash(f'Error deleting transactions: {e}', 'error')
    return redirect(url_for('transactions_page'))


@app.route('/budget', methods=['GET', 'POST'])
def budget():
    user = session.get('user')
    if not user:
        flash('Please log in to set budget goals', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            supabase.table('budget_goals').delete().eq('student_id', user['id']).execute()
            records = []
            for cat in ALLOWED_CATEGORIES:
                raw = request.form.get(cat, '').strip()
                if raw:
                    try:
                        amount = round(float(raw), 2)
                        if amount > 0:
                            records.append({
                                'student_id': user['id'],
                                'category': cat,
                                'monthly_limit_ils': amount,
                            })
                    except ValueError:
                        pass
            if records:
                supabase.table('budget_goals').insert(records).execute()
            flash('Budget goals saved', 'success')
        except Exception as e:
            flash(f'Error saving budget goals: {e}', 'error')
        return redirect(url_for('budget'))

    goals = {}
    try:
        res = supabase.table('budget_goals').select('category,monthly_limit_ils') \
            .eq('student_id', user['id']).execute()
        if not getattr(res, 'error', None) and res.data:
            for row in res.data:
                goals[row['category']] = row['monthly_limit_ils']
    except Exception:
        pass

    return render_template('budget.html', goals=goals, categories=ALLOWED_CATEGORIES)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        if not (name and email and password):
            flash('Name, email and password are required', 'error')
            return redirect(url_for('register'))

        if supabase is None:
            flash('Supabase client not configured', 'error')
            return redirect(url_for('register'))

        try:
            auth_res = supabase.auth.sign_up({'email': email, 'password': password})
            if not auth_res.user:
                flash('Registration failed — please try again', 'error')
                return redirect(url_for('register'))

            supabase.table('students').insert({
                'auth_id': str(auth_res.user.id),
                'name': name,
                'email': email,
            }).execute()

            flash('Registration successful — please log in', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Registration error: {e}', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not (email and password):
            flash('Email and password required', 'error')
            return redirect(url_for('login'))

        if supabase is None:
            flash('Supabase client not configured', 'error')
            return redirect(url_for('login'))

        try:
            auth_res = supabase.auth.sign_in_with_password({'email': email, 'password': password})
            if not auth_res.user:
                flash('Invalid email or password', 'error')
                return redirect(url_for('login'))

            auth_uuid = str(auth_res.user.id)
            user_email = auth_res.user.email
            meta = getattr(auth_res.user, 'user_metadata', None) or {}
            display_name = meta.get('name') if isinstance(meta, dict) else None

            student = None
            try:
                res = supabase.table('students').select('*').eq('auth_id', auth_uuid).maybe_single().execute()
                if res and res.data:
                    student = res.data
            except Exception:
                pass

            if not student:
                try:
                    res = supabase.table('students').select('*').eq('id', auth_uuid).maybe_single().execute()
                    if res and res.data:
                        student = res.data
                except Exception:
                    pass

            if not student:
                try:
                    res = supabase.table('students').upsert(
                        {'id': auth_uuid, 'auth_id': auth_uuid, 'email': user_email,
                         'name': display_name or user_email},
                        on_conflict='id',
                    ).execute()
                    student = (res.data or [{}])[0]
                except Exception:
                    student = {'id': auth_uuid, 'email': user_email, 'name': display_name or user_email}

            session['user'] = {
                'id': student.get('id'),
                'email': student.get('email'),
                'name': student.get('name'),
            }
            flash('Logged in successfully', 'success')
            return redirect(url_for('import_page'))
        except AuthApiError as e:
            flash(f'Login error: {e}', 'error')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Login error: {e}', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out', 'info')
    return redirect(url_for('index'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
