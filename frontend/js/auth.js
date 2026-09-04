/* Token convenience only; all authorization remains enforced by FastAPI. */
const Auth = (() => ({
  getToken: () => localStorage.getItem('job_portal_token'),
  getUser: () => { try { return JSON.parse(localStorage.getItem('job_portal_user') || 'null'); } catch (_) { return null; } },
  isLoggedIn: () => !!localStorage.getItem('job_portal_token'),
  login: async (payload, endpoint='/api/auth/login') => { const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); const d=await r.json(); if(!r.ok) { const detail=Array.isArray(d.detail)?d.detail.map(x=>x.msg).join(' '):d.detail; throw new Error(detail||'Không thể đăng nhập'); } localStorage.setItem('job_portal_token',d.access_token);localStorage.setItem('job_portal_user',JSON.stringify(d));return d; },
  register: async payload => Auth.login(payload, '/api/auth/register'),
  logout: () => { localStorage.removeItem('job_portal_token');localStorage.removeItem('job_portal_user');location.href='/'; },
  fetchMe: async () => {
    const token = Auth.getToken();
    if (!token) return null;
    const response = await fetch('/api/auth/me', { headers: { Authorization: 'Bearer ' + token } });
    if (!response.ok) throw new Error('Phiên đăng nhập không còn hiệu lực.');
    return response.json();
  },
  updateNavbar: () => {
    const area = document.getElementById('nav-auth-area');
    if (!area) return;
    const token = Auth.getToken();
    const user = Auth.getUser();
    area.classList.remove('d-none');
    area.className = 'd-flex align-items-center gap-2 me-3 mb-3 mb-lg-0';
    if (!document.getElementById('account-menu-style')) {
      const style = document.createElement('style');
      style.id = 'account-menu-style';
      style.textContent = '.account-menu{position:relative}.account-menu__toggle{border:0;background:transparent;color:#2b3940;font-weight:600;padding:.45rem .2rem;white-space:nowrap}.account-menu__toggle:hover{color:#00b074}.account-menu__panel{display:none;position:absolute;right:0;top:calc(100% + .45rem);z-index:1050;min-width:180px;padding:.45rem;background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:.45rem;box-shadow:0 .5rem 1rem rgba(0,0,0,.15)}.account-menu.open .account-menu__panel{display:block}.account-menu__name{display:block;padding:.45rem .65rem .6rem;color:#6c757d;font-size:.83rem;border-bottom:1px solid #edf0f1;margin-bottom:.25rem}.account-menu__item{display:block;width:100%;padding:.55rem .65rem;border:0;background:transparent;border-radius:.25rem;color:#33454d;text-align:left;text-decoration:none;font-size:.92rem}.account-menu__item:hover{background:#effaf6;color:#008f60}.account-menu__item--logout{color:#c33d35}';
      document.head.appendChild(style);
    }
    // A token is the source of truth for the initial UI. User data can be
    // missing after an older deployment or a partially cleared localStorage.
    const account = user || (token ? { name: 'Tài khoản', email: '' } : null);
    const accountUrl = account?.role === 'admin' ? '/static/admin.html' : (account?.role === 'partner' ? '/static/hr_insider.html' : '/static/dashboard.html');
    const accountLabel = account?.role === 'admin' ? 'Admin Dashboard' : (account?.role === 'partner' ? 'HR Insider' : 'Tài khoản');
    const walletLink = account?.role === 'user' ? '<a class="account-menu__item" role="menuitem" href="/static/wallet.html"><i class="fa fa-folder-open me-2"></i>Ví giấy tờ</a>' : '';
    area.innerHTML = account
      ? `${account.role === 'admin' ? '<a class="btn btn-outline-dark btn-sm" href="/static/admin.html">Admin</a>' : ''}<div class="account-menu" id="account-menu"><button class="account-menu__toggle" type="button" id="account-menu-toggle" aria-expanded="false" aria-controls="account-menu-panel"><i class="fa fa-user-circle me-1" aria-hidden="true"></i><span>${Auth.escapeHtml(account.name || account.full_name || account.email || 'Tài khoản')}</span><i class="fa fa-chevron-down ms-1 small" aria-hidden="true"></i></button><div class="account-menu__panel" id="account-menu-panel" role="menu"><span class="account-menu__name">${Auth.escapeHtml(account.email || '')}</span><a class="account-menu__item" role="menuitem" href="${accountUrl}"><i class="fa fa-user me-2"></i>${accountLabel}</a>${walletLink}<button class="account-menu__item account-menu__item--logout" role="menuitem" type="button" id="logout-button"><i class="fa fa-sign-out-alt me-2"></i>Đăng xuất</button></div></div>`
      : `<a class="btn btn-outline-primary btn-sm" href="/static/login.html?next=${encodeURIComponent(location.pathname + location.search)}">Đăng nhập</a><a class="btn btn-primary btn-sm" href="/static/register.html?next=${encodeURIComponent(location.pathname + location.search)}">Đăng ký</a>`;
    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) logoutButton.addEventListener('click', Auth.logout);
    const menu = document.getElementById('account-menu');
    const toggle = document.getElementById('account-menu-toggle');
    if (menu && toggle) {
      toggle.addEventListener('click', () => {
        const isOpen = menu.classList.toggle('open');
        toggle.setAttribute('aria-expanded', String(isOpen));
      });
      document.addEventListener('click', event => {
        if (!menu.contains(event.target)) { menu.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); }
      });
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape') { menu.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); toggle.focus(); }
      });
    }
  },
  refreshNavbar: async () => {
    const token = Auth.getToken();
    if (!token) return Auth.updateNavbar();
    try {
      // Always validate the session after navigation. This also repairs stale
      // localStorage left by an older frontend version.
      const profile = await Auth.fetchMe();
      const savedUser = { ...profile, name: profile.full_name || profile.name || profile.email };
      localStorage.setItem('job_portal_user', JSON.stringify(savedUser));
      // Admin accounts stay inside their administration area. Public pages are
      // intentionally not an Admin entry point.
      const path = location.pathname;
      if (savedUser.role === 'admin' && !path.startsWith('/static/admin')) {
        location.replace('/static/admin.html');
        return;
      }
      Auth.updateNavbar();
      const digitalProfileNav = document.getElementById('digital-profile-nav');
      if (digitalProfileNav) digitalProfileNav.classList.toggle('d-none', savedUser.role !== 'user');
    } catch (_) {
      Auth.logout();
    }
  },
  requireAuth: () => Auth.isLoggedIn(),
  escapeHtml: value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))
}))()

