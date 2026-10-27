(() => {
  const moneyFormat = (value) => {
    const amount = Number.isFinite(value) ? value : 0;
    return `${window.LEDGERLY_CURRENCY || 'PKR'} ${amount.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: amount % 1 === 0 ? 0 : 2 })}`;
  };

  const form = document.querySelector('[data-invoice-form]');
  if (form) {
    const lineItems = form.querySelector('[data-line-items]');
    const lineTemplate = form.querySelector('[data-line-template]');
    const addButton = form.querySelector('[data-add-item]');
    const clientSelect = form.querySelector('[name="client_id"]');
    const dueInput = form.querySelector('[name="due_date"]');
    const issueInput = form.querySelector('[name="issue_date"]');
    const taxInput = form.querySelector('[data-tax-rate]');
    const discountInput = form.querySelector('[data-discount]');
    const currency = document.documentElement.dataset.currency || 'PKR';

    const parseValue = (input) => {
      const value = Number.parseFloat(input?.value ?? '0');
      return Number.isFinite(value) && value >= 0 ? value : 0;
    };

    const updateSummary = () => {
      let subtotal = 0;
      lineItems.querySelectorAll('.line-item-row').forEach((row) => {
        const quantity = parseValue(row.querySelector('[name="item_quantity[]"]'));
        const price = parseValue(row.querySelector('[name="item_price[]"]'));
        const lineTotal = quantity * price;
        subtotal += lineTotal;
        const total = row.querySelector('.line-total');
        if (total) total.textContent = moneyFormat(lineTotal).replace(window.LEDGERLY_CURRENCY || 'PKR', currency);
      });
      const taxRate = Math.min(parseValue(taxInput), 100);
      const tax = Math.round(subtotal * taxRate) / 100;
      const discount = parseValue(discountInput);
      const total = Math.max(0, subtotal + tax - discount);
      const display = (selector, value, prefix = '') => {
        const node = form.querySelector(selector);
        if (node) node.textContent = `${prefix}${moneyFormat(value).replace(window.LEDGERLY_CURRENCY || 'PKR', currency)}`;
      };
      display('[data-subtotal]', subtotal);
      display('[data-tax]', tax);
      display('[data-discount-total]', discount, '− ');
      display('[data-grand-total]', total);
      const selected = clientSelect?.selectedOptions?.[0];
      const clientPreview = form.querySelector('[data-client-preview]');
      if (clientPreview && selected) clientPreview.textContent = selected.textContent.split(' · ')[0];
      const duePreview = form.querySelector('[data-due-preview]');
      if (duePreview && dueInput) duePreview.textContent = dueInput.value || '—';
      if (issueInput && dueInput) dueInput.min = issueInput.value;
    };

    addButton?.addEventListener('click', () => {
      if (lineItems.querySelectorAll('.line-item-row').length >= 40) {
        alert('You can add up to 40 line items per invoice.');
        return;
      }
      const clone = lineTemplate.content.cloneNode(true);
      lineItems.appendChild(clone);
      updateSummary();
      lineItems.querySelector('.line-item-row:last-child input[name="item_description[]"]')?.focus();
    });

    lineItems?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-remove-item]');
      if (!button) return;
      const rows = lineItems.querySelectorAll('.line-item-row');
      if (rows.length === 1) {
        const row = button.closest('.line-item-row');
        row.querySelectorAll('input').forEach((input) => { input.value = input.name === 'item_quantity[]' ? '1' : ''; });
      } else {
        button.closest('.line-item-row')?.remove();
      }
      updateSummary();
    });

    form.addEventListener('input', (event) => {
      if (event.target.matches('[name="item_quantity[]"], [name="item_price[]"], [data-tax-rate], [data-discount], [name="issue_date"], [name="due_date"]')) updateSummary();
    });
    form.addEventListener('change', (event) => {
      if (event.target.matches('[name="client_id"], [name="issue_date"], [name="due_date"]')) updateSummary();
    });
    form.addEventListener('submit', (event) => {
      const rows = lineItems.querySelectorAll('.line-item-row');
      if (!rows.length || [...rows].some((row) => !row.querySelector('[name="item_description[]"]').value.trim())) {
        event.preventDefault();
        alert('Add a description for every line item before saving.');
      }
    });
    updateSummary();
  }

  document.querySelectorAll('form[data-confirm]').forEach((confirmForm) => {
    confirmForm.addEventListener('submit', (event) => {
      if (!window.confirm(confirmForm.dataset.confirm || 'Are you sure?')) event.preventDefault();
    });
  });
})();
