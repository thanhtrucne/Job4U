(function () {
  const current = location.pathname.replace(/\/$/, '') || '/';
  const active = path => current === path || (path !== '/' && current.startsWith(path));
  const navbar = document.getElementById('site-navbar');
  if (!navbar) return;
  navbar.innerHTML = `
    <nav class="navbar navbar-expand-lg bg-white navbar-light shadow sticky-top p-0">
      <a href="/static/index.html" class="navbar-brand d-flex align-items-center text-center py-0 px-4 px-lg-5"><h1 class="m-0 text-primary">Job4U</h1></a>
      <button type="button" class="navbar-toggler me-4" data-bs-toggle="collapse" data-bs-target="#siteNavbarCollapse" aria-label="Mở menu"><span class="navbar-toggler-icon"></span></button>
      <div class="collapse navbar-collapse" id="siteNavbarCollapse">
        <div class="navbar-nav ms-auto p-4 p-lg-0">
          <a href="/" class="nav-item nav-link ${active('/') || active('/static/index.html') ? 'active' : ''}">Trang chủ</a>
          <a href="/static/jobs.html" class="nav-item nav-link ${active('/static/jobs.html') ? 'active' : ''}">Việc làm</a>
          <a id="digital-profile-nav" href="/static/cv_match.html" class="nav-item nav-link d-none ${active('/static/cv_match.html') ? 'active' : ''}">Hồ sơ việc làm số</a>
          <a href="/static/career_handbook.html" class="nav-item nav-link ${active('/static/career_handbook.html') || active('/static/career_guide_detail.html') ? 'active' : ''}">Cẩm nang nghề nghiệp</a>
          <a href="/static/register_company.html" class="nav-item nav-link ${active('/static/register_company.html') ? 'active' : ''}">Dành cho doanh nghiệp</a>
        </div>
        <div id="nav-auth-area" class="d-flex gap-2 me-3 mb-3 mb-lg-0">
          <a class="btn btn-outline-primary btn-sm" href="/static/login.html">Đăng nhập</a>
          <a class="btn btn-primary btn-sm" href="/static/register.html">Đăng ký</a>
        </div>
      </div>
    </nav>`;
}());
