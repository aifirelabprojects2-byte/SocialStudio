window.askUser = function (title, message) {
return new Promise((resolve) => {
const modal = document.getElementById("globalConfirmModal");
const card = document.getElementById("globalConfirmCard");
const titleEl = document.getElementById("globalConfirmTitle");
const textEl = document.getElementById("globalConfirmText");
const confirmBtn = document.getElementById("globalConfirmBtn");
const cancelBtn = document.getElementById(
    "globalConfirmCancel",
);

// Set Content
titleEl.textContent = title || "Are you sure?";
textEl.textContent = message || "Please confirm this action.";

// Show Modal
modal.classList.remove("hidden");
setTimeout(() => {
    card.classList.remove("scale-95", "opacity-0");
}, 10);

// Helper to close
const close = (result) => {
    card.classList.add("scale-95", "opacity-0");
    setTimeout(() => {
    modal.classList.add("hidden");
    resolve(result);
    }, 200);
};

// Event Listeners
confirmBtn.onclick = () => close(true);
cancelBtn.onclick = () => close(false);

// Refresh icons if lucide is present
if (window.lucide) lucide.createIcons();
});
};

const gridRvk = document.getElementById("platformGridRvk");
const loaderRvk = document.getElementById("loaderRvk");
const zeroRvk = document.getElementById("zeroStateRvk");
const activeCountRvk = document.getElementById("activeCountRvk");

let pendingIdRvk = null;
let pendingElRvk = null;

const getPlatformSvgRvk = (apiName) => {
const p = SUPPORTED_PLATFORMSBlz.find(
    (item) => item.id === apiName.toLowerCase()
);

if (!p) return "";

return `
    <span class="${p.color}">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
        ${p.svg}
    </svg>
    </span>
`;
};


async function initPlatformsRvk() {
try {
if (loaderRvk) loaderRvk.classList.remove("hidden");
if (zeroRvk) zeroRvk.classList.add("hidden");
if (gridRvk) gridRvk.style.display = "none";

const res = await fetch("/api/active/platforms");
const data = await res.json();

loaderRvk.classList.add("hidden");
if (!data || data.length === 0) {
    zeroRvk.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
    return;
}

activeCountRvk.textContent = `${data.length} Active`;
gridRvk.style.display = "grid";
gridRvk.innerHTML = "";
data.forEach((p) => {
    const card = renderItemRvk(p);
    gridRvk.appendChild(card);
});

if (window.lucide) lucide.createIcons();
} catch (e) {
loaderRvk.innerHTML = `<span class="text-sm font-bold text-red-500">Failed to load active accounts.</span>`;
}
}

function renderItemRvk(p) {
const card = document.createElement("div");
card.className =
"group relative bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl p-5 flex flex-col hover:shadow-xl hover:shadow-gray-100/50 dark:hover:shadow-zinc-950/50 hover:border-gray-200 dark:hover:border-zinc-700";

const days = p.expiry_days_left;
const isPermanent = days === null || days === undefined;
const isExpired = !isPermanent && days <= 0;

const statusText = isPermanent
? "Permanent"
: isExpired
    ? "Expired"
    : `${days}d left`;

const maxDays = 60;
const progressPercent = isPermanent
? 100
: Math.min(100, Math.max(0, (days / maxDays) * 100));

// Circular progress colors
const circleStrokeColor = isExpired ? "#ef4444" : "#2f2f2f";

const circleTrackColor = "currentColor";

// Calculate stroke-dasharray for circular progress (circumference = 2 * PI * radius)
const radius = 18;
const circumference = 2 * Math.PI * radius;
const strokeDashoffset = circumference - (progressPercent / 100) * circumference;

const initial = p.account_name
? p.account_name.charAt(0).toUpperCase()
: "?";

card.innerHTML = `
<div class="flex items-start justify-between gap-3 mb-4">
    <div class="flex items-center gap-3 min-w-0 flex-1">
    <div class="relative flex-shrink-0">
        ${
        p.profile_photo_url
            ? `
            <img src="${p.profile_photo_url}" onerror="this.onerror=null; this.src='https://www.gravatar.com/avatar/0?d=mp';"
                class="w-11 h-11 rounded-lg object-cover ring-1 ring-gray-100 dark:ring-zinc-800" />
            `
            : `
            <div class="w-11 h-11 rounded-lg ring-1 ring-gray-100 dark:ring-zinc-800 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-zinc-800 dark:to-zinc-900 flex items-center justify-center text-gray-500 dark:text-gray-400 font-semibold text-base uppercase">
                ${initial}
            </div>
            `
        }
        <div class="absolute -bottom-1 -right-1 w-5 h-5 bg-white dark:bg-zinc-900 rounded-md flex items-center justify-center shadow-sm ring-1 ring-gray-100 dark:ring-zinc-800">
        ${getPlatformSvgRvk(p.api_name)}
        </div>
    </div>

    <div class="min-w-0 flex-1">
        <h4 class="text-sm font-semibold text-gray-900 dark:text-white truncate">
        ${p.account_name}
        </h4>
        <p class="text-xs text-gray-500 dark:text-gray-500 capitalize mt-0.5">
        ${p.api_name}
        </p>
    </div>
    </div>

    <button
    class="rvk-btn-rvk w-8 h-8 flex items-center justify-center rounded-lg
    text-gray-400 dark:text-gray-600
    hover:text-red-500 dark:hover:text-red-400
    hover:bg-red-50 dark:hover:bg-red-500/10"
    title="Disconnect">
    <i data-lucide="x" class="w-4 h-4"></i>
    </button>
</div>

<div class="flex items-center justify-between pt-4 border-t border-gray-50 dark:border-zinc-800/50">
    <div class="flex items-center gap-3">
    <!-- Circular Progress -->
    <div class="relative w-10 h-10">
        <svg class="w-10 h-10 -rotate-90" viewBox="0 0 44 44">
        <circle
            cx="22"
            cy="22"
            r="${radius}"
            fill="none"
            stroke-width="3"
            class="text-gray-100 dark:text-black"
            stroke="${circleTrackColor}"
        />
        <circle
            cx="22"
            cy="22"
            r="${radius}"
            fill="none"
            stroke-width="3"
            stroke="${circleStrokeColor}"
            stroke-linecap="round"
            stroke-dasharray="${circumference}"
            stroke-dashoffset="${strokeDashoffset}"
        />
        </svg>
        <div class="absolute inset-0 flex items-center justify-center">
        ${isPermanent 
            ? `<i data-lucide="infinity" class="w-3.5 h-3.5 text-gray-600 dark:text-gray-50"></i>`
            : `<span class="text-[10px] font-bold ${isExpired ? 'text-red-500' : 'text-gray-700 dark:text-gray-300'}">${Math.round(progressPercent)}%</span>`
        }
        </div>
    </div>

    <div class="flex flex-col">
        <span class="text-xs font-medium ${isExpired ? 'text-red-500' : 'text-gray-900 dark:text-white'}">
        ${statusText}
        </span>
        <span class="text-[10px] text-gray-400 dark:text-gray-500">
        ${isPermanent ? 'No expiration' : isExpired ? 'Reconnect required' : 'Access validity'}
        </span>
    </div>
    </div>

</div>
`;

card.querySelector(".rvk-btn-rvk").onclick = async () => {
const confirmed = await askUser(
    "Revoke access?",
    `This will disconnect ${p.account_name} and stop all active automation.`
);

if (confirmed) {
    ShowNoti("info","This action is disabled in demo mode")
}
};

return card;
}

function closeModalRvk() {
modalRvk.classList.add("hidden");
}

// Start
initPlatformsRvk();