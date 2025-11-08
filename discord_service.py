import os
import sys
sys.path.insert(0, '/home/robgro/expenses')

from app.services.discord_bot import run_discord_bot

if __name__ == "__main__":
    run_discord_bot()