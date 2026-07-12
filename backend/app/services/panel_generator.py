"""
仲裁庭面板生成器
Panel generator for arbitration mode: synthesizes the arbitral tribunal
(3 arbitrators with distinct judicial philosophies) plus partisan counsel
agents for claimant and respondent, grounded in the Zep case graph.

Output is OASIS-compatible (reuses OasisAgentProfile / save_profiles), so
the simulation runner needs no changes to load the panel.
"""

import time
from typing import Any, Callable, Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger
from .case_intake import format_case_context
from .oasis_profile_generator import OasisAgentProfile, OasisProfileGenerator

logger = get_logger('mirofish.panel_generator')


# 仲裁员配置：三种审裁哲学
ARBITRATOR_SPECS = [
    {
        "role_key": "presiding",
        "name": "Presiding Arbitrator",
        "username": "presiding_arbitrator",
        "philosophy": "doctrinal textualist",
        "philosophy_detail": (
            "You interpret contracts by their plain text and apply the governing law strictly. "
            "Contractual allocation of risk is respected as written; you are skeptical of arguments "
            "that ask the tribunal to rewrite the parties' bargain. You preside: you frame the issues, "
            "keep proceedings orderly, and synthesize the tribunal's final positions."
        ),
    },
    {
        "role_key": "co_arbitrator_1",
        "name": "Co-Arbitrator (Commercial)",
        "username": "co_arbitrator_commercial",
        "philosophy": "commercially pragmatic",
        "philosophy_detail": (
            "You interpret disputes through business common sense and commercial reasonableness. "
            "You ask what sophisticated commercial parties would have intended, weigh industry practice "
            "heavily, and prefer outcomes that reflect the commercial reality of the transaction."
        ),
    },
    {
        "role_key": "co_arbitrator_2",
        "name": "Co-Arbitrator (Equity)",
        "username": "co_arbitrator_equity",
        "philosophy": "equity and good-faith focused",
        "philosophy_detail": (
            "You weigh fairness, good faith, and the parties' conduct. You scrutinize whether each party "
            "acted honestly and cooperatively, consider proportionality of remedies, and are alert to "
            "opportunistic behavior even when the text superficially permits it."
        ),
    },
]

COUNSEL_SPECS = [
    {"side": "claimant", "name_template": "Lead Counsel for {party}", "username": "claimant_counsel"},
    {"side": "respondent", "name_template": "Lead Counsel for {party}", "username": "respondent_counsel"},
]


ARBITRATOR_PERSONA_PROMPT = """You are writing the system persona for an AI agent that will act as an arbitrator in a simulated commercial arbitration. Output valid JSON only: {{"bio": "...", "persona": "..."}}.

- "bio": 1-2 sentences introducing the arbitrator (role on tribunal + philosophy).
- "persona": a detailed (~1500 characters) second-person instruction set covering:
  1. Identity: {name}, {philosophy} arbitrator on a three-member tribunal.
  2. Judicial philosophy: {philosophy_detail}
  3. Duties: strictly NEUTRAL. Never advocate for a party. Reason from the evidence, the contract, and the governing law. When you post or comment, write substantive analysis (identify the issue, the applicable rule/clause, the evidence, and your provisional view). Ask both sides probing questions during tribunal questioning. During deliberation, state your provisional findings per claim with reasons, engage with your co-arbitrators' views, and be willing to change your mind if persuaded.
  4. Style: formal, precise legal prose. Refer to parties as Claimant/Respondent. Cite specific clauses, evidence, and authorities from the case record whenever possible. Never invent facts not in the record.
  5. The proceedings move through phases announced by the Presiding Arbitrator's procedural posts (openings, party submissions, tribunal questions, closings, deliberation). Act according to the current phase visible in the thread.

## Case record
{case_context}

## Key facts retrieved from the case knowledge graph
{zep_context}
"""

COUNSEL_PERSONA_PROMPT = """You are writing the system persona for an AI agent that will act as lead counsel for the {side} in a simulated commercial arbitration. Output valid JSON only: {{"bio": "...", "persona": "..."}}.

- "bio": 1-2 sentences introducing counsel and who they represent ({party}).
- "persona": a detailed (~1500 characters) second-person instruction set covering:
  1. Identity: {name}, representing {party} (the {side}).
  2. Duty: ZEALOUS but professional advocacy for {party}'s position — and only that position. Advance your client's claims/defenses; rebut the opposing side's arguments point by point; concede nothing material.
  3. Argumentation: ground every argument in the case record — specific contract clauses, evidence, and legal authorities under the governing law. Structure arguments as: issue → rule/clause → evidence → conclusion. Directly answer arbitrators' questions when asked, adverse facts included, but frame them favorably.
  4. Your side's core theory of the case, key claims/defenses to press, and the strongest evidence to cite (draw these from the case record below).
  5. Style: persuasive formal advocacy. Refer to parties as Claimant/Respondent. Never invent facts not in the record.
  6. The proceedings move through phases announced by the Presiding Arbitrator's procedural posts (openings, party submissions, tribunal questions, closings). Act according to the current phase visible in the thread; do not post during the tribunal's private deliberation phase.

## Case record
{case_context}

## Key facts retrieved from the case knowledge graph (your side's focus)
{zep_context}
"""


