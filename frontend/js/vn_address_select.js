/* Cascading province and ward selects populated from the supplied catalogue. */
(() => {
  const normalize = value => String(value || '')
    .toLocaleLowerCase('vi-VN')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/^(tinh|thanh pho)\s+/, '').trim();

  const selectFromInput = (input, placeholder) => {
    const select = document.createElement('select');
    for (const attribute of input.attributes) select.setAttribute(attribute.name, attribute.value);
    select.classList.remove('form-control');
    select.classList.add('form-select');
    select.removeAttribute('list');
    select.innerHTML = `<option value="">${placeholder}</option>`;
    input.replaceWith(select);
    return { select, value: input.value };
  };

  const option = (value, label) => {
    const item = document.createElement('option');
    item.value = value;
    item.textContent = label;
    return item;
  };

  const findProvince = (provinces, value) => provinces.find(item =>
    item.name === value || normalize(item.name) === normalize(value)
  );

  const init = async () => {
    const provinceInput = document.getElementById('province');
    const wardInput = document.getElementById('ward');
    if (!provinceInput || !wardInput) return;

    try {
      const response = await fetch('/static/data/vn_admin_units.json?v=20260903-1');
      if (!response.ok) throw new Error('Không tải được danh mục địa giới.');
      const { provinces = [] } = await response.json();
      const provinceField = selectFromInput(provinceInput, '-- Chọn Tỉnh/Thành phố --');
      const wardField = selectFromInput(wardInput, '-- Chọn Tỉnh/Thành phố trước --');
      const province = provinceField.select;
      const ward = wardField.select;
      province.append(...provinces.map(item => option(item.name, item.name)));

      let lastProvince = '';
      const fillWards = (selectedName, desiredWard = '') => {
        const selected = findProvince(provinces, selectedName);
        ward.replaceChildren(option('', selected ? '-- Chọn Phường/Xã --' : '-- Chọn Tỉnh/Thành phố trước --'));
        ward.disabled = !selected;
        if (!selected) return;
        ward.append(...selected.wards.map(item => option(item.name, item.name)));
        const matchingWard = selected.wards.find(item => item.name === desiredWard || normalize(item.name) === normalize(desiredWard));
        ward.value = matchingWard?.name || '';
      };

      const savedProvince = findProvince(provinces, provinceField.value);
      province.value = savedProvince?.name || '';
      fillWards(province.value, wardField.value);
      lastProvince = province.value;
      province.addEventListener('change', () => {
        lastProvince = province.value;
        fillWards(province.value);
      });

      // The dashboard fills saved profile values asynchronously. Keep the
      // second select aligned when that value arrives after this script.
      window.setInterval(() => {
        if (province.value !== lastProvince) {
          lastProvince = province.value;
          fillWards(province.value, ward.value);
        }
      }, 250);
    } catch (error) {
      console.warn('Vietnam address selector:', error.message);
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
