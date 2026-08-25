// content.js — ScamShield v3.0
// Extracts job/email text from the active page and returns it to the popup.
//
// KEY FIX (2025-08-08): LinkedIn now uses 100% obfuscated CSS class names.
// The ONLY reliable selectors are id-based: [id^="JobDetails_AboutTheJob_"]
// Confirmed via live DOM inspection using Chrome DevTools MCP.

// ── Self-destruction guard ─────────────────────────────────────────────────────
(() => {
if (window.__scamshield_v3_active) {
  return;
}
window.__scamshield_v3_active = true;

// ── Context validity guard ─────────────────────────────────────────────────────
// chrome.runtime.id becomes undefined when context is invalidated by extension reload.
// We check this BEFORE every chrome.* API call to prevent the thrown error.
function isContextValid() {
  try {
    // chrome.runtime.id is undefined when extension context is gone
    return typeof chrome !== 'undefined' &&
           chrome.runtime != null &&
           typeof chrome.runtime.id === 'string' &&
           chrome.runtime.id.length > 0;
  } catch (e) {
    return false;
  }
}

// ── Expand LinkedIn "see more" buttons ────────────────────────────────────────
// Covers all known LinkedIn button patterns for expanding truncated descriptions.
function expandSeeMore() {
  try {
    // Selector-based patterns (class/aria — updated for 2025/2026 LinkedIn)
    const patterns = [
      'button.inline-show-more-text__button',
      'button[aria-label*="see more"]',
      'button[aria-label*="See more"]',
      'button[aria-label*="Show more"]',
      'button[aria-label*="show more"]',
      '.jobs-description__footer-button',
      '.jobs-description-details__show-more-button',
      '.feed-shared-inline-show-more-text__see-more-less-toggle',
      '[class*="show-more"] button',
      '[class*="ShowMore"] button',
      '[class*="see-more"] button',
    ];
    patterns.forEach(sel => {
      try { document.querySelectorAll(sel).forEach(b => { try { b.click(); } catch(e) {} }); } catch(e) {}
    });
    // Text-content match — click any button/span whose label is literally "See more" / "Show more"
    document.querySelectorAll('button, span[role="button"]').forEach(b => {
      try {
        const t = (b.innerText || b.textContent || '').trim().toLowerCase();
        if (t === 'see more' || t === 'show more' || t === '…see more') b.click();
      } catch(e) {}
    });
  } catch (e) {}
}

// ── Auto-scroll to trigger lazy-loaded job details ────────────────────────────
function autoScrollJobPage() {
  return new Promise(resolve => {
    try {
      expandSeeMore();
      // Use document.scrollingElement for reliable scrolling on LinkedIn SPA
      const scroller = document.scrollingElement || document.documentElement || document.body;
      const totalHeight = scroller.scrollHeight || 0;

      if (totalHeight <= 200) { resolve(); return; }

      const step = Math.max(200, Math.floor(totalHeight / 5));
      let current = 0;
      let done = false;

      const timer = setInterval(() => {
        current += step;
        try { scroller.scrollTop = current; } catch (e) {}
        if (current >= totalHeight || done) {
          clearInterval(timer);
          try { scroller.scrollTop = 0; } catch (e) {}
          setTimeout(() => { expandSeeMore(); resolve(); }, 300);
        }
      }, 200);

      // Hard cap: never spend more than 2s scrolling
      setTimeout(() => {
        done = true;
        clearInterval(timer);
        try { scroller.scrollTop = 0; } catch (e) {}
        expandSeeMore();
        resolve();
      }, 2000);
    } catch (e) {
      resolve();
    }
  });
}

// ── Get the LinkedIn job description text ─────────────────────────────────────
// LinkedIn 2025/2026 uses id="JobDetails_AboutTheJob_<jobId>" for the description.
// All CSS class names are obfuscated hashes (e.g. _6ebd00b4 _8ba049e9) and change
// with every deploy. Only id-based and aria-label selectors are stable.
function extractLinkedInJobDescription() {
  // PRIMARY: stable id-based selector (confirmed working via live DOM inspection)
  const byId = document.querySelector('[id^="JobDetails_AboutTheJob"]');
  if (byId && byId.innerText.trim().length > 50) {
    return byId.innerText.trim();
  }

  // SECONDARY: try legacy CSS selectors (may work on older LinkedIn layouts)
  const legacySelectors = [
    '#job-details',
    '.jobs-description-content__text',
    '.jobs-description__container',
    '.jobs-description',
    '.jobs-box__html-content',
    '.show-more-less-html__markup',
  ];
  for (const sel of legacySelectors) {
    try {
      const el = document.querySelector(sel);
      if (el && el.innerText.trim().length > 50) return el.innerText.trim();
    } catch (e) {}
  }

  // TERTIARY: look for any rich div with id containing "AboutTheJob" or "job-details"
  const richById = document.querySelector(
    '[id*="AboutTheJob"], [id*="job-details"], [id*="jobDescription"]'
  );
  if (richById && richById.innerText.trim().length > 50) {
    return richById.innerText.trim();
  }

  return '';
}

// ── Find all stable LinkedIn job detail IDs ────────────────────────────────────
function getLinkedInMetadataFromDOM() {
  // Extract the jobId from URL for id-based lookups
  const jobIdMatch = window.location.href.match(/currentJobId=(\d+)|\/jobs\/view\/(\d+)/);
  const jobId = jobIdMatch ? (jobIdMatch[1] || jobIdMatch[2]) : '';

  // Company name — from page title (format: "Job Title | Company | LinkedIn")
  let company = '';
  const titleParts = document.title.split('|').map(p => p.trim());
  if (titleParts.length >= 3) {
    const candidate = titleParts[titleParts.length - 2];
    if (candidate && candidate.toLowerCase() !== 'linkedin') company = candidate;
  } else if (titleParts.length === 2 && titleParts[1].toLowerCase().includes('linkedin')) {
    company = titleParts[0];
  }

  // Job title — from page title (first part before |)
  let jobTitle = '';
  if (titleParts.length >= 2 && !titleParts[0].toLowerCase().startsWith('jobs for')) {
    jobTitle = titleParts[0];
  }

  // Recruiter/poster — look for the hiring team card by stable aria/role attributes
  let posterName = '';
  let posterHeadline = '';
  let posterUrl = '';

  // LinkedIn hiring team card uses aria-label and data attributes that are stable
  const hiringCard = document.querySelector(
    '[data-view-name="profile-entity-lockup"], ' +
    '.hirer-card__hirer-information, ' +
    '.jobs-poster, ' +
    '.jobs-hiring-team-widget'
  );
  if (hiringCard) {
    // The poster name is in the first anchor or strong text within the card
    const nameLink = hiringCard.querySelector('a[href*="/in/"], strong, b');
    if (nameLink) posterName = nameLink.innerText.trim().split('\n')[0];
    const headlineEl = hiringCard.querySelector('p, span:not(a span)');
    if (headlineEl) posterHeadline = headlineEl.innerText.trim().split('\n')[0];
    const linkEl = hiringCard.querySelector('a[href*="/in/"]');
    if (linkEl) posterUrl = (linkEl.getAttribute('href') || '').split('?')[0];
  }

  // Location — stable label/aria patterns
  const locationEl = document.querySelector('[aria-label*="location"], [aria-label*="Location"]');
  const location = locationEl ? locationEl.innerText.trim() : '';

  return { company, jobTitle, posterName, posterHeadline, posterUrl, location, jobId };
}

// ── Capture images from job description area ───────────────────────────────────
function captureJobImages() {
  const imageArea =
    document.querySelector('[id^="JobDetails_AboutTheJob"]') ||
    document.querySelector('#job-details, .jobs-description__container, .jobs-description');
  if (!imageArea) return [];

  const captured = [];
  for (const img of Array.from(imageArea.querySelectorAll('img'))) {
    const w = img.naturalWidth || img.width || 0;
    const h = img.naturalHeight || img.height || 0;
    const src = (img.src || '').toLowerCase();
    if (!src || src.startsWith('data:') || w < 120 || h < 120) continue;
    if (/icon|avatar|logo|sprite|ghost/.test(src)) continue;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      canvas.getContext('2d').drawImage(img, 0, 0);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
      if (dataUrl && dataUrl.length > 200) {
        captured.push({ src: img.src, dataUrl });
        if (captured.length >= 3) break;
      }
    } catch (e) {
      captured.push({ src: img.src, dataUrl: null });
      if (captured.length >= 3) break;
    }
  }
  return captured;
}

// ── Message handler ────────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // CRITICAL: Check context validity FIRST. If this is the old stale script
  // still running after an extension reload, bail out silently.
  if (!isContextValid()) return false;

  if (request.action === 'extract_text') {
    (async () => {
      let extractedText = '';
      const host = window.location.hostname;

      // Shared text helper
      const getText = (...selectors) => {
        for (const sel of selectors) {
          try {
            const el = document.querySelector(sel);
            if (el && el.innerText.trim()) return el.innerText.trim();
          } catch (e) {}
        }
        return '';
      };

      // ── LinkedIn ──────────────────────────────────────────────────────────
      if (host.includes('linkedin.com')) {
        const lnPath = window.location.pathname;

        // ── LinkedIn Job Listing ─────────────────────────────────────────────
        if (lnPath.includes('/jobs/')) {
          await autoScrollJobPage();

          // Extract using stable id-based selectors (2025/2026 LinkedIn)
          const { company, jobTitle, posterName, posterHeadline, posterUrl, location, jobId } =
            getLinkedInMetadataFromDOM();

          const metadata = {
            company,
            title: jobTitle,
            poster_name: posterName,
            poster_headline: posterHeadline,
            poster_url: posterUrl,
            location,
            job_id: jobId,
            source_type: 'linkedin_job',
            is_poster_verified: false,
            company_url: '',
          };

          console.log('[ScamShield v3] metadata:', metadata);

          // Get description text using stable selector
          extractedText = extractLinkedInJobDescription();

          // If still empty, synthesize from title + company + full page text
          if (extractedText.length < 80) {
            const bodyText = (document.body ? document.body.innerText : '').trim();
            extractedText = [
              `Job Title: ${jobTitle || 'Unknown'}`,
              `Company: ${company || 'Unknown'}`,
              `Page: ${document.title}`,
              '',
              bodyText
            ].join('\n');
          }

          console.log(`[ScamShield v3] extracted ${extractedText.length} chars`);

          const images = captureJobImages();
          sendResponse({
            text: extractedText,
            metadata,
            image_urls: images.map(i => i.src),
            image_data: images.filter(i => i.dataUrl).map(i => i.dataUrl)
          });
          return;

        // ── LinkedIn Profile ───────────────────────────────────────────────
        } else if (lnPath.startsWith('/in/')) {
          await new Promise(r => {
            window.scrollBy(0, 600);
            setTimeout(() => { window.scrollTo(0, 0); r(); }, 400);
          });

          const name = getText('h1.text-heading-xlarge', 'h1');
          const headline = getText('.text-body-medium.break-words');

          let aboutText = '';
          const aboutSection = Array.from(document.querySelectorAll('section'))
            .find(s => s.querySelector('[id="about"]'));
          if (aboutSection) aboutText = aboutSection.innerText.trim();

          let expText = '';
          const expSection = Array.from(document.querySelectorAll('section'))
            .find(s => s.querySelector('[id="experience"]'));
          if (expSection) expText = expSection.innerText.trim();

          sendResponse({
            text: `[PROFILE]\nName: ${name}\nHeadline: ${headline}\n\nABOUT:\n${aboutText}\n\nEXPERIENCE:\n${expText}`.slice(0, 4000),
            metadata: { poster_name: name, poster_headline: headline, source_type: 'linkedin_profile' },
            image_urls: [], image_data: []
          });
          return;

        // ── LinkedIn Feed Post ─────────────────────────────────────────────
        } else {
          // Try to find the focused post using stable data-urn attributes
          const POST_SELECTORS = [
            '[data-urn*="urn:li:activity"]',
            '[data-urn*="urn:li:ugcPost"]',
            '[data-id*="urn:li:activity"]',
            '.feed-shared-update-v2',
            'article',
          ];

          let focusedPost = null;
          for (const sel of POST_SELECTORS) {
            const found = Array.from(document.querySelectorAll(sel))
              .filter(el => !el.closest('[class*="aside"], [class*="sidebar"]'));
            if (found.length > 0) {
              // Pick the one closest to center of viewport
              const viewCenter = window.innerHeight / 2;
              let best = found[0], bestDist = Infinity;
              for (const el of found) {
                const r = el.getBoundingClientRect();
                if (r.bottom > 0 && r.top < window.innerHeight) {
                  const d = Math.abs(viewCenter - (r.top + r.height / 2));
                  if (d < bestDist) { bestDist = d; best = el; }
                }
              }
              focusedPost = best;
              break;
            }
          }

          if (!focusedPost) {
            const fallback = document.querySelector('main, #main, body');
            sendResponse({
              text: (fallback ? fallback.innerText : document.body.innerText).slice(0, 4000),
              metadata: { source_type: 'linkedin_post' },
              image_urls: [], image_data: []
            });
            return;
          }

          // Extract post text — stable attributes
          const postTextEl =
            focusedPost.querySelector('[class*="update-components-text"] [class*="break-words"]') ||
            focusedPost.querySelector('[class*="feed-shared-text"] [class*="break-words"]') ||
            focusedPost.querySelector('[class*="update-components-text"]') ||
            focusedPost.querySelector('[class*="feed-shared-text"]');

          extractedText = postTextEl
            ? postTextEl.innerText.trim()
            : focusedPost.innerText.slice(0, 3000).trim();

          // Author from stable aria attributes
          const nameEl =
            focusedPost.querySelector('[class*="actor__name"] span[aria-hidden="true"]') ||
            focusedPost.querySelector('[data-anonymize="person-name"]');
          const authorName = nameEl ? nameEl.innerText.trim().split('\n')[0] : '';

          const bioEl = focusedPost.querySelector('[class*="actor__description"] span[aria-hidden="true"]');
          const authorBio = bioEl ? bioEl.innerText.trim().split('\n')[0] : '';

          // Images
          const postImgs = Array.from(focusedPost.querySelectorAll('img'))
            .filter(img => {
              const src = img.src || '';
              const w = img.naturalWidth || img.width || 0;
              const h = img.naturalHeight || img.height || 0;
              return src && w > 80 && h > 80 && !/profile|ghost|avatar|icon|emoji/.test(src);
            }).slice(0, 4);

          const postImageUrls = postImgs.map(i => i.src);
          const postImageData = [];
          for (const img of postImgs) {
            try {
              const c = document.createElement('canvas');
              c.width = img.naturalWidth || img.width;
              c.height = img.naturalHeight || img.height;
              c.getContext('2d').drawImage(img, 0, 0);
              const d = c.toDataURL('image/jpeg', 0.8);
              if (d && d.length > 200) postImageData.push(d);
            } catch (e) {}
          }

          sendResponse({
            text: extractedText,
            metadata: {
              poster_name: authorName, poster_headline: authorBio,
              source_type: 'linkedin_post', has_images: postImgs.length > 0
            },
            image_urls: postImageUrls, image_data: postImageData
          });
          return;
        }

      // ── Gmail ─────────────────────────────────────────────────────────────
      } else if (host.includes('mail.google.com')) {
        const bodyEls = document.querySelectorAll('.a3s.aiL');
        extractedText = bodyEls.length > 0
          ? bodyEls[bodyEls.length - 1].innerText
          : (document.querySelector('[data-message-id] .ii.gt')?.innerText || document.body.innerText);

        sendResponse({
          text: extractedText,
          metadata: {
            poster_name: getText('.gD', '.go') || '',
            title: document.querySelector('h2.hP')?.innerText || '',
            location: 'gmail'
          }
        });
        return;

      // ── Internshala ───────────────────────────────────────────────────────
      } else if (host.includes('internshala.com')) {
        const jobDesc = document.querySelector('.text-container, .job-description');
        sendResponse({
          text: jobDesc ? jobDesc.innerText : document.body.innerText,
          metadata: {
            company: getText('.company_name'),
            title: getText('.profile_on_detail_page'),
            location: getText('#location_names', '.location_link')
          }
        });
        return;

      // ── Naukri ────────────────────────────────────────────────────────────
      } else if (host.includes('naukri.com')) {
        const jobDesc = document.querySelector('.job-desc, #job-description');
        sendResponse({
          text: jobDesc ? jobDesc.innerText : document.body.innerText,
          metadata: {
            company: getText('.jd-header-comp-name', '.comp-dtls-wrap a'),
            title: getText('.jd-header h1', '[class*="title"]'),
            location: getText('.loc', '.location')
          }
        });
        return;

      // ── Generic fallback ──────────────────────────────────────────────────
      } else {
        const main = document.querySelector('main');
        sendResponse({ text: (main || document.body).innerText });
        return;
      }
    })();

    return true; // Keep message channel open for async sendResponse

  } else if (request.action === 'update_badges') {
    if (!isContextValid()) return false;
    updateJobCards();
    sendResponse({ success: true });
  }

  return true;
});

