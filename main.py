import asyncio
import aiohttp
import os
import logging
import random
import signal

# Configurare Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Variabile de mediu
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', '')
SERVER_ID = os.getenv('SERVER_ID', '1487092822913060994') # ID-ul serverului TĂU sau al țintei

# Reason-ul exact cerut
REPORT_REASON = "This server appears to be involved in raid/spam activity. It is being used to send unsolicited spam and mass mentions such as @everyone/@here, disrupting other Discord servers. Please review the server and take appropriate action if it violates Discord's rules."

# User Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

async def send_report(session, semaphore, stop_event):
    """
    Trimite un raport către Discord folosind endpoint-ul corect pentru selfbot.
    URL: /api/v10/users/@me/guilds/{guild_id}/report
    """
    async with semaphore:
        # Delay mic pentru a evita detecția rapidă
        await asyncio.sleep(random.uniform(0.05, 0.15))
        
        if stop_event.is_set():
            return

        headers = {
            "Authorization": f"Bearer {DISCORD_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENTS)
        }

        # URL CORECT: v10, @me (nu amе), endpoint-ul de report specific
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
                    logger.info(f"[OK] Raport trimis cu succes pentru {SERVER_ID}")
                elif status == 429:
                    # Rate limiting
                    retry_after = int(resp.headers.get('Retry-After', 1))
                    logger.warning(f"[429] Rate Limited! Așteptare {retry_after}s")
                    await asyncio.sleep(retry_after)
                elif status == 404:
                    logger.error(f"[404] Endpoint nu există sau Token invalid. URL: {url}")
                    logger.error(f"[404] Response: {body[:200]}")
                    stop_event.set()
                elif status == 403:
                    logger.error(f"[403] Token invalid sau permisiuni insuficiente.")
                    stop_event.set()
                else:
                    logger.error(f"[ERR] Status {status} - {body[:100]}")
        except Exception as e:
            logger.error(f"[EXC] Eroare conexiune: {e}")

async def run_reporter(stop_event):
    """
    Rulează sesiunile de raportare paralel.
    """
    semaphore = asyncio.Semaphore(15) # 15 sesiuni simultane
    connector = aiohttp.TCPConnector(limit=15, ttl_dns_cache=300)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for _ in range(15):
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
    logger.info(f"Start Mass Report (Selfbot) pentru Server: {SERVER_ID}")
    logger.info(f"Token: Bearer {DISCORD_TOKEN[:10]}...")
    logger.info(f"URL Target: https://discord.com/api/v10/users/@me/guilds/{SERVER_ID}/report")
    
    stop_event = asyncio.Event()
    
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
