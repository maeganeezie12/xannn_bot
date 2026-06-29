import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID") or "0")

FAMILY = {
    "alextaysl": "Alex",
    "sandralimcm": "Sandra",
    "austintayyl": "Austin",
    "keegantay": "Keegan",
    "maeganeezie": "Maegan",
}

SPACES = ["Dining Room", "Attic", "Entire House", "Car"]

TIMEZONE = "Asia/Singapore"
FRIDAY_PROMPT_HOUR = 17
FRIDAY_PROMPT_MINUTE = 0

BOOKING_BUFFER_MINUTES = 30

SERVER_URL  = os.getenv("SERVER_URL", "")   # e.g. http://192.119.82.215:8080
SERVER_PORT = int(os.getenv("SERVER_PORT", "8080"))
ICS_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ics")
