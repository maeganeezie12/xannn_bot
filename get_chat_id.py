"""
Run this, then send any message in your family group chat.
The script will print the chat ID — paste it into .env as GROUP_CHAT_ID.
"""
import asyncio
import os
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()


async def main():
    bot = Bot(os.getenv("BOT_TOKEN"))
    print("Waiting for a message... Send anything in your family group chat now.\n")

    offset = None
    while True:
        updates = await bot.get_updates(offset=offset, timeout=30, limit=5)
        for update in updates:
            offset = update.update_id + 1
            chat = None
            if update.message:
                chat = update.message.chat
            elif update.my_chat_member:
                chat = update.my_chat_member.chat

            if chat and chat.type in ("group", "supergroup"):
                print(f"Found it!")
                print(f"  GROUP_CHAT_ID = {chat.id}")
                print(f"  Group name    = {chat.title}")
                print(f"\nPaste this into your .env file:")
                print(f"  GROUP_CHAT_ID={chat.id}")
                return


asyncio.run(main())
