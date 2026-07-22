# Real-Time Desktop Chess Analyzer

Python + Stockfish backend with a transparent Electron/Angular overlay.

## Quick Start

### 1. Install Stockfish

Download Stockfish 16+ and either:
- Add the binary to your system `PATH` as `stockfish.exe`, or
- Set the environment variable `STOCKFISH_PATH` to the binary location.

### 2. Install Python dependencies

```bash
cd "d:\work\Chess anlizer app"
pip install -r requirements.txt
```

### 3. Generate piece templates

The vision pipeline matches piece images against templates in `assets/templates/`.
Run the default generator (it tries to use common system Unicode fonts):

```bash
python backend/generate_templates.py
```

For best results, replace the generated PNGs with screenshots of the actual pieces from your target chess site.

### 4. Run the backend

```bash
python backend/server.py
```

Optional environment variables:
- `STOCKFISH_PATH` — explicit Stockfish binary path
- `MONITOR_INDEX` — monitor to capture (default `1`, `0` = all monitors)

### 5. Build and run the frontend

```bash
cd frontend
npm install
npm run build
npm start
```

Use **Ctrl+Shift+C** to start manual board calibration and **Ctrl+Shift+H** to toggle the overlay.

## Architecture

- `backend/capture.py` — mss screen capture and pixel-diff change detection.
- `backend/vision.py` — board grid slicing, template matching, and FEN generation.
- `backend/engine.py` — async python-chess UCI wrapper with `MultiPV` and null-move threat search.
- `backend/server.py` — WebSocket server on `ws://127.0.0.1:8765` broadcasting the agreed JSON schema.
- `frontend/electron-main.ts` — transparent, click-through, always-on-top Electron window and global hotkeys.
- `frontend/src/app/overlay-svg.component.ts` — SVG arrows and highlights with per-color markers.
- `frontend/src/app/control-panel.component.ts` — Kendo UI toggle panel with hover-to-enable mouse interaction.

## Calibration

1. Run the backend and frontend.
2. Press **Ctrl+Shift+C**.
3. A `cv2` ROI selector appears — drag a rectangle around the board and press `SPACE`/`ENTER`.
4. Bounds are saved to `config/board_bounds.json` and reused on the next run.

## Notes

- Electron captures calibration bounds in logical pixels and sends them to Python after multiplying by `window.devicePixelRatio`, so `mss` receives physical monitor coordinates.
- The backend only runs Stockfish when the FEN changes, and only runs vision when the board pixels change.
- `python-chess` `board.push(chess.Move.null())` is used for null-move threat detection so en passant and castling rights remain correct.