// Use a project-specific global name: browser extensions often inject a
// generic `window.Auth` object and can overwrite it.
window.JobPortalAuth = Auth;

// Hide candidate-only navigation until a valid candidate session is known.
const digitalProfileNav = document.getElementById('digital-profile-nav');
if (digitalProfileNav && !Auth.isLoggedIn()) digitalProfileNav.classList.add('d-none');

// Complete the applicant account form with the structured fields supported by
// the dashboard API. This runs before dashboard.html loads profile data, so
// all values are restored and submitted through the existing form flow.
const mountCandidateProfileFields = () => {
  const accordion = document.getElementById('profile-accordion');
  if (!accordion || document.getElementById('headingIdentity')) return;
  const basic = document.querySelector('#basic .row');
  const career = document.querySelector('#career .row');
  if (!basic || !career) return;
  const field = (column, label, control) => `<div class="${column}"><label class="form-label" for="${control.match(/id=\"([^\"]+)/)?.[1] || ''}">${label}</label>${control}</div>`;
  basic.insertAdjacentHTML('beforeend', [
    field('col-md-6', 'Nơi sinh', '<input id="place_of_birth" name="place_of_birth" class="form-control">'),
    field('col-md-6', 'Tình trạng hôn nhân', '<select id="marital_status" name="marital_status" class="form-select"><option value="">-- Chọn --</option><option>Độc thân</option><option>Đã kết hôn</option><option>Khác</option></select>'),
    field('col-md-4', 'Chiều cao (cm)', '<input id="height_cm" name="height_cm" type="number" min="0" step=".1" class="form-control">'),
    field('col-md-4', 'Cân nặng (kg)', '<input id="weight_kg" name="weight_kg" type="number" min="0" step=".1" class="form-control">'),
    field('col-md-4', 'Giấy phép lái xe (loại)', '<input id="driving_license_type" name="driving_license_type" class="form-control" placeholder="Ví dụ: B2">'),
  ].join(''));
  career.insertAdjacentHTML('beforeend', [
    field('col-md-4', 'Xếp loại', '<select id="education_grade" name="education_grade" class="form-select"><option value="">-- Chọn --</option><option>Xuất sắc</option><option>Giỏi</option><option>Khá</option><option>Trung bình</option><option>Khác</option></select>'),
    field('col-md-6', 'Nơi học ngoại ngữ', '<input id="foreign_language_school" name="foreign_language_school" class="form-control">'),
    field('col-md-6', 'Nơi học tin học', '<input id="computer_school" name="computer_school" class="form-control">'),
  ].join(''));
  const identity = `<div class="accordion-item"><h3 class="accordion-header" id="headingIdentity"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#identity">Giấy tờ tùy thân</button></h3><div id="identity" class="accordion-collapse collapse"><div class="accordion-body"><div class="row g-3">${field('col-md-6', 'Số CMND / CCCD / Hộ chiếu', '<input id="identity_document_number" name="identity_document_number" class="form-control" autocomplete="off">')}${field('col-md-3', 'Ngày cấp', '<input id="identity_issue_date" name="identity_issue_date" type="date" class="form-control">')}${field('col-md-3', 'Nơi cấp', '<input id="identity_issue_place" name="identity_issue_place" class="form-control">')}</div></div></div></div>`;
  const additional = `<div class="accordion-item"><h3 class="accordion-header" id="headingAdditional"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#additional">Thông tin bổ sung</button></h3><div id="additional" class="accordion-collapse collapse"><div class="accordion-body"><div class="row g-3">${field('col-md-4', 'Tôn giáo', '<select id="religion" name="religion" class="form-select"><option value="">-- Chọn --</option><option>Không</option><option>Phật giáo</option><option>Công giáo</option><option>Tin Lành</option><option>Cao Đài</option><option>Hòa Hảo</option><option>Khác</option></select>')}${field('col-md-4', 'Dân tộc', '<input id="ethnicity" name="ethnicity" class="form-control" placeholder="Ví dụ: Kinh">')}${field('col-md-4', 'Trạng thái', '<select id="employment_status" name="employment_status" class="form-select"><option value="">-- Chọn --</option><option value="seeking">Đang tìm việc</option><option value="employed">Đã có việc</option><option value="paused">Tạm ngưng</option></select>')}${field('col-12', 'Ghi chú', '<textarea id="notes" name="notes" class="form-control" rows="3" placeholder="Thông tin thêm bạn muốn cung cấp"></textarea>')}</div></div></div></div>`;
  accordion.insertAdjacentHTML('beforeend', identity + additional);
};
mountCandidateProfileFields();

