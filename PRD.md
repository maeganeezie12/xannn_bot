# PRD: Family Weekend Planner Bot

## Problem

A family of five has no shared visibility into where everyone will be on weekends. Plans are scattered across DMs, forgotten, or never communicated. There is no single place to see who is going where, create shared events, confirm attendance, or send reminders.

A second, related problem: shared home spaces (living room, common areas) get double-booked. One family member invites friends over without knowing another member had the same idea. There is no way to "claim" a space and make that visible to the family before a conflict happens.

---

## Goal

A Telegram bot that lives in the family group chat. It collects each member's weekend plans, lets anyone create events with attendance polls, and sends automatic reminders — giving the whole family a live picture of the weekend without manual coordination.

---

## Users

Five family members sharing a single Telegram group chat. No external users. No admin hierarchy unless the family wants one.

---

## Core Features

### 1. Weekend Plan Collation

- Every Friday (configurable time), the bot asks each member: "What are your plans this weekend?"
- Members reply directly to the bot or in the group chat
- The bot aggregates all responses and posts a summary card to the group:
  - Saturday and Sunday columns
  - Each member's plans listed under each day
  - Members who haven't responded are flagged

### 2. Event Creation

Command: `/event`

Flow:
1. Bot asks for event name
2. Bot asks for date and time
3. Bot asks for location (optional)
4. Bot asks for notes (optional)
5. Bot asks: "Send reminders for this event? (24h before / 1h before / both / none)"
6. Bot posts the event card to the group chat with an attendance poll attached

### 3. Attendance Poll

- Automatically attached to every created event
- Poll options: Going / Not Going / Maybe
- Bot updates the event card as members respond
- Creator can close the poll manually with `/close_poll [event_id]`

### 4. Reminders

- Reminders are opt-in, configured per event during the `/event` creation wizard
- Options: 24h before only / 1h before only / both / none
- Reminder message mentions all Going and Maybe attendees by Telegram username
- Creator can change the reminder setting after creation: `/reminders [event_id]`
- Anyone can mute reminders for themselves on a specific event: `/mute [event_id]`

### 5. Weekend View

Command: `/weekend`

- Posts a read-only summary of the current or upcoming weekend
- Shows all events and each member's free-form plans side by side
- Anyone can trigger this at any time

### 6. Space Booking

Command: `/book`

A family member can claim a shared home space for a time slot to host guests. This makes the booking visible to the family and blocks others from booking the same space at the same time.

**Flow:**
1. Bot asks which space (e.g. Living Room, Backyard, Entire House — configurable list)
2. Bot asks for the date
3. Bot asks for start time and estimated end time
4. Bot asks for a brief note (e.g. "hosting Priya and friends")
5. Bot checks for conflicts on that space and time slot
   - If no conflict: confirms the booking, posts a notice to the group chat
   - If conflict exists: bot alerts the member, shows who has the conflicting booking, and asks them to resolve it directly

**Group notification format:**
> 🏠 [Name] has booked the Living Room on Saturday 3–7pm ("hosting Priya and friends"). Don't double-book!

**Conflict rules (hard block — no overrides):**
- Two bookings for the same space overlap in time → rejected outright, member must pick a different time or space
- "Entire House" blocks any other space booking on the same day, and cannot be booked if any space is already booked that day
- Partial overlaps (e.g. one booking ends at 5pm, next starts at 4pm) → rejected with a 30-minute buffer enforced between bookings

**Cancellation:**
- `/cancel_booking [booking_id]` — only the member who created the booking can cancel it; the bot rejects attempts by anyone else
- On cancellation, the bot posts a notice to the group so others know the space is now free

**Viewing bookings:**
- `/spaces` — shows all upcoming space bookings for the next 7 days, grouped by space
- Space bookings also appear in the `/weekend` summary view under a "Home" section

**Spaces list:**
- Dining Room, Attic, Entire House
- New spaces can be added by the bot owner via config, not via chat command (v1)

---

### 7. Member Check-in Status

Command: `/status`

- Shows who has submitted their weekend plans and who hasn't
- Bot nudges non-responders (once, not repeatedly)

---

## Commands Reference

| Command | Description |
|---|---|
| `/event` | Start event creation wizard |
| `/weekend` | Show the upcoming weekend summary |
| `/status` | Show who has and hasn't shared plans yet |
| `/reminders [event_id]` | Change reminder settings for an event (creator only) |
| `/mute [event_id]` | Mute reminders for yourself on a specific event |
| `/close_poll [event_id]` | Close the attendance poll for an event |
| `/book` | Book a shared home space |
| `/spaces` | View all upcoming space bookings |
| `/cancel_booking [booking_id]` | Cancel a space booking |
| `/help` | List all commands |

---

## Out of Scope (v1)

- External calendar sync (Google Calendar, iCal)
- Per-member permission levels
- Recurring events
- In-bot chat or DM management
- Web dashboard
- Booking approval workflows (v1 is first-come, first-served)
- Room capacity or guest count tracking

---

## Tech Stack (Proposed)

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Bot framework | `python-telegram-bot` v21 (async) |
| Scheduler | APScheduler (for Friday prompts and reminders) |
| Storage | SQLite via `aiosqlite` (simple, local, no infra) |
| Hosting | Any always-on machine or cheap VPS (bot must run continuously) |

---

## What I Need From You to Build This

To start development, please provide:

1. **Telegram Bot Token** — Create a bot via [@BotFather](https://t.me/BotFather) on Telegram and paste the token here. Steps: open BotFather → `/newbot` → follow prompts → copy the `HTTP API` token.

2. **Group Chat ID** — Add the bot to your family group chat, then send a message. I can write a quick script to print the chat ID, or you can use `https://api.telegram.org/bot<TOKEN>/getUpdates` after sending a message.

3. **Family member Telegram usernames** — So the bot can mention them in reminders and the status check. Format: `@username` for each of the five members.

4. **Friday prompt time and timezone** — e.g. "Friday 7pm, Asia/Singapore". This sets when the bot asks for weekend plans each week.

5. **Hosting environment** — Where will the bot run? Options:
   - A Raspberry Pi or home server (always on)
   - A VPS (e.g. DigitalOcean, Hetzner — ~$5/month)
   - A Windows/Mac machine that stays on
   - Cloud Functions (requires polling → webhook conversion, more complex)

6. **Any naming preferences** — What should the bot be called? Any specific phrasing for messages (formal, casual, etc.)?

---

## Open Questions

- Should unanswered Friday prompts re-prompt on Saturday morning, or drop it?
- Should the weekend summary auto-post on Saturday morning in addition to being on-demand?
- Do all five members need to be able to create events, or just certain people?
- Should past events be archived and viewable, or just deleted after they pass?
