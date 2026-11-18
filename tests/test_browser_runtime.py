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


def _performance_payload():
    return {
        'cpu_percent': 12.0, 'memory_percent': 34.0, 'disk_percent': 56.0,
        'battery_percent': None, 'battery_plugged': None,
        'memory_used_gb': 4.0, 'memory_total_gb': 16.0, 'disk_free_gb': 100.0,
        'platform': 'test', 'cpu_count': 8, 'process_memory_mb': 128,
        'network_bytes_sent': None, 'network_bytes_recv': None,
    }


def test_main_dashboard_provider_summary_real_chromium_and_mobile_layout(tmp_path):
    html = (ROOT / 'app/static/dashboard.html').read_text()
    provider_auth = []

    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(viewport={'width': 390, 'height': 900})

            async def route(route):
                from urllib.parse import urlsplit
                path = urlsplit(route.request.url).path
                if path == '/dashboard':
                    await route.fulfill(status=200, content_type='text/html', body=html)
                elif path == '/api/performance':
                    await route.fulfill(status=200, content_type='application/json', body=json.dumps(_performance_payload()))
                elif path == '/api/runtime/events':
                    await route.fulfill(status=200, content_type='application/json', body=json.dumps({'events': [], 'oldest_id': 0, 'latest_id': 0}))
                elif path == '/api/provider/health':
                    provider_auth.append(route.request.headers.get('authorization'))
                    await route.fulfill(status=200, content_type='application/json', body=json.dumps({
                        'providers': [{
                            'provider': 'gemini<img src=x onerror=alert(1)>', 'events': 3,
                            'success_rate': 0.6667, 'latest_result': 'unknown',
                            'latency_seconds': {'samples': 3, 'average': 0.25},
                        }],
                        'storage': 'sqlite', 'measured_only': True, 'quota_reported': False,
                    }))
                else:
                    await route.abort()

            await page.route('**/*', route)
            await page.goto('http://aether.test/dashboard')
            await page.fill('#token', 'test-token')
            await page.click('#connectBtn')
            await page.wait_for_function('document.getElementById("state").textContent.includes("LIVE")')
            await page.click('#refreshProviderHealth')
            await page.wait_for_function('document.getElementById("providerHealthStatus").textContent.includes("Recorded local history loaded")')
            summary = page.locator('#providerSummary')
            assert await summary.inner_text() != ''
            assert 'gemini<img src=x onerror=alert(1)>' in await summary.inner_text()
            assert '3 recorded events' in await summary.inner_text()
            assert 'latest retained result unknown' in await summary.inner_text()
            assert 'average measured latency 0.250s' in await summary.inner_text()
            assert '&lt;img' in await summary.inner_html()
            assert provider_auth == ['Bearer test-token']
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            await page.screenshot(path=str(tmp_path / 'provider-panel-mobile.png'), full_page=True)
            await page.set_viewport_size({'width': 1280, 'height': 900})
            await page.wait_for_timeout(100)
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            await page.screenshot(path=str(tmp_path / 'provider-panel-desktop.png'), full_page=True)
            await browser.close()

    asyncio.run(run())


