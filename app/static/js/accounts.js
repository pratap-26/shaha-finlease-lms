
let currentPage = 1;
const pageSize = 25;
let totalPages = 1;
let activeAccountId = null;
let currentUserRole = "";
const selectedAccountIds = new Set();

const tableBody = document.getElementById("accounts-table-body");
const errorBox = document.getElementById("accounts-error");

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;",
        '"': "&quot;", "'": "&#39;"
    })[c]);
}

function money(value) {
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0
    }).format(Number(value || 0));
}

function showMessage(message, error = false) {
    const box = document.getElementById("workspace-message");
    box.textContent = message;
    box.style.color = error ? "#b42318" : "#16804a";
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        credentials: "same-origin",
        ...options,
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...options.headers
        }
    });

    if (response.status === 401) {
        window.location.href = "/login";
        throw new Error("Session expired.");
    }

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || data.message || "Request failed.");
    }

    return data;
}

async function loadAccounts() {
    errorBox.textContent = "";
    tableBody.innerHTML = `<tr><td colspan="8">Loading accounts...</td></tr>`;

    const params = new URLSearchParams({
        page: currentPage,
        page_size: pageSize
    });

    const search = document.getElementById("search-input").value.trim();
    const status = document.getElementById("status-filter").value;

    if (search) params.set("search", search);
    if (status) params.set("status", status);

    try {
        const data = await api(`/accounts?${params}`);
        const pagination = data.pagination;

        totalPages = Math.max(pagination.pages, 1);

        document.getElementById("result-count").textContent =
            `${pagination.total.toLocaleString("en-IN")} accounts found`;

        document.getElementById("page-label").textContent =
            `Page ${pagination.page} of ${totalPages}`;

        document.getElementById("previous-button").disabled = currentPage <= 1;
        document.getElementById("next-button").disabled = currentPage >= totalPages;

        if (!data.items.length) {
            tableBody.innerHTML =
                `<tr><td colspan="8">No accounts found.</td></tr>`;
            return;
        }

        tableBody.innerHTML = data.items.map(a => `
            <tr>
                <td><input type="checkbox" class="account-select" data-account-id="${a.id}" ${selectedAccountIds.has(a.id) ? "checked" : ""}></td>
                <td><strong>${escapeHTML(a.loan_no)}</strong></td>
                <td>${escapeHTML(a.customer_name)}</td>
                <td>${escapeHTML(a.mobile)}</td>
                <td>${escapeHTML(a.product)}</td>
                <td class="amount-cell">${money(a.outstanding)}</td>
                <td><span class="status-badge">
                    ${escapeHTML(a.status)}
                </span></td>
                <td>
                    <button class="view-button"
                        data-account-id="${a.id}">View</button>
                </td>
            </tr>
        `).join("");

    } catch (error) {
        tableBody.innerHTML =
            `<tr><td colspan="8">Could not load accounts.</td></tr>`;
        errorBox.textContent = error.message;
    }
}

async function loadAccountDetails(accountId) {
    activeAccountId = Number(accountId);

    document.getElementById("account-modal").classList.remove("hidden");
    document.getElementById("workspace-message").textContent = "";

    switchTab("overview");

    try {
        const account = await api(`/accounts/${accountId}`);
        const paymentEntryPanel = document.getElementById("payment-entry-panel");
        paymentEntryPanel.style.display =
            ["Closed", "Settled"].includes(account.status) ? "none" : "block";

        document.getElementById("modal-customer").textContent =
            account.customer_name;

        document.getElementById("modal-loan-number").textContent =
            account.loan_no;

        const fields = [
            ["Loan Number", account.loan_no],
            ["Mobile", account.mobile],
            ["Email", account.email],
            ["City", account.city],
            ["State", account.state],
            ["Language", account.language],
            ["Product", account.product],
            ["Original Amount", money(account.original_amount)],
            ["Original Outstanding", money(account.outstanding)],
            ["Status", account.status],
            ["Office ID", account.office_id],
            ["Owner ID", account.owner_id]
        ];

        document.getElementById("account-details").innerHTML =
            fields.map(([label, value]) => `
                <div class="detail-item">
                    <span>${escapeHTML(label)}</span>
                    <strong>${escapeHTML(value ?? "—")}</strong>
                </div>
            `).join("");

    } catch (error) {
        showMessage(error.message, true);
    }
}

