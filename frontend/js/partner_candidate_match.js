/* Recruiter-side shortlist based on the criteria entered in digital CVs. */
(() => {
  const token = () => localStorage.getItem('job_portal_token');
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const documentLabel = type => ({
    job_application: 'Hồ sơ ứng tuyển', health_certificate: 'Giấy khám sức khỏe',
    qualification: 'Bằng cấp / chứng chỉ', personal_profile: 'Lý lịch cá nhân',
  }[type] || type);
  const responseData = async (response, fallback) => {
    const body = await response.text();
    try { return JSON.parse(body); }
    catch (_) { throw new Error(response.ok ? fallback : `${fallback} (máy chủ trả lỗi ${response.status}).`); }
  };
  const errorDetail = (detail, fallback) => {
    if (Array.isArray(detail)) return detail.map(item => item.msg || item.message || 'Dữ liệu không hợp lệ.').join(' ');
    if (typeof detail === 'string') return detail;
    return fallback;
  };
  const ensureApplicationPanel = () => {
    let panel = document.getElementById('application-profile');
    if (panel) return panel;
    panel = document.createElement('div'); panel.id = 'application-profile'; panel.className = 'modal fade'; panel.tabIndex = -1;
    panel.setAttribute('aria-labelledby', 'application-profile-title'); panel.setAttribute('aria-hidden', 'true');
    panel.innerHTML = '<div class="modal-dialog modal-dialog-centered modal-xl modal-dialog-scrollable"><section class="modal-content border-0"><div class="modal-header"><h2 id="application-profile-title" class="h5 modal-title mb-0">Hồ sơ ứng tuyển</h2><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Đóng"></button></div><div id="application-profile-content" class="modal-body p-3 p-md-4"></div></section></div>';
    document.body.append(panel); return panel;
  };
  const downloadDocument = async (applicationId, documentId) => {
    const response = await fetch(`/api/applications/partner/${applicationId}/documents/${documentId}/download`, {headers:{Authorization:`Bearer ${token()}`}}), data = await responseData(response, 'Không thể tải tài liệu.');
    if (!response.ok) throw new Error(data.detail || 'Không thể tải tài liệu.'); window.open(data.url, '_blank', 'noopener');
  };
  const showApplication = async applicationId => {
    const panel = ensureApplicationPanel(), content = panel.querySelector('#application-profile-content');
    // Bootstrap 5.0 does not provide getOrCreateInstance (it was added in a
    // later release), so create the modal only when there is no live instance.
    const modal = (bootstrap.Modal.getInstance && bootstrap.Modal.getInstance(panel)) || new bootstrap.Modal(panel);
    modal.show(); content.textContent = 'Đang tải hồ sơ…';
    try {
      const response = await fetch(`/api/applications/partner/${applicationId}`, {headers:{Authorization:`Bearer ${token()}`}}), data = await responseData(response, 'Không thể xem hồ sơ.');
      if (!response.ok) throw new Error(data.detail || 'Không thể xem hồ sơ.');
      const applicant = data.applicant || {}, profile = data.profile || {};
      const salary = profile.desired_salary_min == null ? 'Chưa cập nhật' : `${Number(profile.desired_salary_min).toLocaleString('vi-VN')} - ${profile.desired_salary_max == null ? '…' : Number(profile.desired_salary_max).toLocaleString('vi-VN')} triệu VNĐ`;
      content.innerHTML = `<div class="row g-3"><div class="col-md-6"><strong>${escape(applicant.full_name || 'Ứng viên')}</strong><div class="small text-muted">${escape(applicant.email || '')} · ${escape(applicant.phone_number || '')}</div></div><div class="col-md-6"><strong>${escape(profile.headline || 'Chưa cập nhật vị trí mong muốn')}</strong><div class="small text-muted">${escape(profile.industry || '')}</div></div><div class="col-md-3"><span class="text-muted small d-block">Học vấn</span>${escape(profile.education || 'Chưa cập nhật')}</div><div class="col-md-3"><span class="text-muted small d-block">Kinh nghiệm</span>${escape(profile.years_experience ?? 0)} năm</div><div class="col-md-3"><span class="text-muted small d-block">Địa điểm mong muốn</span>${escape(profile.desired_location || 'Chưa cập nhật')}</div><div class="col-md-3"><span class="text-muted small d-block">Lương mong muốn</span>${escape(salary)}</div><div class="col-md-6"><span class="text-muted small d-block">Cấp bậc</span>${escape(profile.desired_job_level || 'Chưa cập nhật')}</div><div class="col-md-6"><span class="text-muted small d-block">Loại hình</span>${escape(profile.desired_job_type || 'Chưa cập nhật')}</div><div class="col-12"><hr><strong>Tài liệu đã chia sẻ</strong><div id="shared-documents" class="mt-2"></div></div><div class="col-12"><hr><form id="application-feedback-form"><label class="form-label fw-bold" for="application-feedback-message">Phản hồi cho ứng viên</label><textarea id="application-feedback-message" class="form-control" rows="4" minlength="2" maxlength="2000" required placeholder="Nhập phản hồi của bạn…"></textarea><div class="form-text">Ít nhất 2 ký tự. Ứng viên sẽ nhận được thông báo trong tài khoản và email nếu SMTP đã cấu hình.</div><div class="d-flex align-items-center gap-2 mt-3"><button class="btn btn-success" type="submit"><i class="fa fa-paper-plane me-1"></i>Gửi phản hồi</button><span id="application-feedback-status" class="small"></span></div></form></div></div>`;
      const documents = content.querySelector('#shared-documents'); documents.innerHTML = data.documents.length ? data.documents.map(document => `<button type="button" class="btn btn-outline-success btn-sm me-2 mb-2" data-document-id="${document.id}"><i class="fa fa-download me-1"></i>${escape(documentLabel(document.doc_type))}</button>`).join('') : '<span class="text-muted small">Ứng viên chưa chọn giấy tờ bổ sung để chia sẻ.</span>';
      documents.querySelectorAll('[data-document-id]').forEach(button => button.onclick = async () => { try { await downloadDocument(applicationId, button.dataset.documentId); } catch (error) { alert(error.message); } });
      content.querySelector('#application-feedback-form').onsubmit = async event => {
        event.preventDefault(); const feedbackForm = event.currentTarget, message = content.querySelector('#application-feedback-message').value.trim(), status = content.querySelector('#application-feedback-status'), button = feedbackForm.querySelector('button[type="submit"]');
        button.disabled = true; status.className = 'small text-muted'; status.textContent = 'Đang gửi…';
        try {
          const response = await fetch(`/api/applications/partner/${applicationId}/feedback`, {method:'POST', headers:{Authorization:`Bearer ${token()}`, 'Content-Type':'application/json'}, body:JSON.stringify({message})}), result = await responseData(response, 'Không thể gửi phản hồi.');
          if (!response.ok) throw new Error(errorDetail(result.detail, 'Không thể gửi phản hồi.'));
          feedbackForm.reset(); status.className = 'small text-success'; status.textContent = result.message;
        } catch (error) { status.className = 'small text-danger'; status.textContent = error.message; } finally { button.disabled = false; }
      };
    } catch (error) { content.innerHTML = `<p class="text-danger mb-0">${escape(error.message)}</p>`; }
  };
  const attachApplicationButtons = async (attempt = 0) => {
    const container = document.getElementById('applications-list') || document.getElementById('applications'); if (!container) return;
    const response = await fetch('/api/applications/partner/me', {headers:{Authorization:`Bearer ${token()}`}}); if (!response.ok) return;
    const applications = await responseData(response, 'Không thể tải hồ sơ ứng tuyển.'), cards = [...container.children];
    if ((!cards.length || cards.length !== applications.length) && attempt < 10) return setTimeout(() => attachApplicationButtons(attempt + 1), 300);
    cards.forEach((card, index) => {
      const application = applications[index], actions = card.querySelector('.application-actions') || card.querySelector('.d-flex.gap-2.align-items-center');
      if (!application || !actions || actions.querySelector('.view-application')) return;
      const button = document.createElement('button'); button.type = 'button'; button.className = 'btn btn-outline-primary btn-sm view-application'; button.textContent = 'Xem hồ sơ'; button.onclick = () => showApplication(application.id); actions.prepend(button);
    });
  };
  const start = () => { setTimeout(attachApplicationButtons, 300); };
  // HR Insider renders its application cards asynchronously. Re-attach the
  // view buttons immediately after every completed render, rather than relying
  // on a timing-sensitive initial attempt.
  document.addEventListener('hr-applications-rendered', () => attachApplicationButtons());
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true}); else start();
})();
