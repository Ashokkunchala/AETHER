"""Optional real Chromium tests against locally fulfilled fixtures, no internet."""
import asyncio
import json
import socket
from pathlib import Path

import pytest

pytest.importorskip('playwright.async_api')
from playwright.async_api import async_playwright

from jarvis.custom_dashboard import render_dashboard
from jarvis.rendered_browser import _browse, browser_preview

ROOT = Path(__file__).resolve().parents[1]


def test_real_chromium_rendered_js_and_guarded_follow(tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_BROWSER_ENABLED','1')
    monkeypatch.setenv('AETHER_BROWSER_HOSTS','example.com')
    monkeypatch.setenv('JARVIS_SECURITY_DB',str(tmp_path/'security.db'))
    monkeypatch.setenv('AETHER_BROWSER_OUTPUT',str(tmp_path))
    monkeypatch.setattr(socket,'getaddrinfo',lambda *_a,**_k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))])
    class FixtureLauncher:
        async def __aenter__(self):
            self.pw=await async_playwright().start();self.chromium=self;return self
        async def __aexit__(self,*_):await self.pw.stop()
        async def launch(self,**kwargs):
            self.browser=await self.pw.chromium.launch(**kwargs);return self
        async def new_context(self,**kwargs):
            context=await self.browser.new_context(**kwargs)
            original=context.route
            async def route(pattern,handler):
                async def fulfilled(real_route):
                    class Proxy:
                        request=real_route.request
                        async def abort(self):await real_route.abort()
                        async def continue_(self):
                            page='<html><body><div id="result">Initial</div><a href="/next">Next</a><script>document.getElementById("result").textContent="Rendered by JavaScript";</script></body></html>'
                            await real_route.fulfill(status=200,content_type='text/html',body=page)
                    await handler(Proxy())
                await original(pattern,fulfilled)
            context.route=route
            return context
        async def close(self):await self.browser.close()
    result=asyncio.run(_browse(browser_preview('https://example.com/start','https://example.com/next'),FixtureLauncher))
    assert result['url']=='https://example.com/next'
    assert 'Rendered by JavaScript' in result['text']
    assert Path(result['screenshot_path']).read_bytes().startswith(b'\x89PNG')


def test_dashboard_real_chromium_mobile_layout_and_no_requests(tmp_path):
    spec=json.loads((ROOT/'docs/examples/dashboard-spec.json').read_text())
    html=render_dashboard(spec)
    async def run():
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(headless=True)
            for width in (320,390,1280):
                page=await browser.new_page(viewport={'width':width,'height':900})
                requests=[];page.on('request',lambda request:requests.append(request.url))
                await page.set_content(html)
                assert await page.locator('h1').inner_text()==spec['title']
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert not requests
                await page.screenshot(path=str(tmp_path/f'dashboard-{width}.png'),full_page=True)
                await page.close()
            await browser.close()
    asyncio.run(run())
