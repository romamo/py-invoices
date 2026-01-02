const API_BASE = '/';

async function fetchInvoices() {
    const tbody = document.getElementById('invoices-table-body');
    tbody.innerHTML = '<tr><td colspan="5">Loading...</td></tr>';

    try {
        const response = await fetch(`${API_BASE}invoices/`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const invoices = await response.json();
        renderInvoices(invoices);
    } catch (error) {
        console.error('Error fetching invoices:', error);
        tbody.innerHTML = `<tr><td colspan="5" style="color: red">Error loading invoices: ${error.message}</td></tr>`;
    }
}

function renderInvoices(invoices) {
    const tbody = document.getElementById('invoices-table-body');
    tbody.innerHTML = '';

    if (invoices.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5">No invoices found.</td></tr>';
        return;
    }

    invoices.forEach(invoice => {
        const tr = document.createElement('tr');
        const issueDate = new Date(invoice.issue_date).toLocaleDateString();

        tr.innerHTML = `
            <td>${invoice.number}</td>
            <td>${issueDate}</td>
            <td>${invoice.client_name_snapshot}</td>
            <td>$${invoice.total_amount.toFixed(2)}</td>
            <td>${invoice.status}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Load on start
document.addEventListener('DOMContentLoaded', fetchInvoices);
