# Weather-Aware Truck Routing

A React + Django app that helps a truck driver pick the safest route. It compares three route options by forecast weather at the truck's arrival time at each checkpoint, the load weight, and travel time.

> Work in progress. Live link, walkthrough video and full documentation will be added here.

## Stack

- **Frontend:** React, TypeScript, Vite, Material UI, MapLibre GL
- **Backend:** Django, Django REST Framework, Redis cache
- **Data:** TomTom (truck routing, geocoding), Open-Meteo (hourly forecasts), OpenFreeMap (map tiles)

Design decisions, with the tests and measurements behind them, are in [docs/decisions.md](docs/decisions.md).

## Run locally

Requirements: Python 3.10+, Node 22, a TomTom API key.

```bash
cp .env.example .env            # then set TOMTOM_API_KEY

# Backend (http://127.0.0.1:8000)
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows; use .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
python manage.py runserver

# Frontend (http://localhost:5173, proxies /api to the backend)
cd frontend
npm install
npm run dev
```

Or run everything as the production image:

```bash
docker build -t weather-truck-routing .
docker run --rm -p 8000:8000 --env-file .env weather-truck-routing
```

## Tests

```bash
cd backend && pytest
cd frontend && npm test
```

API documentation (OpenAPI) is served at `/api/docs/`.
