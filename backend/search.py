"""Web Search module for InesBot"""
import asyncio
import aiohttp
from typing import List, Optional
import logging

logger = logging.getLogger("inesbot.search")

class WebSearch:
    """Web search using DuckDuckGo and Wikipedia"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def search(self, query: str, max_results: int = 5) -> str:
        """Search web and return formatted results"""
        try:
            results = []

            # DuckDuckGo search
            ddgs_results = await self._duckduckgo_search(query, max_results)
            if ddgs_results:
                results.append("=== DuckDuckGo ===")
                for r in ddgs_results:
                    results.append(r)

            # Wikipedia search
            wiki_results = await self._wikipedia_search(query, max_results)
            if wiki_results:
                results.append("=== Wikipedia ===")
                for r in wiki_results:
                    results.append(r)

            if not results:
                return ""

            return "\n\n".join(results)
        except Exception as e:
            logger.error("Search error: " + str(e))
            return ""

    async def _duckduckgo_search(self, query: str, max_results: int) -> List[str]:
        """Search DuckDuckGo"""
        try:
            session = await self._get_session()
            url = "https://html.duckduckgo.com/html/"
            data = {"q": query, "kl": "pt-pt"}

            async with session.post(url, data=data, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
                return self._parse_duckduckgo(html, max_results)
        except Exception as e:
            logger.error("DDG error: " + str(e))
            return []

    def _parse_duckduckgo(self, html: str, max: int) -> List[str]:
        """Parse DuckDuckGo HTML results"""
        results = []
        import re
        # Extract title and snippet
        pattern = r'<a[^>]*class="result__a"[^>]*>(.*?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        for title, snippet in matches[:max]:
            title = re.sub(r'<[^>]+>', '', title).strip()
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            if title and snippet:
                results.append(title + ": " + snippet)
        return results

    async def _wikipedia_search(self, query: str, max_results: int) -> List[str]:
        """Search Wikipedia"""
        try:
            session = await self._get_session()
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": max_results
            }

            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results = []
                for item in data.get("query", {}).get("search", []):
                    title = item.get("title", "")
                    import re
                    snippet = re.sub(r'<[^>]+>', '', item.get("snippet", "")).strip()
                    if title:
                        results.append(title + ": " + snippet)
                return results
        except Exception as e:
            logger.error("Wiki error: " + str(e))
            return []

# Global instance
web_search = WebSearch()
