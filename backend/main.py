import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import Base, engine

import models  # noqa: F401 - ensure all (M1 + M2) models are registered with Base.metadata

from routes import (
    auth,
    categories,
    inventory,
    transactions,
    dashboard,
    settings as settings_router,
    pos,
    waste,
    recommendations,
    simulations,
    notifications,
    surplus,
    products,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI-Powered Food Waste Management Platform",
    description="Inventory Management & Expiry Tracking + Waste Prediction, Optimization & Decision Support",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(inventory.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(settings_router.router)
app.include_router(pos.router)
app.include_router(waste.router)
app.include_router(recommendations.router)
app.include_router(simulations.router)
app.include_router(notifications.router)
app.include_router(surplus.router)
app.include_router(products.router)


@app.get("/")
def root():
    return {"app": "Food Waste Management Platform", "module": "Module 2 - Waste Prediction, Optimization & Decision Support", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}