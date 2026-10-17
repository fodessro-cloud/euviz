// Google Analytics 4, loaded only after the visitor accepts cookies (GDPR).
// The choice is remembered in localStorage; "finila-consent" is "yes" or "no".

const GA_ID = 'G-9CXHYXMWW4';

function loadAnalytics() {
  const s = document.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { dataLayer.push(arguments); };
  gtag('js', new Date());
  gtag('config', GA_ID, { anonymize_ip: true });
}

function readConsent() {
  try { return localStorage.getItem('finila-consent'); } catch (e) { return null; }
}

function saveConsent(v) {
  try { localStorage.setItem('finila-consent', v); } catch (e) { /* private mode: ask again next time */ }
}

function showConsentBar() {
  const bar = document.createElement('div');
  bar.setAttribute('role', 'region');
  bar.setAttribute('aria-label', 'Cookie consent');
  bar.style.cssText = 'position:fixed;left:12px;right:12px;bottom:12px;z-index:1000;max-width:760px;margin:0 auto;' +
    'background:#17223A;color:#E8EDF7;border:1px solid #2C3A5A;border-radius:12px;padding:14px 16px;' +
    'display:flex;flex-wrap:wrap;gap:12px;align-items:center;font:14px/1.45 "IBM Plex Sans",system-ui,sans-serif;' +
    'box-shadow:0 8px 24px rgba(0,0,0,.4)';
  bar.innerHTML =
    '<span style="flex:1 1 320px">We use analytics cookies (Google Analytics) to understand how FINILA is used. We never sell your data or share it for advertising.</span>' +
    '<span style="display:flex;gap:8px">' +
    '<button type="button" data-v="no" style="height:40px;padding:0 14px;border-radius:8px;border:1px solid #2C3A5A;background:transparent;color:#E8EDF7;font:inherit;cursor:pointer">Decline</button>' +
    '<button type="button" data-v="yes" style="height:40px;padding:0 16px;border-radius:8px;border:0;background:#F2B33D;color:#1A1305;font:inherit;font-weight:600;cursor:pointer">Accept</button>' +
    '</span>';
  bar.addEventListener('click', e => {
    const v = e.target.dataset && e.target.dataset.v;
    if (!v) return;
    saveConsent(v);
    bar.remove();
    if (v === 'yes') loadAnalytics();
  });
  document.body.appendChild(bar);
}

(function () {
  const c = readConsent();
  if (c === 'yes') loadAnalytics();
  else if (c !== 'no') showConsentBar();
})();
