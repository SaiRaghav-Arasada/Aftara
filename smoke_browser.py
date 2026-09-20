import os
import tempfile
from playwright.sync_api import sync_playwright
import remote_desktop
uid='f'*32
try:
 desktop=remote_desktop.start(uid)
 with tempfile.TemporaryDirectory() as profile,sync_playwright() as driver:
  browser=driver.chromium.launch_persistent_context(profile,executable_path='/usr/bin/chromium',headless=False,env=dict(os.environ,DISPLAY=desktop['display']))
  page=browser.pages[0];page.set_content('<h1>Deployment browser check</h1><p>Synthetic test only</p>')
  assert page.locator('h1').inner_text()=='Deployment browser check'
  browser.close()
 print('Visible Chromium and private remote display passed.')
finally:remote_desktop.stop(uid)
