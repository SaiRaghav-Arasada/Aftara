() => {
  const links = [];
  for (const node of document.querySelectorAll('a[href*="/jobs/"]')) {
    links.push(node.href);
  }
  for (const node of document.querySelectorAll('[data-job-id], [data-occludable-job-id], [data-entity-urn]')) {
    const id = node.getAttribute('data-job-id') || node.getAttribute('data-occludable-job-id');
    const urn = node.getAttribute('data-entity-urn') || '';
    const match = urn.match(/^urn:li:(?:fsd_)?jobPosting:(\d+)$/);
    const value = id || (match && match[1]);
    if (value && /^\d{1,20}$/.test(value) && !/^0+$/.test(value)) {
      links.push('https://www.linkedin.com/jobs/view/' + value + '/');
    }
  }
  return links;
}
