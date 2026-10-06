# Vyapar Saarthi AI — Smart Kirana POS & Voice Assistant

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask 3.0](https://img.shields.io/badge/framework-Flask%203.0-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)
[![Status: Active](https://img.shields.io/badge/status-active-brightgreen.svg)]()

> **Voice-First AI Kirana POS & Smart Inventory Assistant for Indian Micro-Retailers.**

Vyapar Saarthi AI is a lightweight, voice-enabled Point-of-Sale (POS), inventory management, and Khata ledger platform tailored specifically for Indian Kirana store owners. It combines speech-to-text processing, phonetic catalog matching (Hinglish), real-time stock tracking, and automated customer credit management into a simple web application.

---

## 🌟 Key Features

* 🎙️ **Voice-First Billing & Search**: Process items using natural voice commands in Hindi, Marathi, and Hinglish with intelligent fuzzy matching.
* 📦 **Real-Time Inventory Engine**: Automated stock deduction on bill completion, stock movement audit logging, and low-stock alerts.
* 🏬 **Multi-Store Management**: Register, switch, and delete multiple store outlets with isolated inventories, products, and customer ledgers per store.
* 📕 **Khata Ledger**: Manage customer credit/debit balances with transaction history and settlement tracking.
* 🤖 **Smart Assistant & Business Queries**: Ask sales, revenue, bill count, top products, low stock, and customer khata questions in natural language (Marathi, Hindi, English) with zero LLM hallucination — numbers are strictly computed by deterministic SQL queries.
* 🔒 **Role-Based Security**: Owner account authentication, session cookie encryption, and multi-tenant store isolation.
* 🧪 **Comprehensive Test Suite**: 33 automated test cases covering authentication, billing, voice pipeline, multilingual sales queries, multi-store, and database migrations.

---

## 📚 Documentation Index

For in-depth technical details, architecture, and specifications, explore our complete documentation suite:

| Document | Description |
| :--- | :--- |
| 📋 **[PROJECT_OVERVIEW.md](file:///d:/projectss/Vypaar%20sarthi/PROJECT_OVERVIEW.md)** | Core business vision, problem statement, and user personas |
| 🏗️ **[ARCHITECTURE.md](file:///d:/projectss/Vypaar%20sarthi/ARCHITECTURE.md)** | End-to-end system design, voice processing pipeline & data flow |
| 🗄️ **[DATABASE_SCHEMA.md](file:///d:/projectss/Vypaar%20sarthi/DATABASE_SCHEMA.md)** | Complete database model reference, entity relations & indexes |
| 📡 **[API_SPECIFICATION.md](file:///d:/projectss/Vypaar%20sarthi/API_SPECIFICATION.md)** | Complete REST API endpoint documentation with JSON schemas |
| 🎙️ **[AI_AND_VOICE_ENGINE.md](file:///d:/projectss/Vypaar%20sarthi/AI_AND_VOICE_ENGINE.md)** | Voice processing, STT integration, and phonetic matching specs |
| 💻 **[DEVELOPER_GUIDE.md](file:///d:/projectss/Vypaar%20sarthi/DEVELOPER_GUIDE.md)** | Local setup, testing instructions, seed loading, and deployment |
| 🛠️ **[TECH_STACK.md](file:///d:/projectss/Vypaar%20sarthi/TECH_STACK.md)** | Detailed breakdown of every technology, package, and library used |
| 🎨 **[DESIGN.md](file:///d:/projectss/Vypaar%20sarthi/DESIGN.md)** | Frontend design system, typography, color tokens, and responsive layout |
| 🚀 **[DEPLOYMENT_GUIDE.md](file:///d:/projectss/Vypaar%20sarthi/DEPLOYMENT_GUIDE.md)** | Step-by-step production cloud deployment guide (Render.com + Supabase) |

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.10+** installed
- **Git** installed

### 1. Clone & Navigate
```bash
git clone https://github.com/Dipesh562/vyapar-saarthi-ai.git
cd vyapar-saarthi-ai
```

### 2. Set Up Virtual Environment
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Optionally configure API keys for Speech-to-Text and AI providers in `.env`)*

### 5. Load Seed Data & Run Server
```bash
# Seed database with initial products & demo store
python seed/load_seed.py

# Run development server
python run.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your web browser.

---

## 📁 Project Structure

```
vyapar-saarthi-ai/
├── app/                            # Main Application Package
│   ├── models/                     # SQLAlchemy ORM Models (Product, Store, OwnerStore, etc.)
│   ├── routes/                     # Flask Blueprints (Billing, Inventory, Voice, Stores, Auth, etc.)
│   ├── services/                   # Business Logic (Billing Engine, Voice Pipeline, STT Client, etc.)
│   ├── templates/                  # Frontend Web Interface (index.html)
│   └── utils/                      # Helper Decorators & Utilities
├── seed/                           # Sample Inventory CSV & Load Scripts
├── tests/                          # Pytest Suite (33 unit & integration tests)
├── config.py                       # Application Configuration Settings
├── DEPLOYMENT_GUIDE.md             # Production Cloud Deployment Guide
├── Procfile                        # Gunicorn Production Server Process Spec
├── requirements.txt                # Python Dependencies
├── run.py                          # Server Application Entry Point
└── start.bat                       # One-Click Launch Script (Windows)
```

---

## 🧪 Running Tests

Execute all 32 automated test cases to verify system functionality:

```bash
pytest
```

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.
