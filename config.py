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
