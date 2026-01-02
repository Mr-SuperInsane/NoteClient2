from __future__ import annotations
import re
from typing import Any, Dict, Optional

from .http import HttpClient

class MagazineResolver:
    def get_magazine_id(self, http: HttpClient, user_urlname: str, headers: Dict[str, str], magazine_key: str) -> Dict[str, Any]:
        if not magazine_key:
            return {"ok": True, "data": {"magazine_id": None}}

        url = f"https://note.com/{user_urlname}/m/{magazine_key}"
        res = http.get(url, headers={"User-Agent": headers.get("User-Agent", "")})
        if not res.get("ok"):
            return {"ok": False, "error": {"type": "MagazinePageFetchFailed", "status_code": res.get("status_code"), "detail": res.get("text"), "url": url}}

        html = res.get("text") or ""

        m = re.search(r"magazineLayout\s*:\s*{\s*id\s*:\s*(\d+)", html)
        if m:
            return {"ok": True, "data": {"magazine_id": int(m.group(1))}}

        m2 = re.search(r'"magazineLayout"\s*:\s*{\s*"id"\s*:\s*(\d+)', html)
        if m2:
            return {"ok": True, "data": {"magazine_id": int(m2.group(1))}}

        return {"ok": False, "error": {"type": "MagazineIdNotFound", "message": "magazine id not found in html", "url": url}}
