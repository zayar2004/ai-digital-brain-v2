# AI DIGITAL BRAIN

AI-powered workplace knowledge and operations system.

- Website = main system (Admin Dashboard + AI Control Center)
- Telegram Bot = chat interface
- Both share the same Flask backend and the same database

## Quick Start (Termux / Linux)

    pkg update && pkg install python git -y
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    # edit .env
    python -m scripts.init_db
    python -m scripts.create_admin
    python run.py

Full docs come in PART 30.
