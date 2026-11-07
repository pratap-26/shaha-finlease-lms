const API_BASE = "";

let currentUser = null;
let accountsById = new Map();
let allSettlements = [];
let settlementPagination = {
    page: 1,
    page_size: 25,
    total: 0,
    pages: 0
};
let accountSearchRequestId = 0;

const $ = (id) => document.getElementById(id);

function money(value) {
    const amount = Number(value || 0);
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2
    }).format(amount);
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

function showMessage(message, type = "error") {
    const error = $("settlement-error");
    const success = $("settlement-success");

    error.textContent = "";
    success.textContent = "";

    if (!message) return;

    if (type === "success") {
        success.textContent = message;
    } else {
        error.textContent = message;
    }
}

async function api(url, options = {}) {
    const response = await fetch(`${API_BASE}${url}`, {
        credentials: "same-origin",
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        const detail = data.detail;
        const message = typeof detail === "string"
            ? detail
            : detail
                ? JSON.stringify(detail)
                : `Request failed (${response.status})`;

        throw new Error(message);
    }

    return data;
}

function setUserProfile(user) {
    currentUser = user;

    $("user-name").textContent = user.name || user.username || "User";
    $("user-role").textContent = (user.role || "user").toUpperCase();
    $("user-avatar").textContent =
        (user.name || user.username || "U").charAt(0).toUpperCase();

    $("current-date").textContent = new Intl.DateTimeFormat("en-IN", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric"
    }).format(new Date());

    const canPropose = ["caller", "manager", "head"].includes(user.role);
    $("proposal-panel").hidden = !canPropose;
}

async function loadUser() {
    const user = await api("/auth/me");
    setUserProfile(user);
}

async function loadAccounts(searchTerm = "") {
    const requestId = ++accountSearchRequestId;
    const params = new URLSearchParams({
        page: "1",
        page_size: "100"
    });

    if (searchTerm.trim()) {
        params.set("search", searchTerm.trim());
    }

    const data = await api(`/accounts?${params.toString()}`);
    if (requestId !== accountSearchRequestId) return;

    const accounts = data.items || [];

    accountsById = new Map(
        accounts.map(account => [Number(account.id), account])
    );

    const datalist = $("settlement-account-options");
    datalist.innerHTML = "";

    accounts.forEach(account => {
        const option = document.createElement("option");
        option.value = `${account.loan_no} — ${account.customer_name}`;
        option.dataset.accountId = account.id;
        datalist.appendChild(option);
    });
}

function resolveSelectedAccount() {
    const entered = $("proposal-account").value.trim();
    const selected = [...$("settlement-account-options").options]
        .find(option => option.value === entered);

    if (!selected) {
        $("proposal-account-id").value = "";
        $("proposal-account-info").textContent =
            "Select an account from the suggestions.";
        return null;
    }

    const accountId = Number(selected.dataset.accountId);
    const account = accountsById.get(accountId);

    if (!account) return null;

    $("proposal-account-id").value = account.id;
    $("proposal-account-info").textContent =
        `${account.loan_no} · ${account.customer_name} · Outstanding: ${money(account.outstanding)} · Status: ${account.status}`;

    $("proposal-amount").max = Math.max(
        0,
        Number(account.outstanding || 0) - 0.01
    );

    return account;
}

function accountFor(settlement) {
    return {
        customer_name: settlement.customer_name || "Unknown",
        loan_no: settlement.loan_no || `ID ${settlement.account_id}`
    };
}

function statusClass(status) {
    return String(status || "").toLowerCase().replace(/\s+/g, "-");
}

function updateKPIs() {
    $("settlement-total").textContent = allSettlements.length;

    $("settlement-pending").textContent = allSettlements.filter(
        item => item.status === "Pending"
    ).length;

    $("settlement-active").textContent = allSettlements.filter(
        item => ["Approved", "In Progress"].includes(item.status)
    ).length;
}

