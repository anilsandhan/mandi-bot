# Mandi Bot — Project Brief

## What this is
A Telegram bot that sends daily personalised mandi price alerts
for Haryana crops to farmers, arhatiyas, and agri-traders.
Subscribers register via bot, choose their district and crops,
and get a Hindi message every morning at 6:30 AM.

## Tech stack
- Python 3.x, Windows dev, deployed on Render (free tier)
- Database: Supabase PostgreSQL (persistent, cloud)
- Data source: Agmarknet API via data.gov.in
- AI layer: Anthropic Claude Haiku (Hindi narrative generation)
- Delivery: Telegram Bot API
- Web framework: Flask (webhook receiver)

## File structure
- db.py           -- Supabase connection, table init, load_env()
- fetcher.py      -- pulls Agmarknet data, saves to prices table
- analyser.py     -- MSP comparison, trend, sell signals
- narrator.py     -- Claude API generates Hindi WhatsApp message
- sender.py       -- Telegram delivery
- subscribers.py  -- subscriber CRUD (Supabase)
- bot.py          -- Flask webhook, registration flow, commands
- main.py         -- daily pipeline entry point
- scheduler_setup.py -- Windows Task Scheduler setup

## Database tables (Supabase PostgreSQL)
- prices       -- daily mandi price data from Agmarknet
- subscribers  -- registered users with district + crop preferences
- sessions     -- mid-registration conversation state

## Target mandis
Karnal, Taraori, Nilokheri, Kurukshetra, Ambala, Panipat,
Rohtak, Sirsa, Gharaunda, Kunjpura, Pipli, Thanesar, Pehowa,
Ladwa, Shahabad, Naraingarh, Jagadhri

## Target crops
Wheat, Paddy, Mustard, Barley, Maize, Bajra, Sunflower,
Potato, Onion, Tomato, Apple, Banana, Chikoos, Cucumber,
Garlic, Ginger, Bottle Gourd, Brinjal, Cotton, Sugarcane,
Dry Fodder, Green Fodder, Mango, Guava

## MSP 2025-26 (Rs/quintal)
Wheat: 2425, Paddy: 2300, Mustard: 5950, Barley: 1850,
Maize: 2225, Bajra: 2625, Sunflower: 7280, Cotton: 7121

## Deployment
- Render free tier: https://mandi-bot.onrender.com
- Webhook: https://mandi-bot.onrender.com/webhook
- Keep-alive ping every 10 min to prevent sleep
- Auto-deploys from GitHub: anilsandhan/mandi-bot

## Environment variables (never commit)
- DATA_GOV_API_KEY   -- data.gov.in API key
- ANTHROPIC_API_KEY  -- Claude API key
- TELEGRAM_BOT_TOKEN -- bot token from BotFather
- TELEGRAM_CHAT_ID   -- your personal chat ID for testing
- DATABASE_URL       -- Supabase PostgreSQL pooler URL

## Daily schedule
- 6:30 AM: main.py runs full pipeline
  fetch -> analyse -> generate Hindi message -> send to all subscribers
- Windows Task Scheduler fires main.py locally as backup

## Bot commands
- Hi / Ram Ram / any greeting -- register or show profile
- /mera_bhav -- instant price for subscriber's crops
- /profile -- show saved profile
- /update -- restart registration to change profile
- /band -- deactivate alerts
- /help -- command list

## Registration flow
1. Greeting -> naam batayein
2. Naam -> jila chunein (1-12)
3. Jila -> category chunein (1=Anaj 2=Sabzi 3=Phal 4=Anya)
4. Category -> fasal numbers chunein
5. Aur category? (1=Haan 2=Nahi)
6. Complete -> confirmation message

## Key rules
- Never hardcode API keys
- db.py load_env() reads .env locally, os.environ on cloud
- All DB operations use psycopg2 with Supabase pooler URL
- Messages must be under 600 chars for Telegram
- Hindi Devanagari in all subscriber-facing messages
- Session state stored in Supabase sessions table