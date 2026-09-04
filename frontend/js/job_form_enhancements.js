/* Visual helpers for the partner job-posting form. */
(() => {
  const form = document.getElementById('job-form');
  if (!form || form.dataset.enhanced === 'true') return;
  form.dataset.enhanced = 'true';

  const modal = form.closest('#jobModal');
  if (modal) {
    modal.querySelector('.modal-dialog')?.classList.add('modal-dialog-scrollable');
    form.classList.add('job-editor');
    const header = form.querySelector('.modal-header');
    if (header && !header.querySelector('.job-modal-subtitle')) {
      const subtitle = document.createElement('p');
      subtitle.className = 'job-modal-subtitle small text-muted mb-0';
      subtitle.textContent = 'Tạo một tin rõ ràng để thu hút ứng viên phù hợp.';
      header.querySelector('.modal-title')?.insertAdjacentElement('afterend', subtitle);
    }
  }

  const row = form.querySelector('.modal-body > .row');
  if (!row) return;
  const intro = document.createElement('div');
  intro.className = 'job-form-intro';
  intro.innerHTML = '<i class="fa fa-lightbulb"></i><p>Hãy nêu rõ trách nhiệm, yêu cầu và quyền lợi. Nội dung cụ thể giúp ứng viên quyết định nhanh hơn.</p>';
  row.insertAdjacentElement('beforebegin', intro);

  const sections = [
    ['title', 'Thông tin vị trí'],
    ['description', 'Nội dung tuyển dụng'],
  ];
  sections.forEach(([fieldId, title]) => {
    const field = document.getElementById(fieldId), column = field?.closest('.col-12, .col-md-6');
    if (!column) return;
    const heading = document.createElement('div');
    heading.className = 'job-form-section'; heading.style.flexBasis = '100%'; heading.textContent = title;
    column.insertAdjacentElement('beforebegin', heading);
  });

  const labels = {
    title: 'Vị trí tuyển dụng *', job_type: 'Hình thức làm việc', location: 'Địa điểm',
    salary: 'Mức lương', experience: 'Kinh nghiệm', deadline: 'Hạn nộp hồ sơ',
    description: 'Mô tả công việc', requirements: 'Yêu cầu công việc', benefits: 'Quyền lợi',
    is_active: 'Hiển thị tin tuyển dụng',
  };
  const placeholders = {
    title: 'Ví dụ: Chuyên viên tư vấn', job_type: 'Ví dụ: Toàn thời gian',
    location: 'Ví dụ: Quận 1, TP. Hồ Chí Minh', salary: 'Ví dụ: 12 - 18 triệu',
    experience: 'Ví dụ: Từ 1 năm',
    description: 'Mỗi ý nên xuống dòng riêng:\n• Công việc chính\n• Mục tiêu cần đạt\n• Cách phối hợp với đội ngũ',
    requirements: 'Nêu kỹ năng, kinh nghiệm, bằng cấp hoặc tố chất cần có…',
    benefits: 'Ví dụ: Thưởng, bảo hiểm, đào tạo, lộ trình phát triển…',
  };
  Object.entries(labels).forEach(([id, labelText]) => {
    const field = document.getElementById(id), label = field?.previousElementSibling, column = field?.closest('.col-12, .col-md-6');
    if (!field || !label || !column) return;
    label.htmlFor = id; label.textContent = labelText;
    column.classList.add('field-card');
    if (placeholders[id]) field.placeholder = placeholders[id];
  });

  ['description', 'requirements', 'benefits'].forEach(id => {
    const field = document.getElementById(id), column = field?.closest('.field-card');
    if (!field || !column) return;
    const maximum = id === 'benefits' ? 4000 : 5000;
    field.maxLength = maximum;
    field.rows = id === 'benefits' ? 4 : 5;
    const footer = document.createElement('div');
    footer.className = 'textarea-footer';
    footer.innerHTML = `<span>${id === 'description' ? 'Gợi ý: dùng gạch đầu dòng để dễ đọc.' : id === 'requirements' ? 'Chỉ liệt kê các yêu cầu thực sự cần thiết.' : 'Điểm khác biệt giúp tin tuyển dụng nổi bật.'}</span><span>0 / ${maximum}</span>`;
    const counter = footer.lastElementChild;
    const update = () => { counter.textContent = `${field.value.length} / ${maximum}`; };
    field.addEventListener('input', update); update();
    field.insertAdjacentElement('afterend', footer);
  });
})();
