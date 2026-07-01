# SmartBudget BI

**SmartBudget BI** is a web application that helps users understand, analyze, and improve their monthly financial behavior using Business Intelligence tools. It turns a raw bank statement into categorized, benchmarked, and actionable financial insight.

## Overview

Many people — students and young professionals alike — live on a tight or irregular monthly budget but don't have a clear picture of where their money actually goes. Bank apps typically show only a raw list of transactions, with no categorization, no comparison to real benchmarks, and no guidance on what to actually change.

SmartBudget BI solves this by transforming a simple CSV bank statement into a full financial picture: transactions are automatically categorized, compared against real Israeli Central Bureau of Statistics (CBS) national averages and the user's own budget goals, visualized through interactive charts, and explained through an AI-powered financial assistant that answers questions and gives personalized recommendations.

## Target Users

SmartBudget BI is built for Israeli young adults and students managing a tight or irregular budget — typically aged 18–30 — relying on part-time income, scholarships, parental support, or freelance work. It's designed for anyone who wants clarity over their spending without manually tracking every transaction.

## Main Features

- User registration and login
- CSV bank statement import (English-language statements)
- Automatic transaction categorization (8 categories) using keyword matching
- Editable, filterable transactions table with duplicate detection on import
- Month-by-month data organization — tag imports to a specific month and switch between months
- Dashboard: total income, total expenses, and balance for the selected month
- Interactive spending-by-category breakdown (pie chart) and monthly spending trend (line chart)
- Comparison to real CBS (Israel Central Bureau of Statistics) national averages, category by category
- Custom monthly budget goals per category, with live utilization tracking and over-budget alerts
- Dynamic, plain-language Recommendation section summarizing the month and flagging problem categories
- AI Financial Assistant (powered by OpenAI GPT-4o-mini) — ask natural-language questions about your own spending and get personalized advice grounded in your real data
- Secure, per-user data isolation via Supabase

## Business Intelligence Value

SmartBudget BI doesn't just display financial data — it turns raw transactions into actionable insight.

Example:
> You spent ₪1,200 on Food this month. The national average is ₪820. You're spending 46% more than average.

This kind of comparison, combined with personal budget goals and AI-generated recommendations, helps users understand their financial behavior and make concrete decisions — not just look at a bigger pile of numbers.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python (Flask) |
| Database | Supabase (PostgreSQL), row-level access control |
| Frontend | HTML, CSS, JavaScript |
| Charts | Chart.js |
| CSV Processing | pandas |
| AI Assistant | OpenAI GPT-4o-mini |
| Hosting / Deployment | Railway (auto-deploy from GitHub on merge to main) |
| Version Control | Git + GitHub (feature branches, pull requests, code review before merge) |
| AI Coding Assistant | Claude Code |

## System Flow

1. User registers / logs in
2. User uploads a CSV bank statement and tags it to a specific month
3. Flask backend parses the CSV (pandas)
4. Transaction Categorizer auto-assigns each transaction to one of 8 categories (keyword-based matching, with duplicate detection against existing data)
5. Categorized transactions are stored in Supabase
6. Dashboard aggregates the month's data: income, expenses, balance, category breakdown, CBS comparison, budget utilization, and a generated recommendation
7. The user can additionally query the AI Financial Assistant, which pulls the same month's data and answers in natural language

## Development Workflow

The project follows a standard Git workflow: every change is made on its own feature branch, committed with focused and descriptive commit messages, opened as a pull request into `main`, reviewed, and only then merged — at which point Railway automatically redeploys the live site.

## Team & Contributions

| Member | Contribution |
|---|---|
| Mohammed Shawahna | UI/UX design — layout, color system, and page flow |
| Charbel Khoury | Research and sourcing of CBS benchmark data; Supabase database setup |
| Leen Abu Leil | Backend development, deployment (Railway), AI chatbot integration |
| Mohammed Tarabieh | Backend development, database logic, AI chatbot integration |

## Live Demo

[web-production-9d74f.up.railway.app](https://web-production-9d74f.up.railway.app/)
