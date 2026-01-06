---
description: Configure the application interactively or via CLI
---

# Setup Workflow

Follow this checklist to configure the `py-invoices` application for your environment.

## 1. Run Interactive Setup

The easiest way to configure the application is to use the interactive setup command.

// turbo
1.  Run `uv run py-invoices setup`
2.  Follow the prompts to configure:
    - **Backend**: Choose between `files`, `sqlite`, `postgres`, `mysql`, or `memory`.
    - **Storage Path**: Specify where to store data (for `files` backend).
    - **File Format**: Choose `json`, `md`, or `xml`.
    - **Database URL**: Provide the connection string for SQL backends.
    - **Output Directory**: Where generated invoices will be saved.

## 2. Automated Setup (for Agents)

If you are an agent and want to skip interactive prompts, use the CLI arguments.

// turbo
1.  Run `uv run py-invoices setup --backend files --storage-path ./data --file-format json --force`
    - Use `--force` to overwrite an existing `.env` file.

## 3. Verify Configuration

After setup, ensure everything is correctly configured.

// turbo
1.  Run `uv run py-invoices config show` to view the active configuration.
2.  Run `uv run py-invoices init` to initialize the database (if using a SQL backend).

## 4. Environment Variables

The setup command creates a `.env` file in the root directory. You can manually edit this file if needed.
