// popup.js — ScamShield Extension

const API_URL = 'http://localhost:8000';
let currentJobId = null;
let currentSource = 'other';

// ── DOM Refs ──────────────────────────────────────────────────────────────────
const idleState     = document.getElementById('idle-state');
const loadingState  = document.getElementById('loading-state');
const resultsState  = document.getElementById('results-state');
const errorState    = document.getElementById('error-state');
const siteBadge     = document.getElementById('site-badge');
const statusDot     = document.getElementById('status-dot');

// ── On Load: detect site & ping API ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Check API health
  try {
    const r = await fetch(`${API_URL}/docs`, { method: 'HEAD' });
    if (!r.ok) throw new Error();
  } catch {
    statusDot.classList.add('offline');
    statusDot.title = 'API Offline — start server';
  }

  // Detect active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const host = new URL(tab.url).hostname;
  if (host.includes('linkedin.com')) {
    siteBadge.textContent = '📋 LinkedIn — ready to analyze';
    currentSource = 'linkedin';
  } else if (host.includes('mail.google.com')) {
    siteBadge.textContent = '📧 Gmail — ready to analyze';
    currentSource = 'gmail';
  } else {
    siteBadge.textContent = '🌐 ' + host + ' — use manual input below';
    currentSource = 'other';
  }
});

// ── Analyze from page ─────────────────────────────────────────────────────────
document.getElementById('analyze-btn').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  showLoading();

  setStep(1);
  chrome.tabs.sendMessage(tab.id, { action: 'extract_text' }, async (response) => {
    if (chrome.runtime.lastError || !response || !response.text || response.text.trim().length < 20) {
      showError('Could not extract text from this page.\n\nTry using the manual paste box below.');
      return;
    }
    setStep(2);
    await runAnalysis(response.text, response.metadata || {});
  });
});

// ── Analyze from manual textarea ─────────────────────────────────────────────
document.getElementById('manual-btn').addEventListener('click', async () => {
  const text = document.getElementById('manual-text').value.trim();
  if (text.length < 20) {
    alert('Please paste at least a short job description.');
    return;
  }
  showLoading();
  setStep(1);
  await runAnalysis(text, {});
});

// ── Re-analyze ────────────────────────────────────────────────────────────────
document.getElementById('reanalyze-btn').addEventListener('click', () => {
  showIdle();
});
document.getElementById('retry-btn').addEventListener('click', () => {
  showIdle();
});