class PanelGenerator:
    """生成仲裁庭（3名仲裁员）+ 双方代理律师的 Agent Profile"""

    def __init__(self, graph_id: Optional[str] = None):
        # 复用 OasisProfileGenerator 的 LLM/Zep 客户端与保存逻辑
        self._base = OasisProfileGenerator(graph_id=graph_id)
        self.graph_id = graph_id

    # ---------- Zep 检索 ----------

    def _zep_search(self, query: str, limit: int = 25) -> str:
        """检索案件图谱，返回拼接的事实上下文（失败时返回空串）"""
        if not self._base.zep_client or not self.graph_id:
            return ""
        # Zep API 限制：查询不能超过400字符
        if len(query) > 400:
            query = query[:397] + "..."
        facts: List[str] = []
        summaries: List[str] = []
        for scope, bucket, attr in (("edges", facts, "fact"), ("nodes", summaries, "summary")):
            delay = 2.0
            for attempt in range(3):
                try:
                    result = self._base.zep_client.graph.search(
                        query=query, graph_id=self.graph_id,
                        limit=limit, scope=scope, reranker="rrf",
                    )
                    items = getattr(result, scope, None) or []
                    for item in items:
                        value = getattr(item, attr, None)
                        if value:
                            bucket.append(value)
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.warning(f"Zep search failed ({scope}): {e}")
        parts = []
        if facts:
            parts.append("Facts:\n" + "\n".join(f"- {f}" for f in facts[:20]))
        if summaries:
            parts.append("Entities:\n" + "\n".join(f"- {s}" for s in summaries[:10]))
        return "\n\n".join(parts)

    # ---------- 人设生成 ----------

    def _generate_persona(self, prompt: str, fallback_bio: str, fallback_persona: str) -> Dict[str, str]:
        try:
            response = self._base.client.chat.completions.create(
                model=self._base.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            import json as _json
            data = _json.loads(response.choices[0].message.content)
            if data.get("bio") and data.get("persona"):
                return data
        except Exception as e:
            logger.warning(f"Persona LLM generation failed, using fallback: {e}")
        return {"bio": fallback_bio, "persona": fallback_persona}

    def generate_panel(
        self,
        case_meta: Optional[Dict[str, Any]],
        progress_callback: Optional[Callable] = None,
    ) -> List[OasisAgentProfile]:
        """
        生成完整仲裁面板：user_id 0-2 为仲裁员，3-4 为双方律师。

        Returns:
            OasisAgentProfile 列表（OASIS reddit 格式兼容）
        """
        case_meta = case_meta or {}
        case_context = format_case_context(case_meta) or "No structured case metadata available."
        claimant = case_meta.get("claimant") or "the Claimant"
        respondent = case_meta.get("respondent") or "the Respondent"

        total = len(ARBITRATOR_SPECS) + len(COUNSEL_SPECS)
        profiles: List[OasisAgentProfile] = []

        # 仲裁员共享一份中立的案件事实检索
        neutral_zep = self._zep_search(
            "key claims, contract terms, evidence, defenses and legal authorities in this dispute"
        ) or "No graph context retrieved."

        for idx, spec in enumerate(ARBITRATOR_SPECS):
            if progress_callback:
                progress_callback(idx, total, f"Generating {spec['name']}")
            prompt = ARBITRATOR_PERSONA_PROMPT.format(
                name=spec["name"],
                philosophy=spec["philosophy"],
                philosophy_detail=spec["philosophy_detail"],
                case_context=case_context,
                zep_context=neutral_zep,
            )
            data = self._generate_persona(
                prompt,
                fallback_bio=f"{spec['name']} — {spec['philosophy']} arbitrator on the tribunal.",
                fallback_persona=(
                    f"You are {spec['name']}, a strictly neutral {spec['philosophy']} arbitrator. "
                    f"{spec['philosophy_detail']} Reason from the record, question both sides, "
                    "and vote per claim with reasons during deliberation.\n\n" + case_context
                ),
            )
            profiles.append(OasisAgentProfile(
                user_id=idx,
                user_name=spec["username"],
                name=spec["name"],
                bio=data["bio"],
                persona=data["persona"],
                profession="Arbitrator",
                interested_topics=["arbitration", "contract law"],
                source_entity_type="Arbitrator",
            ))

        for c_idx, spec in enumerate(COUNSEL_SPECS):
            idx = len(ARBITRATOR_SPECS) + c_idx
            if progress_callback:
                progress_callback(idx, total, f"Generating counsel ({spec['side']})")
            party = claimant if spec["side"] == "claimant" else respondent
            side_zep = self._zep_search(
                f"claims, evidence and arguments supporting {party}; weaknesses of the opposing side"
            ) or neutral_zep
            name = spec["name_template"].format(party=party)
            prompt = COUNSEL_PERSONA_PROMPT.format(
                side=spec["side"], party=party, name=name,
                case_context=case_context, zep_context=side_zep,
            )
            data = self._generate_persona(
                prompt,
                fallback_bio=f"{name} — lead counsel for the {spec['side']}.",
                fallback_persona=(
                    f"You are {name}, zealous counsel for {party} (the {spec['side']}). "
                    "Advance your client's claims/defenses grounded in the record; rebut the other side; "
                    "answer the tribunal's questions.\n\n" + case_context
                ),
            )
            profiles.append(OasisAgentProfile(
                user_id=idx,
                user_name=spec["username"],
                name=name,
                bio=data["bio"],
                persona=data["persona"],
                profession="Counsel",
                interested_topics=["arbitration", "advocacy"],
                source_entity_type="Counsel",
            ))

        if progress_callback:
            progress_callback(total, total, "Panel complete")
        logger.info(f"Generated arbitration panel: {len(profiles)} agents "
                    f"({len(ARBITRATOR_SPECS)} arbitrators, {len(COUNSEL_SPECS)} counsel)")
        return profiles

    def save_profiles(self, profiles: List[OasisAgentProfile], file_path: str, platform: str = "reddit"):
        self._base.save_profiles(profiles, file_path, platform)
