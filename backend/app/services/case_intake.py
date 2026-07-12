"""
案件受理分析服务
Case intake analysis: extracts governing law, seat, parties and claims
from the uploaded case documents so every downstream prompt is
jurisdiction-aware.
"""

import logging
from typing import Any, Dict, List, Optional

from ..utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


CASE_INTAKE_SYSTEM_PROMPT = """You are a senior arbitration case analyst. You will receive the documents of a commercial arbitration matter (contracts, pleadings, evidence, authorities) and a matter description. Extract the structural facts of the case.

**IMPORTANT: Output valid JSON only. No other content.**

Output format:
```json
{
    "governing_law": "The governing substantive law (e.g. 'Indian Contract Act, 1872 / Arbitration and Conciliation Act, 1996', 'New York law', 'English law'). If the documents specify a governing-law clause, quote its source document. If unclear, state your best inference and mark it '(inferred)'.",
    "seat": "Seat/place of arbitration if stated, else null",
    "arbitral_rules": "Institutional rules if stated (e.g. ICC, SIAC, LCIA, UNCITRAL), else null",
    "claimant": "Name of the claimant party",
    "respondent": "Name of the respondent party",
    "claims": [
        {
            "id": "claim_1",
            "title": "Short claim title (e.g. 'Breach of delivery obligations')",
            "basis": "Legal basis (contract clause / statute / doctrine)",
            "relief": "Relief sought for this claim (amount if quantified)"
        }
    ],
    "relief_sought": "Overall relief sought by claimant (total quantum if stated)",
    "key_defenses": ["Respondent's main defenses, e.g. 'force majeure', 'limitation of liability clause'"],
    "case_summary": "5-8 sentence neutral summary of the dispute"
}
```

Rules:
- Ground everything in the documents; never invent parties, amounts, or clauses.
- If a field is genuinely not determinable, use null (or '(inferred)' suffix for governing_law).
- claims must list each distinct cause of action / counterclaim separately (counterclaims get "(counterclaim)" in the title).
"""

# 传给 LLM 的文本最大长度
MAX_TEXT_LENGTH_FOR_LLM = 50000


class CaseIntakeAnalyzer:
    """从案件文档中提取管辖法律、当事人和诉请结构"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def analyze(
        self,
        document_texts: List[str],
        matter_description: str,
        governing_law_override: Optional[str] = None,
        relief_sought: Optional[str] = None,
    ) -> Dict[str, Any]:
        combined_text = "\n\n---\n\n".join(document_texts)
        if len(combined_text) > MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:MAX_TEXT_LENGTH_FOR_LLM] + "\n\n...(truncated for analysis)..."

        user_message = f"""## Matter description

{matter_description}

## Case documents

{combined_text}
"""
        if governing_law_override:
            user_message += f"\n## User-specified governing law (authoritative — use this)\n\n{governing_law_override}\n"
        if relief_sought:
            user_message += f"\n## User-specified relief sought\n\n{relief_sought}\n"

        result = self.llm_client.chat_json(
            messages=[
                {"role": "system", "content": CASE_INTAKE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=8192,
        )

        # 用户覆盖优先
        if governing_law_override:
            result["governing_law"] = governing_law_override
        if relief_sought and not result.get("relief_sought"):
            result["relief_sought"] = relief_sought

        result.setdefault("claims", [])
        result.setdefault("key_defenses", [])
        logger.info(
            "Case intake: governing_law=%s, claimant=%s, respondent=%s, %d claims",
            result.get("governing_law"), result.get("claimant"),
            result.get("respondent"), len(result["claims"]),
        )
        return result


def format_case_context(case_meta: Optional[Dict[str, Any]]) -> str:
    """将 case_meta 渲染为可嵌入下游提示词的上下文块"""
    if not case_meta:
        return ""
    lines = ["## Case context"]
    if case_meta.get("governing_law"):
        lines.append(f"- Governing law: {case_meta['governing_law']}")
    if case_meta.get("seat"):
        lines.append(f"- Seat of arbitration: {case_meta['seat']}")
    if case_meta.get("arbitral_rules"):
        lines.append(f"- Arbitral rules: {case_meta['arbitral_rules']}")
    if case_meta.get("claimant"):
        lines.append(f"- Claimant: {case_meta['claimant']}")
    if case_meta.get("respondent"):
        lines.append(f"- Respondent: {case_meta['respondent']}")
    for claim in case_meta.get("claims", []):
        lines.append(f"- Claim [{claim.get('id')}]: {claim.get('title')} — basis: {claim.get('basis')}; relief: {claim.get('relief')}")
    if case_meta.get("key_defenses"):
        lines.append(f"- Key defenses: {', '.join(case_meta['key_defenses'])}")
    if case_meta.get("relief_sought"):
        lines.append(f"- Relief sought: {case_meta['relief_sought']}")
    if case_meta.get("case_summary"):
        lines.append(f"- Summary: {case_meta['case_summary']}")
    return "\n".join(lines)
