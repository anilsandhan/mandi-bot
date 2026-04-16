# Mandi Bot — Project Brief

## What this is
A WhatsApp bot that sends daily mandi price alerts for Haryana crops
to farmers, arhatiyas, and agri-traders. Hindi-first. Push-based.

## Tech stack
- Python 3.x, Windows, C:\mandi_bot\
- Data source: Agmarknet API via data.gov.in
- AI layer: Anthropic Claude API (Hindi narrative generation)
- Delivery: WhatsApp Cloud API (Meta)
- DB: SQLite (prices.db, subscribers.db)
- Scheduler: Windows Task Scheduler via schedule library

## Target mandis
Karnal, Taraori, Nilokheri, Kurukshetra, Ambala, Panipat, Rohtak, Sirsa

## Target crops
Wheat, Paddy, Mustard, Barley, Maize, Bajra, Sunflower

## Daily schedule
- 6:30 AM: fetch prices → analyse → generate Hindi message → send to all subscribers
- 12:00 PM: live modal price update (shorter message)

## Files
- fetcher.py    — pulls Agmarknet data, saves to prices.db
- analyser.py   — compares vs MSP, detects weekly trend, flags sell signal
- narrator.py   — calls Claude API, generates Hindi WhatsApp message
- sender.py     — sends via WhatsApp Cloud API to subscriber list
- scheduler.py  — orchestrates the daily pipeline
- main.py       — CLI entry point

## Key rules
- Never hardcode API keys — always use .env
- Always handle API failures gracefully — log and skip, don't crash
- Messages must be under 1000 chars for WhatsApp
- Hindi text only in final messages — no English to subscribers