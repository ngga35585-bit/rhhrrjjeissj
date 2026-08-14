import asyncio
import aiohttp
import time
import random
import logging
import os

# Configurare Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CONFIGURARE
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'TOKENTAU_AICI')
SERVER_ID = os.getenv('SERVER_ID', 'ID_SERVERULUI')
MAX_CONCURRENT_SESSIONS = 20  # Crește dacă ai putere, scade dacă e blocat IP
REPORT_REASON = "This server appears to be involved in raid/spam activity. It is being used to send unsolicited spam and mass mentions such as @everyone/@here, disrupting other Discord servers. Please review the server and take appropriate action if it violates Discord's rules."

# User-Agent randomizat
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

async def send_report(session, semaphore, stop_event):
    """
    Trimite un raport către Discord API folosind endpoint-ul corect.
    """
    async with semaphore:
        # Delay între rapoarte pentru a evita rate limit
        delay = random.uniform(0.1, 0.2) # ~10-20ms delay per sesiune
        await asyncio.sleep(delay)

        if stop_event.is_set():
            return

        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENTS),
            "X-Context-Properties": "{}" # Uneori necesar
        }

        # Endpoint-ul corect pentru raportare de la un user/bot
        url = f"https://discord.com/api/v10/users/@me/guilds/{SERVER_ID}/report"

        payload = {
            "categories": [
                "spams",
                "harassment"
            ],
            "reason": REPORT_REASON,
            "description": REPORT_REASON # Uneori Discord cere ambele
        }

        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                status = resp.status
                body = await resp.text()
                
                if status == 200:
                    logger.info(f"[OK] Raport trimis pentru {SERVER_ID} (Status: {status})")
                elif status == 429:
                    retry_after = int(resp.headers.get('Retry-After', 1))
                    logger.warning(f"[429] Rate Limitat! Așteptare {retry_after}s")
                    await asyncio.sleep(retry_after)
                else:
                    logger.error(f"[ERR] Status {status} pentru {SERVER_ID}: {body[:200]}")
        except Exception as e:
            logger.error(f"[EXC] Eroare conexiune pentru {SERVER_ID}: {e}")

async def run_reporter(stop_event):
    """
    Rulează sesiunile de raportare
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SESSIONS)
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_SESSIONS, ttl_dns_cache=300)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for _ in range(MAX_CONCURRENT_SESSIONS):
            tasks.append(asyncio.create_task(send_report(session, semaphore, stop_event)))
        
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

async def main():
    logger.info(f"Start Mass Report pentru Server ID: {SERVER_ID}")
    logger.info(f"Token: {DISCORD_TOKEN[:10]}...")
    logger.info(f"Session Count: {MAX_CONCURRENT_SESSIONS}")
    
    stop_event = asyncio.Event()
    
    import signal
    def signal_handler(sig, frame):
        logger.info("Oprește mass report-ul...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        await run_reporter(stop_event)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("S-a oprit.")

if __name__ == "__main__":
    asyncio.run(main())