// ── Job Card Badges ────────────────────────────────────────────────────────────
// Shows trust score badges on LinkedIn job list cards for previously scanned jobs.
function updateJobCards() {
  if (!isContextValid()) return;
  if (!window.location.hostname.includes('linkedin.com')) return;

  try {
    chrome.storage.local.get(['scamshield_history'], result => {
      if (!isContextValid() || (chrome.runtime.lastError)) return;
      const history = result.scamshield_history || [];
      if (!history.length) return;

      // LinkedIn job cards — these class names ARE stable (BEM-style component names)
      document.querySelectorAll('.job-card-container').forEach(card => {
        if (card.querySelector('.scamshield-badge')) return; // already tagged

        const link = card.querySelector('.job-card-container__link, a[href*="/jobs/view/"]');
        if (!link) return;

        const cardUrl = (link.href || '').split('?')[0];
        const match = history.find(h => cardUrl && h.url && cardUrl.includes(h.url.split('?')[0]));
        if (!match) return;

        const trustScore = 100 - match.risk_score;
        const color = match.color === 'red' ? '#f44336' : match.color === 'orange' ? '#ff9800' : '#4caf50';
        const icon  = match.color === 'red' ? '🚨' : match.color === 'orange' ? '⚠️' : '✅';

        const badge = document.createElement('div');
        badge.className = 'scamshield-badge';
        badge.innerHTML = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:4px;vertical-align:middle;"></span>${icon} ${trustScore} Trust`;
        badge.style.cssText = 'display:inline-flex;align-items:center;font-size:11px;font-weight:600;background:#1a1a1a;color:#fff;padding:2px 8px;border-radius:12px;margin-top:4px;border:1px solid #333;cursor:default;';

        (card.querySelector('.job-card-container__metadata-wrapper') || card).appendChild(badge);
      });
    });
  } catch (e) {
    // Context gone — stop silently
  }
}

