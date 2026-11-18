# Implementation Matrix & Capability Master Key

This document maps every identified feature and action across the codebase to its corresponding implementation in the Interface (Code), CLI, and API.

**Legend**
*   `-` : Not Implemented / Not Applicable

| Entity / Context | Action / Feature | Interface / Service | CLI Command | API Endpoint |
| :--- | :--- | :--- | :--- | :--- |
| **System** | Initialize Database | - | `init` | - |
| **Invoice** | Create Draft Invoice | `operations.invoices.create_invoice` | `invoices create` | `POST /invoices/` |
| **Invoice** | Edit Draft | `operations.invoices.update_invoice` | `invoices update` | - |
| **Invoice** | Issue Draft | `operations.invoices.issue_invoice` | `invoices issue` | `POST /invoices/{number}/issue` |
| **Invoice** | Clone Invoice | `operations.invoices.clone_invoice` | `invoices clone` | - |
| **Invoice** | Check Stored Invoices | `operations.integrity.check_stored_invoices` | `validate data` | - |
| **Invoice** | List Invoices | `InvoiceRepository.get_all` | `invoices list` | `GET /invoices/` |
| **Invoice** | Get Invoice Details | `InvoiceRepository.get_by_number` | `invoices details` | `GET /invoices/{number}` |
| **Invoice** | Generate PDF | `PDFService.generate_pdf` | `invoices pdf` | `GET /invoices/{number}/pdf` |
| **Invoice** | Generate HTML | `HTMLService.save_html` | `invoices html` | `GET /invoices/{number}/html` |
| **Invoice** | Get Overdue | `InvoiceRepository.get_overdue` | `invoices overdue` | `GET /invoices/overdue` |
| **Invoice** | Get Summary | `InvoiceRepository.get_summary` | `invoices summary` | `GET /invoices/summary` |
| **Client** | Create Client | `ClientRepository.create` | `clients create` | `POST /clients/` |
| **Client** | List Clients | `ClientRepository.get_all` | `clients list` | `GET /clients/` |
| **Client** | Get Client Details | `ClientRepository.get_by_id` | `clients details` | `GET /clients/{id}` |
| **Client** | Search Clients | `ClientRepository.search` | `clients search` | `GET /clients/search` |
| **Credit Note** | Create Credit Note | `CreditService.create_credit_note` | `credit-notes create` | `POST /credit-notes/` |
| **Credit Note** | Get Credit Note | `InvoiceRepository.get_by_number` | `credit-notes get` | `GET /credit-notes/{number}` |
| **Validation** | Validate UBL File | `UBLValidator.validate_file` | `validate invoice` | `POST /validation/ubl` |
| **Product** | Get Product by Code | `ProductRepository.get_by_code` | `products get` | `GET /products/{code}` |
| **Product** | List Active Products | `ProductRepository.get_active` | `products list` | `GET /products/` |
| **Product** | Search Products | `ProductRepository.search` | `products search` | `GET /products/search` |
| **Company** | Get Default Company | `CompanyRepository.get_default` | `companies default` | `GET /companies/default` |
| **Company** | Get Active Companies | `CompanyRepository.get_active` | `companies list` | `GET /companies/` |
| **Payment Note** | Set Default | `operations.payment_notes.set_default_payment_note` | `payment-notes set-default` | - |
| **Payment Note** | Deactivate | `operations.payment_notes.deactivate_payment_note` | `payment-notes deactivate` | - |
| **Payment** | Get Payments for Invoice | `PaymentRepository.get_by_invoice` | `payments list` | `GET /payments/` |
| **Payment Note** | Get Default Note | `PaymentNoteRepository.get_default` | `payment-notes default` | `GET /payment-notes/default` |
| **Audit Log** | Log Actions | `AuditService` | `audit list` | `GET /audit/` |
