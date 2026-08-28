(() => {
  'use strict';
  document.querySelectorAll('[data-year]').forEach((node) => { node.textContent = String(new Date().getFullYear()); });
  const toggle = document.querySelector('.nav-toggle');
  const menu = document.querySelector('#primary-links');
  if (toggle && menu) {
    const close = (returnFocus = false) => {
      menu.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      if (returnFocus) toggle.focus();
    };
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      menu.classList.toggle('is-open', open);
    });
    menu.addEventListener('click', (event) => { if (event.target.closest('a')) close(); });
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && menu.classList.contains('is-open')) close(true); });
    document.addEventListener('click', (event) => { if (!event.target.closest('.nav-shell') && menu.classList.contains('is-open')) close(); });
    matchMedia('(min-width: 901px)').addEventListener('change', (event) => { if (event.matches) close(); });
  }
  const revealNodes = [...document.querySelectorAll('[data-reveal]')];
  if (!revealNodes.length) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) {
    revealNodes.forEach((node) => node.classList.add('is-visible'));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    }
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  document.documentElement.classList.add('reveal-ready');
  requestAnimationFrame(() => revealNodes.forEach((node) => observer.observe(node)));
})();
