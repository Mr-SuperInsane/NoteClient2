from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Union

from .http import HttpClient
from .auth import AuthManager
from .images import ImageManager
from .magazines import MagazineResolver
from .markdown_parser import MarkdownParser
from .utils import xsrf_from_cookies

class NoteClient2:
    def __init__(self, email: str, password: str, user_urlname: str, session_file: str = "session.json"):
        self.email = email
        self.password = password
        self.user_urlname = user_urlname

        self.cookies: Dict[str, str] = {}
        self.headers: Dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://editor.note.com",
            "X-Requested-With": "XMLHttpRequest",
        }

        self.http = HttpClient(self.headers, self.cookies)
        self.auth = AuthManager(email, password, session_file, self.headers)
        self.images = ImageManager()
        self.magazines = MagazineResolver()
        self.parser = MarkdownParser(self.images)

    def _sync_cookies(self) -> None:
        self.cookies = dict(self.auth.cookies)
        self.http.set_cookies(self.cookies)

    def _draft_save(self, note_id: int, title: str, body_html: str, image_keys: List[str]) -> Dict[str, Any]:
        xsrf = xsrf_from_cookies(self.cookies)
        url = f"https://note.com/api/v1/text_notes/draft_save?id={note_id}&is_temp_saved=true"

        headers = {
            "X-XSRF-TOKEN": xsrf,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://editor.note.com/",
            "Content-Type": "application/json",
        }

        plain_text = re.sub(r"<[^>]+>", "", body_html)
        body_length = len(plain_text)

        payload = {
            "body": body_html,
            "body_length": body_length,
            "name": title,
            "index": False,
            "is_lead_form": False,
            "image_keys": image_keys or [],
        }

        resp = self.http.post(url, headers=headers, json=payload)
        if not resp.get("ok"):
            return {"ok": False, "error": {"type": "DraftSaveFailed", "status_code": resp.get("status_code"), "detail": resp.get("text")}}
        return {"ok": True}

    def publish(
        self,
        title: str,
        md_file_path: str,
        eyecatch_path: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        price: int = 0,
        magazine_key: Optional[List[str]] = None,
        is_publish: bool = False,
    ) -> Dict[str, Any]:
        hashtags = hashtags or []
        magazine_key = magazine_key or []

        # 1) Auth
        auth_result = self.auth.prepare(self.http)
        if not auth_result.get("ok"):
            return auth_result
        self._sync_cookies()

        # 2) Parse markdown (upload images inside)
        parsed = self.parser.parse(self.http, self.headers, md_file_path)
        if not parsed.get("ok"):
            return parsed

        data = parsed["data"]
        free_html = data["free_html"]
        pay_html = data["pay_html"]
        combined_html = data["combined_html"]
        image_keys = data["image_keys"]
        separator_id = data["separator_id"]

        # 3) Resolve magazines
        magazine_id_list: List[int] = []
        for key in magazine_key:
            r = self.magazines.get_magazine_id(self.http, self.user_urlname, self.headers, key)
            if not r.get("ok"):
                return r
            mid = (r.get("data") or {}).get("magazine_id")
            if mid:
                magazine_id_list.append(mid)

        # 4) Create note skeleton
        created = self.http.post(
            "https://note.com/api/v1/text_notes",
            headers=self.headers,
            json={"template_key": None},
        )
        if not created.get("ok") or not created.get("json"):
            return {"ok": False, "error": {"type": "CreateNoteFailed", "status_code": created.get("status_code"), "detail": created.get("text")}}

        note_data = (created["json"] or {}).get("data")
        if not note_data:
            return {"ok": False, "error": {"type": "CreateNoteInvalidResponse", "detail": created.get("json")}}

        note_id = note_data.get("id")
        note_key = note_data.get("key")
        if not note_id or not note_key:
            return {"ok": False, "error": {"type": "CreateNoteMissingFields", "detail": note_data}}

        # 5) Eyecatch
        if eyecatch_path:
            eye = self.images.upload_eyecatch(self.http, self.headers, note_id, eyecatch_path)
            if not eye.get("ok"):
                return eye

        # 6) Draft only
        if not is_publish:
            draft = self._draft_save(note_id, title, combined_html, image_keys)
            if not draft.get("ok"):
                return draft
            return {
                "ok": True,
                "data": {
                    "mode": "draft",
                    "note_id": note_id,
                    "note_key": note_key,
                    "edit_url": f"https://editor.note.com/notes/{note_key}/edit",
                },
            }

        # 7) Temp save (draft_save)
        temp = self.http.post(
            f"https://note.com/api/v1/text_notes/draft_save?id={note_id}&is_temp_saved=true",
            headers=self.headers,
            json={"body": combined_html, "name": title, "index": True},
        )
        if not temp.get("ok"):
            return {"ok": False, "error": {"type": "TempDraftSaveFailed", "status_code": temp.get("status_code"), "detail": temp.get("text")}}

        # 8) Final PUT
        status_str = "published"
        formatted_hashtags = [t if t.startswith("#") else f"#{t}" for t in hashtags]
        body_len = len(re.sub(r"<[^>]+>", "", combined_html))

        overrides = {
            "name": title,
            "free_body": free_html,
            "pay_body": pay_html if price > 0 else "",
            "status": status_str,
            "price": price,
            "separator": separator_id if price > 0 and separator_id else None,
            "is_refund": False,
            "limited": False,
            "index": True,
            "image_keys": image_keys,
            "hashtags": formatted_hashtags,
            "magazine_ids": magazine_id_list,
            "magazine_keys": [],
            "body_length": body_len,
            "send_notifications_flag": True,
            "lead_form": {"is_active": False, "consent_url": ""},
            "line_add_friend": {"is_active": False, "keyword": "", "add_friend_url": ""},
        }

        update_payload = dict(note_data)
        update_payload.update(overrides)
        payload = {k: v for k, v in update_payload.items() if v is not None}

        put = self.http.put(
            f"https://note.com/api/v1/text_notes/{note_id}",
            headers=self.headers,
            json=payload,
        )
        if not put.get("ok"):
            return {"ok": False, "error": {"type": "PublishFailed", "status_code": put.get("status_code"), "detail": put.get("text")}}

        return {
            "ok": True,
            "data": {
                "mode": "published",
                "note_id": note_id,
                "note_key": note_key,
                "public_url": f"https://note.com/{self.user_urlname}/n/{note_key}",
                "edit_url": f"https://editor.note.com/notes/{note_key}/edit",
                "has_pay": price > 0,
            },
        }
