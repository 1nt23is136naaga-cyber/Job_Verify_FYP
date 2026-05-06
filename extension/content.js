// content.js — ScamShield
// Extracts job/email text from the active page and returns it to the popup.

// Helper to expand LinkedIn 'see more' buttons
function expandSeeMore() {
  document.querySelectorAll(
    'button.inline-show-more-text__button, button.see-more, button.feed-shared-inline-show-more-text__see-more-less-toggle'
  ).forEach(b => {
    if (b.innerText.toLowerCase().includes('more') || b.innerText.toLowerCase().includes('see')) {
      try { b.click(); } catch(e){}
    }
  });
}

// Auto-scroll to trigger lazy-loaded job details
function autoScrollJobPage() {
  return new Promise(resolve => {
    const jobContainer = document.querySelector(
      '.jobs-description__container, .job-view-layout, main, #job-details'
    ) || document.body;
    
    const totalHeight = jobContainer.scrollHeight;
    const step = Math.floor(totalHeight / 4);
    let current = 0;
    
    const scroller = setInterval(() => {
      current += step;
      jobContainer.scrollTo({ top: current, behavior: 'smooth' });
      if (current >= totalHeight) {
        clearInterval(scroller);
        // Scroll back to top and wait for renders
        setTimeout(() => {
          jobContainer.scrollTo({ top: 0, behavior: 'instant' });
          expandSeeMore(); // click any newly revealed 'see more' buttons
          resolve();
        }, 400);
      }
    }, 250);
  });
}