// ── MutationObserver for badge refresh ────────────────────────────────────────
// Watches for new job cards loaded as user scrolls the job list.
let _observerActive = false;
try {
  const _badgeObserver = new MutationObserver(mutations => {
    // Self-terminate if context is gone
    if (!isContextValid()) {
      _badgeObserver.disconnect();
      _observerActive = false;
      return;
    }
    for (const m of mutations) {
      if (m.addedNodes.length > 0) {
        updateJobCards();
        break;
      }
    }
  });
  _badgeObserver.observe(document.body, { childList: true, subtree: true });
  _observerActive = true;
} catch (e) {}

// ── Pre-Apply Blocking Overlay ─────────────────────────────────────────────────
// Intercepts clicks on Apply buttons and warns user if job is unscanned or risky.
document.addEventListener('click', e => {
  if (!isContextValid()) return;

  const applyBtn = e.target.closest('.jobs-apply-button, button[aria-label*="Apply"]');
  if (!applyBtn || applyBtn.classList.contains('scamshield-allowed')) return;

  const currentUrl = window.location.href.split('?')[0];

  try {
    chrome.storage.local.get(['scamshield_history'], result => {
      if (!isContextValid() || chrome.runtime.lastError) return;
      const history = result.scamshield_history || [];
      const match = history.find(h => h.url && currentUrl.includes(h.url.split('?')[0]));

      if (match) {
        const trustScore = 100 - match.risk_score;
        if (trustScore < 50) {
          e.preventDefault();
          e.stopPropagation();
          _showBlockingOverlay(trustScore, match.verdict, applyBtn, false);
        }
      } else {
        // Not scanned yet — soft warning
        e.preventDefault();
        e.stopPropagation();
        _showBlockingOverlay('?', 'Not Scanned', applyBtn, true);
      }
    });
  } catch (e2) {
    // Context gone — let click through
  }
}, true);

