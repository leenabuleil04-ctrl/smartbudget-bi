import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
import config
from supabase_auth.errors import AuthApiError
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

    # category chart data in fixed order
    cat_labels = CATEGORY_ORDER
    cat_values = [metrics['by_category'].get(c, 0) for c in cat_labels]

    # CBS benchmark data per category (uses category + monthly_avg columns)
    cbs_by_category = {}
    try:
        res = supabase.table('cbs_benchmarks').select('category,monthly_avg').execute()
        err = getattr(res, 'error', None)
        if not err and res.data:
            for row in res.data:
                cbs_by_category[row['category']] = float(row.get('monthly_avg', 0) or 0)
    except Exception:
        pass
    cbs_values = [cbs_by_category.get(c, 0) for c in cat_labels]

    # budget utilization
    budget_util = None
    try:
        res = supabase.table('budget_goals').select('*').eq('student_id', user['id']).execute()
        err = getattr(res, 'error', None)
        if not err and res.data:
            total_budget = sum((b.get('amount') or 0) for b in res.data)
            spent = sum(metrics['by_category'].values())
            if total_budget > 0:
                budget_util = round((spent / total_budget) * 100, 1)
    except Exception:
        budget_util = None

    return render_template(
        'dashboard.html',
        metrics=metrics,
        cat_labels=cat_labels,
        cat_values=cat_values,
        cbs_values=cbs_values,
        budget_utilization=budget_util,
    )


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

            # 1) look up by auth_id (normal register flow)
            student = None
            try:
                res = supabase.table('students').select('*').eq('auth_id', auth_uuid).maybe_single().execute()
                if res and res.data:
                    student = res.data
            except Exception:
                pass

            # 2) fall back to id == auth_uuid (manual-upsert accounts)
            if not student:
                try:
                    res = supabase.table('students').select('*').eq('id', auth_uuid).maybe_single().execute()
                    if res and res.data:
                        student = res.data
                except Exception:
                    pass

            # 3) auto-create with both id and auth_id set to the auth UUID
            if not student:
                try:
                    res = supabase.table('students').upsert(
                        {'id': auth_uuid, 'auth_id': auth_uuid, 'email': user_email, 'name': display_name or user_email},
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
            return redirect(url_for('dashboard'))
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