// Capture relevant images from job description as base64 data URLs
function captureJobImages() {
  const imageArea = document.querySelector(
    '#job-details, .jobs-description__container, .jobs-description, main'
  );
  if (!imageArea) return [];
  
  const imgs = Array.from(imageArea.querySelectorAll('img'));
  const captured = [];
  
  for (const img of imgs) {
    // Skip tiny icons, avatars, and SVGs
    const w = img.naturalWidth || img.width;
    const h = img.naturalHeight || img.height;
    if (!img.src || img.src.startsWith('data:') || w < 80 || h < 80) continue;
    if (img.src.includes('icon') || img.src.includes('avatar') || img.src.includes('logo') || img.src.includes('sprite')) continue;
    
    try {
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
      if (dataUrl && dataUrl.length > 100) {
        captured.push({ src: img.src, dataUrl });
        if (captured.length >= 4) break; // max 4 images
      }
    } catch(e) {
      // Cross-origin images can't be canvas'd — send URL only
      captured.push({ src: img.src, dataUrl: null });
    }
  }
  return captured;
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract_text') {
    (async () => {
    let extractedText = '';
    const host = window.location.hostname;

    // Shared helper — works in any scope
    const getText = (...selectors) => {
      for (const sel of selectors) {
        try {
          const el = document.querySelector(sel);
          if (el && el.innerText.trim()) return el.innerText.trim();
        } catch(e){}
      }
      return '';
    };

    if (host.includes('linkedin.com')) {
      const lnPath = window.location.pathname;

      if (lnPath.includes('/jobs/')) {
        // ── LinkedIn Job Listing (/jobs/view/ or /jobs/search/) ─────────────
        // Step 1: Auto-scroll to trigger lazy-loaded content
        await autoScrollJobPage();

        // ── Step 2: Identify the active job detail panel ───────────────────
        const detailPanel =
        document.querySelector('.jobs-search__job-details') ||
        document.querySelector('.jobs-details')             ||
        document.querySelector('.job-view-layout')          ||
        document.querySelector('main');

      // Scoped querySelector helper — only looks inside detailPanel
      const $ = (sel) => { try { return detailPanel.querySelector(sel); } catch(e){ return null; } };
      const $t = (...sels) => {
        for (const s of sels) { const el = $(s); if (el?.innerText?.trim()) return el.innerText.trim(); }
        return '';
      };

      // ── Step 3: Extract company name ──────────────────────────────────────
      // MOST RELIABLE: page title format is "Job Title | Company | LinkedIn"
      let company = '';
      const titleParts = document.title.split('|').map(p => p.trim());
      if (titleParts.length >= 3) {
        // Last part is "LinkedIn", second-to-last is company
        const candidate = titleParts[titleParts.length - 2];
        if (candidate && candidate.toLowerCase() !== 'linkedin') company = candidate;
      }
      // CSS fallback if title parsing failed
      if (!company) {
        company = $t(
          '.job-details-jobs-unified-top-card__company-name a',
          '.job-details-jobs-unified-top-card__company-name',
          '.jobs-unified-top-card__company-name a',
          '.jobs-unified-top-card__company-name',
          '.jobs-details-top-card__company-url'
        );
      }

      // ── Step 4: Extract job title ─────────────────────────────────────────
      // Title format sometimes: "Company Name · Job Title" — clean it
      let jobTitle = $t(
        '.job-details-jobs-unified-top-card__job-title h1',
        '.job-details-jobs-unified-top-card__job-title',
        '.jobs-unified-top-card__job-title h1',
        '.jobs-unified-top-card__job-title',
        'h1.t-24', 'h1'
      );
      // Remove leading "Company ·" or "Company -" prefix if present
      if (company && jobTitle.toLowerCase().startsWith(company.toLowerCase())) {
        jobTitle = jobTitle.slice(company.length).replace(/^[\s·\-–—]+/, '').trim();
      }

      // ── Step 5: Extract recruiter — STRICTLY from hiring team card only ───
      // The .jobs-poster section is specifically the hiring manager card.
      // Do NOT use general name selectors that catch investor/about-company names.
      const posterCard =
        detailPanel.querySelector('.hirer-card__hirer-information') ||
        detailPanel.querySelector('.jobs-poster')                   ||
        detailPanel.querySelector('.jobs-hiring-team-widget');

      const posterName = posterCard
        ? (posterCard.querySelector('.app-aware-link, .jobs-poster__name, .jobs-hiring-team-widget__hiring-manager-name')?.innerText?.trim() || '')
        : '';

      const posterHeadline = posterCard
        ? (posterCard.querySelector('.jobs-poster__headline, .jobs-hiring-team-widget__hiring-manager-title')?.innerText?.trim() || '')
        : '';

      const posterUrl = (posterCard?.querySelector('a')?.getAttribute('href') || '').split('?')[0];

      // ── Step 6: Other metadata ────────────────────────────────────────────
      const metadata = {
        company,
        title: jobTitle,
        poster_name:      posterName,
        poster_headline:  posterHeadline,
        poster_url:       posterUrl,
        is_poster_verified: !!detailPanel.querySelector(
          '.jobs-poster__name-container .verified-badge, [aria-label*="Verified"]'
        ),
        company_url: ($('.job-details-jobs-unified-top-card__company-name a, .jobs-unified-top-card__company-name a')?.getAttribute('href') || '').split('?')[0],
        location: $t(
          '.job-details-jobs-unified-top-card__primary-description-without-tagline span',
          '.jobs-unified-top-card__bullet',
          '.jobs-details-top-card__bullet'
        ),
        applicants:  $t('.jobs-unified-top-card__applicant-count', '.job-details-jobs-unified-top-card__job-insight span'),
        is_promoted: !!$('.jobs-unified-top-card__promoted-status'),
        company_size:     $t('.jobs-company__inline-information', '.jobs-details-top-card__company-info'),
        company_industry: $t('.jobs-company__inline-information + .jobs-company__inline-information'),
        hiring_stats:     $t('.jobs-poster__hirer-context', '.jobs-hiring-team-widget__hirer-context')
      };

      console.log('ScamShield metadata:', metadata);

      // ── Step 7: Extract job description text (scoped to detail panel) ─────
      const descEl =
        detailPanel.querySelector('#job-details') ||
        detailPanel.querySelector('.jobs-description__container') ||
        detailPanel.querySelector('.jobs-description');
      extractedText = descEl ? descEl.innerText.trim() : (detailPanel.innerText || '');

      // ── Step 8: Capture images ────────────────────────────────────────────
      const images = captureJobImages();
      const imageUrls = images.map(i => i.src);
      const imageDataUrls = images.filter(i => i.dataUrl).map(i => i.dataUrl);

      sendResponse({ text: extractedText, metadata, image_urls: imageUrls, image_data: imageDataUrls });
      return;

      } else if (lnPath.startsWith('/in/')) {
        // ── LinkedIn User Profile Page ──────────────────────────────────────
        // Scrapes the person's profile to evaluate them directly
        
        // Auto-scroll slightly to trigger lazy loading of About/Experience
        await new Promise(r => {
          window.scrollBy(0, 500);
          setTimeout(() => { window.scrollTo(0, 0); r(); }, 300);
        });

        const $t = (sel) => {
          const el = document.querySelector(sel);
          return el ? el.innerText.trim() : '';
        };

        const name = $t('h1.text-heading-xlarge');
        const headline = $t('.text-body-medium.break-words');
        
        // Find About section
        let aboutText = '';
        const aboutCard = Array.from(document.querySelectorAll('section')).find(s => s.querySelector('div[id="about"]'));
        if (aboutCard) {
          const aboutContent = aboutCard.querySelector('.display-flex.ph5.pv3');
          if (aboutContent) aboutText = aboutContent.innerText.trim();
        }

        // Find Experience section
        let expText = '';
        const expCard = Array.from(document.querySelectorAll('section')).find(s => s.querySelector('div[id="experience"]'));
        if (expCard) {
          expText = expCard.innerText.trim();
        }

        const profileText = `[PROFILE EVALUATION]\nName: ${name}\nHeadline: ${headline}\n\nABOUT:\n${aboutText}\n\nEXPERIENCE:\n${expText}`;
        
        const meta = {
          poster_name: name,
          poster_headline: headline,
          source_type: 'linkedin_profile'
        };

        console.log(`ScamShield: Scraped profile for ${name}`);
        sendResponse({ text: profileText.slice(0, 4000), metadata: meta, image_urls: [], image_data: [] });
        return;

      } else {
      // ── LinkedIn Feed Post / Share URL ────────────────────────────────────
      // Handles: /feed/, /posts/..., /company/.../posts/

      let focusedPost = null;

      // Strategy 1: direct post detail page — single main article
      if (lnPath.includes('/posts/') || lnPath.includes('/pulse/')) {
        focusedPost =
          document.querySelector('.scaffold-layout__main [data-id]')   ||
          document.querySelector('.scaffold-layout__main article')      ||
          document.querySelector('[data-id*="urn:li:activity"]');
      }

      // Strategy 2: feed list — try every known post container selector
      if (!focusedPost) {
        const POST_SELECTORS = [
          '[data-id*="urn:li:activity"]',
          '[data-id*="urn:li:ugcPost"]',
          '[data-id*="urn:li:share"]',
          '.feed-shared-update-v2',
          'li.scaffold-finite-scroll__list-item',
          'article[data-id]',
          '.occludable-update',
        ];

        let candidates = [];
        for (const sel of POST_SELECTORS) {
          const found = Array.from(document.querySelectorAll(sel));
          if (found.length > 0) { candidates = found; break; }
        }

        // Pick the post closest to the CENTER of the viewport
        let closestDist = Infinity;
        const viewportCenter = window.innerHeight / 2;
        
        for (const post of candidates) {
          const rect = post.getBoundingClientRect();
          // Check if post is visible at all
          if (rect.bottom > 0 && rect.top < window.innerHeight) {
            const postCenter = rect.top + (rect.height / 2);
            const dist = Math.abs(viewportCenter - postCenter);
            if (dist < closestDist) {
              closestDist = dist;
              focusedPost = post;
            }
          }
        }
      }

      // Strategy 3: any container that has the hiring post text visible
      if (!focusedPost) {
        const mainArea = document.querySelector('.scaffold-layout__main, main, #main');
        if (mainArea) {
          // Use main area text — avoid document.body which starts with nav
          extractedText = mainArea.innerText.slice(0, 4000);
        }
        sendResponse({ text: extractedText || '', metadata: { source_type: 'linkedin_post' } });
        return;
      }

      // ── Extract author info ─────────────────────────────────────────────
      // Multiple selector attempts for LinkedIn's varying class names
      const nameEl =
        focusedPost.querySelector('.update-components-actor__name span[aria-hidden="true"]') ||
        focusedPost.querySelector('.update-components-actor__name span:not(.visually-hidden)') ||
        focusedPost.querySelector('.update-components-actor__name')     ||
        focusedPost.querySelector('.feed-shared-actor__name')           ||
        focusedPost.querySelector('[data-anonymize="person-name"]');

      const authorName = nameEl?.innerText?.trim().replace(/\n.*/s, '') || '';  // first line only

      const bioEl =
        focusedPost.querySelector('.update-components-actor__description span[aria-hidden="true"]') ||
        focusedPost.querySelector('.update-components-actor__description')  ||
        focusedPost.querySelector('.update-components-actor__subtitle')     ||
        focusedPost.querySelector('.feed-shared-actor__description');

      const authorBio = bioEl?.innerText?.trim().replace(/\n.*/s, '') || '';

      // ── Extract post text ONLY (exclude reactions/comments bar) ────────
      const postTextEl =
        focusedPost.querySelector('.update-components-text .break-words')  ||
        focusedPost.querySelector('.update-components-text__text-view')    ||
        focusedPost.querySelector('.feed-shared-text .break-words')        ||
        focusedPost.querySelector('.feed-shared-text')                     ||
        focusedPost.querySelector('.update-components-text')               ||
        focusedPost.querySelector('.attributed-text-segment-list__content');

      if (postTextEl) {
        extractedText = postTextEl.innerText.trim();
      } else {
        // Controlled fallback: take innerText but cap it to avoid reaction bar garbage
        const raw = focusedPost.innerText || '';
        // LinkedIn posts rarely exceed 3000 chars; beyond that is reactions/comments
        extractedText = raw.slice(0, 3000).trim();
      }

      // ── Capture images from the post (hiring flyers, salary tables, etc.) ──
      const postImgEls = Array.from(
        focusedPost.querySelectorAll(
          '.update-components-image__image img, .feed-shared-image__container img, ' +
          '.update-components-document__thumbnail img, img[data-delayed-url], img'
        )
      ).filter(img => {
        const src = img.src || img.getAttribute('data-delayed-url') || '';
        const w   = img.naturalWidth  || img.width  || 0;
        const h   = img.naturalHeight || img.height || 0;
        return src && !src.startsWith('data:') && w > 80 && h > 80 &&
               !src.includes('profile') && !src.includes('ghost') &&
               !src.includes('avatar') && !src.includes('icon') &&
               !src.includes('emoji');
      }).slice(0, 4);

      const postImageUrls    = postImgEls.map(img => img.src || img.getAttribute('data-delayed-url') || '');
      const postImageDataUrls = [];

      for (const img of postImgEls) {
        try {
          const canvas = document.createElement('canvas');
          canvas.width  = img.naturalWidth  || img.width;
          canvas.height = img.naturalHeight || img.height;
          canvas.getContext('2d').drawImage(img, 0, 0);
          const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
          if (dataUrl && dataUrl.length > 200) postImageDataUrls.push(dataUrl);
        } catch(e) { /* cross-origin — URL captured, backend will fetch */ }
      }

      console.log(`ScamShield post: author="${authorName}" bio="${authorBio}" text=${extractedText.length}chars images=${postImgEls.length}`);

      sendResponse({
        text:       extractedText,
        metadata:   { poster_name: authorName, poster_headline: authorBio, source_type: 'linkedin_post', has_images: postImgEls.length > 0 },
        image_urls: postImageUrls,
        image_data: postImageDataUrls
      });
      return;
      } // end else (post page)


    } else if (host.includes('mail.google.com')) {
      // Gmail — extract email body + sender metadata
      const emailBodyElements = document.querySelectorAll('.a3s.aiL');
      if (emailBodyElements.length > 0) {
        extractedText = emailBodyElements[emailBodyElements.length - 1].innerText;
      } else {
        const msgBody = document.querySelector('[data-message-id] .ii.gt');
        extractedText = msgBody ? msgBody.innerText : document.body.innerText;
      }
      
      const gmailMeta = {
        poster_name: getText('[email~="from"] span[email], .gD', '.go') || '',
        title: document.querySelector('h2.hP')?.innerText || '',
        location: 'gmail'
      };
      sendResponse({ text: extractedText, metadata: gmailMeta });
      return;

    } else if (host.includes('internshala.com')) {
      const metadata = {
        company: getText('.company_name'),
        title: getText('.profile_on_detail_page'),
        hiring_stats: getText('.hiring_since_container', '.hiring_stats_container', '.activity_stats'),
        location: getText('#location_names', '.location_link')
      };
      const jobDesc = document.querySelector('.text-container') || document.querySelector('.job-description');
      extractedText = jobDesc ? jobDesc.innerText : '';
      sendResponse({ text: extractedText, metadata: metadata });
      return;

    } else if (host.includes('naukri.com')) {
      const metadata = {
        company: getText('.jd-header-comp-name', '.comp-dtls-wrap a'),
        title: getText('.jd-header h1', '[class*="title"]'),
        location: getText('.loc', '.location'),
        company_size: getText('.comp-dtls-wrap .ni-job-tuple-icon-srp-loc'),
        company_industry: getText('.ind-type')
      };
      const jobDesc = document.querySelector('.job-desc') || document.querySelector('#job-description');
      extractedText = jobDesc ? jobDesc.innerText : document.body.innerText;
      sendResponse({ text: extractedText, metadata: metadata });
      return;

    } else {
      // Generic fallback
      const main = document.querySelector('main');
      extractedText = main ? main.innerText : document.body.innerText;
    }

    sendResponse({ text: extractedText });
    })();
  } else if (request.action === 'update_badges') {
    updateJobCards();
    sendResponse({ success: true });
  }
  return true;
});