function _showBlockingOverlay(score, verdict, originalBtn, isUnscanned = false) {
  const existing = document.getElementById('scamshield-blocker');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = 'scamshield-blocker';
  overlay.style.cssText = [
    'position:fixed;top:0;left:0;width:100vw;height:100vh',
    'background:rgba(0,0,0,0.88);backdrop-filter:blur(8px)',
    'z-index:999999;display:flex;align-items:center;justify-content:center',
    'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif'
  ].join(';');

  const title = isUnscanned ? 'Hold on a second! 🛡️' : '⚠️ High Scam Risk Detected';
  const desc  = isUnscanned
    ? "You haven't scanned this job with ScamShield yet. We strongly recommend scanning before you apply."
    : `This job has a Trust Score of <strong style="color:#f44336">${score}/100</strong> and is flagged as <strong>${verdict}</strong>. Applying may expose your personal data to fraudsters.`;

  overlay.innerHTML = `
    <div style="background:#111;border:1px solid #333;padding:32px;border-radius:16px;max-width:450px;width:90%;text-align:center;color:#fff;box-shadow:0 24px 48px rgba(0,0,0,0.5)">
      <div style="font-size:52px;margin-bottom:16px">${isUnscanned ? '🛡️' : '🚨'}</div>
      <h2 style="margin:0 0 12px;font-size:22px;font-weight:700">${title}</h2>
      <p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:#aaa">${desc}</p>
      <div style="display:flex;justify-content:center;gap:12px;flex-wrap:wrap">
        ${isUnscanned ? '<button id="ss-scan" style="background:#0a66c2;color:#fff;border:none;padding:10px 20px;border-radius:100px;font-weight:600;cursor:pointer;font-size:14px">Scan Job Now</button>' : ''}
        <button id="ss-proceed" style="background:transparent;color:#888;border:1px solid #444;padding:10px 20px;border-radius:100px;font-weight:600;cursor:pointer;font-size:14px">
          ${isUnscanned ? 'Apply Without Scanning' : 'Proceed Anyway (Risky)'}
        </button>
      </div>
      <button id="ss-cancel" style="background:none;border:none;color:#666;margin-top:20px;cursor:pointer;text-decoration:underline;font-size:13px">Cancel and Go Back</button>
    </div>`;

  document.body.appendChild(overlay);

  if (isUnscanned) {
    document.getElementById('ss-scan').onclick = () => {
      overlay.remove();
      alert('Click the ScamShield 🛡️ icon in your browser toolbar to scan this job!');
    };
  }
  document.getElementById('ss-proceed').onclick = () => {
    overlay.remove();
    originalBtn.classList.add('scamshield-allowed');
    originalBtn.click();
  };
  document.getElementById('ss-cancel').onclick = () => overlay.remove();
}
})();

