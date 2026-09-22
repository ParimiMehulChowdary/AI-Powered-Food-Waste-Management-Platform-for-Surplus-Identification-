# Milestone 2 — AI-Powered Waste Prediction, Optimization & Decision Support

This document covers the Module 2 architecture: the forecasting/AI pipeline, the new
data model, the scheduled jobs and the API surface. It complements `README.md`.

## AI/ML pipeline

All intelligence lives in `backend/services/`. It is **100% Python-standard-library** —
no heavy ML framework — so it runs anywhere Python runs and is fully explainable.

### Daily inference job (`backend/jobs/daily.py`, `run_for_tenant`)

For every inventory item of a tenant:

1. **Forecast** (`forecasting.py`) — builds a daily sales demand series from sale
   transactions (recent active sales window) and predicts demand, waste and surplus for
   the next 7 days. Model selection per item by history volume:
   - `exponential_smoothing` (enough data) → damped single exponential smoothing
   - `moving_average` (more history than smoothing window) → rolling mean
   - `linear_trend` → least-squares linear trend
   - `rule_based_fallback` (too little / all-zero history) → mean demand estimate with
     `confidence = 0` and `is_fallback = True`; waste estimated from the configured
     `waste_rate`; the platform never fabricates statistical confidence.
   - Waste cap per day = stock available + predicted receipts.
2. **Risk assessment** (`risk_engine.py`) — 4-tier risk (`low | moderate | high | critical`)
   scored 0–100 from weighted, individually-visible factors:
   days-to-expiry, stock-vs-forecast-demand ratio, historical waste rate, recent sales
   trend, category perishability, storage requirement and stock age. `classify_item`
   returns the score, 4-level label (bands from `RISK_THRESHOLDS` env, default
   `35,60,80`) and a human-readable explanation.
3. **Recommendations** (`recommendation_engine.py`) — `count / cost / income / waste`
   heuristics produce prioritized action items: discount offer (price-cut % from expected
   waste), donate before expiry, reduce next purchase (`qty * recent_waste_rate`), stop
   reorder, mark for disposal (expired), urgency note on expiring items.
4. **Surplus allocation** (`surplus_engine.py`) — for items ending today with a positive
   balance: `surplus_quantity`, `safe_days_remaining` (up to shelf-life), suggested
   `allocation_type` (`donation` when safe window allows, else `promotion`, else `transfer`),
   urgency-sorted.
5. **Anomaly detection** (`anomaly_detector.py`) — rolling-window z-score and IQR tests on
   sales, waste, stock and stock-increase series; records `detected_value`,
   `expected_value`, severity (4-level) and explanation. Global (business-level) anomalies
   use the summed series.
6. **Waste causes** (`cause_classifier.py`) — rule-based attribution of recent waste to
   `overstocking`, `low_demand`, `expiry`, `poor_forecasting`, `storage_issues`, ... with
   counts.
7. **Notifications** (`notification_service.py`) — deduplicated, typed in-app notifications
   for high waste risk, critical expires (`reorder_point` break), forecast surplus,
   donation opportunities and anomalies/accuracy dips.

### Weekly accuracy job (`backend/jobs/weekly.py`)

Fetches predictions whose `target_date` has passed, pairs them with actual sales/waste,
computes **MAE / RMSE / MAPE / accuracy** per product (`forecast_evaluator.py`), stores the
run in `forecast_performance`, and notifies when business accuracy is below the
`LOW_ACCURACY_THRESHOLD` (92%).

### Other services

- `simulation_engine.py` — what-if models (`discount`, `donation`, `reduced_order`,
  `full_optimization`), each returning labelled results, an explanation, a `confidence`,
  `is_simulation = True` and `potential_savings`. Nothing is written to inventory.
- `inventory_optimization.py` — reorder point, max stock, safety stock, recommended order
  quantity from demand forecast, lead time and service level.
- `analytics_service.py` — period KPIs and time buckets for the Analytics page.

## Data model (new M2 tables)

`WastePrediction`, `RiskAssessment`, `Recommendation`, `SurplusAllocation`,
`DonationPartner`, `Anomaly`, `WasteCause`, `ForecastPerformance`, `Simulation`,
`Notification` — all tenant-scoped via `owner_id`, all registered in
`backend/models/__init__.py` and created automatically by SQLAlchemy `create_all` on
startup (17 tables total).

## Scheduler

`backend/scheduler.py` is a standalone, dependency-light loop:

```bash
python scheduler.py --daily            # run the daily AI job for all tenants, then exit
python scheduler.py --daily --wait     # keep running; fires daily at DAILY_JOB_TIME (02:00)
python scheduler.py --weekly           # run the weekly accuracy job, then exit
python scheduler.py --monthly          # run both, then exit (or --wait for looped monthly)
```

It is safe to run alongside `uvicorn`: all work is database-driven and deduplicated
(upsert-style records keyed on item + target date; notifications deduplicated by type+key).

## API surface (Module 2)

See the README endpoint table. Highlights:

- `POST /api/waste/jobs/daily` — trigger the daily AI job for the current tenant from the UI.
- `POST /api/waste/predict?item_id=` — on-demand forecasting inference.
- `GET /api/waste/predictions`, `/predictions/summary`, `/risk`, `/analytics`, `/trends`,
  `/causes`, `/anomalies`, `/forecast-accuracy`, `/reorder`
- `GET|PATCH /api/recommendations`, `POST|GET /api/simulations`,
  `GET /api/notifications`, `/unread-count`, `POST /{id}/read`, `/read-all`,
  `GET /api/surplus/allocations`, `PATCH /api/surplus/allocations/{id}`,
  `GET|POST /api/surplus/partners`
- `GET /api/products/{item_id}/forecast` and `/risk` — per-product AI page payloads.
- `GET /api/dashboard/summary` — M2 dashboards: KPIs, charts, action center.

All endpoints require a JWT Bearer token and scope to `owner_id` (tenant isolation is
enforced in the route layer; cross-tenant access returns 404).

## Testing

```bash
cd backend
python -m pytest tests -q
```

- `tests/conftest.py` — in-memory SQLite (`StaticPool`) + test client + `register_user`,
  `seed_transaction` helpers.
- Unit tests: forecasting (incl. all-zero fallback), risk engine (band boundaries), anomaly
  detection, simulation, cause classifier, surplus engine.
- Integration: M1 regression, auth (401 without token), the full M2 flow
  (job → predictions → risk → recommendations → simulations → notifications → surplus),
  order of `/predict` params, `compute_metrics` error pairing, and tenant isolation
  (cross-tenant item access is 404, tenant B predictions are empty).

## Known limitations / notes

- Forecasting is univariate; it does not model promotions, seasonality beyond the recent
  window, or inter-product effects — it prefers an honest fallback over fake confidence.
- Accuracy after a fresh daily run shows `items_evaluated: 0` until target dates lapse and
  the weekly job (or a later daily run) evaluates them.
- Existing tenants on the real `foodwaste.db` were migrated by `create_all` on startup; a
  standalone `backend/migrations.py` is included for creating the schema from scratch
  (`python migrations.py`).
- `datetime.utcnow()` is used store-side (matches Module 1); Python 3.12+ emits a
  deprecation warning for it — cosmetic only.