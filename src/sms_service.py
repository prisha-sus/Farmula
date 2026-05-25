# -*- coding: utf-8 -*-
"""
SMS service for sending farmer alerts via Fast2SMS Quick SMS API.
Supports English, Hindi, and Marathi using unicode route.
"""

import os

import requests
from dotenv import load_dotenv
from sqlalchemy import text

from db_utils import engine

load_dotenv()

FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY")
FAST2SMS_URL = "https://www.fast2sms.com/dev/bulkV2"


def _log_alert(user_email, phone, message, language, status, error=None):
    """Log every SMS attempt for audit and debugging."""
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO alert_log (user_email, phone_number, message, language, status, error_message)
                VALUES (:email, :phone, :msg, :lang, :status, :err)
            """
                ),
                {
                    "email": user_email or "system",
                    "phone": phone,
                    "msg": message[:500],
                    "lang": language,
                    "status": status,
                    "err": str(error)[:500] if error else None,
                },
            )
            conn.commit()
    except Exception as e:
        print(f"Failed to log alert: {e}")


def send_sms(phone_number: str, message: str, language: str = "en", user_email: str = None) -> dict:
    """
    Send SMS via Fast2SMS Quick SMS route.
    For Hindi/Marathi (Devanagari script), uses unicode route.
    Returns {success: bool, message_id: str, error: str}
    """
    if not FAST2SMS_API_KEY:
        return {"success": False, "error": "FAST2SMS_API_KEY not configured"}

    phone = "".join(ch for ch in str(phone_number) if ch.isdigit())
    if phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]
    if len(phone) != 10:
        _log_alert(user_email, phone_number, message, language, "failed", "Invalid phone number")
        return {"success": False, "error": "Phone number must be 10 digits"}

    sms_language = "unicode" if language in ("hi", "mr") else "english"

    payload = {
        "route": "q",
        "message": message,
        "language": sms_language,
        "flash": 0,
        "numbers": phone,
    }
    headers = {
        "authorization": FAST2SMS_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(FAST2SMS_URL, json=payload, headers=headers, timeout=15)

        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}

        if response.status_code != 200:
            raw = data.get("message", response.text[:200])
            if isinstance(raw, list):
                raw = " | ".join(str(i) for i in raw)
            error_msg = f"Fast2SMS HTTP {response.status_code}: {raw}"
            _log_alert(user_email, phone, message, language, "failed", error_msg)
            return {"success": False, "error": error_msg}

        if data.get("return") is True:
            request_id = data.get("request_id", "")
            _log_alert(user_email, phone, message, language, "sent")
            return {"success": True, "message_id": request_id}

        status_code = data.get("status_code")
        raw_error = data.get("message", "Unknown Fast2SMS error")
        if isinstance(raw_error, list):
            error_msg = " | ".join(str(item) for item in raw_error)
        else:
            error_msg = str(raw_error)

        if status_code == 999:
            error_msg = (
                "Fast2SMS account not activated for API use. "
                "Log in at fast2sms.com and complete a minimum ₹100 recharge to enable the API route."
            )

        _log_alert(user_email, phone, message, language, "failed", error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        _log_alert(user_email, phone, message, language, "failed", str(e))
        return {"success": False, "error": str(e)}


TEMPLATES = {
    "daily_price": {
        "en": "Farmula: Today's {commodity} modal price at {market} is Rs.{price}/qtl. {trend}",
        "hi": "फार्मूला: आज {market} में {commodity} का मोडल मूल्य रु.{price}/क्विं है। {trend}",
        "mr": "फार्मुला: आज {market} मध्ये {commodity} चा मोडल दर रु.{price}/क्विं आहे. {trend}",
    },
    "price_threshold_above": {
        "en": "Farmula ALERT: {commodity} at {market} crossed Rs.{price}/qtl (above your target Rs.{threshold}). Consider selling now.",
        "hi": "फार्मूला अलर्ट: {market} में {commodity} रु.{price}/क्विं पार कर गया (आपके लक्ष्य रु.{threshold} से ऊपर). अभी बेचने पर विचार करें.",
        "mr": "फार्मुला अलर्ट: {market} मध्ये {commodity} रु.{price}/क्विं पार झाला (तुमच्या लक्ष्य रु.{threshold} पेक्षा जास्त). आता विकण्याचा विचार करा.",
    },
    "price_threshold_below": {
        "en": "Farmula ALERT: {commodity} at {market} dropped to Rs.{price}/qtl (below Rs.{threshold}). Consider holding.",
        "hi": "फार्मूला अलर्ट: {market} में {commodity} रु.{price}/क्विं तक गिरा (रु.{threshold} से नीचे). रोकने पर विचार करें.",
        "mr": "फार्मुला अलर्ट: {market} मध्ये {commodity} रु.{price}/क्विं पर्यंत घसरला (रु.{threshold} पेक्षा कमी). थांबण्याचा विचार करा.",
    },
    "harvest_sell_now": {
        "en": "Farmula: {commodity} forecast says SELL NOW. Today Rs.{today}/qtl, in {horizon} days expected Rs.{future}/qtl (down {change}%).",
        "hi": "फार्मूला: {commodity} पूर्वानुमान - अभी बेचें. आज रु.{today}/क्विं, {horizon} दिन में अनुमानित रु.{future}/क्विं ({change}% कम).",
        "mr": "फार्मुला: {commodity} अंदाज - आता विका. आज रु.{today}/क्विं, {horizon} दिवसांत अंदाजित रु.{future}/क्विं ({change}% कमी).",
    },
    "harvest_hold": {
        "en": "Farmula: {commodity} forecast says HOLD. Today Rs.{today}/qtl, in {horizon} days expected Rs.{future}/qtl (up {change}%).",
        "hi": "फार्मूला: {commodity} पूर्वानुमान - रोकें. आज रु.{today}/क्विं, {horizon} दिन में अनुमानित रु.{future}/क्विं ({change}% बढ़त).",
        "mr": "फार्मुला: {commodity} अंदाज - थांबा. आज रु.{today}/क्विं, {horizon} दिवसांत अंदाजित रु.{future}/क्विं ({change}% वाढ).",
    },
}

COMMODITY_NAMES = {
    "onion": {"en": "Onion", "hi": "प्याज", "mr": "कांदा"},
    "potato": {"en": "Potato", "hi": "आलू", "mr": "बटाटा"},
    "soyabean": {"en": "Soyabean", "hi": "सोयाबीन", "mr": "सोयाबीन"},
}


def build_message(template_key: str, language: str, **kwargs) -> str:
    """Build a localized message from template."""
    templates_for_key = TEMPLATES.get(template_key)
    if not templates_for_key:
        raise KeyError(f"Unknown message template: {template_key}")

    template = templates_for_key.get(language) or templates_for_key["en"]

    if "commodity" in kwargs and kwargs["commodity"]:
        commodity_key = str(kwargs["commodity"]).lower()
        if commodity_key in COMMODITY_NAMES:
            kwargs["commodity"] = COMMODITY_NAMES[commodity_key].get(language, kwargs["commodity"])

    return template.format(**kwargs)
