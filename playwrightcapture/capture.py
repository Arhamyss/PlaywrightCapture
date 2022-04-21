#!/usr/bin/env python3

import json
import os

from tempfile import NamedTemporaryFile
from typing import Optional, Dict, List, Union

from playwright.async_api import async_playwright, ProxySettings


class Capture():

    _browsers = ['chromium', 'firefox', 'webkit']
    _viewport = {'width': 1920, 'height': 1080}
    _general_timeout = 90 * 1000   # in miliseconds, set to 90s by default

    def __init__(self, browser: str='chromium'):

        self._temp_harfile = NamedTemporaryFile(delete=False)

    async def prepare_capture(self, browser: str='chromium', proxy: Optional[Union[str, Dict[str, str]]]=None):
        '''Launch the browser, with or without a proxy.
        :param proxy: The proxy, as a dictionary with the following format:
            ```
               {'server': 'proxy.server',
                'username': 'user',
                'password': 'pwd'}
            ```
        '''
        self.playwright = await async_playwright().start()
        if browser not in self._browsers:
            raise Exception(f'Incorrect browser name, must be in {", ".join(self._browsers)}')

        if browser == 'chromium':
            browser_type = self.playwright.chromium
        elif browser == 'firefox':
            browser_type = self.playwright.firefox
        elif browser == 'webkit':
            browser_type = self.playwright.webkit
        if proxy:
            p: ProxySettings
            if isinstance(proxy, str):
                p = {'server': proxy}
            else:
                p = {'server': proxy['server'], 'bypass': proxy.get('bypass', ''),
                     'username': proxy.get('username', ''), 'password': proxy.get('password', '')}
            self.browser = await browser_type.launch(proxy=p)
        else:
            self.browser = await browser_type.launch()

    async def prepare_context(self):
        self.context = await self.browser.new_context(
            record_har_path=self._temp_harfile.name,
            viewport=self.viewport,
            user_agent=self.user_agent,
            # http_credentials=self.http_credentials
        )
        self.context.set_default_navigation_timeout(self._general_timeout)
        if hasattr(self, 'http_headers'):
            await self.context.set_extra_http_headers(self.http_headers)
        if hasattr(self, 'session_cookies'):
            await self.context.add_cookies(self.session_cookies)

    @property
    def user_agent(self) -> str:
        if not hasattr(self, '_user_agent'):
            return ''
        return self._user_agent

    @user_agent.setter
    def user_agent(self, user_agent: str):
        self._user_agent = user_agent

    @property
    def http_headers(self) -> Dict[str, str]:
        if not hasattr(self, '_http_headers'):
            return {}
        return self._http_headers

    @http_headers.setter
    def http_headers(self, headers: Dict[str, str]):
        '''HTTPheaders to send along to the initial request.
        :param headers: The headers, in this format (no space in the header name, value must be a string):
            ```
                {'header_name': 'value', 'other_header_name': 'value'}
            ```
        '''
        self._http_headers = headers

    @property
    def cookies(self) -> List[Dict]:
        if not hasattr(self, '_cookies'):
            return []
        return self._cookies

    @cookies.setter
    def cookies(self, cookies: List[Dict]):
        '''Cookies to send along to the initial request.
        :param cookies: The headers, in this format: https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-cookies
        '''
        self._cookies = cookies

    @property
    def viewport(self):
        return self._viewport

    def set_viewport(self, width: int, height: int):
        self._viewport = {'width': width, 'height': height}

    @property
    def http_credentials(self) -> Dict:
        if not hasattr(self, '_http_credentials'):
            return {}
        return self._http_credentials

    def set_http_credentials(self, username: str, password: str):
        self._http_credentials = {'username': username, 'password': password}

    async def capture_page(self, url: str, referer: Optional[str]=None):
        page = await self.context.new_page()
        await page.goto(url, wait_until='networkidle', referer=referer if referer else '')

        # page instrumentation
        await page.wait_for_timeout(5000)  # Wait 5 sec after network idle
        # move mouse
        await page.mouse.move(x=500, y=400)
        await page.wait_for_load_state('networkidle')

        # scroll
        await page.mouse.wheel(delta_y=2000, delta_x=0)
        await page.wait_for_load_state('networkidle')

        await page.wait_for_timeout(5000)  # Wait 5 sec after network idle

        to_return = {}
        to_return['html'] = await page.content()
        to_return['png'] = await page.screenshot(full_page=True)
        to_return['last_redirected_url'] = page.url
        to_return['cookies'] = await self.context.cookies()
        await self.context.close()
        with open(self._temp_harfile.name) as _har:
            to_return['har'] = json.load(_har)

        return to_return

    async def __exit__(self):
        if hasattr(self, '_temp_harfile'):
            os.unlink(self._temp_harfile)

        await self.browser.close()
        await self.playwright.stop()