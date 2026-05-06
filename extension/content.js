// content.js — ScamShield
// Extracts job/email text from the active page and returns it to the popup.

// Helper to expand LinkedIn 'see more' buttons
function expandSeeMore() {
  const buttons = document.querySelectorAll('button.inline-show-more-text__button, button.see-more, button.feed-shared-inline-show-more-text__see-more-less-toggle');
  buttons.forEach(b => {
    if (b.innerText.toLowerCase().includes('more') || b.innerText.toLowerCase().includes('see')) {
      try { b.click(); } catch(e){}
    }
  });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract_text') {
    let extractedText = '';
    const host = window.location.hostname;

    if (host.includes('linkedin.com')) {
      // 1. Expand hidden text
      expandSeeMore();
      
      // 2. Extract Metadata
      const metadata = {
        company: document.querySelector('.job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name, .jobs-details-top-card__company-url')?.innerText.trim() || '',
        title: document.querySelector('.job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, h1')?.innerText.trim() || '',
        poster_name: document.querySelector('.jobs-poster__name, .jobs-poster__name-container')?.innerText.trim() || '',
        poster_headline: document.querySelector('.jobs-poster__headline')?.innerText.trim() || '',
        is_poster_verified: !!document.querySelector('.jobs-poster__name-container .verified-badge, .jobs-hiring-team-widget__hiring-manager [aria-label*="Verified"]'),
        poster_url: (document.querySelector('.jobs-poster__name-link, .jobs-poster__name-container a')?.getAttribute('href') || '').split('?')[0],
        location: document.querySelector('.jobs-unified-top-card__bullet, .jobs-details-top-card__bullet')?.innerText.trim() || '',
        applicants: document.querySelector('.jobs-unified-top-card__applicant-count')?.innerText.trim() || '',
        is_promoted: !!document.querySelector('.jobs-unified-top-card__promoted-status, .jobs-details-top-card__promoted-status'),
        company_size: document.querySelector('.jobs-company__inline-information, .jobs-details-top-card__company-info')?.innerText.trim() || '',
        company_industry: document.querySelector('.jobs-company__inline-information')?.innerText.trim() || ''
      };
      console.log('ScamShield Extracted Metadata:', metadata);

      // 3. Selectors ranked by specificity (Job pages -> Feed posts -> General)
      const selectors = [
        '#job-details',
        '.jobs-description__container',
        '.jobs-description',
        '.job-view-layout',
        '.feed-shared-update-v2__description-wrapper',
        '.update-components-text',
        '.feed-shared-text',
        '.attributed-text-segment-list__content',
        'article',
        'main'
      ];
      
      // 4. Find the longest chunk of text among all matches
      let bestMatch = '';
      for (const sel of selectors) {
        const elements = document.querySelectorAll(sel);
        for (const el of elements) {
          const txt = el.innerText.trim();
          if (txt.length > bestMatch.length && txt.length > 50) {
            bestMatch = txt;
          }
        }
        if (bestMatch.length > 250) break;
      }
      
      extractedText = bestMatch;
      
      // 5. Last resort
      if (!extractedText) {
        const main = document.querySelector('main');
        extractedText = main ? main.innerText : document.body.innerText;
      }

      sendResponse({ text: extractedText, metadata: metadata });
      return;
    }
 else if (host.includes('mail.google.com')) {
      // Gmail specific logic stays the same
      const emailBodyElements = document.querySelectorAll('.a3s.aiL');
      if (emailBodyElements.length > 0) {
        extractedText = emailBodyElements[emailBodyElements.length - 1].innerText;
      } else {
        const msgBody = document.querySelector('[data-message-id] .ii.gt');
        extractedText = msgBody ? msgBody.innerText : document.body.innerText;
      }

    } else {
      // Generic fallback
      const main = document.querySelector('main');
      extractedText = main ? main.innerText : document.body.innerText;
    }

    sendResponse({ text: extractedText });
  }
  return true; 
});
