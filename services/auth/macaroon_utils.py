import hmac
import hashlib
import json
import base64
from typing import List

class Macaroon:
    """
    A simplified representation of a Macaroon for Decentralized Authorization.
    Instead of central DB checks, caveats (e.g., 'ip=10.0.0.4', 'action=TRADE_BTC')
    are cryptographically appended to the token. 
    A service can verify the token without contacting the Auth server.
    """
    def __init__(self, key: bytes, identifier: str, location: str):
        self.location = location
        self.identifier = identifier
        # The initial signature is simply HMAC(key, identifier)
        self.signature = hmac.new(key, identifier.encode(), hashlib.sha256).digest()
        self.caveats: List[str] = []

    def add_first_party_caveat(self, caveat: str):
        """
        Appends a restriction to the token (e.g., 'time < 2026-05-01').
        The new signature becomes HMAC(old_signature, caveat).
        """
        self.caveats.append(caveat)
        self.signature = hmac.new(self.signature, caveat.encode(), hashlib.sha256).digest()

    def serialize(self) -> str:
        """Returns a URL-safe Base64 encoded string of the Macaroon."""
        data = {
            "l": self.location,
            "i": self.identifier,
            "c": self.caveats,
            "s": base64.urlsafe_b64encode(self.signature).decode()
        }
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()

    @classmethod
    def deserialize(cls, serialized_token: str) -> dict:
        """Decodes the serialized Macaroon back into a dictionary."""
        json_data = base64.urlsafe_b64decode(serialized_token.encode()).decode()
        return json.loads(json_data)

def verify_macaroon(macaroon_dict: dict, root_key: bytes, context: dict) -> bool:
    """
    Verifies that the Macaroon was signed by the root key AND that all caveats 
    hold true in the current execution context.
    """
    # 1. Rebuild the signature sequence from the root key
    current_sig = hmac.new(root_key, macaroon_dict['i'].encode(), hashlib.sha256).digest()
    
    for caveat in macaroon_dict.get('c', []):
        current_sig = hmac.new(current_sig, caveat.encode(), hashlib.sha256).digest()
        
        # 2. Context Verification (Evaluating the Caveats)
        # e.g., caveat: "target_entity=BTC_USD"
        key, required_value = caveat.split('=', 1)
        if context.get(key) != required_value:
             return False # Context restriction failed!

    # 3. Final Cryptographic Proof
    expected_sig = base64.urlsafe_b64encode(current_sig).decode()
    return expected_sig == macaroon_dict['s']
