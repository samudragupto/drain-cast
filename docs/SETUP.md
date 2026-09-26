# DrainCast - Local Setup Guide

Step-by-step instructions to run DrainCast locally on your machine.

## Prerequisites

- **Node.js** 18+ ([Download](https://nodejs.org/))
- **Python** 3.9+ ([Download](https://www.python.org/))
- **Git** ([Download](https://git-scm.com/))
- **Terminal/Command Prompt** (PowerShell on Windows, Bash on Mac/Linux)

## Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/draincast.git
cd draincast
```

## Step 2: Backend Setup

### Windows

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Flask server
python app.py
```

### macOS/Linux

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run Flask server
python app.py
```

**Expected Output:**
```
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

Keep this terminal open. Backend is running on **http://localhost:5000**

## Step 3: Frontend Setup (New Terminal)

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start development server
npm start
```

**Expected Output:**
```
Compiled successfully!

You can now view draincast in the browser.

  Local:            http://localhost:3000
  On Your Network:  http://192.168.x.x:3000
```

App automatically opens at **http://localhost:3000**

## Step 4: Verify Setup

### Backend Health Check

Open terminal and run:
```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{"status":"ok","timestamp":"2026-01-15T14:30:00"}
```

### Frontend Check

Open browser to **http://localhost:3000**

You should see:
- DrainCast header with logo
- Interactive map of Kurla East, Mumbai
- Green roads (no flood risk initially)
- Blue dots (drainage nodes)

## Step 5: Test the System

1. **Adjust Rainfall Slider**
   - Move slider to 70 mm/hr
   - Watch map redraw (takes 2-3 seconds)
   - Roads should turn yellow/orange/red

2. **Change Timeline**
   - Click "+1 Hour", "+2 Hour", "+3 Hour"
   - Predictions update based on time
   - Risk levels change dynamically

3. **Click on a Road**
   - Click any colored road on map
   - Info panel appears on right
   - Shows water depth, runoff, drain capacity

4. **Find Safe Route** (Optional)
   - Enter start/end locations in Route panel
   - Click "Find Safe Route"
   - See comparison with normal route

## Troubleshooting

### Problem: Backend won't start

**Error:** `ModuleNotFoundError: No module named 'flask'`

**Solution:**
```bash
# Make sure you're in backend directory with venv activated
cd backend
venv\Scripts\activate  # or source venv/bin/activate on Mac/Linux
pip install -r requirements.txt
python app.py
```

### Problem: Frontend won't compile

**Error:** `npm ERR! code ERESOLVE`

**Solution:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
npm start
```

### Problem: Port already in use

**Port 5000 already in use:**
```bash
# Windows: Find process using port 5000
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Mac/Linux
lsof -i :5000
kill -9 <PID>
```

**Port 3000 already in use:**
```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Mac/Linux
lsof -i :3000
kill -9 <PID>
```

### Problem: API calls return 404

**Error:** `POST http://localhost:5000/api/predict 404 Not Found`

**Solution:**
1. Verify backend is running on port 5000
2. Check `.env.local` file exists in `frontend/` with:
   ```
   REACT_APP_API_URL=http://localhost:5000/api
   ```
3. Restart frontend with `npm start`

### Problem: Data files not found

**Error:** `FileNotFoundError: ../data/roads.geojson`

**Solution:**
1. Verify you're in `/backend` directory when running `python app.py`
2. Check data files exist:
   ```bash
   ls ../data/  # Mac/Linux
   dir ..\data  # Windows PowerShell
   ```

## Environment Configuration

### Frontend (.env.local)

Create file `frontend/.env.local`:
```
REACT_APP_API_URL=http://localhost:5000/api
```

### Backend (.env) - Optional

Create file `backend/.env`:
```
FLASK_ENV=development
LOG_LEVEL=DEBUG
PORT=5000
```

## Project Structure After Setup

```
draincast/
├── frontend/
│   ├── node_modules/        ← Created by npm install
│   ├── public/
│   ├── src/
│   ├── .env.local           ← Create this
│   └── package.json
├── backend/
│   ├── venv/                ← Created by python -m venv venv
│   ├── *.py files
│   ├── requirements.txt
│   └── .env                 ← Optional
├── data/
│   ├── roads.geojson
│   ├── drainage_nodes.json
│   ├── drainage_edges.json
│   ├── elevation.json
│   └── ward_boundary.geojson
└── README.md
```

## Useful Commands

### Backend

```bash
# Activate virtual environment
source venv/bin/activate          # Mac/Linux
venv\Scripts\activate             # Windows

# Install new package
pip install package_name

# Deactivate virtual environment
deactivate

# View installed packages
pip list

# Run with debug off
FLASK_ENV=production python app.py
```

### Frontend

```bash
# Start development server
npm start

# Build for production
npm run build

# Run tests
npm test

# Install new package
npm install package_name

# Update dependencies
npm update
```

## Development Workflow

### Making Changes

1. **Backend Changes:**
   ```bash
   # Edit file in backend/
   # Flask auto-reloads (if running with debug=True)
   # Browser may need manual refresh
   ```

2. **Frontend Changes:**
   ```bash
   # Edit file in frontend/src/
   # React auto-reloads (hot module replacement)
   # Changes visible in browser immediately
   ```

### Testing Changes

1. Adjust rainfall slider
2. Click different timeline buttons
3. Click roads on map
4. Enter route start/end points
5. Verify no console errors (F12 → Console tab)

### Debug Mode

**Backend (Flask):**
- Already runs in debug mode by default
- Check terminal for error messages

**Frontend (React):**
- Open browser DevTools: F12 or Cmd+Option+I
- Console tab shows JavaScript errors
- Network tab shows API calls

## Clean Rebuild (If Things Break)

```bash
# Backup your changes if any
git status

# Clean frontend
cd frontend
rm -rf node_modules package-lock.json
npm install
npm start

# In new terminal, clean backend
cd backend
deactivate  # Exit venv if active
rm -rf venv
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Next Steps

After successful local setup:

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand system design
2. Read [METHODOLOGY.md](METHODOLOGY.md) to understand flood prediction logic
3. Explore code in `backend/coupling_engine.py` - core flood logic
4. Modify data files in `data/` to test with different road networks
5. Prepare for deployment (see README.md)

## Getting Help

- Check terminal output for error messages
- Read stack trace carefully (last line usually shows the problem)
- Google the error message
- Check [GitHub Issues](https://github.com/yourusername/draincast/issues)
- Post detailed error with:
  ```
  - What you tried to do
  - Exact error message
  - Your OS (Windows/Mac/Linux)
  - Python version (python --version)
  - Node version (node --version)
  ```

## First Run Checklist

- [ ] Backend running on http://localhost:5000
- [ ] Frontend running on http://localhost:3000
- [ ] Health check responds `{"status":"ok"}`
- [ ] Map displays with green roads
- [ ] Rainfall slider works
- [ ] Timeline buttons work
- [ ] Clicking road shows info panel
- [ ] No red errors in browser console
- [ ] No red errors in terminal

---

**Estimated Setup Time:** 10-15 minutes  
**Last Updated:** January 2026
