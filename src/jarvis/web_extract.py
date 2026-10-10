"""Bounded, inert HTML/plain extraction; no JS, subresource or canonical fetching."""

import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

from jarvis.web_data import WebError, public_url


def clean(text, limit=1000):
    # Remove terminal controls and bidi controls from every displayed/model field.
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]", "", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def page_date(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except ValueError:
        return None


class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts, self.main_parts, self.headings = [], [], []
        self.meta = {}
        self.title = []
        self.canonical = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = (
            tag
            in {"script", "style", "nav", "footer", "noscript", "iframe", "svg", "form", "template"}
            or "hidden" in attrs
            or attrs.get("aria-hidden") == "true"
            or bool(
                re.search(
                    r"display\s*:\s*none|visibility\s*:\s*hidden", attrs.get("style", ""), re.I
                )
            )
        )
        if tag == "meta":
            key = attrs.get("property", attrs.get("name", "")).casefold()
            self.meta.setdefault(key, attrs.get("content", "")[:512])
        if tag == "link" and attrs.get("rel", "").casefold() == "canonical":
            self.canonical = attrs.get("href", "")[:2048]
        if tag not in {
            "meta",
            "link",
            "img",
            "br",
            "hr",
            "input",
            "source",
            "wbr",
            "area",
            "base",
            "embed",
            "param",
            "track",
            "col",
        }:
            self.stack.append((tag, hidden))
            if len(self.stack) > 256:
                raise WebError("HTML_DEPTH_LIMIT")
        if tag in {"p", "div", "section", "article", "main", "h1", "h2", "h3", "li", "pre", "br"}:
            self.parts.append("\n")
            self.main_parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if tag in {"p", "div", "section", "article", "main", "h1", "h2", "h3", "li", "pre"}:
            self.parts.append("\n")
            self.main_parts.append("\n")

    def handle_data(self, data):
        if any(hidden for _, hidden in self.stack):
            return
        tags = [tag for tag, _ in self.stack]
        if "title" in tags:
            self.title.append(data)
            return
        if "head" in tags:
            return
        data = re.sub(r"\s+", " ", data)
        self.parts.append(data)
        if any(tag in {"main", "article"} for tag in tags):
            self.main_parts.append(data)
        if any(tag in {"h1", "h2", "h3"} for tag in tags):
            self.headings.append(clean(data, 160))


def extract(body, receipt, config):
    if len(body) > config.max_response_bytes:
        raise WebError("OVERSIZED_PAYLOAD")
    if receipt["content_type"] == "application/pdf":
        return extract_pdf(body, config)
    try:
        text = body.decode("utf-8-sig", errors="strict")
    except UnicodeError:
        raise WebError("TEXT_ENCODING_UNSUPPORTED") from None
    metadata = {}
    if receipt["content_type"] == "text/html":
        parser = DocumentParser()
        parser.feed(text)
        text = "".join(parser.main_parts)
        if len(clean(text, config.max_text_chars)) < 100:
            text = "".join(parser.parts)
        canonical_url = None
        if parser.canonical:
            try:
                canonical_url = public_url(urljoin(receipt["url"], parser.canonical))
            except ValueError:
                pass
        metadata = {
            "title": clean("".join(parser.title), 200),
            "author": clean(parser.meta.get("author", ""), 160) or None,
            "published_at": page_date(
                parser.meta.get("article:published_time", parser.meta.get("datepublished"))
            ),
            "updated_at": page_date(
                parser.meta.get("article:modified_time", parser.meta.get("datemodified"))
            ),
            "canonical_url": canonical_url,
            "headings": tuple(dict.fromkeys(parser.headings))[:20],
        }
    elif receipt["content_type"] != "text/plain":
        raise WebError("CONTENT_TYPE_UNSUPPORTED")
    paragraphs, used = [], 0
    for line in text.splitlines():
        value = clean(line, min(2000, config.max_text_chars - used))
        if not value or value in paragraphs:
            continue
        paragraphs.append(value)
        used += len(value)
        if used >= config.max_text_chars:
            break
    if not paragraphs:
        raise WebError("NO_USABLE_TEXT")
    return {**metadata, "chunks": tuple(paragraphs)}


def extract_pdf(body, config):
    """Parse text only. Runtime calls occur in a memory/time-limited worker."""
    from io import BytesIO

    from pypdf import PdfReader

    if not body.startswith(b"%PDF-"):
        raise WebError("INVALID_PDF")
    try:
        reader = PdfReader(BytesIO(body), strict=True)
        if reader.is_encrypted:
            raise WebError("ENCRYPTED_PDF_UNSUPPORTED")
        if len(reader.pages) > 15:
            raise WebError("PDF_PAGE_LIMIT")
        metadata = reader.metadata
        chunks, used = [], 0
        for number, page in enumerate(reader.pages, 1):
            content = page.get_contents()
            if content is not None and len(content.get_data()) > 2 * 1024 * 1024:
                raise WebError("PDF_CONTENT_STREAM_LIMIT")
            value = clean(page.extract_text() or "", min(2000, config.max_text_chars - used))
            if value:
                chunk = f"[PDF page {number}] {value}"
                chunks.append(chunk[: config.max_text_chars - used])
                used += len(chunks[-1])
            if used >= config.max_text_chars:
                break
        if not chunks:
            raise WebError("NO_USABLE_PDF_TEXT_NO_OCR")
        return {
            "title": clean(str(metadata.title or ""), 200) if metadata else "",
            "author": clean(str(metadata.author or ""), 160) or None if metadata else None,
            "chunks": tuple(chunks),
        }
    except WebError:
        raise
    except Exception:
        raise WebError("PDF_PARSE_FAILED") from None
