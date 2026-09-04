/* Consent is collected at the point where the digital profile is submitted. */
(() => {
  const mount = () => {
    const form = document.getElementById('profile-form');
    const actions = form?.querySelector('.sticky-actions');
    if (!actions || document.getElementById('profile-policy-accepted')) return;
    const consent = document.createElement('div');
    consent.className = 'form-check border rounded p-3 mb-3 bg-white';
    consent.innerHTML = '<input id="profile-policy-accepted" name="policy_accepted" class="form-check-input" type="checkbox" required><label class="form-check-label" for="profile-policy-accepted">Tôi đồng ý để Job4U tạo, lưu hồ sơ việc làm số và đề xuất việc làm phù hợp theo <a href="/static/personal_data_policy.html" target="_blank" rel="noopener">Chính sách dữ liệu cá nhân</a>.</label>';
    actions.before(consent);
    const notice = document.getElementById('notice');
    if (notice) notice.innerHTML = '<strong>Hoàn thiện hồ sơ để nhận gợi ý việc làm phù hợp.</strong> Vui lòng đồng ý chính sách ở cuối form trước khi lưu.';
    form.addEventListener('submit', event => {
      if (!form.checkValidity()) { event.preventDefault(); event.stopImmediatePropagation(); form.reportValidity(); }
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once:true}); else mount();
})();
