# AI-Powered Food Waste Management Platform

**Module 1 (Weeks 1–2): Inventory Management & Expiry Tracking System**
**Module 2 (Weeks 3–4): AI-Powered Waste Prediction, Optimization & Decision Support**

Full-stack web platform that helps food businesses track inventory with real-time expiry
monitoring and AI-driven waste prediction, risk scoring and decision support.

## Features (Module 1)

- **Inventory Management** — manual entry, CSV bulk upload
- **Expiry Tracking** — automated alerts when items approach days-to-expiry thresholds
- **Product Categorization** — food taxonomy by perishability risk & storage requirement
- **Waste Risk Scoring** — combines days-to-expiry, stock level, perishability, and storage
  into an actionable 0–100 risk score per item
- **Transaction Logging** — purchase / sale / donation / disposal / adjustment
- **Dashboard** — inventory health, risk breakdown, expiring & surplus items, analytics
- **Multi-tenant** — each business sees only its own data (JWT auth)
- **Barcode/QR scanning** — scan product barcodes/QR codes with the camera to instantly find,
  update, or add inventory (powered by `html5-qrcode`, lazy-loaded)
- **Alert settings** — configure low-stock threshold, expiry-alert window, and alert toggles
- **POS integration** — generate API keys to push inventory / record sales from a POS terminal

## Features (Module 2)

- **Advanced Waste Prediction** — pure-Python statistical forecasting (exponential smoothing,
  moving average, linear trend) of daily demand, waste and surplus per product over a 7-day
  horizon. Never fabricates data: with too little history it transparently falls back to a
  rule-based estimate (`is_fallback` flag, confidence 0).
- **Explainable Risk Engine v2** — 4-level risk (low/moderate/high/critical) built from
  transparent, configurable factors (expiry, stock-vs-demand, historical waste rate, sales
  trend, perishability, storage, stock age) with a plain-language explanation per product.
- **Action Recommendations** — prioritized, quantified actions (discount, donation, reduce next
  purchase, stop reorder, mark for disposal, …) each with a data-grounded reason and expected
  benefit ($).
- **Surplus Allocation** — predicts surplus quantity, remaining safe period and recommended
  allocation (donation / promotion / transfer) with urgency ranking; integrates the donation
  partner registry.
- **Anomaly Detection** — rolling z-score / IQR detection of sales spikes & drops, unusual waste,
  stock increases and stock accumulation, with expected ranges and human-readable explanations;
  deduplicated notifications.
- **Waste Cause Classification** — rule-based root-cause analysis (overstocking, low demand,
  expiry, poor forecasting, seasonal shifts, storage issues, …).
- **What-If Simulation** — model pricing, donation and purchasing decisions to estimate waste,
  waste value and potential savings before acting; results are clearly labelled simulations.
- **Reorder Optimization** — recommended order quantity, reorder point, max/safety stock per
  product.
- **Forecast vs Actual** — MAE / RMSE / MAPE / accuracy per product and across the business;
  low-accuracy products surface as notifications.
- **Notifications** — in-app notifications for high waste risk, critical expiry, forecast
  surplus, donation opportunities and anomalies.
- **Scheduled Jobs** — pure-Python scheduler (`scheduler.py`) runs the daily AI job (predict →
  assess → recommend → allocate → notify) and a weekly forecast-evaluation job out-of-band.
- **M2 Dashboard & pages** — AI dashboard (KPIs, action center, charts), Analytics, Risk,
  Recommendations, Anomalies, Simulation, Notifications, and per-product detail pages.

## Architecture

- **Backend**: FastAPI + SQLAlchemy + SQLite (multi-tenant)
- **Frontend**: React (Vite) + React Router (hand-rolled SVG charts, no chart dependencies)
- **Forecasting/AI**: dependency-free statistical layer in `services/`, no ML framework required
- **API**: REST with JWT Bearer authentication (OAuth2 password flow)

## Project Structure

