// MorphoGenix waitlist form handler.
// Extracted from index.html so we can set a strict Content-Security-Policy
// that forbids inline scripts ('unsafe-inline' is dropped in production).

(function () {
  const form = document.getElementById('waitlist-form');
  const btn = document.getElementById('submit-btn');
  const msg = document.getElementById('form-msg');
  if (!form || !btn || !msg) return;

  const pageLoadedAt = Date.now();

  function showMsg(text, ok) {
    msg.textContent = text;
    msg.className =
      'mt-4 text-sm rounded-lg px-4 py-3 ' +
      (ok
        ? 'bg-neon/10 border border-neon/30 text-neon'
        : 'bg-red-500/10 border border-red-500/30 text-red-300');
    msg.classList.remove('hidden');
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(form);

    // Consent is required before submit.
    const consent = fd.get('consent');
    if (!consent) {
      showMsg('Please accept the privacy notice to continue.', false);
      return;
    }

    const payload = {
      email:   (fd.get('email')   || '').toString().trim(),
      name:    (fd.get('name')    || '').toString().trim() || null,
      persona: (fd.get('persona') || '').toString().trim() || null,
      reason:  (fd.get('reason')  || '').toString().trim() || null,
      // Honeypot — must remain empty. Bots fill every field; humans don't see this.
      website: (fd.get('website') || '').toString(),
      // Turnstile token (empty string if Turnstile is not configured).
      turnstile_token: (fd.get('cf-turnstile-response') || '').toString(),
      // Anti-bot: time spent on page before submit, in ms.
      elapsed_ms: Date.now() - pageLoadedAt,
    };

    btn.disabled = true;
    const labelEl = btn.querySelector('.label');
    const original = labelEl ? labelEl.textContent : btn.textContent;
    if (labelEl) labelEl.textContent = 'Sending…';

    try {
      const resp = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await resp.json().catch(() => ({}));
      if (resp.ok && data.ok) {
        showMsg(data.message || "You're in. We'll reach out when the first cohort opens.", true);
        form.reset();
        // Reset Turnstile widget so it can be submitted again if needed.
        if (window.turnstile && typeof window.turnstile.reset === 'function') {
          window.turnstile.reset();
        }
      } else if (resp.status === 429) {
        showMsg('Too many requests from your network. Give it a minute and try again.', false);
      } else {
        showMsg(data.message || 'Something went wrong. Try again?', false);
      }
    } catch (err) {
      showMsg('Network error. Try again in a moment.', false);
    } finally {
      btn.disabled = false;
      if (labelEl) labelEl.textContent = original;
    }
  });
})();
