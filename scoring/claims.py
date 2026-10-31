"""Claim extraction and cited-passage support, using only the standard library.

This is a conservative v1 instrument, not an entailment oracle. Every prose
sentence/compound clause is a candidate. Deterministic support accepts complete
normalized statement equality or a narrow subject/relation/value assertion.
Anything else is UNSUPPORTED *by these checks*, with ``needs_judge`` explicit.
A separate judge row can settle that residue; it never rewrites deterministic
counts. Citations identify captured fetches, never evidence fetched elsewhere.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit

VERDICTS = ("SUPPORTED", "UNSUPPORTED", "CONTRADICTED")
EXTRACTION_LIMITS = [
    "Rule-based prose candidates, not a claim-completeness guarantee; tables, "
    "ellipsis, pronouns, multilingual text and nested assertions may need review.",
    "Unresolved semantics are UNSUPPORTED by deterministic checks, not a proof "
    "that no passage entails the claim; needs_judge identifies this residue.",
    "Explicit inline/reference citations or a run citation map are required; "
    "question assignment and relied_on do not invent citations.",
]
_URL = re.compile(r"https?://[^\s<>\])]+")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)(?:\s+['\"][^)]*)?\)")
_REFDEF = re.compile(r"(?m)^\s*\[([^\]]+)\]:\s*(https?://\S+).*$")
_REF = re.compile(r"\[([^\]]+)\](?:\[([^\]]*)\])?")
# Finding E1: a removable citation may hug a following comma ("[1], and").
# That comma is the citation's presentational punctuation, not claim
# content, so it is consumed with the token. A comma followed by a digit
# is never consumed: digit-grouping commas are content.
_REF_HUG = re.compile(_REF.pattern + r"(?:\s*,(?!\d))?")
_VERB = r"(?:costs?|includes?|supports?|provides?|offers?|has|have|is|are|allows?|requires?|contains?|uses?|was|were|does|do|can|will)"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _url_key(url: str) -> str:
    # URL fragments select within a captured document. Query strings remain
    # significant; neither host aliases nor trailing paths are guessed.
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, p.query, ""))


def _clean(text: str) -> str:
    text = _LINK.sub(lambda m: m.group(1) if not re.fullmatch(r"(?:\d+|source|cite|citation)", m.group(1), re.I) else "", text)
    text = re.sub(r"<https?://[^>]+>|https?://\S+", "", text)
    # Source brackets and footnote/formatting markers remain evidence. In
    # particular [2024] and a trailing * cannot be erased into unqualified
    # support. Conservative formatting misses can go to the judge residue.
    return re.sub(r"\s+", " ", text).strip(" \t\r\n.!?;:")


def _clean_claim(text: str, mapping: dict) -> str:
    # Only references defined by captured attribution are removable. Source
    # bracketed prose such as [only if paid annually] must retain its meaning.
    # A non-removable reference is returned verbatim, hugging comma included.
    text = _REF_HUG.sub(
        lambda m: "" if ((m.group(2) or m.group(1)) in mapping or
                         re.fullmatch(r"\d+(?:\s*,\s*\d+)*", m.group(2) or m.group(1)))
        else m.group(0), text)
    # Removing a citation can leave its empty parentheses behind ("([1])").
    # Empty parentheses carry no meaning; non-empty parentheses are claim
    # content (e.g. a "(per month)" unit context) and are never touched.
    text = re.sub(r"\(\s*\)", "", text)
    # A comma orphaned at the end of the cleaned claim (e.g. "([1])," after
    # the removals above) is a separator remnant, not content. Passages
    # never pass through here, so passage normalization is unchanged.
    return _clean(text).rstrip(" ,")


def _norm(text: str) -> str:
    return _clean(text).casefold()


def _citation_map(run: dict) -> dict:
    mapping = {}
    for m in _REFDEF.finditer(run["final_answer"]):
        mapping[m.group(1)] = [m.group(2).rstrip(".")]
    supplied = run.get("citations", {})
    if not isinstance(supplied, dict):
        raise ValueError("run citations must be an object mapping reference labels to URLs")
    for label, urls in supplied.items():
        urls = [urls] if isinstance(urls, str) else urls
        if not isinstance(urls, list) or not urls or not all(isinstance(u, str) and u.startswith(("https://", "http://")) for u in urls):
            raise ValueError(f"citation {label!r} must map to a URL or nonempty list of URLs")
        if str(label) in mapping and mapping[str(label)] != urls:
            raise ValueError(f"conflicting citation definition for {label!r}")
        mapping[str(label)] = urls
    return mapping


def _citations(text: str, mapping: dict) -> list[dict]:
    out = []
    covered = []
    for m in _LINK.finditer(text):
        out.append({"reference": m.group(0), "url": m.group(2)})
        covered.append(m.span())
    for m in _REF.finditer(text):
        if any(a <= m.start() < b for a, b in covered):
            continue
        label = m.group(2) or m.group(1)
        if label in mapping:
            out.extend({"reference": m.group(0), "url": u} for u in mapping[label])
        elif re.fullmatch(r"\d+(?:\s*,\s*\d+)*", label):
            for part in re.split(r"\s*,\s*", label):
                if part in mapping:
                    out.extend({"reference": m.group(0), "url": u} for u in mapping[part])
                else:
                    out.append({"reference": m.group(0), "url": None, "error": "unresolved reference"})
        else:
            # Ordinary bracketed prose is not assumed to cite a source.
            continue
    for m in _URL.finditer(text):
        if not any(a <= m.start() < b for a, b in covered):
            out.append({"reference": m.group(0), "url": m.group(0).rstrip(".,;")})
    unique = []
    seen = set()
    for row in out:
        key = (row["reference"], row["url"])
        if key not in seen:
            unique.append(row); seen.add(key)
    return unique


def _segments(answer: str):
    """Sentence/line spans; punctuation inside links, decimals and brackets protected."""
    protected = set()
    for pattern in (_LINK, _REFDEF, _URL):
        for m in pattern.finditer(answer):
            protected.update(range(m.start(), m.end()))
    depth = 0
    start = 0
    for i, ch in enumerate(answer):
        if ch in "([": depth += 1
        if ch in ")]": depth = max(0, depth - 1)
        is_stop = ch == "\n" or (ch in ".!?" and depth == 0 and i not in protected and
                  (i + 1 == len(answer) or answer[i + 1].isspace()) and
                  not (ch == "." and i and answer[i-1].isdigit() and i+1 < len(answer) and answer[i+1].isdigit()))
        if is_stop:
            yield start, i + 1
            start = i + 1
    if start < len(answer): yield start, len(answer)


def extract_claims(run: dict) -> list[dict]:
    """Extract stable candidates with exact answer spans and explicit citations.

    Optional ``claim_citations`` maps stable claim IDs to URL lists. This is
    captured attribution data, never accepted claim text or pregraded verdicts.
    It allows a task pack to supply separately captured citation metadata.
    """
    answer = run.get("final_answer")
    if not isinstance(answer, str) or not isinstance(run.get("run_id"), str):
        raise ValueError("claim extraction requires final_answer and run_id strings")
    mapping = _citation_map(run)
    attribution = run.get("claim_citations", {})
    if not isinstance(attribution, dict):
        raise ValueError("claim_citations must be an object")
    claims = []
    used_attribution = set()
    consumed_citations_until = 0
    for lo, hi in _segments(answer):
        # A post-sentence reference belongs only to its preceding sentence.
        # It must be consumed before the next segment is considered (A1).
        lo = max(lo, min(hi, consumed_citations_until))
        raw = answer[lo:hi]
        if _REFDEF.fullmatch(raw.rstrip("\n")):
            continue
        heading = re.match(r"\s*#{1,6}\s+", raw)
        if heading:
            heading_content = _clean_claim(raw[heading.end():], mapping)
            if not re.search(r"\b" + _VERB + r"\b", heading_content, re.I):
                continue  # Nonfactual headings such as Overview are labels.
            lo += heading.end()
            raw = answer[lo:hi]
        leading = re.match(r"\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:SYNTHETIC fixture answer:\s*)?", raw, re.I).end()
        lo += leading
        hi = lo + len(answer[lo:hi].rstrip())
        if lo >= hi: continue
        sentence = answer[lo:hi]
        if not _clean_claim(sentence, mapping): continue
        # A citation-only fragment after sentence punctuation belongs to the
        # preceding sentence. Bind it there rather than losing that evidence.
        if not re.search(r"[A-Za-z]", _clean_claim(sentence, mapping)):
            continue
        citations = _citations(sentence, mapping)
        # Typical prose puts citation tokens after a full stop.
        tail = answer[hi:]
        trailing = re.match(r"[ \t]*((?:\[[^\]\n]+\](?:\([^\n)]+\))?[ \t]*)+)", tail)
        if (trailing and not tail[trailing.end():].startswith(":") and
                not _clean_claim(trailing.group(1), mapping)):
            citations += _citations(trailing.group(1), mapping)
            consumed_citations_until = max(consumed_citations_until, hi + trailing.end())
        # Split only explicit verbal conjuncts. Subject ellipsis is restored as
        # a labeled context prefix; the raw text and offsets stay untouched.
        boundaries = []
        for m in re.finditer(r"\s+(?:and|but)\s+|;\s*", sentence, re.I):
            rhs = _clean_claim(sentence[m.end():], mapping)
            if re.match(_VERB + r"\b", rhs, re.I) or re.match(r"[^,;.!?]{1,100}?\s+" + _VERB + r"\b", rhs, re.I):
                boundaries.append((m.start(), m.end()))
        pieces = []
        cursor = 0
        for a, b in boundaries:
            pieces.append((cursor, a)); cursor = b
        pieces.append((cursor, len(sentence)))
        # A sole citation at the end conventionally applies to the compound
        # sentence. When earlier clauses cite separately, each clause keeps
        # only its own citations and cannot borrow a sibling's supporting URL.
        shared_tail_citations = not any(
            _citations(sentence[a:b], mapping) for a, b in pieces[:-1]
        )
        context_subject = ""
        for a, b in pieces:
            part = sentence[a:b]
            trim = len(part) - len(part.lstrip())
            a += trim; part = sentence[a:b].rstrip()
            b = a + len(part)
            clean = _clean_claim(part, mapping)
            if not clean or not re.search(r"[A-Za-z]", clean): continue
            if clean.casefold() in {"thanks", "thank you", "hello", "hi"}: continue
            prefix = ""
            if re.match(_VERB + r"\b", clean, re.I) and context_subject:
                prefix = context_subject + " "
            subject = re.match(r"^(.+?)\s+" + _VERB + r"\b", clean, re.I)
            if subject: context_subject = subject.group(1)
            number = len(claims) + 1
            cid = f"{run['run_id']}:claim:{number}"
            chosen_citations = citations if shared_tail_citations else _citations(part, mapping)
            own_citations = [dict(c) for c in chosen_citations]
            if cid in attribution:
                urls = attribution[cid]
                urls = [urls] if isinstance(urls, str) else urls
                if not isinstance(urls, list) or not urls or not all(isinstance(u, str) and u.startswith(("https://", "http://")) for u in urls):
                    raise ValueError(f"claim_citations {cid!r} must contain URLs")
                own_citations.extend({"reference": "captured claim_citations", "url": u} for u in urls)
                used_attribution.add(cid)
            claims.append({
                "claim_id": cid, "text": answer[lo+a:lo+b],
                "answer_span": {"start": lo+a, "end": lo+b},
                "normalized_claim": prefix + clean,
                "context_prefix": prefix,
                "citations": own_citations,
                "answer_sha256": _sha(answer),
            })
    unknown = set(attribution) - used_attribution
    if unknown:
        raise ValueError(f"claim_citations references unknown claim IDs: {sorted(unknown)}")
    return claims


def populate_claims(run: dict) -> list[dict]:
    """Fill the run's placeholder from its actual final answer; never trust supplied claims."""
    run["claims"] = extract_claims(run)
    run["claims_note"] = "Session 2 rule-based extraction; review extraction limits."
    run["claim_extraction"] = {"method": "rule-based-v1", "limits": list(EXTRACTION_LIMITS)}
    return run["claims"]


