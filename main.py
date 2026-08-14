import asyncio
import aiohttp
import os
import logging
import random
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurare din variabile de mediu sau hardcoded pentru test local
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'TOKENTAU_AICI')
SERVER_ID = os.getenv('SERVER_ID', 'ID_SERVER_AICI')

REPORT_REASON = "This server appears to be involved in raid/spam activity. It is being used to send unsolicited spam and mass mentions such as @everyone/@here, disrupting other Discord servers. Please review the server and take appropriate action if it violates Discord's rules."

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

async def send_report(session, semaphore, stop_event):
    async with semaphore:
        # Delay mic pentru a simula comportament uman și a nu bloca
        await asyncio.sleep(random.uniform(0.05, 0.12))
        
        if stop_event.is_set():
            return

        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}", # Uneori "Bot" merge, uneori "User" sau fără prefix dacă e user token. 
            # Pentru selfbot pur, uneori e nevoie de "User" sau token-ul direct.
            # Dacă e user token, încearcă "Bearer {DISCORD_TOKEN}" sau "User {DISCORD_TOKEN}"
            # Cel mai sigur pentru selfbot modern este:
            "Authorization": f"User {DISCORD_TOKEN}", 
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENTS),
            "X-Super-Properties": "eyJicm93c2VyIjoiQ2hyb21lIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzEyMC4wLjAuMCBTYWZhcmkvNTM3LjM2Iiwib3BlcmF0aW5nX3N5c3RlbSI6IldpbmRvd3MiLCJsdWFndWFnZSI6ImVuLVVTIn0="
        }

        # ENDPOINT CORECT PENTRU SELFREPORT
        url = f"https://discord.com/api/v9/guilds/{SERVER_ID}/reports"

        payload = {
            "reason": REPORT_REASON,
            "category": 4  # 4 = Spams / Raid
        }

        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                status = resp.status
                body = await resp.text()
                
                if status == 200:
                    logger.info(f"[OK] Raport trimis pentru {SERVER_ID}")
                elif status == 429:
                    retry_after = int(resp.headers.get('Retry-After', 1))
                    logger.warning(f"[429] Rate Limited. Așteptare {retry_after}s")
                    await asyncio.sleep(retry_after)
                elif status == 404:
                    logger.error(f"[404] Endpoint invalid sau ID greșit. URL: {url}")
                    logger.error(f"[404] Body: {body[:100]}")
                    stop_event.set()
                elif status == 403:
                    logger.error(f"[403] Token invalid sau insuficient. Body: {body[:100]}")
                    stop_event.set()
                else:
                    logger.error(f"[ERR] Status {status}: {body[:100]}")
        except Exception as e:
            logger.error(f"[EXC] {e}")

async def run_reporter(stop_event):
    # 15 sesiuni paralele pentru a ajunge la ~500 req/min
    semaphore = asyncio.Semaphore(15)
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
    if not DISCORD_TOKEN or not SERVER_ID:
        logger.error("Erori de configurare: DISCORD_TOKEN sau SERVER_ID lipsesc.")
        return

    logger.info(f"Start Mass Report pentru Server: {SERVER_ID}")
    logger.info(f"Token Type: User (auto-modified to 'User' prefix)")
    
    stop_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        logger.info("Oprește...")
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
