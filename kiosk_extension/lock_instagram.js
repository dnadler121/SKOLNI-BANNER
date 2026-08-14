(() => {
  'use strict';
  const BANNER_URL = 'http://127.0.0.1:5000/';

  function isBackButton(target) {
    return target && target.closest && target.closest('#school-banner-back');
  }

  // Na profilu školy nesmí žádné kliknutí otevřít příspěvek, Reels,
  // zprávy, jiný profil ani jinou část Instagramu.
  for (const eventName of ['click', 'auxclick', 'dblclick']) {
    window.addEventListener(eventName, (event) => {
      if (isBackButton(event.target)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      event.stopPropagation();
    }, true);
  }

  // Klávesové zkratky, které by mohly opustit povolenou obrazovku.
  window.addEventListener('keydown', (event) => {
    const allowed = ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End'];
    if (allowed.includes(event.key)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);

  function addBackButton() {
    if (!document.body || document.getElementById('school-banner-back')) return;
    const button = document.createElement('button');
    button.id = 'school-banner-back';
    button.type = 'button';
    button.textContent = '← ZPĚT';
    button.setAttribute('aria-label', 'Zpět do školního banneru');
    Object.assign(button.style, {
      position: 'fixed', left: '18px', top: '18px', zIndex: '2147483647',
      border: '0', borderRadius: '14px', padding: '16px 28px',
      background: '#42b51f', color: '#fff', fontSize: '20px',
      fontWeight: '800', cursor: 'pointer', boxShadow: '0 4px 14px rgba(0,0,0,.28)'
    });
    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      location.href = BANNER_URL;
    }, true);
    document.body.appendChild(button);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addBackButton, {once: true});
  } else {
    addBackButton();
  }
  new MutationObserver(addBackButton).observe(document.documentElement, {childList: true, subtree: true});
})();
