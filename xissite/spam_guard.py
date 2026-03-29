"""
Anti-Spam / Anti-Bot Safeguards
===============================

Layered defense system for the contact form:
1. Honeypot field detection
2. Time-based submission validation
3. Rate limiting per IP
4. Email domain blocklist
5. URL/link detection
6. Suspicious content scoring

All individual checks return (passed, reason, score) tuples.
The master validate_submission() function aggregates results.
"""

import re
import time
import hashlib
from collections import defaultdict
from threading import Lock


# ============================================================================
# CONFIGURATION
# ============================================================================

# Minimum seconds between form load and submit
MIN_SUBMISSION_TIME_SECONDS = 3

# Rate limiting: max submissions per IP within the window
RATE_LIMIT_MAX_SUBMISSIONS = 3
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour

# Spam score threshold (0-100). Submissions scoring above this are rejected.
SPAM_SCORE_THRESHOLD = 50

# Disposable/temporary email domains to block
DISPOSABLE_EMAIL_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'tempmail.com', 'throwaway.email',
    'yopmail.com', 'sharklasers.com', 'guerrillamailblock.com', 'grr.la',
    'dispostable.com', 'trashmail.com', 'fakeinbox.com', 'mailnesia.com',
    'maildrop.cc', 'discard.email', 'temp-mail.org', 'minutemail.com',
    'emailondeck.com', 'tempr.email', 'binkmail.com', 'mohmal.com',
    'getnada.com', '10minutemail.com', 'tempail.com', 'burnermail.io',
    'mailcatch.com', 'inboxbear.com', 'spamgourmet.com',
}

# Known spam phrases (case-insensitive matching)
SPAM_PHRASES = [
    'buy now', 'click here', 'free money', 'act now', 'limited time',
    'congratulations you', 'you have been selected', 'dear friend',
    'wire transfer', 'bitcoin', 'crypto investment',
    'earn money fast', 'work from home', 'make money online',
    'seo services', 'web traffic', 'backlinks', 'casino',
    'viagra', 'cialis', 'pharmacy', 'diet pills',
]


# ============================================================================
# IN-MEMORY RATE LIMITER
# ============================================================================

class RateLimiter:
    """
    Thread-safe in-memory rate limiter using sliding window.

    Tracks submission timestamps per IP address. Automatically prunes
    expired entries to prevent memory growth.
    """

    def __init__(self, max_requests, window_seconds):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = defaultdict(list)
        self._lock = Lock()
        self._last_cleanup = time.time()

    def is_rate_limited(self, ip_address):
        """Check if IP has exceeded the rate limit. Returns (limited, count)."""
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            self._requests[ip_address] = [
                t for t in self._requests[ip_address] if t > cutoff
            ]
            count = len(self._requests[ip_address])

            if now - self._last_cleanup > 300:
                self._cleanup(cutoff)
                self._last_cleanup = now

            return count >= self.max_requests, count

    def record(self, ip_address):
        """Record a submission from this IP."""
        with self._lock:
            self._requests[ip_address].append(time.time())

    def _cleanup(self, cutoff):
        """Remove all entries older than cutoff across all IPs."""
        empty_ips = []
        for ip, timestamps in self._requests.items():
            self._requests[ip] = [t for t in timestamps if t > cutoff]
            if not self._requests[ip]:
                empty_ips.append(ip)
        for ip in empty_ips:
            del self._requests[ip]


# Module-level singleton
contact_rate_limiter = RateLimiter(
    max_requests=RATE_LIMIT_MAX_SUBMISSIONS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)


# ============================================================================
# HONEYPOT CHECK
# ============================================================================

def check_honeypot(form_data):
    """
    Check if the honeypot field was filled in.

    Real users never see this field (hidden via CSS).
    Bots filling all fields will populate it.
    """
    honeypot_value = form_data.get('website', '').strip()
    if honeypot_value:
        return False, 'honeypot_filled', 100
    return True, '', 0


# ============================================================================
# TIME-BASED VALIDATION
# ============================================================================

def generate_timestamp_token(secret_key):
    """Generate an HMAC-signed timestamp token for the form."""
    timestamp = str(int(time.time()))
    signature = hashlib.sha256(
        f"{timestamp}:{secret_key}".encode()
    ).hexdigest()[:16]
    return f"{timestamp}:{signature}"


def check_submission_time(token, secret_key):
    """
    Validate that enough time elapsed between form load and submission.

    Bots typically submit within milliseconds of loading the page.
    Real humans need at least a few seconds to read and fill the form.
    """
    if not token:
        return False, 'missing_timestamp', 80

    try:
        parts = token.split(':')
        if len(parts) != 2:
            return False, 'invalid_timestamp_format', 80

        timestamp_str, signature = parts

        expected_sig = hashlib.sha256(
            f"{timestamp_str}:{secret_key}".encode()
        ).hexdigest()[:16]
        if signature != expected_sig:
            return False, 'invalid_timestamp_signature', 80

        load_time = int(timestamp_str)
        elapsed = time.time() - load_time

        if elapsed < MIN_SUBMISSION_TIME_SECONDS:
            return False, f'too_fast ({elapsed:.1f}s)', 70

        if elapsed > 3600:
            return False, 'form_expired', 30

    except (ValueError, TypeError):
        return False, 'timestamp_parse_error', 80

    return True, '', 0


