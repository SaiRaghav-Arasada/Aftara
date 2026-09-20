"""Real Chromium DOM checks with synthetic pages; no requests reach LinkedIn."""
from playwright.sync_api import sync_playwright
from browser_jobs import collect_job_links

with sync_playwright() as driver:
 browser=driver.chromium.launch(executable_path='/usr/bin/chromium',headless=True)
 page=browser.new_page()
 cases=[
  ('<a href="https://in.linkedin.com/jobs/view/test-engineer-123456/">Test role</a>',['123456']),
  ('<a href="/jobs/search/?currentJobId=234567">Test role</a><li data-occludable-job-id="234567"></li>',['234567']),
  ('<li data-entity-urn="urn:li:fsd_jobPosting:345678">Test role</li>',['345678']),
  ('<a href="https://linkedin.com.evil.test/jobs/view/456789/">Invalid</a><div data-entity-urn="urn:li:member:456789"></div>',[]),
 ]
 for html,ids in cases:
  page.route('**/*',lambda route,request,html=html:route.fulfill(status=200,body=html,content_type='text/html'))
  page.goto('https://www.linkedin.com/jobs/search/')
  assert collect_job_links(page,timeout=0)==['https://www.linkedin.com/jobs/view/'+i+'/' for i in ids]
  page.unroute('**/*')
 browser.close()
 print('PASS: four Chromium job-link fixtures; no LinkedIn or Gemini requests.')
