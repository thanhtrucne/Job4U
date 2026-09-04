/* One education-level catalogue shared by account and digital CV forms. */
(() => {
  const levels = [
    'Trung học cơ sở (THCS)', 'Trung học phổ thông (THPT)', 'Trung cấp',
    'Cao đẳng', 'Đại học', 'Kỹ sư', 'Cử nhân', 'Thạc sĩ', 'Tiến sĩ'
  ];
  const mount = id => {
    const field = document.getElementById(id);
    if (!field || field.dataset.educationLevelsMounted) return;
    field.dataset.educationLevelsMounted = 'true';
    const current = field.value;
    let select = field;
    if (field.tagName !== 'SELECT') {
      select = document.createElement('select');
      for (const attribute of field.attributes) select.setAttribute(attribute.name, attribute.value);
      select.classList.remove('form-control'); select.classList.add('form-select');
      field.replaceWith(select);
    }
    select.replaceChildren(new Option('-- Chọn trình độ học vấn --', ''), ...levels.map(level => new Option(level, level)));
    if (current && !levels.includes(current)) select.append(new Option(current, current));
    select.value = current;
  };
  const start = () => ['education', 'education_level'].forEach(mount);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true}); else start();
})();