function switchTab(tab) {
    document.querySelectorAll(".workspace-tab").forEach(button => {
        button.classList.toggle("active", button.dataset.tab === tab);
    });

    document.querySelectorAll(".workspace-section").forEach(section => {
        section.classList.toggle("hidden", section.id !== `tab-${tab}`);
    });

    if (!activeAccountId) return;

    if (tab === "calls") loadCallHistory();
    if (tab === "ptps") loadPTPHistory();
    if (tab === "payments") loadPaymentHistory();
    if (tab === "allocations") loadAllocationWorkspace();
    if (tab === "settlements") loadAccountSettlements();
}
async function loadAccountSettlements() {
    const box = document.getElementById("account-settlement-history");
    box.textContent = "Loading settlement history...";

    try {
        const data = await api(
            `/settlements?account_id=${activeAccountId}&page=1&page_size=100`
        );

        const items = data.items || [];

        if (!items.length) {
            box.textContent = "No settlement proposals for this account.";
            return;
        }

        box.innerHTML = items.map(item => `
            <div class="history-item">
                <strong>Settlement #${item.id} — ${escapeHTML(item.status)}</strong>
                <p>Proposed: ${money(item.proposed_amount)}</p>
                <p>Approved: ${item.approved_amount !== null
                    ? money(item.approved_amount) : "Pending review"}</p>
                <p>Paid: ${money(item.amount_paid)}</p>
                <p>Remaining: ${money(item.amount_remaining)}</p>
                <p>Waiver: ${item.waiver_amount !== null
                    ? money(item.waiver_amount) : "—"}</p>
                <p>Reason: ${escapeHTML(item.reason || "Not specified")}</p>
                <p>Proposed: ${escapeHTML(item.proposed_at || "—")}</p>
            </div>
        `).join("");

    } catch (error) {
        box.textContent = error.message;
    }
}
async function loadCallHistory() {
    const box = document.getElementById("call-history");
    box.textContent = "Loading...";

    try {
        const data = await api(`/call-logs/${activeAccountId}`);

        box.innerHTML = data.items.length ? data.items.map(item => `
            <div class="history-item">
                <strong>${escapeHTML(item.disposition)}</strong>
                <p>${escapeHTML(item.remarks || "No remarks")}</p>
                <p>Follow-up: ${escapeHTML(item.next_follow_up || "Not scheduled")}</p>
                <p>${escapeHTML(item.created_at)}</p>
            </div>
        `).join("") : "<p>No call history available.</p>";

    } catch (error) {
        box.textContent = error.message;
    }
}


async function loadPTPHistory() {
    const box = document.getElementById("ptp-history");
    box.textContent = "Loading...";

    try {
        const data = await api(`/ptp/${activeAccountId}`);

        box.innerHTML = data.items.length ? data.items.map(item => `
            <div class="history-item">
                <strong>
                    ${money(item.promised_amount)} — ${escapeHTML(item.status)}
                </strong>
                <p>Promised date: ${escapeHTML(item.promised_date)}</p>
                <p>${escapeHTML(item.remarks || "No remarks")}</p>

                <div class="ptp-status-controls">
                    <select class="ptp-status-select"
                        data-ptp-id="${item.id}">
                        <option value="Pending" ${item.status === "Pending" ? "selected" : ""}>Pending</option>
                        <option value="Kept" ${item.status === "Kept" ? "selected" : ""}>Kept</option>
                        <option value="Broken" ${item.status === "Broken" ? "selected" : ""}>Broken</option>
                        <option value="Cancelled" ${item.status === "Cancelled" ? "selected" : ""}>Cancelled</option>
                    </select>

                    <button type="button"
                        class="primary-button compact update-ptp-button"
                        data-ptp-id="${item.id}">
                        Update Status
                    </button>
                </div>
            </div>
        `).join("") : "<p>No promises recorded.</p>";

    } catch (error) {
        box.textContent = error.message;
    }
}


async function loadPaymentHistory() {
    const box = document.getElementById("payment-history");
    box.textContent = "Loading...";

    try {
        const data = await api(`/payments/${activeAccountId}`);

        box.innerHTML = `<div class="history-item"><strong>Total paid: ${money(data.total_paid || 0)}</strong><p>Original outstanding: ${money(data.loaded_outstanding || 0)}</p></div>` +
            (data.items.length ? data.items.map(item => `
            <div class="history-item">
                <strong>${money(item.amount)}</strong>
                <p>Reference: ${escapeHTML(item.reference || "—")}</p>
                <p>${escapeHTML(item.remarks || "No remarks")}</p>
                <p>${escapeHTML(item.paid_at)}</p>
            </div>
        `).join("") : "<p>No payments recorded.</p>");

    } catch (error) {
        box.textContent = error.message;
    }
}

document.getElementById("call-form").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        await api("/call-logs", {
            method: "POST",
            body: JSON.stringify({
                account_id: activeAccountId,
                disposition: document.getElementById("call-disposition").value,
                remarks: document.getElementById("call-remarks").value,
                next_follow_up:
                    document.getElementById("call-followup").value || null
            })
        });

        event.target.reset();
        showMessage("Call log recorded successfully.");
        loadCallHistory();

    } catch (error) {
        showMessage(error.message, true);
    }
});

