from __future__ import annotations
import os
import re
from typing import Any, Dict, List, Tuple, Optional

from .utils import gen_uuid
from .http import HttpClient
from .images import ImageManager

class MarkdownParser:
    def __init__(self, image_manager: ImageManager):
        self.image_manager = image_manager
        self.img_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')

    def _parse_inline(self, text: str) -> str:
        text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)
        return text

    def _build_list_html(self, buffer: List[Dict[str, Any]]) -> Tuple[str, Optional[str]]:
        if not buffer:
            return "", None

        html_output: List[str] = []
        first = buffer[0]
        is_ordered_root = bool(re.match(r'^\d+\.', first['marker']))
        root_type = 'ol' if is_ordered_root else 'ul'

        root_uid = gen_uuid()
        if root_type == 'ol':
            html_output.append(f'<{root_type} data-start="1" name="{root_uid}" id="{root_uid}">')
        else:
            html_output.append(f'<{root_type} name="{root_uid}" id="{root_uid}">')

        tag_stack = [{'indent': first['indent'], 'type': root_type}]

        for item in buffer:
            indent = item['indent']
            marker = item['marker']
            content_text = item['clean_text']
            content_inner = self._parse_inline(content_text)

            p_uid = gen_uuid()
            list_content = f'<p name="{p_uid}" id="{p_uid}">{content_inner}</p>'

            current_item_type = 'ol' if re.match(r'^\d+\.', marker) else 'ul'
            current_stack = tag_stack[-1]

            if indent > current_stack['indent']:
                new_uid = gen_uuid()
                if current_item_type == 'ol':
                    html_output.append(f'<{current_item_type} data-start="1" name="{new_uid}" id="{new_uid}">')
                else:
                    html_output.append(f'<{current_item_type} name="{new_uid}" id="{new_uid}">')
                tag_stack.append({'indent': indent, 'type': current_item_type})

            elif indent < current_stack['indent']:
                while tag_stack and tag_stack[-1]['indent'] > indent:
                    closed = tag_stack.pop()
                    html_output.append(f"</{closed['type']}>")

            else:
                if current_item_type != current_stack['type']:
                    html_output.append(f"</{current_stack['type']}>")
                    tag_stack.pop()
                    new_uid = gen_uuid()
                    if current_item_type == 'ol':
                        html_output.append(f'<{current_item_type} data-start="1" name="{new_uid}" id="{new_uid}">')
                    else:
                        html_output.append(f'<{current_item_type} name="{new_uid}" id="{new_uid}">')
                    tag_stack.append({'indent': indent, 'type': current_item_type})

            html_output.append(f'<li>{list_content}</li>')

        while tag_stack:
            closed = tag_stack.pop()
            html_output.append(f"</{closed['type']}>")

        return "".join(html_output), root_uid

    def parse(self, http: HttpClient, headers: Dict[str, str], md_path: str) -> Dict[str, Any]:
        if not os.path.exists(md_path):
            return {"ok": False, "error": {"type": "FileNotFound", "message": "md not found", "path": md_path}}

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            return {"ok": False, "error": {"type": type(e).__name__, "message": str(e), "where": "read_md"}}

        free_parts: List[str] = []
        pay_parts: List[str] = []
        current_parts = free_parts

        image_keys: List[str] = []
        separator_id: Optional[str] = None
        last_block_id: Optional[str] = None

        in_code_block = False
        list_buffer: List[Dict[str, Any]] = []
        pay_tag_count = 0

        def flush_list_buffer():
            nonlocal list_buffer, last_block_id
            if list_buffer:
                l_html, l_uid = self._build_list_html(list_buffer)
                current_parts.append(l_html)
                last_block_id = l_uid
                list_buffer = []

        def build_html(parts: List[str]) -> str:
            final = ""
            is_in_code = False
            for part in parts:
                if "<pre" in part:
                    is_in_code = True
                final += (part + "\n") if is_in_code else part
                if "</pre>" in part:
                    is_in_code = False
            return final

        for line in lines:
            raw_line = line.rstrip("\r\n")
            stripped = raw_line.strip()
            lower = stripped.lower()

            if "</pay>" in lower:
                return {"ok": False, "error": {"type": "InvalidPayTag", "message": "</pay> is not allowed"}}

            if stripped.startswith("```"):
                flush_list_buffer()
                if not in_code_block:
                    in_code_block = True
                    uid = gen_uuid()
                    lang = stripped.lstrip("`").strip()
                    current_parts.append(f'<pre name="{uid}" id="{uid}" data-lang="{lang}"><code>')
                    last_block_id = uid
                else:
                    in_code_block = False
                    current_parts.append("</code></pre>")
                continue

            if in_code_block:
                current_parts.append(raw_line)
                continue

            if not stripped:
                flush_list_buffer()
                continue

            list_match = re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)', raw_line)
            if list_match:
                list_buffer.append({
                    "indent": len(list_match.group(1)),
                    "marker": list_match.group(2),
                    "clean_text": list_match.group(3),
                })
                continue
            else:
                flush_list_buffer()

            if "<toc>" in lower or "<table of content>" in lower:
                uid = gen_uuid()
                head_uid = gen_uuid()
                current_parts.append(f'<h2 name="{head_uid}" id="{head_uid}">目次</h2>')
                current_parts.append(f'<table-of-contents name="{uid}" id="{uid}"><br></table-of-contents>')
                last_block_id = uid
                continue

            if "<pay>" in lower or "<pay_line>" in lower:
                if lower != "<pay>":
                    return {"ok": False, "error": {"type": "InvalidPayTag", "message": "<pay> must be on its own line"}}
                if pay_tag_count >= 1:
                    return {"ok": False, "error": {"type": "InvalidPayTag", "message": "<pay> allowed only once"}}

                pay_tag_count += 1
                if last_block_id:
                    separator_id = last_block_id

                current_parts = pay_parts
                sep_uid = gen_uuid()
                current_parts.append(f'<span name="{sep_uid}" id="{sep_uid}"></span>')
                last_block_id = sep_uid
                continue

            img_match = self.img_pattern.search(stripped)
            if img_match:
                img_path = img_match.group(2)
                up = self.image_manager.upload_image(http, headers, img_path)
                if not up.get("ok"):
                    up["error"]["where"] = "markdown_image_upload"
                    up["error"]["md_path"] = md_path
                    up["error"]["image_path"] = img_path
                    return up

                img_url = up["data"]["url"]
                img_key_full = up["data"]["path"]

                uid = gen_uuid()
                current_parts.append(
                    f'<figure name="{uid}" id="{uid}" class="note-image" data-image-key="{img_key_full}">'
                    f'<a href="{img_url}" rel="noopener noreferrer" target="_blank">'
                    f'<img src="{img_url}" alt="画像" data-src="{img_url}"></a>'
                    f'<figcaption>{img_match.group(1)}</figcaption></figure>'
                )
                pure_key = os.path.splitext(os.path.basename(img_key_full))[0]
                image_keys.append(pure_key)
                last_block_id = uid
                continue

            uid = gen_uuid()
            line_content = self._parse_inline(stripped)

            if stripped.startswith("### "):
                current_parts.append(f'<h3 name="{uid}" id="{uid}">{line_content.lstrip("# ").strip()}</h3>')
            elif stripped.startswith("# ") or stripped.startswith("## "):
                current_parts.append(f'<h2 name="{uid}" id="{uid}">{line_content.lstrip("# ").strip()}</h2>')
            elif stripped.startswith("> "):
                current_parts.append(f'<blockquote name="{uid}" id="{uid}">{line_content.lstrip("> ").strip()}</blockquote>')
            elif stripped.startswith("---") or stripped.startswith("***"):
                current_parts.append(f'<hr name="{uid}" id="{uid}">')
            else:
                current_parts.append(f'<p name="{uid}" id="{uid}">{line_content}</p>')

            last_block_id = uid

        flush_list_buffer()

        free_html = build_html(free_parts)
        pay_html = build_html(pay_parts)

        return {
            "ok": True,
            "data": {
                "free_html": free_html,
                "pay_html": pay_html,
                "combined_html": free_html + pay_html,
                "image_keys": image_keys,
                "separator_id": separator_id,
                "has_pay": pay_tag_count == 1,
            },
        }
