/* Searchable job-title suggestions shared by admin and partner job forms. */
(() => {
  const positions = [
    'Kinh doanh kênh MT', 'Kinh doanh kênh GT', 'Sales Representative/Phát triển kinh doanh',
    'Account Executive', 'Account Manager (Quản lý khách hàng)', 'Sales Supervisor/Giám sát bán hàng',
    'Sales Manager/Trưởng phòng kinh doanh', 'Sales Director/Giám đốc kinh doanh', 'Telesales',
    'Chăm sóc khách hàng', 'Customer Success', 'Customer Experience (Trải nghiệm khách hàng)',
    'Content Marketing', 'Copywriter', 'Content Creator', 'Digital Marketing', 'SEO', 'Social Media',
    'Performance Marketing', 'Marketing Planner', 'Brand Marketing', 'Product Marketing', 'Marketing Manager',
    'Software Engineer', 'Backend Developer', 'Frontend Developer', 'Fullstack Developer', 'Mobile Developer',
    'AI Engineer', 'Data Engineer', 'Data Scientist', 'Data Analyst', 'QA Engineer', 'Automation Tester',
    'Manual Tester', 'DevOps Engineer', 'Cloud Engineer', 'Network Engineer', 'System Engineer',
    'System Administrator', 'Database Administrator (DBA)', 'IT Helpdesk/IT Support', 'Cyber Security Engineer',
    'Business Analyst (Phân tích nghiệp vụ)', 'Product Owner/Product Manager', 'UI/UX Design',
    'IT Project Manager', 'Scrum Master', 'Software Architect', 'Technical Leader',
    'Tuyển dụng', 'Đối tác nhân sự (HRBP)', 'Đào tạo', 'Nhân sự tổng hợp',
    'Payroll/C&B (Lương/Thưởng/Phúc lợi)', 'Trưởng phòng nhân sự', 'Hành chính nhân sự',
    'Kế toán tổng hợp', 'Kế toán nội bộ', 'Kế toán thuế', 'Kế toán trưởng', 'Kiểm toán viên',
    'Chuyên viên tín dụng', 'Giao dịch viên', 'Chuyên viên xử lý nợ', 'Chuyên viên pháp lý',
    'Kỹ sư xây dựng', 'Kỹ sư cơ điện', 'Kỹ sư điện', 'Kỹ sư cơ khí', 'Kỹ sư tự động hóa',
    'Kỹ sư thiết kế nội thất', 'Kiến trúc sư', 'Quản lý dự án xây dựng', 'Giám sát công trình',
    'Kỹ sư sản xuất', 'Kỹ sư chất lượng (QA/QC)', 'Quản đốc phân xưởng/nhà máy',
    'Công nhân sản xuất', 'Thủ kho/Quản lý kho', 'Nhân viên kho', 'Quản lý Logistics',
    'Điều phối vận tải', 'Nhân viên hiện trường Logistics', 'Chứng từ xuất nhập khẩu',
    'Giáo viên tiếng Anh', 'Giáo viên mầm non', 'Giáo viên tiểu học', 'Giảng viên',
    'Bác sĩ đa khoa', 'Y tá/Điều dưỡng', 'Dược sĩ/Bán thuốc', 'Trình dược viên',
    'Thiết kế đồ họa (Graphic Design)', 'Photographer/Video Editor', 'Biên tập viên',
    'Đầu bếp', 'Phụ bếp', 'Pha chế (Barista)', 'Quản lý nhà hàng', 'Lễ tân/Đón tiếp',
    'Nhân viên bán hàng', 'Thu ngân', 'Quản lý cửa hàng/Cửa hàng trưởng', 'Nhân viên siêu thị',
    'Tài xế xe tải', 'Tài xế B2', 'Shipper (Nhân viên giao hàng)', 'Bảo vệ',
    'Tư vấn bảo hiểm', 'Tư vấn tuyển sinh/khoá học', 'Tư vấn đầu tư', 'Tư vấn du học/định cư'
  ];
  window.JobPositionOptions = positions;
  window.mountJobPositionOptions = (id = 'job-position-options') => {
    if (document.getElementById(id)) return;
    const list = document.createElement('datalist');
    list.id = id;
    list.innerHTML = positions.map(value => `<option value="${value}"></option>`).join('');
    document.body.appendChild(list);
  };

  const enforceDeadlineNotPast = () => {
    const today = new Date().toISOString().slice(0, 10);
    document.querySelectorAll('input[type="date"][id="deadline"], input[type="date"][id="job-deadline"]').forEach(input => {
      input.min = today;
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enforceDeadlineNotPast);
  } else {
    enforceDeadlineNotPast();
  }

  document.addEventListener('submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const deadline = form.querySelector('input[type="date"][id="deadline"], input[type="date"][id="job-deadline"]');
    if (deadline && !deadline.checkValidity()) {
      event.preventDefault();
      event.stopImmediatePropagation();
      deadline.reportValidity();
    }
  }, true);

  const formatVnd = value => Number(value || 0).toLocaleString('vi-VN');
  const digits = value => Number(String(value || '').replace(/\D/g, '')) || 0;
  const parseSavedSalary = value => {
    const text = String(value || '');
    const values = (text.match(/\d{1,3}(?:[.,]\d{3})+|\d+/g) || []).map(item => Number(item.replace(/\D/g, '')));
    if (/triệu|tr\b/i.test(text)) return values.map(item => item * 1000000);
    return values;
  };

  const mountSalaryRange = id => {
    const saved = document.getElementById(id);
    if (!saved || saved.dataset.salaryRangeMounted) return;
    saved.dataset.salaryRangeMounted = 'true';
    saved.type = 'hidden';
    const range = document.createElement('div');
    range.className = 'salary-range';
    range.innerHTML = '<input type="text" inputmode="numeric" class="form-control" placeholder="Từ (VNĐ)" aria-label="Mức lương từ"><span>—</span><input type="text" inputmode="numeric" class="form-control" placeholder="Đến (VNĐ)" aria-label="Mức lương đến"><small class="salary-range__error" aria-live="polite"></small>';
    saved.insertAdjacentElement('afterend', range);
    const [minimum, maximum] = range.querySelectorAll('input');
    const message = range.querySelector('small');
    let previous = saved.value;

    const sync = () => {
      const min = digits(minimum.value), max = digits(maximum.value);
      minimum.value = min ? formatVnd(min) : '';
      maximum.value = max ? formatVnd(max) : '';
      const error = (min && min < 1000000) || (max && max < 1000000)
        ? 'Ngân sách phải từ 1.000.000 trở lên.'
        : (min && max && max < min ? 'Mức lương đến phải lớn hơn hoặc bằng mức lương từ.' : '');
      minimum.setCustomValidity(error);
      maximum.setCustomValidity(error);
      message.textContent = error;
      range.classList.toggle('salary-range--invalid', Boolean(error));
      saved.value = min && max
        ? `${formatVnd(min)} - ${formatVnd(max)} VNĐ`
        : (min ? `Từ ${formatVnd(min)} VNĐ` : (max ? `Đến ${formatVnd(max)} VNĐ` : ''));
      previous = saved.value;
    };
    const loadSaved = value => {
      const values = parseSavedSalary(value);
      minimum.value = values[0] ? formatVnd(values[0]) : '';
      maximum.value = values[1] ? formatVnd(values[1]) : '';
      sync();
    };
    minimum.addEventListener('input', sync);
    maximum.addEventListener('input', sync);
    saved.closest('form')?.addEventListener('reset', () => window.setTimeout(() => loadSaved(''), 0));
    window.setInterval(() => {
      if (saved.value !== previous) loadSaved(saved.value);
    }, 200);
    loadSaved(saved.value);
  };

  const mountSalaryRanges = () => ['salary', 'job-salary'].forEach(mountSalaryRange);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountSalaryRanges);
  else mountSalaryRanges();

  const jobLevels = ['Nhân viên', 'Trưởng nhóm', 'Trưởng / Phó phòng', 'Quản lý / Giám sát', 'Trưởng chi nhánh', 'Phó giám đốc', 'Giám đốc', 'Thực tập sinh'];
  const mountJobLevel = id => {
    const input = document.getElementById(id);
    if (!input || input.tagName === 'SELECT') return;
    const select = document.createElement('select');
    for (const attribute of input.attributes) select.setAttribute(attribute.name, attribute.value);
    select.classList.remove('form-control');
    select.classList.add('form-select');
    const makeOption = (value, text) => {
      const item = document.createElement('option');
      item.value = value;
      item.textContent = text;
      return item;
    };
    select.append(makeOption('', '-- Chọn cấp bậc --'), ...jobLevels.map(level => makeOption(level, level)));
    select.value = jobLevels.includes(input.value) ? input.value : '';
    input.replaceWith(select);
    const label = select.closest('label') || select.previousElementSibling;
    if (label?.tagName === 'LABEL') {
      const text = [...label.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.nodeValue.trim());
      if (text) text.nodeValue = 'Cấp bậc';
      else label.textContent = 'Cấp bậc';
    }
  };
  const mountJobLevels = () => ['experience', 'job-experience'].forEach(mountJobLevel);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountJobLevels);
  else mountJobLevels();

  const jobTypes = [
    { value: 'Toàn thời gian', label: 'Toàn thời gian (Full-time)' },
    { value: 'Bán thời gian', label: 'Bán thời gian (Part-time)' },
    { value: 'Thực tập', label: 'Thực tập (Internship)' },
    { value: 'Cộng tác viên', label: 'Cộng tác viên (Freelancer/Collaborator)' },
    { value: 'Thời vụ', label: 'Thời vụ (Temporary/Seasonal)' },
    { value: 'Hợp đồng', label: 'Hợp đồng (Contract)' },
    { value: 'Làm việc từ xa', label: 'Làm việc từ xa (Remote)' },
    { value: 'Hybrid', label: 'Hybrid' }
  ];
  const mountJobType = id => {
    const field = document.getElementById(id);
    if (!field || field.dataset.jobTypeMounted) return;
    field.dataset.jobTypeMounted = 'true';
    const previousValue = field.value;
    let select = field;
    if (field.tagName !== 'SELECT') {
      select = document.createElement('select');
      for (const attribute of field.attributes) select.setAttribute(attribute.name, attribute.value);
      select.classList.remove('form-control');
      select.classList.add('form-select');
      field.replaceWith(select);
    }
    const makeOption = (value, text) => {
      const item = document.createElement('option');
      item.value = value;
      item.textContent = text;
      return item;
    };
    select.replaceChildren(makeOption('', '-- Chọn loại hình làm việc --'), ...jobTypes.map(type => makeOption(type.value, type.label)));
    if (previousValue && !jobTypes.some(type => type.value === previousValue)) select.append(makeOption(previousValue, previousValue));
    select.value = previousValue;
  };
  const mountJobTypes = () => ['job_type', 'job-type'].forEach(mountJobType);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountJobTypes);
  else mountJobTypes();

  const normalizeLocation = value => String(value || '')
    .toLocaleLowerCase('vi-VN').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/^(tinh|thanh pho)\s+/, '').trim();
  const makeSelectOption = (value, text) => {
    const item = document.createElement('option');
    item.value = value;
    item.textContent = text;
    return item;
  };
  const findProvince = (provinces, value) => provinces.find(item =>
    item.name === value || normalizeLocation(value).includes(normalizeLocation(item.name))
  );

  const mountJobLocation = async id => {
    const saved = document.getElementById(id);
    if (!saved || saved.dataset.locationSelectMounted) return;
    saved.dataset.locationSelectMounted = 'true';
    try {
      const response = await fetch('/static/data/vn_admin_units.json?v=20260903-1');
      if (!response.ok) throw new Error('Không tải được danh mục địa giới.');
      const { provinces = [] } = await response.json();
      saved.type = 'hidden';
      const control = document.createElement('div');
      control.className = 'job-location-select';
      const province = document.createElement('select');
      const ward = document.createElement('select');
      province.className = ward.className = 'form-select';
      province.setAttribute('aria-label', 'Tỉnh hoặc Thành phố');
      ward.setAttribute('aria-label', 'Phường hoặc Xã');
      province.append(makeSelectOption('', '-- Chọn Tỉnh/Thành phố --'), ...provinces.map(item => makeSelectOption(item.name, item.name)));
      ward.append(makeSelectOption('', '-- Chọn Tỉnh/Thành phố trước --'));
      ward.disabled = true;
      control.append(province, ward);
      saved.insertAdjacentElement('afterend', control);
      let previous = saved.value;

      const populateWards = (provinceName, preferredWard = '') => {
        const selected = findProvince(provinces, provinceName);
        ward.replaceChildren(makeSelectOption('', selected ? '-- Chọn Phường/Xã --' : '-- Chọn Tỉnh/Thành phố trước --'));
        ward.disabled = !selected;
        if (!selected) return;
        ward.append(...selected.wards.map(item => makeSelectOption(item.name, item.name)));
        const foundWard = selected.wards.find(item => item.name === preferredWard || normalizeLocation(preferredWard).includes(normalizeLocation(item.name)));
        ward.value = foundWard?.name || '';
      };
      const sync = () => {
        saved.value = [province.value, ward.value].filter(Boolean).join(', ');
        previous = saved.value;
      };
      const loadSaved = value => {
        const selected = findProvince(provinces, value);
        if (!selected) {
          province.value = '';
          populateWards('');
          previous = value;
          return;
        }
        province.value = selected?.name || '';
        populateWards(province.value, value);
        sync();
      };
      province.addEventListener('change', () => { populateWards(province.value); sync(); });
      ward.addEventListener('change', sync);
      saved.closest('form')?.addEventListener('reset', () => window.setTimeout(() => loadSaved(''), 0));
      window.setInterval(() => {
        if (saved.value !== previous) loadSaved(saved.value);
      }, 200);
      loadSaved(saved.value);
    } catch (error) {
      saved.type = 'text';
      delete saved.dataset.locationSelectMounted;
      console.warn('Job location selector:', error.message);
    }
  };
  const mountJobLocations = () => ['location', 'job-location'].forEach(mountJobLocation);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountJobLocations);
  else mountJobLocations();

  const style = document.createElement('style');
  style.textContent = '.salary-range{display:grid;grid-template-columns:1fr auto 1fr;gap:.5rem;align-items:center}.salary-range>span{font-size:1.5rem;color:#566}.salary-range__error{grid-column:1/-1;color:#dc3545;font-size:.875rem;min-height:1.2em}.salary-range--invalid .form-control{border-color:#dc3545}.salary-range--invalid .form-control:focus{box-shadow:0 0 0 .2rem rgba(220,53,69,.12)}.job-location-select{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}.job-location-select .form-select{min-width:0}@media(max-width:576px){.job-location-select{grid-template-columns:1fr}}';
  document.head.appendChild(style);

  if (document.getElementById('jobs') && document.getElementById('title') && !document.getElementById('partner-candidate-match-script')) {
    const script = document.createElement('script');
    script.id = 'partner-candidate-match-script';
    script.src = '/static/js/partner_candidate_match.js?v=20260903-9';
    document.head.appendChild(script);
  }
  if (document.getElementById('job-form') && !document.getElementById('job-form-enhancements-script')) {
    const script = document.createElement('script');
    script.id = 'job-form-enhancements-script';
    script.src = '/static/js/job_form_enhancements.js?v=20260903-1';
    document.head.appendChild(script);
  }
})();
