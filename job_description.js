() => {
  const visible = el => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
  const clean = value => (value || '').replace(/\u00a0/g, ' ').replace(/[ \t]+\n/g, '\n').trim();
  const textOf = el => clean(el.innerText);
  const title = [...document.querySelectorAll('h1')].filter(visible).map(textOf).find(Boolean) || '';
  const selectors = ['.jobs-description__content', '.jobs-description-content__text', '.jobs-box__html-content', '.show-more-less-html__markup', '#job-details', '[data-testid="job-description"]', '[data-test-id="job-description"]'];
  // Try every match: LinkedIn can leave a hidden duplicate ahead of the visible panel.
  for (const selector of selectors) {
    for (const el of document.querySelectorAll(selector)) {
      if (!visible(el)) continue;
      const text = textOf(el);
      if (text.length >= 80) return {text: text.slice(0, 20000), title, method: 'visible job description'};
    }
  }
  const headings = [...document.querySelectorAll('h1,h2,h3,[role="heading"]')].filter(visible);
  const heading = headings.find(el => /^(about (the|this) job|job description)\s*$/i.test(textOf(el)));
  if (heading) {
    // Bound extraction to the description's own section, never the full page or account UI.
    let container = heading.parentElement;
    for (let depth = 0; container && depth < 4; depth++, container = container.parentElement) {
      if (container.matches('main,body,html') || container.querySelector('nav,aside,[role="navigation"]')) break;
      const text = textOf(container);
      const otherHeadings = [...container.querySelectorAll('h1,h2,h3,[role="heading"]')].filter(visible);
      if (otherHeadings.some(h => /^(similar jobs|about the company|people you can reach out to|meet the hiring team|more jobs)/i.test(textOf(h)))) break;
      if (text.length >= 120 && text.length <= 30000) return {text: text.slice(0, 20000), title, method: 'About the job section'};
    }
  }
  const currentId = location.pathname.match(/\/jobs\/view\/(?:[^/]*-)?(\d+)/)?.[1];
  const postings = [];
  const walk = value => {
    if (Array.isArray(value)) return value.forEach(walk);
    if (!value || typeof value !== 'object') return;
    if ([value['@type']].flat().includes('JobPosting')) postings.push(value);
    if (value['@graph']) walk(value['@graph']);
  };
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    try { walk(JSON.parse(script.textContent)); } catch (_) {}
  }
  for (const job of postings) {
    const declaredId = String(job.identifier?.value || '');
    const declaredUrl = String(job.url || job.mainEntityOfPage?.['@id'] || '');
    const urlId = declaredUrl.match(/\/jobs\/view\/(?:[^/]*-)?(\d+)/)?.[1];
    if (currentId && ((urlId && urlId !== currentId) || (/^\d+$/.test(declaredId) && declaredId !== currentId))) continue;
    if (postings.length > 1 && currentId && urlId !== currentId && declaredId !== currentId) continue;
    if (typeof job.description !== 'string') continue;
    const parsed = new DOMParser().parseFromString(job.description, 'text/html');
    parsed.querySelectorAll('script,style').forEach(el=>el.remove());
    parsed.querySelectorAll('br').forEach(el=>el.replaceWith('\n'));
    parsed.querySelectorAll('p,li,div,h1,h2,h3').forEach(el=>el.append('\n'));
    const text = clean(parsed.body.textContent);
    if (text.length >= 80) return {text: text.slice(0,20000), title: title || String(job.title || ''), method:'structured JobPosting data'};
  }
  const unavailable = headings.some(el=>/job (is )?(no longer available|not found)|page (not found|doesn.t exist)/i.test(textOf(el)));
  return {text:'',title,method:'',unavailable};
}
