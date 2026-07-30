# Demo run commands

Run these in 3 terminals, in order. All from `moveai_prototype/`.

## 1. Backend (FastAPI)

```
cd /Users/mvinc/projects/COMP6211K_Prototype_1/moveai_prototype
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8010
```

Check it's up: http://localhost:8010/docs

## 2. Customer app (Streamlit)

```
cd /Users/mvinc/projects/COMP6211K_Prototype_1/moveai_prototype/Frontend_V2
export MOVEAI_API_BASE=http://localhost:8010
../.venv/bin/python -m streamlit run move_ai.py --server.port 8501
```

http://localhost:8501

## 3. Administrator app (Streamlit)

```
cd /Users/mvinc/projects/COMP6211K_Prototype_1/moveai_prototype/Frontend_V2
export MOVEAI_API_BASE=http://localhost:8010
../.venv/bin/python -m streamlit run administrator.py --server.port 8502
```

http://localhost:8502

## Notes

- Start the backend first — both frontends need it before uploading images or using any feature.
- Ports must stay: backend 8010, customer 8501, admin 8502.
- Stop any app with Ctrl+C in its terminal.
- If a command isn't found, dependencies may be missing: `.venv/bin/python -m pip install -r requirements.txt` (and for Frontend_V2: `-r Frontend_V2/requirements.txt`).

## Demo on phone (same Wi-Fi)

Requirements:
- Phone and Mac must be on the **same Wi-Fi network**.
- Streamlit needs `--server.address 0.0.0.0` so it's reachable from other devices.
- `MOVEAI_API_BASE` must point to the LAN IP, not `localhost` — the frontend runs in the phone's browser, so `localhost` there means the phone itself.
- macOS may prompt to allow incoming connections for Python the first time — allow it.

First, print your Mac's current LAN IP (you'll need it for the phone's browser):

```
ipconfig getifaddr en0
```

```
cd /Users/mvinc/projects/COMP6211K_Prototype_1/moveai_prototype
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8010
```

```
cd /Users/mvinc/projects/COMP6211K_Prototype_1/moveai_prototype/Frontend_V2
export MOVEAI_API_BASE=http://$(ipconfig getifaddr en0):8010
../.venv/bin/python -m streamlit run move_ai.py --server.port 8501 --server.address 0.0.0.0
```

```
cd /Users/mvinc/projects/COMP6211K_Prototype_1/moveai_prototype/Frontend_V2
export MOVEAI_API_BASE=http://$(ipconfig getifaddr en0):8010
../.venv/bin/python -m streamlit run administrator.py --server.port 8502 --server.address 0.0.0.0
```

On the phone's browser, use the IP printed above:
- Customer app: `http://<ip>:8501`
- Administrator app: `http://<ip>:8502`
