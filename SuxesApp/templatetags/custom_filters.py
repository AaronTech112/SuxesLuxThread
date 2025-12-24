import hashlib
from django import template

register = template.Library()

@register.filter(name='hash_sha256')
def hash_sha256(value):
    """
    Returns the SHA-256 hash of the value.
    Useful for hashing PII data for TikTok Pixel.
    """
    if not value:
        return ""
    # Ensure value is string and lowercased/stripped as per TikTok requirements usually, 
    # but the user said "hashed on client side" which usually implies we pass the hashed value.
    # Standard normalization for emails/phones: lowercase, trim.
    normalized_value = str(value).strip().lower()
    return hashlib.sha256(normalized_value.encode('utf-8')).hexdigest()
