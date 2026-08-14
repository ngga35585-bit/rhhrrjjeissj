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
SERVER_ID = os.getenv('SERVER_ID', '1487092822913060994')
MAX_CONCURRENT_SESSIONS = 10 # Redus pentru a evita blocarea rapidă
REPORT_REASON = "This server appears to be involved in raid/spam activity. It is being used to send unsolicited spam and mass mentions such as @everyone/@here, disrupting other Discord servers. Please review the server and take appropriate action if it violates Discord's rules."

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

async def send_report(session, semaphore, stop_event):
    async with semaphore:
        delay = random.uniform(0.2, 0.4) # Delay mai mare pentru a evita rate limit
        await asyncio.sleep(delay)

        if stop_event.is_set():
            return

        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENTS),
            "X-Context-Properties": "{}",
            "X-Debug-Options": "bugReporter"
        }

        # Încercăm endpoint-ul corectat v10/v11
        url = f"https://discord.com/api/v10/users/@me/guilds/{SERVER_ID}/report"

        payload = {
            "categories": ["spams", "harassment"],
            "reason": REPORT_REASON,
            "description": REPORT_REASON
        }

        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                status = resp.status
                body = await resp.text()
                
                if status == 200:
                    logger.info(f"[OK] Raport trimis pentru {SERVER_ID}")
                elif status == 429:
                    retry_after = int(resp.headers.get('Retry-After', 1))
                    logger.warning(f"[429] Rate Limitat! Așteptare {retry_after}s")
                    await asyncio.sleep(retry_after)
                elif status == 404:
                    logger.error(f"[404] Endpoint nu găsit pentru {url}. Verifică dacă bot-ul are acces sau dacă URL-ul e actualizat.")
                    # Oprim pentru a nu mai spama 404-uri
                    stop_event.set()
                else:
                    logger.error(f"[ERR] Status {status} pentru {SERVER_ID}: {body[:200]}")
        except Exception as e:
            logger.error(f"[EXC] Eroare conexiune pentru {SERVER_ID}: {e}")

async def run_reporter(stop_event):
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
    logger.info(f"URL Test: https://discord.com/api/v10/users/@me/guilds/{SERVER_ID}/report")
    
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
