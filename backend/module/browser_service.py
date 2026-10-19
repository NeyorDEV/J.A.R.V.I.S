import asyncio
from playwright.async_api import async_playwright
from typing import List, Dict

class AutonomousBrowser:
    def __init__(self):
        self.browser = None
        self.context = None
        self._playwright = None

    async def start(self):
        if not self.browser:
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
                }
            )


    async def _handle_popups(self, page):
        """Tente de fermer les popups de cookies ou de consentement."""
        try:
            # Sélecteurs communs pour les boutons d'acceptation
            selectors = [
                "button:has-text('Accepter')", "button:has-text('Tout accepter')",
                "button:has-text('I agree')", "button:has-text('Accept all')",
                "button:has-text('Autoriser')", "#L2AGLb", "button[id*='accept']"
            ]
            for selector in selectors:
                if await page.is_visible(selector, timeout=1000):
                    await page.click(selector)
                    break
        except:
            pass

    async def get_page_content(self, url: str) -> str:
        """Navigue vers une URL et extrait le texte structuré."""
        await self.start()
        page = await self.context.new_page()
        try:
            await page.goto(url, timeout=45000, wait_until="domcontentloaded")
            await asyncio.sleep(2) # Laisser le temps au JS de charger
            await self._handle_popups(page)
            
            # Extraction intelligente : on cherche les balises de contenu
            text = await page.evaluate('''() => {
                const article = document.querySelector('article') || document.querySelector('main') || document.body;
                // Supprimer les scripts, styles, nav, footer pour ne garder que le contenu
                const clones = article.cloneNode(true);
                const toRemove = clones.querySelectorAll('script, style, nav, footer, header, aside, iframe, .ads, .menu');
                toRemove.forEach(el => el.remove());
                return clones.innerText;
            }''')
            
            lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 30]
            return "\n".join(lines[:100]) 
        except Exception as e:
            return f"Erreur navigation vers {url} : {e}"
        finally:
            await page.close()

    async def search_and_browse(self, query: str, num_results: int = 3) -> List[Dict[str, str]]:
        """Effectue une recherche via SerpApi puis analyse les pages avec Playwright."""
        all_data = []
        try:
            print(f"[BROWSER] Recherche SerpApi pour : {query}")
            from module.recherche_web import serpapi_donnees_brutes

            
            # On récupère les résultats bruts (JSON) via SerpApi
            results = serpapi_donnees_brutes(query)
            links = []
            
            if results and "organic_results" in results:
                for res in results["organic_results"][:num_results]:
                    links.append({
                        "title": res.get("title", "Sans titre"),
                        "href": res.get("link")
                    })
            
            print(f"[BROWSER] Liens SerpApi trouvés : {len(links)}")
            
            if not links:
                # Fallback manuel si SerpApi échoue
                print("[BROWSER] Fallback manuel DuckDuckGo...")
                return await self._manual_search_fallback(query, num_results)

            for item in links:
                content = await self.get_page_content(item['href'])
                if content and len(content) > 100 and "Erreur" not in content:
                    all_data.append({
                        "title": item['title'],
                        "url": item['href'],
                        "content": content
                    })
            
            return all_data
        except Exception as e:
            print(f"[BROWSER] Erreur recherche : {e}")
            return await self._manual_search_fallback(query, num_results)

    async def _manual_search_fallback(self, query: str, num_results: int) -> List[Dict[str, str]]:
        """Méthode de secours sans API."""
        await self.start()
        page = await self.context.new_page()
        all_data = []
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            links = await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('.result__a'))
                    .map(a => ({ title: a.innerText, href: a.href }))
                    .filter(item => item.href && !item.href.includes('duckduckgo.com'))
                    .slice(0, 3);
            }''')
            
            for item in links:
                content = await self.get_page_content(item['href'])
                if content and len(content) > 100:
                    all_data.append({"title": item['title'], "url": item['href'], "content": content})
            return all_data
        except:
            return []
        finally:
            await page.close()

    async def stop(self):
        if self.browser:
            await self.browser.close()
            await self._playwright.stop()
            self.browser = None
            self._playwright = None

