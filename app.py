import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import config
from models.supabase_client import get_supabase_client
from services.csv_parser import parse_csv
from services.categorizer import categorize_transactions, ALLOWED_CATEGORIES
from services.analytics import compute_metrics, CATEGORY_ORDER

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY or os.urandom(24)

# Initialize Supabase client (raises if env not set)
supabase = None
try:
    supabase = get_supabase_client()
except Exception:
    supabase = None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    user = session.get('user')
    if not user:
        flash('Please log in to view the dashboard', 'error')
        return redirect(url_for('login'))

    # fetch transactions for the user
    transactions = []
    try:
        res = supabase.table('transactions').select('*').eq('student_id', user['id']).execute()
        err = getattr(res, 'error', None)
        if not err:
            transactions = res.data or []
    except Exception:
        transactions = []

    metrics = compute_metrics(transactions)

    # prepare category chart data in fixed order
    cat_labels = CATEGORY_ORDER
    cat_values = [metrics['by_category'].get(c, 0) for c in cat_labels]

    # simple CBS comparison placeholder (monthly totals last 6 months)
    cbs_labels = []
    cbs_values = []
    try:
        res = supabase.table('cbs_benchmarks').select('*').limit(6).execute()
        err = getattr(res, 'error', None)
        if not err and res.data:
            for row in res.data:
                cbs_labels.append(row.get('label', ''))
                cbs_values.append(row.get('value', 0))
    except Exception:
        cbs_labels = ['Jan','Feb','Mar']
        cbs_values = [0,0,0]

    # budget utilization: try fetching budget_goals
    budget_util = None
    try:
        res = supabase.table('budget_goals').select('*').eq('student_id', user['id']).execute()
        err = getattr(res, 'error', None)
        if not err and res.data:
            total_budget = sum((b.get('amount') or 0) for b in res.data)
            spent = sum(metrics['by_category'].values())
            if total_budget > 0:
                budget_util = f"{round((spent/total_budget)*100,1)}%"
            else:
                budget_util = 'No budget amounts configured'
    except Exception:
        budget_util = None

    return render_template('dashboard.html', metrics=metrics, cat_labels=cat_labels, cat_values=cat_values, cbs_labels=cbs_labels, cbs_values=cbs_values, budget_utilization=budget_util)


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

        try:
            transactions = parse_csv(file)
            transactions = categorize_transactions(transactions)

            # attach student_id and ensure fields
            records = []
            for t in transactions:
                records.append({
                    'student_id': user['id'],
                    'date': t['date'],
                    'description': t.get('description',''),
                    'amount': round(float(t.get('amount',0)),2),
                    'category': t.get('category','Other'),
                })

            # insert into Supabase in a try/except
            try:
                res = supabase.table('transactions').insert(records).execute()
                err = getattr(res, 'error', None)
                if err:
                    message = getattr(err, 'message', str(err))
                    flash(f'Error saving transactions: {message}', 'error')
                    return redirect(url_for('import_page'))
                flash(f'Imported {len(records)} transactions', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                flash(f'Unexpected DB error: {e}', 'error')
                return redirect(url_for('import_page'))

        except Exception as e:
            flash(f'Failed to parse CSV: {e}', 'error')
            return redirect(url_for('import_page'))

    return render_template('import.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        if not (email and password):
            flash('Email and password required', 'error')
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)

        # Insert user into Supabase `students` table
        if supabase is None:
            flash('Supabase client not configured', 'error')
            return redirect(url_for('register'))

        try:
            data = {
                'email': email,
                'password_hash': password_hash,
            }
            res = supabase.table('students').insert(data).execute()
            err = getattr(res, 'error', None)
            if err:
                flash(f'Registration error: {err}', 'error')
                return redirect(url_for('register'))
            flash('Registration successful — please log in', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Unexpected error: {e}', 'error')
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
            res = supabase.table('students').select('*').eq('email', email).execute()
            err = getattr(res, 'error', None)
            if err:
                flash('Login error', 'error')
                return redirect(url_for('login'))
            rows = res.data or []
            if not rows:
                flash('Invalid credentials', 'error')
                return redirect(url_for('login'))
            user = rows[0]
            stored_hash = user.get('password_hash')
            if not stored_hash or not check_password_hash(stored_hash, password):
                flash('Invalid credentials', 'error')
                return redirect(url_for('login'))

            # Login success
            session['user'] = {'id': user.get('id'), 'email': user.get('email'), 'name': user.get('name')}
            flash('Logged in successfully', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Unexpected error: {e}', 'error')
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