function renderSettlements() {
    const search = $("settlement-search").value.trim().toLowerCase();
    const status = $("settlement-status-filter").value;

    const filtered = allSettlements.filter(item => {
        const account = accountFor(item);
        const searchText = [
            account.loan_no,
            account.customer_name,
            item.reason,
            item.status
        ].join(" ").toLowerCase();

        return (!status || item.status === status) &&
            (!search || searchText.includes(search));
    });

    const tbody = $("settlement-table-body");

    if (!filtered.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state">
                    No settlement records match your filters.
                </td>
            </tr>`;
    } else {
        tbody.innerHTML = filtered.map(item => {
            const account = accountFor(item);

            return `
                <tr>
                    <td>
                        <strong>${escapeHTML(account.customer_name)}</strong>
                        <small>${escapeHTML(account.loan_no)}</small>
                    </td>
                    <td>${money(item.proposed_amount)}</td>
                    <td>${item.approved_amount == null ? "—" : money(item.approved_amount)}</td>
                    <td>${item.waiver_amount == null ? "—" : money(item.waiver_amount)}</td>
                    <td>${money(item.amount_paid)}</td>
                    <td>${item.approved_amount == null ? "—" : money(item.amount_remaining)}</td>
                    <td>
                        <span class="status-badge ${escapeHTML(statusClass(item.status))}">
                            ${escapeHTML(item.status)}
                        </span>
                    </td>
                    <td>
                        <button class="secondary-button settlement-action-button"
                            data-settlement-id="${item.id}" type="button">
                            View / Action
                        </button>
                    </td>
                </tr>`;
        }).join("");
    }

    const pagination = settlementPagination;
    $("settlement-record-count").textContent =
        `Showing ${filtered.length} of ${pagination.total} records`;

    $("settlement-page-info").textContent =
        `Page ${pagination.page} of ${Math.max(pagination.pages, 1)}`;

    $("settlement-prev").disabled = pagination.page <= 1;
    $("settlement-next").disabled =
        pagination.page >= pagination.pages;
}
async function loadSettlements() {
    const params = new URLSearchParams({
        page: settlementPagination.page,
        page_size: settlementPagination.page_size
    });

    const status = $("settlement-status-filter").value;
    if (status) params.set("status", status);

    const data = await api(`/settlements?${params.toString()}`);

    allSettlements = data.items || [];
    settlementPagination = data.pagination;

    updateKPIs();
    renderSettlements();
}

async function refreshPage() {
    showMessage("");

    try {
        await loadAccounts();
        await loadSettlements();
    } catch (error) {
        showMessage(error.message);
    }
}

async function submitProposal(event) {
    event.preventDefault();
    showMessage("");

    const account = resolveSelectedAccount();

    if (!account) {
        showMessage("Please select a valid account from the suggestions.");
        return;
    }

    const payload = {
        account_id: Number(account.id),
        proposed_amount: Number($("proposal-amount").value),
        reason: $("proposal-reason").value.trim(),
        remarks: $("proposal-remarks").value.trim() || null,
        payment_due_date: $("proposal-due-date").value || null
    };

    if (!payload.reason || !payload.proposed_amount) {
        showMessage("Please enter a valid amount and settlement reason.");
        return;
    }

    const button = $("submit-proposal");
    button.disabled = true;

    try {
        const result = await api("/settlements", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        $("settlement-proposal-form").reset();
        $("proposal-account-id").value = "";
        $("proposal-account-info").textContent =
            "Search for an account to view its outstanding balance.";

        showMessage(
            result.message || "Settlement proposal submitted.",
            "success"
        );

        await loadSettlements();
    } catch (error) {
        showMessage(error.message);
    } finally {
        button.disabled = false;
    }
}

let activeSettlement = null;
let activeAction = null;

function openSettlementModal(settlement, action) {
    activeSettlement = settlement;
    activeAction = action;

    const account = {
    customer_name: settlement.customer_name || "Unknown",
    loan_no: settlement.loan_no || settlement.account_id
    };

    $("modal-title").textContent = {
        approve: "Approve Settlement",
        reject: "Reject Settlement",
        payment: "Record Settlement Payment"
    }[action];

    const details = [
        ["Customer", account?.customer_name || "Unknown"],
        ["Loan Number", account?.loan_no || settlement.account_id],
        ["Original Outstanding", money(settlement.original_outstanding)],
        ["Proposed Amount", money(settlement.proposed_amount)],
        ["Approved Amount", settlement.approved_amount == null ? "Pending" : money(settlement.approved_amount)],
        ["Waiver", settlement.waiver_amount == null ? "—" : money(settlement.waiver_amount)],
        ["Amount Paid", money(settlement.amount_paid)],
        ["Remaining", settlement.approved_amount == null ? "—" : money(settlement.amount_remaining)],
        ["Status", settlement.status],
        ["Reason", settlement.reason || "—"]
    ];

    $("modal-summary").innerHTML = details.map(([label, value]) => `
        <div class="settlement-detail-item">
            <span>${escapeHTML(label)}</span>
            <strong>${escapeHTML(value)}</strong>
        </div>
    `).join("");

    $("approval-fields").hidden = action !== "approve";
    $("rejection-fields").hidden = action !== "reject";
    $("payment-fields").hidden = action !== "payment";

    $("approval-remarks").value = "";
    $("rejection-remarks").value = "";
    $("payment-amount").value = "";
    $("payment-reference").value = "";
    $("payment-remarks").value = "";

    $("rejection-remarks").required = action === "reject";
    $("payment-amount").required = action === "payment";

    $("confirm-settlement-action").textContent = {
        approve: "Approve Settlement",
        reject: "Reject Proposal",
        payment: "Record Payment"
    }[action];
    $("confirm-settlement-action").hidden = action === "view";
    $("reject-settlement-action").hidden =
        !(action === "approve");
    $("settlement-modal").hidden = false;
    loadSettlementPaymentHistory(settlement.id);
}

async function loadSettlementPaymentHistory(settlementId) {
    const container = $("payment-history-list");
    const totalLabel = $("payment-history-total");

    container.textContent = "Loading payment records...";
    totalLabel.textContent = "";

    try {
        const data = await api(`/settlements/${settlementId}/payments`);

        const items = data.items || [];

        totalLabel.textContent =
            `${items.length} payments · ${money(data.total_paid || 0)} recovered`;

        if (!items.length) {
            container.innerHTML =
                '<p class="muted">No settlement payments recorded yet.</p>';
            return;
        }

        container.innerHTML = items.map(payment => {
            const date = payment.paid_at
                ? new Date(payment.paid_at).toLocaleString("en-IN")
                : "Date unavailable";

            return `
                <div class="payment-history-item">
                    <div class="payment-history-main">
                        <strong>${escapeHTML(money(payment.amount))}</strong>
                        <span>${escapeHTML(date)}</span>
                    </div>
                    <p>Reference: ${escapeHTML(payment.reference || "—")}</p>
                    <p>Recorded by: ${escapeHTML(payment.recorded_by_name || "Unknown")}</p>
                    ${payment.remarks
                        ? `<p>${escapeHTML(payment.remarks)}</p>`
                        : ""}
                </div>
            `;
        }).join("");

    } catch (error) {
        container.innerHTML =
            `<p class="error-message">${escapeHTML(error.message)}</p>`;
        totalLabel.textContent = "";
        console.error("Settlement payment history error:", error);
    }
}
function closeSettlementModal() {
    $("settlement-modal").hidden = true;
    $("settlement-action-form").reset();

    activeSettlement = null;
    activeAction = null;
}

async function showSettlementAction(settlementId) {
    const settlement = allSettlements.find(
        item => Number(item.id) === Number(settlementId)
    );

    if (!settlement) return;

    const isApprover = ["manager", "head"].includes(currentUser?.role);

    const canReview =
        isApprover &&
        settlement.status === "Pending" &&
        Number(settlement.proposed_by_id) !== Number(currentUser.id);

    const canPay = ["Approved", "In Progress"].includes(settlement.status);

    if (canReview) {
        openSettlementModal(settlement, "approve");
    } else if (canPay) {
        openSettlementModal(settlement, "payment");
    } else {
        openSettlementModal(settlement, "view");
        $("confirm-settlement-action").hidden = true;
    }
}

async function submitSettlementAction(event) {
    event.preventDefault();

    if (!activeSettlement || !activeAction || activeAction === "view") return;

    const button = $("confirm-settlement-action");
    button.disabled = true;

    try {
        let endpoint;
        let payload;

        if (activeAction === "approve") {
            endpoint = `/settlements/${activeSettlement.id}/approve`;
            payload = {
                remarks: $("approval-remarks").value.trim()
            };
        } else if (activeAction === "reject") {
            const remarks = $("rejection-remarks").value.trim();

            if (!remarks) {
                throw new Error("Please provide a rejection reason.");
            }

            endpoint = `/settlements/${activeSettlement.id}/reject`;
            payload = { remarks };
        } else if (activeAction === "payment") {
            const amount = Number($("payment-amount").value);
            const remaining = Number(activeSettlement.amount_remaining);

            if (!Number.isFinite(amount) || amount <= 0) {
                throw new Error("Enter a valid payment amount.");
            }

            if (amount > remaining) {
                throw new Error(`Payment cannot exceed ${money(remaining)}.`);
            }

            endpoint = `/settlements/${activeSettlement.id}/payments`;

            payload = {
                amount,
                reference: $("payment-reference").value.trim(),
                remarks: $("payment-remarks").value.trim()
            };
        }

        const result = await api(endpoint, {
            method: "POST",
            body: JSON.stringify(payload)
        });

        closeSettlementModal();

        showMessage(
            result.message || "Settlement action completed successfully.",
            "success"
        );

        await loadSettlements();

    } catch (error) {
        showMessage(error.message);
    } finally {
        button.disabled = false;
    }
}

function attachEvents() {
    $("logout-button").addEventListener("click", async () => {
        try {
            await api("/auth/logout", { method: "POST" });
        } finally {
            window.location.href = "/login";
        }
    });

    $("refresh-settlements").addEventListener("click", refreshPage);
    $("settlement-proposal-form").addEventListener("submit", submitProposal);

    let accountSearchTimer;

    $("proposal-account").addEventListener("input", () => {
        $("proposal-account-id").value = "";
        $("proposal-account-info").textContent = "Searching accounts...";

        clearTimeout(accountSearchTimer);

        const query = $("proposal-account").value.trim();

        if (query.length < 2) {
            accountSearchRequestId++;
            $("settlement-account-options").innerHTML = "";
            $("proposal-account-info").textContent =
                "Enter at least 2 characters to search.";
            return;
        }

        accountSearchTimer = setTimeout(async () => {
            try {
                await loadAccounts(query);
                $("proposal-account-info").textContent =
                    "Select an account from the suggestions.";
            } catch (error) {
                showMessage(error.message);
            }
        }, 300);
    });

    $("proposal-account").addEventListener("change", resolveSelectedAccount);

    $("settlement-search").addEventListener("input", renderSettlements);

    $("settlement-status-filter").addEventListener("change", () => {
        settlementPagination.page = 1;
        loadSettlements();
    });

    $("settlement-prev").addEventListener("click", () => {
        if (settlementPagination.page > 1) {
            settlementPagination.page--;
            loadSettlements();
        }
    });

    $("settlement-next").addEventListener("click", () => {
        if (settlementPagination.page < settlementPagination.pages) {
            settlementPagination.page++;
            loadSettlements();
        }
    });

    $("settlement-table-body").addEventListener("click", event => {
        const button = event.target.closest("[data-settlement-id]");
        if (button) {
            showSettlementAction(button.dataset.settlementId);
        }
    });
        $("close-settlement-modal").addEventListener(
        "click", closeSettlementModal
    );

    $("cancel-settlement-action").addEventListener(
        "click", closeSettlementModal
    );

    $("settlement-modal").addEventListener("click", event => {
        if (event.target.id === "settlement-modal") {
            closeSettlementModal();
        }
    });

    $("settlement-action-form").addEventListener(
        "submit", submitSettlementAction
    );

    $("reject-settlement-action").addEventListener("click", () => {
    if (activeSettlement) {
        openSettlementModal(activeSettlement, "reject");
    }
});
}

async function initialize() {
    attachEvents();

    try {
        await loadUser();
        await refreshPage();
    } catch (error) {
        showMessage(error.message);
    }
}

document.addEventListener("DOMContentLoaded", initialize);