// ── Core Analysis Call ────────────────────────────────────────────────────────
async function runAnalysis(text, metadata) {
  setStep(2);
  try {
    console.log('Sending Analysis Request:', { source: currentSource, metadata });
    const res = await fetch(`${API_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source: currentSource, metadata: metadata })
    });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    setStep(3);
    const data = await res.json();
    currentJobId = data.job_id;
    renderResults(data);
  } catch (err) {
    showError(`Failed to connect to the backend.\n\nMake sure the server is running:\n→ python -m uvicorn api:app --port 8000\n\n${err.message}`);
  }
}

// ── Render Results ────────────────────────────────────────────────────────────
function renderResults(data) {
  // Score ring animation
  const score = data.risk_score ?? 0;
  const circumference = 314;
  const offset = circumference - (score / 100) * circumference;
  const ring = document.getElementById('ring-fill');
  ring.style.strokeDashoffset = offset;

  // Score number count-up
  const numEl = document.getElementById('score-number');
  let count = 0;
  const target = score;
  const interval = setInterval(() => {
    count = Math.min(count + 2, target);
    numEl.textContent = count;
    if (count >= target) clearInterval(interval);
  }, 20);

  // Verdict
  const verdictEl = document.getElementById('verdict-text');
  const subEl = document.getElementById('verdict-sub');
  verdictEl.textContent = data.verdict || '—';

  // Color class on score section
  const scoreSection = document.querySelector('.score-section');
  scoreSection.classList.remove('verdict-green','verdict-orange','verdict-red');
  if (data.color === 'green') {
    scoreSection.classList.add('verdict-green');
    subEl.textContent = 'No major red flags detected';
  } else if (data.color === 'orange') {
    scoreSection.classList.add('verdict-orange');
    subEl.textContent = 'Proceed with caution';
  } else {
    scoreSection.classList.add('verdict-red');
    subEl.textContent = 'High likelihood of fraud';
  }

  // Info grid
  document.getElementById('res-company').textContent   = data.company   || 'Unknown';
  document.getElementById('res-recruiter').textContent = data.recruiter  || 'Unknown';
  document.getElementById('res-email').textContent     = data.email      || 'Not found';
  document.getElementById('res-title').textContent     = data.job_title  || 'Not detected';

  // Risk pills
  const pillsContainer = document.getElementById('risk-pills');
  pillsContainer.innerHTML = '';
  if (data.risk_factors && data.risk_factors.length > 0) {
    data.risk_factors.forEach(rf => {
      const pill = document.createElement('span');
      pill.className = `risk-pill ${rf.includes('(-') ? 'good' : 'bad'}`;
      // Shorten for display
      pill.textContent = rf.length > 60 ? rf.substring(0, 58) + '…' : rf;
      pill.title = rf;
      pillsContainer.appendChild(pill);
    });
  } else {
    const pill = document.createElement('span');
    pill.className = 'risk-pill good';
    pill.textContent = '✅ All checks passed clean';
    pillsContainer.appendChild(pill);
  }

  showResults();
}

// ── Feedback Handlers ───────────────────────────────────────────────────────
document.getElementById('fb-safe').addEventListener('click', () => submitFeedback(false));
document.getElementById('fb-scam').addEventListener('click', () => submitFeedback(true));

async function submitFeedback(isScam) {
  if (!currentJobId) {
    console.warn('Feedback clicked but no Job ID available');
    return;
  }
  
  const safeBtn = document.getElementById('fb-safe');
  const scamBtn = document.getElementById('fb-scam');
  const thanks = document.getElementById('feedback-thanks');
  
  // Visual state
  safeBtn.classList.add('selected');
  scamBtn.classList.add('selected');
  thanks.textContent = 'Updating...';
  thanks.classList.remove('hidden');

  try {
    const res = await fetch(`${API_URL}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: currentJobId, is_scam: isScam })
    });
    if (res.ok) {
      thanks.textContent = 'Feedback received! 🛡️';
      console.log('Feedback saved successfully');
    } else {
      throw new Error(`Server returned ${res.status}`);
    }
  } catch (err) {
    console.error('Feedback error:', err);
    thanks.textContent = 'Failed to save feedback.';
    safeBtn.classList.remove('selected');
    scamBtn.classList.remove('selected');
  }
}

// ── UI State Helpers ──────────────────────────────────────────────────────────
function showIdle() {
  idleState.classList.remove('hidden');
  loadingState.classList.add('hidden');
  resultsState.classList.add('hidden');
  errorState.classList.add('hidden');
  document.getElementById('feedback-thanks').classList.add('hidden');
  document.getElementById('fb-safe').classList.remove('selected');
  document.getElementById('fb-scam').classList.remove('selected');
  currentJobId = null;
}

function showLoading() {
  idleState.classList.add('hidden');
  loadingState.classList.remove('hidden');
  resultsState.classList.add('hidden');
  errorState.classList.add('hidden');
  // Reset steps
  document.getElementById('step-1').className = 'step';
  document.getElementById('step-2').className = 'step';
  document.getElementById('step-3').className = 'step';
}

function showResults() {
  idleState.classList.add('hidden');
  loadingState.classList.add('hidden');
  resultsState.classList.remove('hidden');
  errorState.classList.add('hidden');
}

function showError(msg) {
  idleState.classList.add('hidden');
  loadingState.classList.add('hidden');
  resultsState.classList.add('hidden');
  errorState.classList.remove('hidden');
  document.getElementById('error-msg').textContent = msg;
}

function setStep(n) {
  for (let i = 1; i <= 3; i++) {
    const el = document.getElementById(`step-${i}`);
    if (i < n) el.className = 'step done';
    else if (i === n) el.className = 'step active';
    else el.className = 'step';
  }
}
