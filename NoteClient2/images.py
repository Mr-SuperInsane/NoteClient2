from __future__ import annotations
import os
import mimetypes
import uuid
from typing import Any, Dict, Tuple, Optional

from .http import HttpClient

class ImageManager:
    def __init__(self):
        self.uploaded: Dict[str, Tuple[str, str]] = {}  # file_path -> (url, path)

    def upload_image(self, http: HttpClient, headers: Dict[str, str], file_path: str) -> Dict[str, Any]:
        if file_path in self.uploaded:
            url, key = self.uploaded[file_path]
            return {"ok": True, "data": {"url": url, "path": key, "cached": True}}

        if not os.path.exists(file_path):
            return {"ok": False, "error": {"type": "FileNotFound", "message": "image not found", "path": file_path}}

        ext = os.path.splitext(file_path)[1] or ".png"
        uuid_name = f"{uuid.uuid4().hex}{ext}"
        mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        presign = http.post(
            "https://note.com/api/v3/images/upload/presigned_post",
            headers=headers,
            files={"filename": (None, uuid_name)},
        )
        if not presign.get("ok") or not presign.get("json"):
            return {"ok": False, "error": {"type": "PresignFailed", "status_code": presign.get("status_code"), "detail": presign.get("text")}}

        data = (presign["json"] or {}).get("data") or {}
        if "action" not in data:
            return {"ok": False, "error": {"type": "PresignInvalid", "message": "missing action", "detail": data}}

        try:
            with open(file_path, "rb") as f:
                up = http.post(
                    data["action"],
                    headers={},  # S3 へは base headers を使いたくないので空
                    data=data.get("post"),
                    files={"file": (uuid_name, f, mime)},
                )
            if not up.get("ok"):
                return {"ok": False, "error": {"type": "S3UploadFailed", "status_code": up.get("status_code"), "detail": up.get("text")}}
        except Exception as e:
            return {"ok": False, "error": {"type": type(e).__name__, "message": str(e), "where": "open/upload"}}

        result = (data.get("url"), data.get("path"))
        if not result[0] or not result[1]:
            return {"ok": False, "error": {"type": "UploadResultInvalid", "detail": data}}

        self.uploaded[file_path] = result
        return {"ok": True, "data": {"url": result[0], "path": result[1], "cached": False}}

    def upload_eyecatch(self, http: HttpClient, headers: Dict[str, str], note_id: int, file_path: str) -> Dict[str, Any]:
        if not file_path:
            return {"ok": True, "data": {"skipped": True}}
        if not os.path.exists(file_path):
            return {"ok": False, "error": {"type": "FileNotFound", "message": "eyecatch not found", "path": file_path}}

        try:
            with open(file_path, "rb") as f:
                files = {"file": ("blob", f, "image/png")}
                data = {"note_id": note_id, "width": 1920, "height": 1080}
                resp = http.post(
                    "https://note.com/api/v1/image_upload/note_eyecatch",
                    headers=headers,
                    files=files,
                    data=data,
                )
            if not resp.get("ok"):
                return {"ok": False, "error": {"type": "EyecatchUploadFailed", "status_code": resp.get("status_code"), "detail": resp.get("text")}}
            return {"ok": True, "data": {"uploaded": True}}
        except Exception as e:
            return {"ok": False, "error": {"type": type(e).__name__, "message": str(e), "where": "upload_eyecatch"}}