def _passages(fetch: dict, index: int):
    content = fetch["content_markdown"]
    for lo, hi in _segments(content):
        raw = content[lo:hi]
        offset = len(raw) - len(raw.lstrip())
        lo += offset; hi = lo + len(content[lo:hi].rstrip())
        # Punctuation may have split a source note marker from its statement.
        # Keep an immediately following marker in that statement's passage so
        # "fact. *" and "fact. [2024]" cannot pass as unqualified evidence.
        following_marker = re.match(r"[ \t]*(?:\[[^\]\n]+\]|[*†‡]+)", content[hi:])
        if following_marker:
            hi += following_marker.end()
        if hi > lo:
            yield {"fetch_index": index, "url": fetch["url"], "start": lo, "end": hi,
                   "text": content[lo:hi], "document_sha256": _sha(content)}


def _assertion(text: str):
    """Very narrow scalar assertions, including subject and unit context.

    Equality never drops negation or qualifiers. Numeric mismatch is a
    contradiction only when subject, relation and unit context match exactly.
    """
    clean = _norm(text)
    if re.search(r"\b(?:not|never|no|may|might|if|unless|up to|at least|at most|approximately|about|formerly|previously|example|claim|claims|false|incorrect)\b", clean):
        return None
    match = re.fullmatch(r"(.+?)\s+(costs?|is priced at|[—–-])\s+(\$\d+(?:,\d{3})*(?:\.\d+)?)\s+(per\s+\w+|a\s+\w+)", clean)
    if match:
        return (match.group(1), "price", Decimal(match.group(3).replace("$", "").replace(",", "")), match.group(4))
    match = re.fullmatch(r"(.+?)\s+(includes?|provides?|allows?)\s+(\d+(?:,\d{3})*(?:\.\d+)?)\s+(.+)", clean)
    if match:
        return (match.group(1), "includes", Decimal(match.group(3).replace(",", "")), match.group(4))
    return None


