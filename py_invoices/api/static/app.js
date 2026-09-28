const API_BASE = '/';
const KEY_STORAGE = 'py-invoices-api-key';

function apiKey() {
    let key = sessionStorage.getItem(KEY_STORAGE);
    if (!key) {
        key = window.prompt('API key (INVOICES_API_KEY)') || '';
        sessionStorage.setItem(KEY_STORAGE, key);
    }
    return key;
}

function messageRow(tbody, text, isError) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 5;
    td.textContent = text;
    if (isError) td.style.color = 'red';
    tr.appendChild(td);
    tbody.replaceChildren(tr);
}

async function fetchInvoices() {
    const tbody = document.getElementById('invoices-table-body');
    messageRow(tbody, 'Loading...', false);

    try {
        const response = await fetch(`${API_BASE}invoices/`, {
            headers: { 'X-API-Key': apiKey() },
        });
        if (response.status === 401) {
            sessionStorage.removeItem(KEY_STORAGE);
        }
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        renderInvoices(await response.json());
    } catch (error) {
        console.error('Error fetching invoices:', error);
        messageRow(tbody, `Error loading invoices: ${error.message}`, true);
    }
}

function renderInvoices(invoices) {
    const tbody = document.getElementById('invoices-table-body');
    if (invoices.length === 0) {
        messageRow(tbody, 'No invoices found.', false);
        return;
    }

    tbody.replaceChildren(...invoices.map(invoice => {
        const tr = document.createElement('tr');
        const cells = [
            invoice.number,
            new Date(invoice.issue_date).toLocaleDateString(),
            invoice.client_name_snapshot ?? '',
            // Money is serialized as a decimal string without its currency
            Number(invoice.total_amount).toFixed(2),
            invoice.status,
        ];
        for (const value of cells) {
            const td = document.createElement('td');
            td.textContent = value;
            tr.appendChild(td);
        }
        return tr;
    }));
}

document.addEventListener('DOMContentLoaded', fetchInvoices);
