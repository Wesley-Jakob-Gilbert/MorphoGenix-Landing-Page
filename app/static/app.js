// MorphoGenix waitlist form handler.
// Extracted from index.html so we can set a strict Content-Security-Policy
// that forbids inline scripts ('unsafe-inline' is dropped in production).

(function () {
  const form = document.getElementById('waitlist-form');
  const btn = document.getElementById('submit-btn');
  const msg = document.getElementById('form-msg');
  if (!form || !btn || !msg) return;

  const pageLoadedAt = Date.now();

  // Share-card elements (may be absent if the template is older).
  const shareCard = document.getElementById('share-card');
  const shareCardMsg = document.getElementById('share-card-msg');
  const shareX = document.getElementById('share-x');
  const shareSms = document.getElementById('share-sms');
  const shareEmail = document.getElementById('share-email');
  const shareCopy = document.getElementById('share-copy');
  const shareCopyLabel = document.getElementById('share-copy-label');

  // Canonical landing-page URL used in every share link. Prefer the live
  // custom domain so the link is identical no matter what host the visitor
  // came in on (apex, www, or fly.dev preview).
  const SHARE_URL = 'https://morphogenix.ai';
  const SHARE_TEXT =
    'Cool new biotech device for jaw/bruxism/mewing tracking. Worth a look:';

  function showMsg(text, ok) {
    msg.textContent = text;
    msg.className =
      'mt-4 text-sm rounded-lg px-4 py-3 ' +
      (ok
        ? 'bg-neon/10 border border-neon/30 text-neon'
        : 'bg-red-500/10 border border-red-500/30 text-red-300');
    msg.classList.remove('hidden');
  }

  function showShareCard(serverMsg) {
    if (!shareCard) {
      // Older template without share card — fall back to the inline success bubble.
      showMsg(serverMsg || "You're in. We'll reach out when the first cohort opens.", true);
      return;
    }
    if (shareCardMsg && serverMsg) {
      shareCardMsg.textContent = serverMsg;
    }
    // Hide the form (and any leftover inline message), reveal the share card.
    form.classList.add('hidden');
    msg.classList.add('hidden');
    shareCard.classList.remove('hidden');
    // Scroll the share card into view so the user actually sees it on small screens.
    shareCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function wireShareLinks() {
    if (!shareCard) return;
    const text = encodeURIComponent(SHARE_TEXT + ' ' + SHARE_URL);
    const textNoUrl = encodeURIComponent(SHARE_TEXT);
    const url = encodeURIComponent(SHARE_URL);
    const subject = encodeURIComponent('Thought you might like this — MorphoGenix');
    const emailBody = encodeURIComponent(SHARE_TEXT + '\n\n' + SHARE_URL);

    if (shareX) {
      // X wants ?text= and ?url= as separate params (it builds the tweet itself).
      shareX.setAttribute(
        'href',
        'https://twitter.com/intent/tweet?text=' + textNoUrl + '&url=' + url
      );
    }
    if (shareSms) {
      // sms: URI — the ?body= form works on iOS and modern Android.
      shareSms.setAttribute('href', 'sms:?&body=' + text);
    }
    if (shareEmail) {
      shareEmail.setAttribute(
        'href',
        'mailto:?subject=' + subject + '&body=' + emailBody
      );
    }
    if (shareCopy) {
      shareCopy.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(SHARE_URL);
          if (shareCopyLabel) {
            const original = shareCopyLabel.textContent;
            shareCopyLabel.textContent = 'Copied';
            shareCopy.classList.add('text-neon', 'border-neon/60');
            setTimeout(() => {
              shareCopyLabel.textContent = original;
              shareCopy.classList.remove('text-neon', 'border-neon/60');
            }, 2000);
          }
        } catch (_err) {
          // Clipboard API can fail on older browsers / non-HTTPS. Fall back to
          // selecting the URL so the user can copy manually.
          window.prompt('Copy this link:', SHARE_URL);
        }
      });
    }
  }
  wireShareLinks();

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
        form.reset();
        // Reset Turnstile widget so it can be submitted again if needed.
        if (window.turnstile && typeof window.turnstile.reset === 'function') {
          window.turnstile.reset();
        }
        // Swap the form out for the share card (or fall back to inline message).
        showShareCard(data.message);
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
