/* api.js - shared API configuration */
// The static frontend is served by FastAPI. Keep API calls on the exact same
// origin so localhost and 127.0.0.1 never become a cross-origin request.
const API_BASE = window.location.origin + '/api';

async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) throw new Error(`API error ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error('API fetch error:', e);
    throw e;
  }
}

function formatSalary(s) {
  return s && s !== 'N/A' && s !== 'Thoa thuan' ? s : 'Thoả thuận';
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const diff = (Date.now() - d) / 1000;
  if (diff < 60) return 'Vừa đăng';
  if (diff < 3600) return Math.floor(diff/60) + ' phút trước';
  if (diff < 86400) return Math.floor(diff/3600) + ' giờ trước';
  return Math.floor(diff/86400) + ' ngày trước';
}

function initLogoText(name) {
  if (!name) return '?';
  return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
}

function buildJobCardHTML(job) {
  return `
    <div class="job-card" onclick="window.location='/static/job_detail.html?id=${job.id}'">
      <div class="job-card-header">
        <div class="company-logo">${initLogoText(job.company_name)}</div>
        <div>
          <div class="job-card-title">${job.title || 'N/A'}</div>
          <div class="job-card-company">${job.company_name || 'Công ty'}</div>
        </div>
      </div>
      <div class="job-card-meta">
        <span class="tag tag-salary">${formatSalary(job.salary)}</span>
        ${job.location ? `<span class="tag tag-loc">${job.location}</span>` : ''}
        ${job.experience ? `<span class="tag tag-exp">${job.experience}</span>` : ''}
      </div>
      <div class="job-card-footer">
        <span class="job-card-deadline">${job.created_time || timeAgo(job.created_at)}</span>
        <button class="btn-apply" onclick="event.stopPropagation(); window.open('${job.job_url}','_blank')">Ứng tuyển</button>
      </div>
    </div>`;
}

window.API_BASE = API_BASE;
window.apiFetch = apiFetch;
window.formatSalary = formatSalary;
window.timeAgo = timeAgo;
window.initLogoText = initLogoText;
window.buildJobCardHTML = buildJobCardHTML;