```
food-waste-platform/
├── backend/
│   ├── main.py             # FastAPI app entry (all routers wired)
│   ├── config.py           # settings / env (pydantic-settings)
│   ├── database.py         # SQLAlchemy engine/session
│   ├── security.py         # password hashing + JWT
│   ├── scheduler.py        # standalone daily/weekly job runner
│   ├── models/             # SQLAlchemy ORM models (M1 + M2)
│   ├── schemas/            # Pydantic schemas
│   ├── routes/             # API route handlers (+ M2: waste, risk, recommendations,
│   │                       #   simulations, notifications, surplus, products, dashboard/summary)
│   ├── services/           # forecasting, risk_engine, recommendation_engine, surplus_engine,
│   │                       #   anomaly_detector, cause_classifier, simulation_engine,
│   │                       #   inventory_optimization, forecast_evaluator, analytics_service,
│   │                       #   notification_service (+ M1 risk_service/CSV parser)
│   ├── jobs/               # daily.py, weekly.py inference jobs
│   ├── tests/              # pytest: unit + API integration + tenant isolation
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── pages/          # dashboard, inventory, analytics, risk, recommendations,
    │   │                   #   anomalies, simulation, notifications, products/:id, …
    │   ├── components/     # layout (nav + notification bell), badges, SVG charts
    │   ├── context/        # auth context
    │   └── services/api.js # API client
    ├── vite.config.js      # dev proxy to backend
    └── package.json
```

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm

---

## Running the Project

### 1. Start the Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Backend runs at http://127.0.0.1:8000.
Interactive API docs at http://127.0.0.1:8000/docs.

### 2. Start the Frontend (React)

In a **second terminal**:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173.

### 3. Use the application

1. Open http://localhost:5173
2. Click **Register**, create a food business account
3. You'll be logged in to the **AI Dashboard**
4. Go to **Categories** to set up product categories (perishability, storage)
5. Go to **Inventory** to add items (or use CSV bulk upload)
6. Hit **⚡ Run AI analysis now** on the dashboard (or let the scheduler run)
7. Explore **Analytics / Risk / Recommendations / Anomalies / Simulation** and click any
   product name for its full AI page

### 4. Scheduled AI jobs (optional — runs in-process out-of-band)

```bash
cd backend
python scheduler.py --daily          # one daily AI run (all tenants)
python scheduler.py --daily --wait   # keep running, runs daily at configured time
python scheduler.py --weekly         # one weekly forecast-evaluation run
python scheduler.py --monthly        # one monthly run
python scheduler.py --monthly --wait # keep running, monthly
```

### 5. Scan barcodes / QR codes

Camera scanning needs **localhost or an HTTPS** connection (browser requirement).

- **Scan to Find** — on the Inventory page, look up a product by camera and the list
  filters down to the matching item (fallback: opens the form prefilled with the barcode).
- **Scan to Update** — scan an item already in inventory to open it in the edit form.
- **Barcode / QR field** — the Scan button next to the field fills it with the decoded
  value while adding/editing.

Scanned codes hit `GET /api/inventory/barcode/{barcode}` after decoding.

### 6. Tests

```bash
cd backend
python -m pytest tests -q
```

### 7. Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./foodwaste.db` | SQLAlchemy DB URL |
| `SECRET_KEY` | (generated) | JWT signing key; set a fixed value in prod |
| `CORS_ORIGINS` | `http://localhost:5173` | comma-separated allowed origins |
| `RISK_THRESHOLDS` | `35,60,80` | risk engine band boundaries (low/moderate/high/critical) |
| `DAILY_JOB_TIME` | `02:00` | daily job clock time (`--wait` mode) |
| `WEEKLY_JOB_DAY` | `mon` | weekly job day |
| `WEEKLY_JOB_TIME` | `03:00` | weekly job time |

---

## CSV Bulk Upload Format

Header row (first line) with these columns:

```
name,category_id,sku,barcode,quantity,unit,cost_per_unit,expiry_date,storage_location,supplier,notes
Milk,1,M001,890123,50,L,50,2026-09-05,Chiller,Dairy Co,
Bread,2,B002,,20,loaf,10,2026-09-01,Ambient,Bakery A,
```