// ── Job Card Badges ──────────────────────────────────────────────────────────
function updateJobCards() {
  if (!window.location.hostname.includes('linkedin.com')) return;
  
  chrome.storage.local.get(['scamshield_history'], (result) => {
    const history = result.scamshield_history || [];
    if (history.length === 0) return;
    
    // Find all job cards in the list
    const cards = document.querySelectorAll('.job-card-container');
    cards.forEach(card => {
      const link = card.querySelector('.job-card-container__link');
      if (!link) return;
      
      const url = link.href.split('?')[0];
      const match = history.find(h => url.includes(h.url));
      
      if (match) {
        // Prevent adding multiple badges
        if (card.querySelector('.scamshield-badge')) return;
        
        const trustScore = 100 - match.risk_score;
        let color = '#4caf50'; // Green
        let icon = '✅';
        if (match.color === 'orange') { color = '#ff9800'; icon = '⚠️'; }
        if (match.color === 'red') { color = '#f44336'; icon = '🚨'; }
        
        const badge = document.createElement('div');
        badge.className = 'scamshield-badge';
        badge.innerHTML = `<span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${color}; margin-right:4px;"></span> ${icon} ${trustScore} Trust`;
        badge.style.cssText = `
          display: inline-flex; align-items: center; font-size: 11px; font-weight: 600;
          background: #222; color: #fff; padding: 2px 6px; border-radius: 12px;
          margin-top: 4px; border: 1px solid #444; z-index: 10;
        `;
        
        const metadataContainer = card.querySelector('.job-card-container__metadata-wrapper') || card;
        metadataContainer.appendChild(badge);
      }
    });
  });
}

