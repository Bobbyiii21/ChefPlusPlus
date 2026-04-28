// Theme handler

const root = document.documentElement;
const btn = document.getElementById('themeToggle');
const icon = document.getElementById('themeIcon');
const saved = localStorage.getItem('theme') || 'light';

function updateNavLogo(theme) {
    const navLogo = document.getElementById('navLogo');
    if (navLogo) {
        navLogo.src = theme === 'dark' ? navLogo.dataset.dark : navLogo.dataset.light;
    }
}

new MutationObserver(() => {
    const theme = root.getAttribute('data-theme');
    updateNavLogo(theme);
}).observe(root, { attributes: true, attributeFilter: ['data-theme'] });

window.onload = function () {
    root.setAttribute('data-theme', saved);
    icon.textContent = (saved === 'dark') ? 'light_mode' : 'dark_mode';
};

function changeTheme() {
    const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    icon.textContent = (next === 'dark') ? 'light_mode' : 'dark_mode';
}

// End theme handler