def test_main_dashboard_ignores_stale_provider_summary_after_token_change():
    html = (ROOT / 'app/static/dashboard.html').read_text()

    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(viewport={'width': 1280, 'height': 900})
            provider_calls = 0
            release_first = asyncio.Event()

            async def route(route):
                nonlocal provider_calls
                from urllib.parse import urlsplit
                path = urlsplit(route.request.url).path
                if path == '/dashboard':
                    await route.fulfill(status=200, content_type='text/html', body=html)
                elif path == '/api/performance':
                    await route.fulfill(status=200, content_type='application/json', body=json.dumps(_performance_payload()))
                elif path == '/api/runtime/events':
                    await route.fulfill(status=200, content_type='application/json', body=json.dumps({'events': [], 'oldest_id': 0, 'latest_id': 0}))
                elif path == '/api/provider/health':
                    provider_calls += 1
                    if provider_calls == 1:
                        await release_first.wait()
                        provider = 'stale-provider'
                    else:
                        provider = 'current-provider'
                    await route.fulfill(status=200, content_type='application/json', body=json.dumps({
                        'providers': [{'provider': provider, 'events': 1, 'success_rate': 1, 'latest_result': 'success', 'latency_seconds': {'samples': 1, 'average': 0.1}}],
                        'measured_only': True, 'quota_reported': False,
                    }))
                else:
                    await route.abort()

            await page.route('**/*', route)
            await page.goto('http://aether.test/dashboard')
            await page.fill('#token', 'first-token')
            await page.click('#connectBtn')
            await page.wait_for_function('document.getElementById("state").textContent.includes("LIVE")')
            await page.click('#refreshProviderHealth')
            await page.wait_for_function('document.getElementById("providerHealthStatus").textContent.includes("Reading")')
            await page.fill('#token', 'second-token')
            await page.click('#connectBtn')
            await page.wait_for_function('document.getElementById("providerHealthStatus").textContent.includes("Connected")')
            release_first.set()
            await page.wait_for_function('!document.getElementById("refreshProviderHealth").disabled')
            assert 'stale-provider' not in await page.locator('#providerSummary').inner_text()
            assert 'Token changed' in await page.locator('#providerSummary').inner_text()
            await page.click('#refreshProviderHealth')
            await page.wait_for_function('document.getElementById("providerHealthStatus").textContent.includes("Recorded local history loaded")')
            assert 'current-provider' in await page.locator('#providerSummary').inner_text()
            await browser.close()

    asyncio.run(run())


def _routes_for_dashboard(html, provider_auth=None):
    async def route(route):
        from urllib.parse import urlsplit
        path = urlsplit(route.request.url).path
        if path == '/dashboard':
            await route.fulfill(status=200, content_type='text/html', body=html)
        elif path == '/api/performance':
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(_performance_payload()))
        elif path == '/api/runtime/events':
            await route.fulfill(status=200, content_type='application/json', body=json.dumps({'events': [], 'oldest_id': 0, 'latest_id': 0}))
        elif path == '/api/provider/health':
            await route.fulfill(status=200, content_type='application/json', body=json.dumps({'providers': [], 'storage': 'sqlite', 'measured_only': True, 'quota_reported': False}))
        else:
            await route.abort()
    return route


def test_main_dashboard_alert_history_records_persists_and_clears(tmp_path):
    html = (ROOT / 'app/static/dashboard.html').read_text()

    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1280, 'height': 900})
            page = await context.new_page()
            await page.route('**/*', _routes_for_dashboard(html))
            await page.goto('http://aether.test/dashboard')
            await page.fill('#token', 'test-token')
            await page.click('#connectBtn')
            await page.wait_for_function('document.getElementById("state").textContent.includes("LIVE")')
            assert 'No threshold crossings recorded' in await page.locator('#alertHistory').inner_text()
            await page.check('#warningsEnabled')
            await page.wait_for_timeout(2300)
            assert 'No threshold crossings recorded' in await page.locator('#alertHistory').inner_text()
            await page.eval_on_selector('#cpuThreshold', 'el=>{el.value="1";el.dispatchEvent(new Event("change"))}')
            await page.wait_for_function('document.getElementById("alertHistory").textContent.includes("CPU usage crossed")', timeout=15000)
            text = await page.locator('#alertHistory').inner_text()
            assert 'CPU usage crossed 1%' in text

            # A reload keeps the recorded history in this browser.
            await page.reload()
            await page.wait_for_function('document.getElementById("alertHistory") && document.getElementById("alertHistory").textContent.includes("CPU usage crossed")')

            # Clearing removes only the local record.
            await page.click('#clearAlertHistory')
            assert 'No threshold crossings recorded' in await page.locator('#alertHistory').inner_text()
            assert await page.evaluate('localStorage.getItem("jarvisAlertHistory")') is None
            await context.close()
            await browser.close()

    asyncio.run(run())