def _exact_statement(claim: str, passage: str) -> bool:
    # Complete statement equality, not substring containment. This prevents
    # 'not CLAIM', 'OtherCo says CLAIM' and extra qualifications from passing.
    left, right = _norm(claim), _norm(passage)
    if not left or left != right: return False
    if re.search(r"\b(?:if|unless|may|might|claim|claims|example|allegedly)\b", right):
        return False
    return True


def _bind(claim: dict, fetches: list[dict]):
    indices, errors = [], []
    for citation in claim["citations"]:
        if citation.get("error"):
            errors.append(citation["error"] + ": " + citation["reference"]); continue
        url = citation.get("url")
        matches = [i for i, f in enumerate(fetches) if _url_key(f["url"]) == _url_key(url)]
        if not matches:
            errors.append("cited URL was not fetched: " + url)
        for i in matches:
            if i not in indices: indices.append(i)
    return indices, errors


def _deterministic(claim: dict, run: dict) -> dict:
    indices, errors = _bind(claim, run["fetches"])
    row = {**claim, "method": "DETERMINISTIC", "binding_errors": errors,
           "bound_fetch_indices": indices, "passages": [], "absence": None,
           "verdict": "UNSUPPORTED", "needs_judge": False}
    if not claim["citations"]:
        row.update(reason="No citation supplied for this claim.", absence="No cited evidence; no URL inferred from question assignment or relied_on.")
        return row
    if errors or not indices:
        row.update(reason="Citation binding failed.", absence="At least one cited reference is unresolved or was never fetched.")
        return row
    usable = [i for i in indices if run["fetches"][i].get("statusCode") == 200 and isinstance(run["fetches"][i].get("content_markdown"), str)]
    if not usable:
        row.update(reason="Cited fetches contain no successful 200 document.", absence="No eligible cited document; error responses cannot support factual claims.")
        return row
    assertion = _assertion(claim["normalized_claim"])
    supporting, contradicting, qualified = [], [], []
    for index in usable:
        for passage in _passages(run["fetches"][index], index):
            # Keep visible unresolved source markers with their actual passage
            # receipts, even when our narrow matcher cannot interpret them.
            if re.search(r"\[[^\]]+\]|[*†‡]", passage["text"]):
                qualified.append(passage)
            found = _assertion(passage["text"])
            if _exact_statement(claim["normalized_claim"], passage["text"]) or (assertion and found == assertion):
                supporting.append(passage)
            elif assertion and found and assertion[:2] == found[:2] and assertion[3] == found[3] and assertion[2] != found[2]:
                contradicting.append(passage)
    if contradicting:
        row.update(verdict="CONTRADICTED", passages=contradicting + supporting,
                   reason="Cited document states a different scalar value for the same subject, relation and unit context.")
        if supporting:
            row["reason"] = "Cited evidence conflicts: both matching and contradictory scalar passages are present."
            row["needs_judge"] = True
    elif supporting:
        row.update(verdict="SUPPORTED", passages=supporting, reason="Complete statement or narrow subject/relation/value assertion matches a cited captured passage.")
    else:
        row.update(reason="No complete statement or narrow scalar assertion match in cited documents.",
                   absence="No supporting passage identified by deterministic checks in bound fetch indices " + str(usable) + ". Semantic entailment remains unmeasured.", needs_judge=True)
        if qualified:
            row["reason"] += " Source qualification/reference markers remain unresolved; no markers were removed to establish support."
            row["qualification_passages"] = qualified
    return row


