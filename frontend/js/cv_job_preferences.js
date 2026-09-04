/* Job criteria use the same controlled values as the recruiter job form. */
(() => {
  const levelOptions = ['Nhân viên', 'Trưởng nhóm', 'Trưởng / Phó phòng', 'Quản lý / Giám sát', 'Trưởng chi nhánh', 'Phó giám đốc', 'Giám đốc', 'Thực tập sinh'];
  const typeOptions = [
    ['Toàn thời gian', 'Toàn thời gian (Full-time)'], ['Bán thời gian', 'Bán thời gian (Part-time)'],
    ['Thực tập', 'Thực tập (Internship)'], ['Cộng tác viên', 'Cộng tác viên (Freelancer/Collaborator)'],
    ['Thời vụ', 'Thời vụ (Temporary/Seasonal)'], ['Hợp đồng', 'Hợp đồng (Contract)'],
    ['Làm việc từ xa', 'Làm việc từ xa (Remote)'], ['Hybrid', 'Hybrid']
  ];
  const addField = (id, label, values) => {
    const location = document.getElementById('desired_location');
    if (!location || document.getElementById(id)) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'col-md-4';
    const text = document.createElement('label');
    text.className = 'form-label'; text.htmlFor = id; text.textContent = label;
    const select = document.createElement('select');
    select.id = id; select.name = id; select.className = 'form-select';
    select.append(new Option('-- Chọn --', ''));
    values.forEach(value => select.append(new Option(Array.isArray(value) ? value[1] : value, Array.isArray(value) ? value[0] : value)));
    wrapper.append(text, select);
    location.closest('.col-md-4').before(wrapper);
  };
  const mount = () => {
    addField('desired_job_level', 'Cấp bậc mong muốn', levelOptions);
    addField('desired_job_type', 'Loại hình làm việc', typeOptions);
    ['desired_salary_min', 'desired_salary_max'].forEach(id => {
      const input = document.getElementById(id);
      if (!input || input.dataset.vndMounted) return;
      input.dataset.vndMounted = 'true'; input.type = 'text'; input.inputMode = 'numeric'; input.placeholder = 'Ví dụ: 10.000.000';
      const label = document.querySelector(`label[for="${id}"]`);
      if (label) label.textContent = id.endsWith('_min') ? 'Mức lương từ (VNĐ)' : 'Mức lương đến (VNĐ)';
      input.addEventListener('input', () => {
        const value = input.value.replace(/\D/g, '');
        input.value = value ? Number(value).toLocaleString('vi-VN') : '';
        input.setCustomValidity(value && Number(value) < 1000000 ? 'Mức lương phải từ 1.000.000 VNĐ trở lên.' : '');
      });
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true }); else mount();
})();