// Dashboard hồ sơ uses the official province/ward catalogue. Load it only
// on pages that contain those fields so public pages do not make an extra request.
if (document.getElementById('province') && document.getElementById('ward')) {
  const addressScript = document.createElement('script');
  addressScript.src = '/static/js/vn_address_select.js?v=20260903-1';
  document.head.appendChild(addressScript);
}

if (document.getElementById('education') || document.getElementById('education_level')) {
  const educationScript = document.createElement('script');
  educationScript.src = '/static/js/education_levels.js?v=20260903-1';
  document.head.appendChild(educationScript);
}

document.querySelectorAll('a[href^="/static/privacy.html"]').forEach(link => link.remove());
if (document.getElementById('profile-form')) {
  const policyScript = document.createElement('script');
  policyScript.src = '/static/js/cv_policy_consent.js?v=20260903-2';
  document.head.appendChild(policyScript);
}

if (document.getElementById('application-form')) {
  const attachmentScript = document.createElement('script');
  attachmentScript.src = '/static/js/application_attachments.js?v=20260903-1';
  document.head.appendChild(attachmentScript);
}

// The script may be loaded after DOMContentLoaded (for example by a cached
// page or deferred loader), so render immediately when the document is ready.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', Auth.refreshNavbar, { once: true });
} else {
  Auth.refreshNavbar();
}
window.addEventListener('pageshow', Auth.refreshNavbar);
