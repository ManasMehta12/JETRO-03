"""Source ingestion and release-scoped retrieval primitives.

The default tokenizer counts lexical tokens; callers can inject a model tokenizer
for exact provider budgets. Original source checksums and locators remain stable.
PDF extraction requires optional pypdf; scanned pages require a separate OCR step.
"""
import hashlib
import io
import math
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple
from xml.etree import ElementTree


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    task_id: str
    release_id: str

    def __post_init__(self):
        if not all(isinstance(v, str) and v.strip() for v in (self.tenant_id, self.task_id, self.release_id)):
            raise ValueError('Tenant, task, and release scope are required')


@dataclass(frozen=True)
class Section:
    text: str
    locator: str


@dataclass(frozen=True)
class Source:
    id: str
    scope: Scope
    title: str
    version: str
    media_type: str
    checksum: str
    sections: Tuple[Section, ...]
    available: bool = True


@dataclass(frozen=True)
class Chunk:
    id: str
    source_id: str
    scope: Scope
    locator: str
    text: str
    token_count: int
    available: bool = True
    embedding: Optional[Tuple[float, ...]] = None


def ingest_bytes(data: bytes, *, source_id: str, scope: Scope, title: str,
                 media_type: str, version: str = '1', max_bytes: int = 20_000_000) -> Source:
    """Extract source text without executing document content or guessing pages."""
    if not source_id or not version or not isinstance(data, bytes) or not data or len(data) > max_bytes:
        raise ValueError('A nonempty supported source within the byte limit is required')
    sections = []
    if media_type in ('text/plain', 'text/markdown'):
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('Text sources must be UTF-8') from exc
        sections = [Section(part.strip(), f'Paragraph {i + 1}')
                    for i, part in enumerate(re.split(r'\n\s*\n', text)) if part.strip()]
    elif media_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                info = archive.getinfo('word/document.xml')
                if info.file_size > max_bytes:
                    raise ValueError('Expanded DOCX exceeds the extraction limit')
                xml = archive.read(info)
                if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
                    raise ValueError('External entities are not supported')
                root = ElementTree.fromstring(xml)
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                for i, paragraph in enumerate(root.findall('.//w:p', ns)):
                    text = ''.join(node.text or '' for node in paragraph.findall('.//w:t', ns)).strip()
                    if text:
                        sections.append(Section(text, f'Paragraph {i + 1}'))
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
            raise ValueError('Malformed DOCX source') from exc
    elif media_type == 'application/pdf':
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError('PDF ingestion requires the optional pypdf dependency') from exc
        try:
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ValueError('Encrypted PDF sources are not supported')
            if len(reader.pages) > 1000:
                raise ValueError('PDF page limit exceeded')
            extracted = 0
            for i, page in enumerate(reader.pages):
                text = (page.extract_text() or '').strip()
                extracted += len(text.encode('utf-8'))
                if extracted > max_bytes:
                    raise ValueError('Extracted PDF text exceeds the limit')
                if text:
                    sections.append(Section(text, f'Page {i + 1}'))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('Malformed or unextractable PDF source') from exc
    else:
        raise ValueError('Unsupported source media type')
    if not sections:
        raise ValueError('No extractable source text; OCR or another source is required')
    return Source(source_id, scope, title, version, media_type, hashlib.sha256(data).hexdigest(), tuple(sections))


def lexical_tokens(text: str) -> Sequence[str]:
    return re.findall(r'\S+', text)


def chunk_source(source: Source, max_tokens: int = 600, overlap: int = 100,
                 tokenize: Callable[[str], Sequence] = lexical_tokens,
                 detokenize: Callable[[Sequence], str] = lambda values: ' '.join(values)):
    """Keep chunk boundaries within source sections; inject encode/decode together."""
    if max_tokens <= 0 or overlap < 0 or overlap >= max_tokens:
        raise ValueError('Overlap must be nonnegative and less than the positive chunk size')
    chunks = []
    for section_index, section in enumerate(source.sections):
        tokens = tokenize(section.text)
        for start in range(0, len(tokens), max_tokens - overlap):
            part = tokens[start:start + max_tokens]
            if not part:
                continue
            identity = f'{source.scope.tenant_id}\0{source.scope.task_id}\0{source.scope.release_id}\0{source.id}\0{source.version}\0{source.checksum}\0{section_index}\0{start}'
            chunks.append(Chunk(hashlib.sha256(identity.encode()).hexdigest(), source.id, source.scope,
                                section.locator, detokenize(part), len(part), source.available))
            if start + max_tokens >= len(tokens):
                break
    return chunks


def _terms(text):
    return Counter(re.findall(r'\w+', text.casefold()))


def _cosine(a, b):
    if len(a) != len(b) or not a or not all(math.isfinite(float(v)) for v in tuple(a) + tuple(b)):
        return 0.0
    norm = math.sqrt(sum(v * v for v in a) * sum(v * v for v in b))
    return sum(x * y for x, y in zip(a, b)) / norm if norm else 0.0


def hybrid_retrieve(query: str, chunks: Sequence[Chunk], scope: Scope, *,
                    query_embedding: Optional[Sequence[float]] = None,
                    max_passages: int = 8, token_budget: int = 4800):
    """Authorize before ranking; merge lexical/vector ranks using reciprocal rank.

    This pure function is useful for bounded release indexes and regression tests.
    A database adapter must apply the same scope predicates in SQL before ranking.
    """
    if token_budget <= 0 or max_passages <= 0:
        raise ValueError('A positive passage and token budget is required')
    scoped = {chunk.id: chunk for chunk in chunks if chunk.scope == scope and chunk.available}
    candidates = list(scoped.values())
    query_terms = _terms(query)
    term_sets = [_terms(chunk.text) for chunk in candidates]
    lexical = []
    for chunk, terms in zip(candidates, term_sets):
        score = sum((1 + math.log(terms[term])) * math.log(1 + len(candidates) / (1 + sum(term in other for other in term_sets)))
                    for term in query_terms if terms[term])
        if score > 0:
            lexical.append((score, chunk.id))
    vector = []
    if query_embedding is not None:
        for chunk in candidates:
            if chunk.embedding is not None:
                score = _cosine(query_embedding, chunk.embedding)
                if score > 0:
                    vector.append((score, chunk.id))
    scores = Counter()
    for ranked in (lexical, vector):
        for rank, (_, chunk_id) in enumerate(sorted(ranked, key=lambda pair: (-pair[0], pair[1])), start=1):
            scores[chunk_id] += 1.0 / (60 + rank)
    result = []
    used = 0
    for chunk_id in sorted(scores, key=lambda value: (-scores[value], value)):
        chunk = scoped[chunk_id]
        if used + chunk.token_count <= token_budget:
            result.append(chunk)
            used += chunk.token_count
        if len(result) >= min(8, max_passages):
            break
    return result
