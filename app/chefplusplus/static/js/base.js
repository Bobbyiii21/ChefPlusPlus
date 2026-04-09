// Theme handler

const root = document.documentElement;
const btn = document.getElementById('themeToggle');
const icon = document.getElementById('themeIcon');
const saved = localStorage.getItem('theme') || 'light';

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