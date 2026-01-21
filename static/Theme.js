(function() {
    const sidebar = document.getElementById('main-sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle');

    toggleBtn.addEventListener('click', function() {
        sidebar.classList.toggle('sidebar-collapsed');
    });
})();

const themes = ["system", "light", "dark"];
const root = document.documentElement;
const toggleBtn = document.getElementById("themeToggle");
const label = document.getElementById("themeLabel");

function applyTheme(theme) {
root.classList.remove("dark");

if (theme === "dark") {
    root.classList.add("dark");
}

if (theme === "system") {
    if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    root.classList.add("dark");
    }
}

localStorage.setItem("theme", theme);
updateThemeUI(theme);
}

function updateThemeUI(theme) {
document.querySelectorAll("[data-theme-icon]").forEach(i =>
    i.classList.add("hidden")
);

document
    .querySelector(`[data-theme-icon="${theme}"]`)
    .classList.remove("hidden");

label.textContent =
    theme === "system"
    ? "Mode (System)"
    : theme === "dark"
    ? "Mode (Dark)"
    : "Mode (Light)";
}

function cycleTheme() {
const current = localStorage.getItem("theme") || "system";
const next = themes[(themes.indexOf(current) + 1) % themes.length];
applyTheme(next);
}

toggleBtn.addEventListener("click", cycleTheme);

applyTheme(localStorage.getItem("theme") || "system");
window
.matchMedia("(prefers-color-scheme: dark)")
.addEventListener("change", e => {
    if (localStorage.getItem("theme") === "system") {
    applyTheme("system");
    }
});