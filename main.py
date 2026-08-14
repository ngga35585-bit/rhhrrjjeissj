import asyncio
import aiohttp
import random
import logging
import signal
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CONFIGURARE
# Token-ul selfbot (fără "Bot " în față, direct token-ul brut)
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'TU_TOKEN_AICI') 
SERVER_ID = os.getenv('SERVER_ID', '000000000000000000')

REPORT_REASON = "This server appears to be involved in raid/spam activity. It is being used to send unsolicited spam and mass mentions such as @everyone/@here, disrupting other Discord servers. Please review the server and take appropriate action if it violates Discord's rules."

# Reducem sesiunile pentru a nu fi banat rapid
MAX_SESSIONS = 10 
BASE_DELAY = 1.5  # Un raport la fiecare 1.5s per sesiune

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

async def send_report(session, semaphore, stop_event, target_id):
    async with semaphore:
        if stop_event.is_set():
            return
        
        await asyncio.sleep(random.uniform(BASE_DELAY, BASE_DELAY + 0.5))

        headers = {
            "Authorization": DISCORD_TOKEN,
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENTS)
        }

        # ÎNCERCĂM /rules ÎNTÂI, PENTRU CĂ UNEORI FUNCȚIONAZĂ FĂRĂ PERMISIUNI
        # Dacă /rules dă 403, încercăm /reports
        url = f"https://discord.com/api/v9/guilds/{target_id}/rules"
        
        payload = {
            "reason": REPORT_REASON,
            "categories": ["spams"]
        }

        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                status = resp.status
                if status == 200:
                    logger.debug(f"[OK] Raportat via /rules: {target_id}")
                elif status == 429:
                    retry = int(resp.headers.get('Retry-After', 5))
                    logger.warning(f"[429] Rate Limit. Așteptare {retry}s")
                    await asyncio.sleep(retry)
                elif status == 403:
                    content = await resp.json()
                    # Dacă e 403, încercăm endpoint-ul /reports
                    logger.warning(f"[403] Încerc /reports pentru {target_id}...")
                    await try_reports_endpoint(session, headers, target_id)
                else:
                    logger.error(f"[ERR] Status {status}")
        except Exception as e:
            logger.error(f"[CONN] {e}")

async def try_reports_endpoint(session, headers, target_id):
    """Încearcă endpoint-ul /reports dacă /rules a eșuat"""
    url = f"https://discord.com/api/v9/guilds/{target_id}/reports"
    payload = {
        "reason": REPORT_REASON,
        "categories": ["spams"]
    }
    try:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status == 200:
                logger.debug(f"[OK] Raportat via /reports: {target_id}")
            elif resp.status == 403:
                content = await resp.json()
                if content.get("message") == "Missing Access":
                    logger.error(f"[403] Nu ai acces în {target_id}. Nu poți raporta fără permisiuni.")
                else:
                    logger.error(f"[403] Alte erori: {content}")
            elif resp.status == 429:
                retry = int(resp.headers.get('Retry-After', 5))
                await asyncio.sleep(retry)
            else:
                logger.error(f"[ERR] Status {resp.status}")
    except Exception as e:
        logger.error(f"[CONN] {e}")

async def run_reporter(stop_event, target_id):
    semaphore = asyncio.Semaphore(MAX_SESSIONS)
    connector = aiohttp.TCPConnector(limit=MAX_SESSIONS)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for _ in range(MAX_SESSIONS):
            tasks.append(asyncio.create_task(send_report(session, semaphore, stop_event, target_id)))
        
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

async def main():
    logger.info(f"Start Selfbot Mass Report (No Perms Mode) pentru Server ID: {SERVER_ID}")
    stop_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        logger.info("Oprește selfbot...")
        stop_event.set()
    signal.signal(signal.SIGINT, signal_handler)

    try:
        await run_reporter(stop_event, SERVER_ID)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    asyncio.run(main())