Only `name` is required. `category_id` must match an existing category id.
`expiry_date` accepts `YYYY-MM-DD`.

## API Endpoints

### Module 1

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register business |
| POST | `/api/auth/login` | Login (OAuth2 form) |
| GET/POST | `/api/categories` | List / create categories |
| PUT/DELETE | `/api/categories/{id}` | Update / delete category |
| GET/POST | `/api/inventory` | List / create inventory items |
| GET | `/api/inventory/barcode/{barcode}` | Look up an item by barcode/QR value |
| PUT/DELETE | `/api/inventory/{id}` | Update / delete item |
| POST | `/api/inventory/sale/{id}` | Record sale |
| POST | `/api/inventory/donate/{id}` | Record donation |
| POST | `/api/inventory/dispose/{id}` | Record disposal |
| POST | `/api/inventory/bulk` | CSV bulk upload |
| GET | `/api/transactions` | Transaction history |
| GET | `/api/dashboard` | Dashboard analytics (M1) |
| GET | `/api/dashboard/alerts` | Regenerate + list active alerts |
| POST | `/api/dashboard/alerts/{id}/resolve` | Resolve an alert |
| GET/PUT | `/api/settings` | Get / update alert thresholds |
| GET/POST | `/api/settings/api-keys` | List / create POS API keys |
| DELETE | `/api/settings/api-keys/{id}` | Delete a POS API key |
| POST | `/api/pos/inventory` | POS inventory push (API-key auth) |
| POST | `/api/pos/sales` | Record sale from POS (API-key auth) |
| POST | `/api/pos/webhook/inventory-update` | Webhook inventory sync (API-key auth) |

### Module 2 — Prediction, Risk & Decision Support

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/dashboard/summary` | M2 dashboard: KPIs, charts + action center |
| POST | `/api/waste/jobs/daily` | Run the daily AI job for the current tenant |
| POST | `/api/waste/predict?item_id=` | On-demand forecast (inference only) |
| GET | `/api/waste/predictions` | Stored predictions (optional `item_id`, `limit`, `offset`) |
| GET | `/api/waste/predictions/summary` | Latest forecast per product |
| GET | `/api/waste/risk?risk_level=` | Risk assessments (4-level filter) |
| GET | `/api/waste/analytics?period=` | KPIs + waste/chart aggregates (`day|week|month`) |
| GET | `/api/waste/trends?days=` | Daily series + forecast-vs-actual |
| GET | `/api/waste/causes` | Waste cause classifications |
| GET | `/api/waste/anomalies` | Detected anomalies |
| POST | `/api/waste/anomalies/{id}/resolve` | Resolve an anomaly |
| GET | `/api/waste/forecast-accuracy` | Business-level forecast accuracy headline |
| GET | `/api/waste/reorder` | Reorder / inventory optimization per product |
| GET/PATCH | `/api/recommendations` | List / update status of AI recommendations |
| POST/GET | `/api/simulations` | Run / list what-if simulations |
| GET | `/api/notifications` | Notification list (`unread_only`, `notification_type`) |
| GET | `/api/notifications/unread-count` | Unread count (bell badge) |
| POST | `/api/notifications/{id}/read` | Mark read |
| POST | `/api/notifications/read-all` | Mark all read |
| GET | `/api/surplus/allocations` | Pending surplus allocations |
| PATCH | `/api/surplus/allocations/{id}` | Update allocation status |
| GET/POST | `/api/surplus/partners` | List / create donation partners |
| GET | `/api/products/{item_id}/forecast` | Product forecast page payload |
| GET | `/api/products/{item_id}/risk` | Product AI page payload (risk + forecast + recs + accuracy) |

The **Settings** page manages alert thresholds and generates POS API keys (key shown once at creation,
masked in the list). See `docs/MILESTONE2.md` for the AI/ML pipeline, data model and scheduler
documentation.