document.getElementById("ptp-form").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        await api("/ptp", {
            method: "POST",
            body: JSON.stringify({
                account_id: activeAccountId,
                promised_amount:
                    Number(document.getElementById("ptp-amount").value),
                promised_date: document.getElementById("ptp-date").value,
                remarks: document.getElementById("ptp-remarks").value
            })
        });

        event.target.reset();
        showMessage("Promise to Pay recorded successfully.");
        loadPTPHistory();

    } catch (error) {
        showMessage(error.message, true);
    }
});

document.getElementById("payment-form").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        await api("/payments", {
            method: "POST",
            body: JSON.stringify({
                account_id: activeAccountId,
                amount: Number(document.getElementById("payment-amount").value),
                reference: document.getElementById("payment-reference").value,
                remarks: document.getElementById("payment-remarks").value
            })
        });

        event.target.reset();
        showMessage("Payment recorded successfully.");
        loadPaymentHistory();

    } catch (error) {
        showMessage(error.message, true);
    }
});

document.querySelectorAll(".workspace-tab").forEach(button => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
});

tableBody.addEventListener("click", event => {
    const button = event.target.closest("[data-account-id]");
    if (button) loadAccountDetails(button.dataset.accountId);
});

document.getElementById("search-button").addEventListener("click", () => {
    currentPage = 1;
    loadAccounts();
});

document.getElementById("search-input").addEventListener("keydown", event => {
    if (event.key === "Enter") {
        currentPage = 1;
        loadAccounts();
    }
});

document.getElementById("status-filter").addEventListener("change", () => {
    currentPage = 1;
    loadAccounts();
});

document.getElementById("refresh-button").addEventListener("click", loadAccounts);

document.getElementById("previous-button").addEventListener("click", () => {
    if (currentPage > 1) {
        currentPage--;
        loadAccounts();
    }
});

document.getElementById("next-button").addEventListener("click", () => {
    if (currentPage < totalPages) {
        currentPage++;
        loadAccounts();
    }
});

document.getElementById("close-modal").addEventListener("click", () => {
    document.getElementById("account-modal").classList.add("hidden");
});

document.getElementById("account-modal").addEventListener("click", event => {
    if (event.target.id === "account-modal") {
        event.currentTarget.classList.add("hidden");
    }
});

document.getElementById("logout-button").addEventListener("click", async () => {
    try {
        await api("/auth/logout", { method: "POST" });
    } finally {
        window.location.href = "/login";
    }
});

document.getElementById("current-date").textContent =
    new Date().toLocaleDateString("en-IN", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric"
    });

async function loadUser() {
    try {
        const user = await api("/auth/me");
        const name = user.name || user.user?.name || "User";
        const role = user.role || user.user?.role || "User";
        currentUserRole = role.toLowerCase();
        if (!["manager", "head"].includes(currentUserRole)) {
            document.getElementById("manager-tools").style.display = "none";
        }

        document.getElementById("user-name").textContent = name;
        document.getElementById("user-role").textContent = role;
        document.getElementById("user-avatar").textContent =
            name.charAt(0).toUpperCase();
        if (["manager", "head"].includes(currentUserRole)) {
            const callers = await api(`/allocations/callers?office_id=${user.office_id}`);
            document.getElementById("bulk-caller").innerHTML =
                '<option value="">Select caller</option>' + callers.items.map(c =>
                    `<option value="${c.id}">${escapeHTML(c.name)}</option>`).join("");
        }

    } catch {
        window.location.href = "/login";
    }
}

async function refreshBulkCallerOptions() {
    if (!selectedAccountIds.size) return;
    try {
        const firstId = [...selectedAccountIds][0];
        const account = await api(`/accounts/${firstId}`);
        const callers = await api(`/allocations/callers?office_id=${account.office_id}`);
        document.getElementById("bulk-caller").innerHTML =
            '<option value="">Select caller</option>' + callers.items.map(c =>
                `<option value="${c.id}">${escapeHTML(c.name)}</option>`).join("");
    } catch (error) { showMessage(error.message, true); }
}

document.getElementById("accounts-table-body").addEventListener("change", async event => {
    if (!event.target.classList.contains("account-select")) return;
    const id = Number(event.target.dataset.accountId);
    if (event.target.checked) selectedAccountIds.add(id);
    else selectedAccountIds.delete(id);
    document.getElementById("selected-count").textContent = `${selectedAccountIds.size} selected`;
    await refreshBulkCallerOptions();
});

