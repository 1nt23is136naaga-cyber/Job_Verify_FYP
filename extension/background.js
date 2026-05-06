// background.js — ScamShield

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    if (tab.url.includes('linkedin.com/jobs/') || tab.url.includes('linkedin.com/search/results/')) {
      // Check if we already have a score for this URL
      const currentUrl = tab.url.split('?')[0]; // Simplify URL
      chrome.storage.local.get(['scamshield_history'], (result) => {
        const history = result.scamshield_history || [];
        const existing = history.find(h => currentUrl.includes(h.url));
        
        if (existing) {
          // Already scanned
          const trustScore = 100 - existing.risk_score;
          let color = '#4caf50'; // Green
          if (existing.color === 'orange') color = '#ff9800';
          if (existing.color === 'red') color = '#f44336';
          
          chrome.action.setBadgeText({ text: trustScore.toString(), tabId });
          chrome.action.setBadgeBackgroundColor({ color: color, tabId });
        } else {
          // Not scanned yet
          chrome.action.setBadgeText({ text: '?', tabId });
          chrome.action.setBadgeBackgroundColor({ color: '#888888', tabId });
        }
      });
    } else {
      chrome.action.setBadgeText({ text: '', tabId });
    }
  }
});
