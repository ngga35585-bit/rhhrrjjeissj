import asyncio
import aiohttp
import random
import logging
import signal
import os

# Configurare Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Variabile de Mediu (cu valori default)
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'TU_TOKEN_AICI')
SERVER_ID = os.getenv('SERVER_ID', '000000000000000000')
REPORT_REASON = os.getenv('REPORT_REASON', 'This server appears to be involved in raid/spam activity. It is being used to send unsolicited spam and mass mentions such as @everyone/@here, disrupting other Discord servers. Please review the server and take appropriate action if it violates Discord\'s rules.')

# Configurații pentru a evita banul de IP pe Render
# Reducem sesiunile paralele și creștim delay-ul pentru a fi mai "uman"
MAX_CONCURRENT_SESSIONS = 6  # Scăzut de la 15 la 6 pentru stabilitate pe IP-uri partajate
BASE_DELAY = 1.5           # Secunde între fiecare cerere per sesiune (total ~20-25 req/sec pentru 6 sesiuni)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
]

async def send_report(session, semaphore, stop_event, target_id, reason):
    """Trimite un singur raport cu delay controlat"""
    async with semaphore:
        if stop_event.is_set():
            return

        # Delay mare pentru a evita rate-limitul agresiv
        await asyncio.sleep(random.uniform(BASE_DELAY, BASE_DELAY + 0.5))

        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENTS)
        }

        # Endpoint standard de reportare
        url = f"https://discord.com/api/v9/guilds/{target_id}/reports"
        
        payload = {
            "reason": reason,
            "categories": ["spams", "harassment"]
        }

        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    logger.debug(f"[OK] Raport trimis pentru {target_id}")
                elif resp.status == 429:
                    retry_after = int(resp.headers.get('Retry-After', 2))
                    logger.warning(f"[RATE LIMIT] Așteptare {retry_after}s")
                    await asyncio.sleep(retry_after)
                elif resp.status == 403:
                    logger.error(f"[403] Acces interzis pentru {target_id}. Verifică token-ul.")
                else:
                    error_text = await resp.text()
                    logger.error(f"[ERR] Status {resp.status}: {error_text[:100]}")
        except Exception as e:
            logger.error(f"[CONN ERR] {e}")

async def run_reporter(stop_event, target_id, reason):
    """Rulează sesiunile paralele"""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SESSIONS)
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_SESSIONS)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for _ in range(MAX_CONCURRENT_SESSIONS):
            tasks.append(asyncio.create_task(send_report(session, semaphore, stop_event, target_id, reason)))
        
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

async def main():
    logger.info("="*50)
    logger.info("   Discord Mass Report Script (Stabilized)")
    logger.info("="*50)
    logger.info(f"Token: {DISCORD_TOKEN[:10]}...")
    logger.info(f"Target Server ID: {SERVER_ID}")
    logger.info(f"Sessions: {MAX_CONCURRENT_SESSIONS}")
    logger.info(f"Delay/Base: {BASE_DELAY}s")
    logger.info("Press Ctrl+C to stop.")
    logger.info("="*50)

    stop_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info("Oprește mass report-ul...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        await run_reporter(stop_event, SERVER_ID, REPORT_REASON)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Script oprit.")

if __name__ == "__main__":
    asyncio.run(main())
