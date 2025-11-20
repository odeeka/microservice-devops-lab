"""
Device Fingerprinting Service

Generates unique device fingerprints and detects suspicious login attempts.
Helps prevent account takeovers and unauthorized access.
"""
from typing import Dict, Optional, List
from datetime import datetime
import hashlib
import json
import re
import logging

logger = logging.getLogger(__name__)


class DeviceFingerprintService:
    """
    Service for device fingerprinting and suspicious login detection.
    
    Features:
    - Generates unique device fingerprints from request data
    - Parses user agent strings for device/browser info
    - Compares new logins against known devices
    - Calculates risk scores for suspicious activity
    - Provides detailed security recommendations
    """
    
    @staticmethod
    def parse_user_agent(user_agent: str) -> Dict[str, str]:
        """
        Parse user agent string to extract device/browser information.
        
        Args:
            user_agent: User-Agent header value
            
        Returns:
            Dictionary with browser, version, os, device info
        """
        if not user_agent:
            return {
                "browser": "Unknown",
                "browser_version": "Unknown",
                "os": "Unknown",
                "device_type": "Unknown"
            }
        
        # Detect browser
        browser = "Unknown"
        browser_version = "Unknown"
        
        if "Chrome" in user_agent and "Edg" not in user_agent:
            browser = "Chrome"
            match = re.search(r"Chrome/([\d.]+)", user_agent)
            if match:
                browser_version = match.group(1)
        elif "Firefox" in user_agent:
            browser = "Firefox"
            match = re.search(r"Firefox/([\d.]+)", user_agent)
            if match:
                browser_version = match.group(1)
        elif "Safari" in user_agent and "Chrome" not in user_agent:
            browser = "Safari"
            match = re.search(r"Version/([\d.]+)", user_agent)
            if match:
                browser_version = match.group(1)
        elif "Edg" in user_agent:
            browser = "Edge"
            match = re.search(r"Edg/([\d.]+)", user_agent)
            if match:
                browser_version = match.group(1)
        
        # Detect OS
        os = "Unknown"
        if "Windows NT 10" in user_agent:
            os = "Windows 10/11"
        elif "Windows NT 6.3" in user_agent:
            os = "Windows 8.1"
        elif "Windows NT 6.2" in user_agent:
            os = "Windows 8"
        elif "Windows NT 6.1" in user_agent:
            os = "Windows 7"
        elif "Mac OS X" in user_agent:
            match = re.search(r"Mac OS X ([\d_]+)", user_agent)
            if match:
                version = match.group(1).replace("_", ".")
                os = f"macOS {version}"
            else:
                os = "macOS"
        elif "Linux" in user_agent and "Android" not in user_agent:
            os = "Linux"
        elif "Android" in user_agent:
            match = re.search(r"Android ([\d.]+)", user_agent)
            if match:
                os = f"Android {match.group(1)}"
            else:
                os = "Android"
        elif "iOS" in user_agent or "iPhone" in user_agent or "iPad" in user_agent:
            match = re.search(r"OS ([\d_]+)", user_agent)
            if match:
                version = match.group(1).replace("_", ".")
                os = f"iOS {version}"
            else:
                os = "iOS"
        
        # Detect device type
        device_type = "Desktop"
        if "Mobile" in user_agent or "Android" in user_agent:
            device_type = "Mobile"
        elif "Tablet" in user_agent or "iPad" in user_agent:
            device_type = "Tablet"
        
        return {
            "browser": browser,
            "browser_version": browser_version,
            "os": os,
            "device_type": device_type
        }
    
    @staticmethod
    def generate_fingerprint(
        user_agent: str,
        ip_address: Optional[str] = None,
        accept_language: Optional[str] = None,
        accept_encoding: Optional[str] = None
    ) -> str:
        """
        Generate unique device fingerprint hash.
        
        Args:
            user_agent: User-Agent header
            ip_address: Client IP address (optional)
            accept_language: Accept-Language header (optional)
            accept_encoding: Accept-Encoding header (optional)
            
        Returns:
            SHA256 hash as fingerprint ID
        """
        # Parse user agent for core device info
        ua_info = DeviceFingerprintService.parse_user_agent(user_agent)
        
        # Build fingerprint components
        components = [
            ua_info["browser"],
            ua_info["os"],
            ua_info["device_type"],
            accept_language or "unknown",
            accept_encoding or "unknown",
            # Note: IP is NOT included in fingerprint as it can change
            # (mobile networks, VPNs, etc.)
        ]
        
        # Create hash
        fingerprint_string = "|".join(components)
        fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()
        
        return fingerprint_hash
    
    @staticmethod
    def create_fingerprint_data(
        user_agent: str,
        ip_address: Optional[str] = None,
        accept_language: Optional[str] = None,
        accept_encoding: Optional[str] = None,
        screen_resolution: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> Dict:
        """
        Create comprehensive fingerprint data for storage.
        
        Args:
            user_agent: User-Agent header
            ip_address: Client IP address
            accept_language: Accept-Language header
            accept_encoding: Accept-Encoding header
            screen_resolution: Screen resolution (from client JS)
            timezone: Client timezone (from client JS)
            
        Returns:
            Dictionary with fingerprint and all metadata
        """
        ua_info = DeviceFingerprintService.parse_user_agent(user_agent)
        fingerprint = DeviceFingerprintService.generate_fingerprint(
            user_agent,
            ip_address,
            accept_language,
            accept_encoding
        )
        
        return {
            "fingerprint_id": fingerprint,
            "browser": ua_info["browser"],
            "browser_version": ua_info["browser_version"],
            "os": ua_info["os"],
            "device_type": ua_info["device_type"],
            "ip_address": ip_address,
            "accept_language": accept_language,
            "accept_encoding": accept_encoding,
            "screen_resolution": screen_resolution,
            "timezone": timezone,
            "user_agent_raw": user_agent,
            "created_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def analyze_login_risk(
        new_fingerprint: Dict,
        known_fingerprints: List[Dict],
        ip_address: Optional[str] = None
    ) -> Dict:
        """
        Analyze login attempt and calculate risk score.
        
        Args:
            new_fingerprint: Fingerprint data for current login
            known_fingerprints: List of user's previous fingerprints
            ip_address: Current IP address
            
        Returns:
            Dictionary with risk_score, is_suspicious, and reasons
        """
        risk_score = 0
        risk_factors = []
        
        # Check if this is a completely new device
        new_fp_id = new_fingerprint["fingerprint_id"]
        known_fp_ids = [fp.get("fingerprint_id") for fp in known_fingerprints]
        
        if new_fp_id not in known_fp_ids:
            risk_score += 30
            risk_factors.append("new_device")
            logger.info(f"🔍 New device detected: {new_fingerprint['browser']} on {new_fingerprint['os']}")
        
        # Check for new IP address
        if ip_address and known_fingerprints:
            known_ips = [fp.get("ip_address") for fp in known_fingerprints if fp.get("ip_address")]
            if ip_address not in known_ips:
                risk_score += 20
                risk_factors.append("new_ip_address")
                logger.info(f"🔍 New IP address: {ip_address}")
        
        # Check for new OS
        if known_fingerprints:
            known_oses = [fp.get("os") for fp in known_fingerprints if fp.get("os")]
            if new_fingerprint["os"] not in known_oses:
                risk_score += 25
                risk_factors.append("new_operating_system")
                logger.info(f"🔍 New OS: {new_fingerprint['os']}")
        
        # Check for new browser
        if known_fingerprints:
            known_browsers = [fp.get("browser") for fp in known_fingerprints if fp.get("browser")]
            if new_fingerprint["browser"] not in known_browsers:
                risk_score += 15
                risk_factors.append("new_browser")
                logger.info(f"🔍 New browser: {new_fingerprint['browser']}")
        
        # Check for new device type
        if known_fingerprints:
            known_device_types = [fp.get("device_type") for fp in known_fingerprints if fp.get("device_type")]
            if new_fingerprint["device_type"] not in known_device_types:
                risk_score += 10
                risk_factors.append("new_device_type")
                logger.info(f"🔍 New device type: {new_fingerprint['device_type']}")
        
        # Determine if suspicious (threshold: 50)
        is_suspicious = risk_score >= 50
        
        # Generate recommendation
        if is_suspicious:
            recommendation = "High risk login detected. Consider requiring additional verification (2FA, email confirmation)."
        elif risk_score >= 30:
            recommendation = "Medium risk login. Consider sending email notification to user."
        else:
            recommendation = "Low risk login. Normal activity."
        
        result = {
            "risk_score": risk_score,
            "is_suspicious": is_suspicious,
            "risk_factors": risk_factors,
            "recommendation": recommendation,
            "fingerprint_summary": {
                "browser": new_fingerprint["browser"],
                "os": new_fingerprint["os"],
                "device_type": new_fingerprint["device_type"],
                "ip": ip_address
            }
        }
        
        if is_suspicious:
            logger.warning(
                f"🚨 Suspicious login detected! Risk score: {risk_score}, "
                f"Factors: {', '.join(risk_factors)}"
            )
        
        return result


# Singleton instance
_fingerprint_service = None


def get_fingerprint_service() -> DeviceFingerprintService:
    """
    Get or create DeviceFingerprintService instance.
    
    Returns:
        DeviceFingerprintService instance
    """
    global _fingerprint_service
    if _fingerprint_service is None:
        _fingerprint_service = DeviceFingerprintService()
    return _fingerprint_service