def _judge_row(decision: dict, original: dict, run: dict) -> dict:
    if not isinstance(decision, dict) or decision.get("verdict") not in VERDICTS:
        raise ValueError("judge decision needs a valid verdict")
    if not original["needs_judge"]:
        raise ValueError("judge decisions are allowed only for deterministic semantic residue")
    provenance = decision.get("judge")
    if not isinstance(provenance, dict) or not all(isinstance(provenance.get(k), str) and provenance[k].strip() for k in ("seat", "model", "reviewed_at")):
        raise ValueError("judge decision needs seat, model and reviewed_at provenance")
    try: datetime.fromisoformat(provenance["reviewed_at"].replace("Z", "+00:00"))
    except ValueError as exc: raise ValueError("judge reviewed_at must be an ISO timestamp") from exc
    if not isinstance(decision.get("reasoning"), str) or not decision["reasoning"].strip():
        raise ValueError("judge decision needs reasoning")
    passages = decision.get("passages", [])
    if not isinstance(passages, list): raise ValueError("judge passages must be a list")
    checked = []
    for passage in passages:
        if not isinstance(passage, dict): raise ValueError("judge passage must be an object")
        index, start, end = (passage.get(k) for k in ("fetch_index", "start", "end"))
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (index, start, end)) or index not in original["bound_fetch_indices"]:
            raise ValueError("judge passage must reference a bound fetch and integer offsets")
        fetch = run["fetches"][index]
        content = fetch["content_markdown"]
        if fetch.get("statusCode") != 200 or not 0 <= start < end <= len(content) or passage.get("text") != content[start:end]:
            raise ValueError("judge passage does not equal the captured successful document at those offsets")
        checked.append({**passage, "url": fetch["url"], "document_sha256": _sha(content)})
    if decision["verdict"] in ("SUPPORTED", "CONTRADICTED") and not checked:
        raise ValueError("judge support/contradiction requires a captured passage")
    absence = decision.get("absence")
    if decision["verdict"] == "UNSUPPORTED" and (not isinstance(absence, str) or not absence.strip()):
        raise ValueError("judge UNSUPPORTED requires an explicit absence declaration")
    return {**original, "method": "JUDGE", "verdict": decision["verdict"],
            "passages": checked, "absence": absence, "reason": decision["reasoning"],
            "judge": dict(provenance), "needs_judge": False,
            "deterministic_verdict": original["verdict"]}


