# 🐔 CHICKEN TWIN - AI-Powered Poultry Robotics

Welcome to the Chicken Twin system! This project simulates a poultry farm with AI-driven monitoring and robotic intervention.

## 🚀 Quick Start

**Option 1: Automated Startup (Windows)**
Simply double-click `start_app.bat`. This will:
1.  Launch the backend server.
2.  Launch the AI monitor agent.
3.  Open the 3D demo in your browser.

**Option 2: Manual Startup**
Open two terminal windows/tabs:

**Terminal 1 (Backend):**
```bash
python server.py
```

**Terminal 2 (AI Agent):**
```bash
python monitor.py
```

Then open your browser to: `http://localhost:5000/demo.html`

## 📦 Installation

Prerequisites:
- Python 3.8+
- Modern Web Browser (Chrome/Edge recommended)

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration:**
    - Ensure you have a `.env` file with your `OPENAI_API_KEY` if you want to use the full AI analysis features.

## 🖥️ Components

- **demo.html**: The main 3D simulation interface.
- **dashboard.html**: Real-time stats and health monitoring.
- **analytics.html**: Historical data and trends.
- **sessions.html**: Replay recorded sessions.
- **monitor.py**: The "Brain" - handles AI logic and WebSocket broadcasting.
- **server.py**: The Backend - handles API requests and file serving.