// Re-run badge update when user scrolls/loads more jobs
const observer = new MutationObserver((mutations) => {
  for (let m of mutations) {
    if (m.addedNodes.length > 0) {
      updateJobCards();
      break;
    }
  }
});
observer.observe(document.body, { childList: true, subtree: true });

// ── Pre-Apply Blocking Overlay ───────────────────────────────────────────────
document.addEventListener('click', (e) => {
  // Check if click was on or inside an Apply button
  const applyBtn = e.target.closest('.jobs-apply-button, button[aria-label*="Apply"]');
  if (!applyBtn) return;
  
  // We only intercept if it's not our own "Proceed Anyway" button
  if (applyBtn.classList.contains('scamshield-allowed')) return;

  const currentUrl = window.location.href.split('?')[0];
  
  chrome.storage.local.get(['scamshield_history'], (result) => {
    const history = result.scamshield_history || [];
    const match = history.find(h => currentUrl.includes(h.url));
    
    if (match) {
      const trustScore = 100 - match.risk_score;
      // Hard block if score < 50
      if (trustScore < 50) {
        e.preventDefault();
        e.stopPropagation();
        showBlockingOverlay(trustScore, match.verdict, applyBtn);
      }
    } else {
      // Not scanned yet — Soft warning
      e.preventDefault();
      e.stopPropagation();
      showBlockingOverlay('?', 'Not Scanned', applyBtn, true);
    }
  });
}, true); // Use capture phase to intercept before React

