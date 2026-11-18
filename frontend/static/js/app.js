/* SaveLoop frontend: URL bar, platform detection, extraction states. */
(() => {
  'use strict';

  const API_URL = '/api/extract';
  const DEMO = new URLSearchParams(location.search).has('demo');

  const $ = (id) => document.getElementById(id);
  const form = $('extract-form');
  const input = $('post-url');
  const toggleBtn = $('paste-toggle');
  const submitBtn = $('submit-btn');
  const badgeLabel = $('badge-label');
  const badges = document.querySelectorAll('.platform-badge');
  const states = { loading: $('state-loading'), result: $('state-result'), error: $('state-error') };

  const PLATFORMS = {
    instagram: { name: 'Instagram', test: /(^|\.)(instagram\.com|instagr\.am)$/ },
    facebook: { name: 'Facebook', test: /(^|\.)(facebook\.com|fb\.watch|fb\.com)$/ },
    x: { name: 'X', test: /(^|\.)(x\.com|twitter\.com)$/ },
  };

  const ERRORS = {
    empty: ['Paste a link first', 'Copy a link from Instagram, Facebook or X, then tap Paste.'],
    invalid_url: ["That doesn't look like a link", 'Check the link and try again. It should start with https://'],
    unsupported_platform: ["That site isn't supported yet", 'SaveLoop works with public posts from Instagram, Facebook and X.'],
    private: ['This post is private', 'SaveLoop can only save media from public posts. Try a different link.'],
    not_found: ['Post not found', 'It may have been deleted, or the link is incomplete.'],
    no_video: ['No video in this post', 'This post only has photos. SaveLoop can save videos and GIFs for now.'],
    rate_limited: ['Too many requests', 'Please wait a moment and try again.'],
    extraction_failed: ["We couldn't get this one", 'Something went wrong while fetching the media. Please try again.'],
    network: ["Can't reach SaveLoop", 'Check your connection and try again.'],
  };

  let current = null; // last extraction result
  let selectedQuality = null;
  let inFlight = null;

  /* ---------- Platform detection ---------- */
  function parseUrl(value) {
    const v = value.trim();
    if (!v) return null;
    try {
      const u = new URL(/^https?:\/\//i.test(v) ? v : `https://${v}`);
      return u.protocol === 'https:' || u.protocol === 'http:' ? u : null;
    } catch {
      return null;
    }
  }

  function detectPlatform(value) {
    const u = parseUrl(value);
    if (!u) return '';
    const host = u.hostname.toLowerCase().replace(/^www\.|^m\.|^mobile\./, '');
    return Object.keys(PLATFORMS).find((k) => PLATFORMS[k].test.test(host)) || '';
  }

  function renderBadges() {
    const platform = detectPlatform(input.value);
    badgeLabel.textContent = platform ? 'Detected' : 'Works with';
    badges.forEach((b) => {
      const on = b.dataset.platform === platform;
      b.classList.toggle('bg-forest', on);
      b.classList.toggle('border-forest', on);
      b.classList.toggle('text-white', on);
      b.classList.toggle('text-[#4B4A5E]', !on);
      b.classList.toggle('border-line-strong', !on);
      const dot = b.firstElementChild;
      dot.classList.toggle('bg-white', on);
      dot.classList.toggle('bg-[#B3A994]', !on);
    });
  }

  /* ---------- Paste / Clear toggle ---------- */
  function renderToggle() {
    const has = input.value.trim().length > 0;
    toggleBtn.querySelector('[data-label]').textContent = has ? 'Clear' : 'Paste';
    toggleBtn.querySelector('[data-icon="paste"]').classList.toggle('hidden', has);
    toggleBtn.querySelector('[data-icon="clear"]').classList.toggle('hidden', !has);
    toggleBtn.setAttribute('aria-label', has ? 'Clear the link' : 'Paste a link from your clipboard');
  }

  async function onToggle() {
    if (input.value.trim()) {
      input.value = '';
      showState(null);
      onInput();
      input.focus();
      return;
    }
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        input.value = text.trim();
        onInput();
        return;
      }
    } catch {
      /* Clipboard blocked: fall through and let the person paste manually. */
    }
    input.focus();
  }

  function onInput() {
    renderBadges();
    renderToggle();
    if (!states.error.classList.contains('hidden')) showState(null);
  }

  /* ---------- States ---------- */
  function showState(name) {
    Object.entries(states).forEach(([k, el]) => el.classList.toggle('hidden', k !== name));
  }

  function showError(code, message) {
    const [title, body] = ERRORS[code] || ERRORS.extraction_failed;
    $('error-title').textContent = title;
    $('error-body').textContent = message || body;
    showState('error');
  }

  function setBusy(busy) {
    submitBtn.disabled = busy;
    submitBtn.querySelector('[data-label]').textContent = busy ? 'Finding…' : 'Download';
  }

  /* ---------- Extraction ---------- */
  async function onSubmit(e) {
    e.preventDefault();
    const value = input.value.trim();
    if (!value) return showError('empty');
    if (!parseUrl(value)) return showError('invalid_url');
    if (!detectPlatform(value)) return showError('unsupported_platform');

    if (inFlight) inFlight.abort();
    inFlight = new AbortController();
    setBusy(true);
    showState('loading');

    try {
      const data = DEMO ? await mockExtract(value) : await extract(value, inFlight.signal);
      renderResult(data);
      showState('result');
    } catch (err) {
      if (err.name === 'AbortError') return;
      showError(err.code || 'network', err.serverMessage);
    } finally {
      setBusy(false);
    }
  }

  async function extract(url, signal) {
    let res;
    try {
      res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
        signal,
      });
    } catch (err) {
      if (err.name === 'AbortError') throw err;
      throw Object.assign(new Error('network'), { code: 'network' });
    }
    let body = null;
    try { body = await res.json(); } catch { /* non-JSON response */ }
    if (!res.ok) {
      const code = body?.error?.code || (res.status === 429 ? 'rate_limited' : 'extraction_failed');
      throw Object.assign(new Error(code), { code });
    }
    return body;
  }

  /* ---------- Result card ---------- */
  function formatDuration(sec) {
    if (!Number.isFinite(sec)) return '';
    const s = Math.round(sec);
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  }

  function initials(handle) {
    const clean = (handle || '').replace(/^@/, '').replace(/[^a-z0-9]/gi, '');
    return (clean.slice(0, 2) || 'SL').toUpperCase();
  }

  function renderResult(data) {
    current = data;
    const formats = Array.isArray(data.formats) ? data.formats : [];
    const videos = formats.filter((f) => f.type === 'video');
    const extras = formats.filter((f) => f.type !== 'video');

    const thumb = $('result-thumb');
    if (data.thumbnail) {
      thumb.src = data.thumbnail;
      thumb.classList.remove('hidden');
    } else {
      thumb.removeAttribute('src');
      thumb.classList.add('hidden');
    }

    const duration = formatDuration(data.duration);
    $('result-duration-chip').textContent = duration;
    $('result-duration-chip').classList.toggle('hidden', !duration);
    $('result-avatar').textContent = initials(data.creator);
    $('result-creator').textContent = data.creator || 'Unknown creator';
    const platformName = PLATFORMS[data.platform]?.name || '';
    const dims = data.width && data.height ? `${data.width} × ${data.height}` : '';
    $('result-meta').textContent = [platformName && `${platformName} ${data.kind || ''}`.trim(), duration, dims].filter(Boolean).join(' · ');

    // Quality options
    const group = $('quality-group');
    const options = $('quality-options');
    options.replaceChildren();
    group.classList.toggle('hidden', videos.length === 0);
    selectedQuality = videos[0]?.id || null;
    videos.forEach((f) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('role', 'radio');
      btn.dataset.id = f.id;
      btn.className = 'h-[42px] flex-1 rounded-xl text-sm font-bold transition';
      btn.textContent = f.quality || f.label;
      btn.addEventListener('click', () => { selectedQuality = f.id; renderPrimary(); });
      options.appendChild(btn);
    });

    // Extra formats (GIF, stickers)
    const extraWrap = $('extra-formats');
    extraWrap.querySelectorAll('a').forEach((a) => a.remove());
    extraWrap.classList.toggle('hidden', extras.length === 0);
    extras.forEach((f) => {
      const a = document.createElement('a');
      a.className = 'chip-btn inline-flex items-center';
      a.href = f.url;
      a.setAttribute('download', '');
      a.textContent = (f.ext || f.label || '').toUpperCase();
      a.setAttribute('aria-label', `Download as ${f.label || f.ext}`);
      extraWrap.appendChild(a);
    });

    renderPrimary();
  }

  function renderPrimary() {
    const formats = current?.formats || [];
    const videos = formats.filter((f) => f.type === 'video');
    const chosen = videos.find((f) => f.id === selectedQuality) || formats[0];

    $('quality-options').querySelectorAll('button').forEach((btn) => {
      const on = btn.dataset.id === selectedQuality;
      btn.setAttribute('aria-checked', String(on));
      btn.classList.toggle('bg-white', on);
      btn.classList.toggle('text-ink', on);
      btn.classList.toggle('shadow-seg', on);
      btn.classList.toggle('text-muted-soft', !on);
    });

    const link = $('primary-download');
    if (!chosen) { link.classList.add('hidden'); return; }
    link.classList.remove('hidden');
    link.href = chosen.url;
    link.setAttribute('download', '');
    const label = chosen.type === 'video'
      ? `Download ${(chosen.ext || 'mp4').toUpperCase()} · ${chosen.quality || ''}`.trim()
      : `Download ${(chosen.ext || '').toUpperCase()}`;
    link.querySelector('[data-label]').textContent = label;
  }

  /* ---------- Demo data (add ?demo to the URL) ---------- */
  function mockExtract(url) {
    const platform = detectPlatform(url);
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        if (/private/i.test(url)) return reject(Object.assign(new Error('private'), { code: 'private' }));
        resolve({
          platform,
          kind: platform === 'x' ? 'Post' : 'Reel',
          creator: '@sample_creator',
          duration: 24,
          width: 1080,
          height: 1920,
          thumbnail: null,
          formats: [
            { id: 'v1080', type: 'video', ext: 'mp4', quality: '1080p', label: 'MP4 1080p', url: '#' },
            { id: 'v720', type: 'video', ext: 'mp4', quality: '720p', label: 'MP4 720p', url: '#' },
            { id: 'v480', type: 'video', ext: 'mp4', quality: '480p', label: 'MP4 480p', url: '#' },
            { id: 'gif', type: 'gif', ext: 'gif', label: 'GIF loop', url: '#' },
            { id: 'webp', type: 'image', ext: 'webp', label: 'WEBP sticker', url: '#' },
            { id: 'png', type: 'image', ext: 'png', label: 'PNG sticker', url: '#' },
          ],
        });
      }, 1200);
    });
  }

  /* ---------- Wire up ---------- */
  input.addEventListener('input', onInput);
  toggleBtn.addEventListener('click', onToggle);
  form.addEventListener('submit', onSubmit);
  $('error-dismiss').addEventListener('click', () => { showState(null); input.focus(); });
  document.querySelectorAll('[data-focus-input]').forEach((a) =>
    a.addEventListener('click', () => setTimeout(() => input.focus({ preventScroll: true }), 300)),
  );

  renderBadges();
  renderToggle();
})();
