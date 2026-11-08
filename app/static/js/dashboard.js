function formatMoney(value) {
    const amount = Number(value || 0);

    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0
    }).format(amount);
}

function renderBreakdown(elementId, rows, labelKey) {
    const container = document.getElementById(elementId);

    if (!rows.length) {
        container.textContent = "No records available.";
        return;
    }

    const maximum = Math.max(...rows.map(row => row.count), 1);

    container.innerHTML = rows.map(row => {
        const percentage = (row.count / maximum) * 100;

        return `
            <div class="data-row">
                <div class="data-row-top">
                    <span>${row[labelKey]}</span>
                    <strong>${row.count.toLocaleString("en-IN")}</strong>
                </div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:${percentage}%"></div>
                </div>
            </div>
        `;
    }).join("");
}

async function loadDashboard() {
    const errorBox = document.getElementById("dashboard-error");
    errorBox.textContent = "";

    try {
        const response = await fetch("/dashboard/summary", {
            credentials: "same-origin"
        });

        if (response.status === 401) {
            window.location.href = "/login";
            return;
        }

        if (!response.ok) {
            throw new Error("Unable to load dashboard data.");
        }

        const data = await response.json();
        const k = data.kpis;

        document.getElementById("user-name").textContent = data.user.name;
        document.getElementById("user-role").textContent = data.user.role;
        document.getElementById("user-avatar").textContent =
            data.user.name.charAt(0).toUpperCase();
        document.getElementById("welcome-name").textContent =
            data.user.name.split(" ")[0];

        document.getElementById("total-accounts").textContent =
            k.total_accounts.toLocaleString("en-IN");

        document.getElementById("total-outstanding").textContent =
            formatMoney(k.total_outstanding);

        document.getElementById("total-recovered").textContent =
            formatMoney(k.total_recovered);

        document.getElementById("total-calls").textContent =
            k.total_calls.toLocaleString("en-IN");

        document.getElementById("pending-ptps").textContent =
            k.pending_ptps.toLocaleString("en-IN");

        document.getElementById("pending-amount").textContent =
            formatMoney(k.pending_ptp_amount);

        document.getElementById("total-settlements").textContent =
            k.total_settlements.toLocaleString("en-IN");

        document.getElementById("pending-settlements").textContent =
            k.pending_settlements.toLocaleString("en-IN");

        document.getElementById("settlement-recovered").textContent =
            formatMoney(k.total_settlement_recovered);

        document.getElementById("closed-accounts").textContent =
            k.closed_accounts.toLocaleString("en-IN");

        renderBreakdown("status-list", data.account_status, "status");
        renderBreakdown("office-list", data.office_distribution, "office");

    } catch (error) {
        errorBox.textContent = error.message;
    }
}

document.getElementById("current-date").textContent =
    new Date().toLocaleDateString("en-IN", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric"
    });

document.getElementById("logout-button").addEventListener("click", async () => {
    await fetch("/auth/logout", {
        method: "POST",
        credentials: "same-origin"
    });

    window.location.href = "/login";
});

loadDashboard();