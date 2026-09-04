/* Lets an applicant attach verified Wallet documents to one application. */
(() => {
  const labels = { health_certificate: 'Giấy khám sức khỏe', qualification: 'Bằng cấp/chứng chỉ', personal_profile: 'Lý lịch cá nhân' };
  const mount = async () => {
    const form = document.getElementById('application-form'), fileField = document.getElementById('application-file');
    const token = window.JobPortalAuth?.getToken();
    if (!form || !fileField || !token || document.getElementById('wallet-attachments')) return;
    try {
      const response = await fetch('/api/documents', {headers:{Authorization:`Bearer ${token}`}}), documents = await response.json();
      if (!response.ok) return;
      const types = [...new Set(documents.filter(item => item.status === 'verified' && labels[item.doc_type]).map(item => item.doc_type))];
      if (!types.length) return;
      const section = document.createElement('div'); section.id = 'wallet-attachments'; section.className = 'border rounded p-3 mb-3 bg-white';
      section.innerHTML = `<div class="fw-semibold mb-1"><i class="fa fa-paperclip text-primary me-1"></i>Giấy tờ đính kèm từ Ví giấy tờ</div><p class="small text-muted mb-2">Chọn từng giấy tờ đã xác minh mà bạn đồng ý chia sẻ riêng với nhà tuyển dụng này. Nhà tuyển dụng chỉ xem được các mục bạn chọn.</p>${types.map(type => `<div class="form-check"><input id="attach-${type}" class="form-check-input" type="checkbox" name="additional_doc_types" value="${type}"><label class="form-check-label" for="attach-${type}">${labels[type]}</label></div>`).join('')}<a class="small d-inline-block mt-2" href="/static/wallet.html"><i class="fa fa-folder-open me-1"></i>Quản lý giấy tờ trong Ví giấy tờ</a>`;
      fileField.closest('.mb-3')?.insertAdjacentElement('afterend', section);
    } catch (_) { /* The main application form remains usable. */ }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once:true}); else mount();
})();
