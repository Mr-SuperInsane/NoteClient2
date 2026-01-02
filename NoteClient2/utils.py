import uuid
import urllib.parse
from typing import Dict


def gen_uuid() -> str:
    """
    note の body / free_body / pay_body で使う
    name / id 用の UUID を生成する

    - 全モジュールで共通仕様
    """
    return str(uuid.uuid4())


def xsrf_from_cookies(cookies: Dict[str, str]) -> str:
    """
    Cookie に含まれる XSRF-TOKEN を安全に取り出す

    note の XSRF-TOKEN は URL エンコードされていることがあるため
    必ず unquote して返す
    """
    token = cookies.get("XSRF-TOKEN", "")
    if not token:
        return ""
    return urllib.parse.unquote(token)