document.getElementById("select-page").addEventListener("change", async event => {
    document.querySelectorAll(".account-select").forEach(box => {
        box.checked = event.target.checked;
        const id = Number(box.dataset.accountId);
        if (box.checked) selectedAccountIds.add(id);
        else selectedAccountIds.delete(id);
    });
    document.getElementById("selected-count").textContent = `${selectedAccountIds.size} selected`;
    await refreshBulkCallerOptions();
});

document.getElementById("upload-csv-button").addEventListener("click", async () => {
    const file = document.getElementById("accounts-csv").files[0];
    const result = document.getElementById("upload-result");
    if (!file) { result.textContent = "Choose a CSV file first."; return; }
    const form = new FormData();
    form.append("file", file);
    result.textContent = "Uploading and validating CSV...";
    try {
        const response = await fetch("/imports/accounts", {method:"POST", body:form, credentials:"same-origin"});
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Upload failed");
        result.textContent = `Imported ${data.imported}; skipped duplicates ${data.skipped_duplicates}; row errors ${data.error_count}.`;
        currentPage = 1;
        await loadAccounts();
    } catch (error) { result.textContent = error.message; }
});

document.getElementById("bulk-allocate-button").addEventListener("click", async () => {
    const ids = [...selectedAccountIds];
    const callerId = Number(document.getElementById("bulk-caller").value);
    const reason = document.getElementById("bulk-reason").value.trim();
    if (!ids.length || !callerId) { showMessage("Select accounts and a caller.", true); return; }
    try {
        const result = await api("/allocations/bulk", {method:"POST", body:JSON.stringify({account_ids:ids,new_owner_id:callerId,reason})});
        showMessage(`Bulk allocation complete: ${result.updated} updated, ${result.unchanged} unchanged.`);
        selectedAccountIds.clear();
        document.getElementById("selected-count").textContent = "0 selected";
        await loadAccounts();
    } catch (error) { showMessage(error.message, true); }
});

loadUser();
loadAccounts();

async function loadAllocationWorkspace() {
    const historyBox = document.getElementById("allocation-history");
    const controls = document.getElementById("allocation-controls");
    const ownerSelect = document.getElementById("allocation-owner");

    if (!["manager", "head"].includes(currentUserRole)) {
        controls.style.display = "none";
    } else {
        controls.style.display = "block";
    }

    historyBox.textContent = "Loading allocation history...";

    try {
        const account = await api(`/accounts/${activeAccountId}`);
        const history = await api(`/allocations/${activeAccountId}`);

        historyBox.innerHTML = history.items.length
            ? history.items.map(item => `
                <div class="history-item">
                    <strong>Caller ${item.previous_owner_id}
                        → Caller ${item.new_owner_id}</strong>
                    <p>Allocated by User ${item.allocated_by_id}</p>
                    <p>Reason: ${escapeHTML(item.reason || "Not specified")}</p>
                    <p>${escapeHTML(item.allocated_at)}</p>
                </div>
            `).join("")
            : "<p>No previous allocation records.</p>";

        if (["manager", "head"].includes(currentUserRole)) {
            const callers = await api(
                `/allocations/callers?office_id=${account.office_id}`
            );

            ownerSelect.innerHTML =
                '<option value="">Select a caller</option>' +
                callers.items.map(caller => `
                    <option value="${caller.id}"
                        ${caller.id === account.owner_id ? "disabled" : ""}>
                        ${escapeHTML(caller.name)}
                        (${escapeHTML(caller.username)})
                    </option>
                `).join("");
        }
    } catch (error) {
        historyBox.textContent = error.message;
    }
}

document.getElementById("allocation-form")
    .addEventListener("submit", async event => {
        event.preventDefault();

        const newOwnerId = Number(
            document.getElementById("allocation-owner").value
        );

        const reason = document.getElementById("allocation-reason").value.trim();

        if (!newOwnerId) {
            showMessage("Please select a new account owner.", true);
            return;
        }

        try {
            await api("/allocations", {
                method: "POST",
                body: JSON.stringify({
                    account_id: activeAccountId,
                    new_owner_id: newOwnerId,
                    reason: reason
                })
            });

            event.target.reset();
            showMessage("Account reassigned successfully.");

            await loadAllocationWorkspace();
            await loadAccounts();

        } catch (error) {
            showMessage(error.message, true);
        }
    });
    
document.getElementById("ptp-history").addEventListener("click", async event => {
    const button = event.target.closest(".update-ptp-button");

    if (!button) return;

    const ptpId = button.dataset.ptpId;
    const select = document.querySelector(
        `.ptp-status-select[data-ptp-id="${ptpId}"]`
    );

    try {
        await api(`/ptp/${ptpId}`, {
            method: "PATCH",
            body: JSON.stringify({
                status: select.value
            })
        });

        showMessage("Promise status updated successfully.");
        await loadPTPHistory();

    } catch (error) {
        showMessage(error.message, true);
    }
});
