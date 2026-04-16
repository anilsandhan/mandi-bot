from fetcher import run as fetch_run
from analyser import analyse_for_subscriber
from narrator import generate_hindi_message, build_personalised_prompt
from sender import send_to
from subscribers import get_active_subscribers, init_db as init_subs_db
from datetime import datetime


def run_pipeline():
    print(f"\n{'=' * 50}")
    print(f"MANDI BOT -- {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'=' * 50}\n")

    print("STEP 1: Fetching prices...")
    prices = fetch_run()
    if not prices:
        print("[MAIN] No prices today -- aborting")
        return

    init_subs_db()
    subscribers = get_active_subscribers()
    print(f"\nSTEP 2: {len(subscribers)} active subscribers\n")

    for sub in subscribers:
        print(f"--- {sub['name']} ({sub['district']}) ---")

        summary = analyse_for_subscriber(sub)
        if not summary:
            print(f"  No data -- skipping\n")
            continue

        prompt = build_personalised_prompt(summary)
        message = generate_hindi_message(summary, prompt_override=prompt)

        print(f"  Preview: {message[:80]}...")
        success = send_to(sub["telegram_id"], message)
        print(f"  Sent: {'OK' if success else 'FAILED'}\n")

    print("[MAIN] Pipeline complete")


if __name__ == "__main__":
    run_pipeline()