# ============================================================================
# URL / LINK DETECTION
# ============================================================================

URL_PATTERN = re.compile(
    r'('
    r'https?://[^\s<>\"\']+|'
    r'www\.[^\s<>\"\']+|'
    r'[a-zA-Z0-9-]+\.(com|net|org|io|co|info|biz|xyz|top|ru|cn|tk)'
    r'(/[^\s<>\"\']*)?'
    r')',
    re.IGNORECASE,
)


def check_for_urls(text):
    """
    Detect URLs/links in message content.

    Legitimate feedback messages to a hydroponics company
    should not contain URLs.
    """
    if not text:
        return True, '', 0

    matches = URL_PATTERN.findall(text)
    if matches:
        url_count = len(matches)
        score = min(60 + (url_count - 1) * 20, 100)
        return False, f'contains_{url_count}_url(s)', score

    return True, '', 0


# ============================================================================
# EMAIL DOMAIN VALIDATION
# ============================================================================

def check_email_domain(email):
    """Check if the email uses a known disposable/temporary domain."""
    if not email or '@' not in email:
        return True, '', 0

    domain = email.rsplit('@', 1)[1].lower().strip()

    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return False, f'disposable_domain ({domain})', 60

    return True, '', 0


# ============================================================================
# SUSPICIOUS CONTENT SCORING
# ============================================================================

def check_suspicious_content(text):
    """
    Score submission based on multiple spam signals.

    Signals: known spam phrases, excessive capitalization,
    repetitive characters, generic short bot-probe messages.
    """
    if not text:
        return True, '', 0

    score = 0
    reasons = []
    text_lower = text.lower()

    # Known spam phrases
    phrase_hits = sum(1 for phrase in SPAM_PHRASES if phrase in text_lower)
    if phrase_hits > 0:
        score += min(phrase_hits * 20, 60)
        reasons.append(f'{phrase_hits}_spam_phrase(s)')

    # Excessive capitalization (>60% caps in messages over 20 chars)
    if len(text) > 20:
        alpha_chars = [c for c in text if c.isalpha()]
        if alpha_chars:
            caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if caps_ratio > 0.6:
                score += 20
                reasons.append('excessive_caps')

    # Repetitive characters (e.g., "aaaaaa")
    if re.search(r'(.)\1{5,}', text):
        score += 15
        reasons.append('repetitive_chars')

    # Very short generic messages that look like bot probes
    if len(text.strip()) < 15 and any(w in text_lower for w in ['test', 'hello', 'hi', 'hey']):
        score += 10
        reasons.append('generic_short_message')

    reason_str = ', '.join(reasons) if reasons else ''
    return score < SPAM_SCORE_THRESHOLD, reason_str, score


# ============================================================================
# MASTER VALIDATION
# ============================================================================

def validate_submission(form_data, email, message, timestamp_token, secret_key, ip_address):
    """
    Run all spam checks and return aggregate result.

    Returns dict with:
        is_spam: True if submission should be rejected
        is_silent_reject: True if rejection should look like success
        total_score: Aggregate spam score
        failed_checks: List of (check_name, reason, score) tuples
        rejection_message: User-facing message if rejected
    """
    result = {
        'is_spam': False,
        'is_silent_reject': False,
        'total_score': 0,
        'failed_checks': [],
        'rejection_message': '',
    }

    # Run rate limit check once and cache the result
    rate_limited, _count = contact_rate_limiter.is_rate_limited(ip_address)

    checks = [
        ('honeypot', check_honeypot(form_data)),
        ('timing', check_submission_time(timestamp_token, secret_key)),
        ('rate_limit', (not rate_limited, 'rate_limited' if rate_limited else '', 80 if rate_limited else 0)),
        ('email_domain', check_email_domain(email)),
        ('url_detection', check_for_urls(message)),
        ('content_score', check_suspicious_content(message)),
    ]

    for check_name, (passed, reason, score) in checks:
        result['total_score'] += score
        if not passed:
            result['failed_checks'].append((check_name, reason, score))

    if not result['failed_checks']:
        return result

    result['is_spam'] = True
    failed_names = {c[0] for c in result['failed_checks']}

    # Silent rejects: bot-only triggers (show fake success)
    if failed_names & {'honeypot', 'rate_limit'}:
        result['is_silent_reject'] = True
        result['rejection_message'] = 'Thank you! Your feedback has been submitted successfully.'

    elif 'timing' in failed_names and any(
        'too_fast' in c[1] or 'missing' in c[1] or 'invalid' in c[1]
        for c in result['failed_checks'] if c[0] == 'timing'
    ):
        result['is_silent_reject'] = True
        result['rejection_message'] = 'Thank you! Your feedback has been submitted successfully.'

    elif 'url_detection' in failed_names:
        result['rejection_message'] = 'Please remove any URLs or links from your message and try again.'

    elif 'email_domain' in failed_names:
        result['rejection_message'] = 'Please use a non-disposable email address.'

    elif result['total_score'] >= SPAM_SCORE_THRESHOLD:
        result['rejection_message'] = 'Your message could not be submitted. Please revise and try again.'

    else:
        # Score elevated but below threshold -- let it through
        result['is_spam'] = False

    return result