def test_main_dashboard_alert_history_is_bounded_and_survives_corrupt_storage():
    html = (ROOT / 'app/static/dashboard.html').read_text()

    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context()
            await context.add_init_script(
                'localStorage.setItem("jarvisAlertHistory", JSON.stringify('
                'Array.from({length: 60}, (_, i) => ({message: "CPU usage crossed " + i + "% <img src=x onerror=alert(1)>", time: "t" + i}))))'
            )
            page = await context.new_page()
            await page.route('**/*', _routes_for_dashboard(html))
            await page.goto('http://aether.test/dashboard')
            await page.wait_for_function('document.getElementById("alertHistory") && document.getElementById("alertHistory").children.length === 50')
            rendered = await page.locator('#alertHistory').inner_html()
            assert '&lt;img' in rendered
            assert '<img src=x' not in rendered

            # Corrupt storage falls back to the empty state without a script error.
            await page.evaluate('localStorage.setItem("jarvisAlertHistory", "not json {")')
            await page.click('#clearAlertHistory')
            assert 'No threshold crossings recorded' in await page.locator('#alertHistory').inner_text()
            await context.close()
            await browser.close()

    asyncio.run(run())


def test_main_dashboard_network_threshold_crossing_records_one_alert():
    html = (ROOT / 'app/static/dashboard.html').read_text()
    state = {'with_network': False, 'served': 0}

    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1280, 'height': 900})
            page = await context.new_page()

            async def route(route):
                from urllib.parse import urlsplit
                path = urlsplit(route.request.url).path
                if path == '/dashboard':
                    await route.fulfill(status=200, content_type='text/html', body=html)
                elif path == '/api/performance':
                    payload = _performance_payload()
                    if state['with_network']:
                        state['served'] += 1
                        payload['network_bytes_sent'] = state['served'] * 204800
                        payload['network_bytes_recv'] = state['served'] * 409600
                    await route.fulfill(status=200, content_type='application/json', body=json.dumps(payload))
                elif path == '/api/runtime/events':
                    await route.fulfill(status=200, content_type='application/json', body=json.dumps({'events': [], 'oldest_id': 0, 'latest_id': 0}))
                elif path == '/api/provider/health':
                    await route.fulfill(status=200, content_type='application/json', body=json.dumps({'providers': [], 'storage': 'sqlite', 'measured_only': True, 'quota_reported': False}))
                else:
                    await route.abort()

            await page.route('**/*', route)
            await page.goto('http://aether.test/dashboard')
            await page.fill('#token', 'test-token')
            await page.click('#connectBtn')
            await page.wait_for_function('document.getElementById("state").textContent.includes("LIVE")')
            await page.check('#warningsEnabled')
            await page.eval_on_selector('#netDownThreshold', 'el=>{el.value="100";el.dispatchEvent(new Event("change"))}')
            state['with_network'] = True
            await page.wait_for_function('document.getElementById("alertHistory").textContent.includes("Net download rate crossed 100 KB/s")', timeout=20000)
            text = await page.locator('#alertHistory').inner_text()
            assert text.count('Net download rate crossed') == 1
            assert 'Net upload rate crossed' not in text

            # A steady high rate does not re-alert, and reload keeps the record.
            await page.wait_for_timeout(4500)
            text = await page.locator('#alertHistory').inner_text()
            assert text.count('Net download rate crossed') == 1
            await page.reload()
            await page.wait_for_function('document.getElementById("alertHistory") && document.getElementById("alertHistory").textContent.includes("Net download rate crossed")')
            saved = await page.evaluate('localStorage.getItem("jarvisThresholdWarnings")')
            assert '"netDown":100' in saved
            await context.close()
            await browser.close()

    asyncio.run(run())
