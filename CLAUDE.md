# SmartBudget BI

## Project Overview
SmartBudget BI is a web application for Israeli university students to manage and understand personal finances using business intelligence insights.

The MVP focuses on a single, working CSV upload flow that parses bank transactions, auto-categorizes them using Hebrew keyword matching, saves transactions to Supabase, and presents dashboard insights.

## Tech Stack
- Python + Flask backend
- Jinja2 HTML templates frontend
- Chart.js from CDN for visualizations
- Supabase PostgreSQL for database and authentication
- Railway for deployment
- Git + GitHub for version control

## Main MVP Flow
1. Student uploads a bank transaction CSV file.
2. Python reads and parses the CSV file.
3. The system extracts `date`, `description`, `amount`, and `transaction type`.
4. Each transaction is auto-categorized using Hebrew keyword matching.
   - Examples: `שופרסל` => `Food`, `רכבת` => `Transport`, `סופר פארם` => `Health`.
5. Transactions are saved to Supabase.
6. Dashboard shows BI insights.

## Dashboard Requirements
The dashboard must show:
- Total income
- Total expenses
- Current balance
- Spending by category chart
- CBS benchmark comparison chart
- End-of-month projection
- Budget utilization percentage

## Database Tables
The data model should include these tables:
- `students`
- `transactions`
- `categories`
- `budget_goals`
- `cbs_benchmarks`
- `monthly_summary`

## Key Files and Responsibilities
- `app.py` — Flask routes and request handling
- `services/categorizer.py` — Hebrew keyword categorization logic
- `services/csv_parser.py` — CSV parsing and normalization
- `services/analytics.py` — BI calculations and dashboard metrics
- `models/supabase_client.py` — Supabase database connection
- `templates/` — Jinja2 HTML pages
- `static/` — CSS and client-side JavaScript files

## Important Implementation Rules
- Never hardcode Supabase credentials.
- Always use environment variables for Supabase URL, API keys, and other secrets.
- Store all amounts as numbers with 2 decimal places.
- Date format must always be `YYYY-MM-DD`.
- Category names must be exactly:
  - `Food`
  - `Rent`
  - `Transport`
  - `Entertainment`
  - `Education`
  - `Health`
  - `Shopping`
  - `Other`
- Always wrap database calls in `try/except` error handling.
- Keep the code simple enough for students to explain in class.
- Build one working CSV flow perfectly before adding extra features.
- PDF and Excel upload support are future extensions; do not build them until CSV works.

## Environment Variables
Set the following variables in your deployment or local `.env` file:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (if required for backend writes)
- `FLASK_ENV` (optional)
- `SECRET_KEY` (Flask session secret)

## Development Notes
- Focus on a clean CSV upload page and a dashboard page.
- Validate and normalize transaction dates and amounts on import.
- Use a category map with Hebrew keywords to assign the exact allowed category names.
- Use Chart.js from CDN in templates for charts.
- Keep the backend simple and easy to explain.
- Do not add PDF or Excel parsing until the CSV flow is stable.

## Deployment
- Use Railway for deployment.
- Ensure environment variables are configured in Railway.
- Do not store secrets in source control.

## Recommended Next Steps
1. Create `app.py` with CSV upload and dashboard routes.
2. Implement `services/csv_parser.py` to read CSV and normalize fields.
3. Implement `services/categorizer.py` for Hebrew keyword mapping.
4. Add `models/supabase_client.py` with environment-based connection logic.
5. Build the dashboard using `services/analytics.py`.
6. Add Jinja2 templates for upload and dashboard pages.
7. Test end-to-end flow with a sample bank CSV.
