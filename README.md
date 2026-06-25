# SmartBudget BI

SmartBudget BI is a web application designed to help Israeli students understand, analyze, and improve their monthly financial behavior using Business Intelligence tools.

The system allows students to upload a CSV file exported from their bank account, automatically categorizes transactions, stores the data in Supabase, and presents financial insights through an interactive dashboard.

---

## Project Overview

Many students in Israel live on a limited monthly budget but do not clearly understand where their money goes.

Bank applications usually show raw transactions only, without categorization, comparison, or meaningful insights. SmartBudget BI solves this problem by transforming raw bank transaction data into useful financial intelligence.

Instead of only showing how much a student spent, the system compares the student’s spending to benchmark data and highlights categories where the student may be overspending.

---

## Main Features

- User registration and login
- Monthly budget setting
- Bank CSV file upload
- Automatic transaction categorization
- Transactions table
- Dashboard with total income, total expenses, and balance
- Spending by category
- Comparison to CBS / Israel Central Bureau of Statistics benchmark data
- End-of-month spending projection
- Budget alerts and insights

---

## Business Intelligence Value

SmartBudget BI does not only display financial data.  
It turns raw transactions into actionable insights.

Example:

> You spent 1,200 NIS on food this month.  
> The average student spends 820 NIS.  
> You are spending 46% more than average.

This helps students understand their financial behavior and make better decisions.

---

## Target Users

The target users are Israeli university students, usually aged 18–28, who receive monthly income from part-time jobs, scholarships, parental support, or other sources.

The system is designed for students who want to manage their money without manually entering every transaction.

---

## Tech Stack

| Layer | Technology |
|------|------------|
| Backend | Python Flask |
| Database | Supabase / PostgreSQL |
| Frontend | HTML, CSS, JavaScript |
| Charts | Chart.js |
| CSV Processing | pandas |
| Version Control | Git + GitHub |
| Deployment | Railway |
| AI Coding Assistant | Claude CLI |

---

## System Flow

```text
User
 ↓
Upload Bank CSV
 ↓
Flask Backend
 ↓
Python CSV Parser
 ↓
Transaction Categorizer
 ↓
Supabase Database
 ↓
BI Dashboard + Charts