function showBlockingOverlay(score, verdict, originalBtn, isUnscanned = false) {
  // Remove existing if any
  const existing = document.getElementById('scamshield-blocker');
  if (existing) existing.remove();
  
  const overlay = document.createElement('div');
  overlay.id = 'scamshield-blocker';
  overlay.style.cssText = `
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0,0,0,0.85); backdrop-filter: blur(8px);
    z-index: 999999; display: flex; align-items: center; justify-content: center;
    font-family: -apple-system, system-ui, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Fira Sans", Ubuntu, Oxygen, "Oxygen Sans", Cantarell, "Droid Sans", "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Lucida Grande", Helvetica, Arial, sans-serif;
  `;
  
  const title = isUnscanned ? "Hold on a second! 🛡️" : "⚠️ High Scam Risk Detected";
  const desc = isUnscanned 
    ? "You haven't scanned this job with ScamShield yet. We strongly recommend scanning before you apply."
    : `This job has a Trust Score of <strong style="color:#f44336">${score}/100</strong> and is flagged as <strong>${verdict}</strong>. Applying may expose your personal information to fraudsters.`;
    
  const scanBtnHTML = isUnscanned 
    ? `<button id="ss-scan" style="background:#0a66c2; color:white; border:none; padding:10px 20px; border-radius:100px; font-weight:600; cursor:pointer; font-size:15px; margin-right:12px;">Scan Job Now</button>`
    : '';
    
  overlay.innerHTML = `
    <div style="background: #111; border: 1px solid #333; padding: 32px; border-radius: 16px; max-width: 450px; text-align: center; color: #fff; box-shadow: 0 20px 40px rgba(0,0,0,0.4);">
      <div style="font-size: 48px; margin-bottom: 16px;">${isUnscanned ? '🛡️' : '🚨'}</div>
      <h2 style="margin: 0 0 12px 0; font-size: 22px;">${title}</h2>
      <p style="margin: 0 0 24px 0; font-size: 15px; line-height: 1.5; color: #aaa;">${desc}</p>
      <div style="display: flex; justify-content: center; gap: 12px;">
        ${scanBtnHTML}
        <button id="ss-proceed" style="background:transparent; color:#888; border:1px solid #444; padding:10px 20px; border-radius:100px; font-weight:600; cursor:pointer; font-size:15px;">
          ${isUnscanned ? 'Apply Without Scanning' : 'Proceed Anyway (Risky)'}
        </button>
      </div>
      <button id="ss-cancel" style="background:transparent; border:none; color:#aaa; margin-top: 20px; cursor:pointer; text-decoration:underline;">Cancel and Go Back</button>
    </div>
  `;
  
  document.body.appendChild(overlay);
  
  if (isUnscanned) {
    document.getElementById('ss-scan').addEventListener('click', () => {
      overlay.remove();
      // Attempt to open the popup or prompt user
      alert("Click the ScamShield extension icon in your toolbar to scan!");
    });
  }
  
  document.getElementById('ss-proceed').addEventListener('click', () => {
    overlay.remove();
    // Allow the original click to pass through
    originalBtn.classList.add('scamshield-allowed');
    originalBtn.click();
  });
  
  document.getElementById('ss-cancel').addEventListener('click', () => {
    overlay.remove();
  });
}