def grade_claim_support(run: dict, judge_decisions=None) -> dict:
    """Return deterministic and judge ledgers separately, with receipted flags.

    This function always re-extracts from final_answer, so prefilled ``claims``
    cannot silently hide a sentence or inject a supplied SUPPORTED verdict.
    Judge decisions are data from a separately operated seat; this code makes
    no model/API calls and does not certify the judge's semantic judgment.
    """
    claims = populate_claims(run)
    rows = [_deterministic(c, run) for c in claims]
    decisions = [] if judge_decisions is None else judge_decisions
    if not isinstance(decisions, list): raise ValueError("judge_decisions must be a list")
    by_id = {r["claim_id"]: r for r in rows}
    judged, seen = [], set()
    for decision in decisions:
        if not isinstance(decision, dict): raise ValueError("judge decision must be an object")
        cid = decision.get("claim_id")
        if cid not in by_id: raise ValueError(f"judge decision references unknown claim: {cid!r}")
        if cid in seen: raise ValueError(f"duplicate judge decision for {cid!r}")
        seen.add(cid)
        judged.append(_judge_row(decision, by_id[cid], run))
    flags = []
    for row in rows + judged:
        if row["verdict"] == "SUPPORTED": continue
        grader = "claim-support" if row["method"] == "DETERMINISTIC" else "claim-support-judge"
        flags.append({"flag_id": f"{row['claim_id']}:{grader}", "grader": grader,
                      "dimension": "Claim support", "criterion": "Each factual claim must be supported by its cited captured evidence.",
                      "subject": row["text"], "evidence": row})
    def counts(pool):
        return {**{v: sum(r["verdict"] == v for r in pool) for v in VERDICTS}, "total": len(pool)}
    return {"grader": "claim-support", "claims": rows, "judge_claims": judged,
            "deterministic": counts(rows), "judge": counts(judged),
            "flag_count": len(flags), "flags": flags,
            "extraction": run["claim_extraction"]}
