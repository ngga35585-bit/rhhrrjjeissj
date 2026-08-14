import asyncio
import aiohttp
import random
import logging
import signal
import os

# Configurare Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURARE ---
# Lipește aici token-ul selfbot (fără "Bot " în față)
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'TU_TOKEN_AICI')
# ID-ul serverului țintă
SERVER_ID = os.getenv('SERVER_ID', '000000000000000000')

# Reason-ul exact
REPORT_REASON = "This server appears to be involved in raid/spam activity. It is being used to send unsolicited spam and mass mentions such as @everyone/@here, disrupting other Discord servers. Please review the server and take appropriate action if it violates Discord's rules."

# Parametri de viteză (pentru ~500 req/min)
# 15 sesiuni paralele * 1.2s delay ~ 125 req/min per sesiune * 15 = ~1800 max teoretic, dar limitat de API
MAX_SESSIONS = 15 
BASE_DELAY = 0.8  # Secunde între rapoarte per sesiune

# User-Agent randomizat
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

async def send_report(session, semaphore, stop_event, target_id):
    """Trimite un singur raport"""
    async with semaphore:
        if stop_event.is_set():
            return
        
        # Delay random pentru a părea organic
        await asyncio.sleep(random.uniform(BASE_DELAY, BASE_DELAY + 0.2))

        headers = {
            "Authorization": DISCORD_TOKEN,
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENTS)
        }

        # Încercăm mai întâi /rules (adesea acceptă fără permisiuni de admin)
        url = f"https://discord.com/api/v9/guilds/{target_id}/rules"
        payload = {
            "reason": REPORT_REASON,
            "categories": ["spams"]
        }

        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                status = resp.status
                
                if status == 200:
                    logger.info(f"[OK] Raportat prin /rules: {target_id}")
                    
                elif status == 429:
                    retry_after = int(resp.headers.get('Retry-After', 5))
                    logger.warning(f"[429] Rate Limit! Așteptare {retry_after}s")
                    await asyncio.sleep(retry_after)
                    
                elif status == 403:
                    # Dacă /rules dă 403, încercăm /reports
                    logger.warning(f"[403] /rules refuzat, încerc /reports pentru {target_id}...")
                    await try_reports_endpoint(session, headers, target_id)
                    
                else:
                    logger.error(f"[ERR] Status {status} pentru {target_id}")
                    
        except Exception as e:
            logger.error(f"[CONN] Eroare conexiune: {e}")

async def try_reports_endpoint(session, headers, target_id):
    """Fallback la endpoint-ul /reports"""
    url = f"https://discord.com/api/v9/guilds/{target_id}/reports"
    payload = {
        "reason": REPORT_REASON,
        "categories": ["spams"]
    }
    try:
        async with session.post(url, headers=headers, json=payload) as resp:
            status = resp.status
            if status == 200:
                logger.info(f"[OK] Raportat prin /reports: {target_id}")
            elif status == 403:
                content = await resp.json()
                if content.get("message") == "Missing Access":
                    logger.error(f"[403] Nu ai permisiuni în serverul {target_id}. Nu se poate raporta fără access.")
                else:
                    logger.error(f"[403] Erori generale: {content}")
            elif status == 429:
                retry_after = int(resp.headers.get('Retry-After', 5))
                await asyncio.sleep(retry_after)
            else:
                logger.error(f"[ERR] Status {status} la /reports")
    except Exception as e:
        logger.error(f"[CONN] Eroare la /reports: {e}")

async def run_reporter(stop_event, target_id):
    """Rulează sesiunile paralele"""
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
    logger.info(f"=== START MASS REPORT (No Perms Mode) ===")
    logger.info(f"Server ID: {SERVER_ID}")
    logger.info(f"Token: {DISCORD_TOKEN[:10]}...")
    logger.info(f"Sessions: {MAX_SESSIONS}")
    
    stop_event = asyncio.Event()
    
    # Handler pentru Ctrl+C
    def signal_handler(sig, frame):
        logger.info("Oprește mass report-ul...")
        stop_event.set()
    signal.signal(signal.SIGINT, signal_handler)

    try:
        await run_reporter(stop_event, SERVER_ID)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("=== STOPPED ===")

if __name__ == "__main__":
    asyncio.run(main())
