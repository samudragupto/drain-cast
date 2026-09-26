# Setup

## Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer (tested on 22)

## Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py                  # http://127.0.0.1:5000
```

Check it with `curl http://127.0.0.1:5000/api/health`.

`gunicorn` is listed for Linux deployment. It installs on Windows but won't run there; use `python app.py` locally.

## Frontend

```bash
cd frontend
npm install
npm start                      # http://localhost:3000
```

In development the React dev server proxies `/api` to `localhost:5000`, so no environment variable is needed. For a deployed build, set `REACT_APP_API_URL` (see `.env.example`).

## Tests

```bash
cd backend
python -m unittest discover -s tests -v
```

## Rebuilding ward data

The ward data in `data/wards/` is committed, so nothing needs to be downloaded to run the app. To rebuild it or add a ward:

```bash
python tools/build_ward_data.py                  # all wards
python tools/build_ward_data.py velachery        # one ward (substring match)
```

This calls the public Overpass and OpenTopoData APIs. Overpass sometimes returns 504; the script retries across mirrors. Raw responses are cached in `tools/.cache/`, which is ignored by git.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Red "Backend offline" in the header | Start `python app.py` in `backend/`. The page retries every 5 s. |
| `pip install` hangs on `pypi.ngc.nvidia.com` | An extra index is configured globally. Run `pip install -r requirements.txt --index-url https://pypi.org/simple`. |
| Live forecast shows an error | There is no connection to Open-Meteo. Use a design storm; the rest of the app is offline-capable. |
| Port 3000 or 5000 busy | Stop the other process, or run `PORT=5001 python app.py` and update `proxy` in `frontend/package.json`. |
