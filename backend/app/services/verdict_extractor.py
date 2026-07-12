"""
裁决提取服务
Verdict extractor: after the deliberation simulation completes (env alive),
interviews each arbitrator through the existing IPC channel with a
structured-JSON ballot, parses and aggregates the votes into a predicted
award, and persists verdict.json in the simulation directory.
"""

import json
import os
import re
from datetime import datetime
from statistics import median
from typing import Any, Dict, List, Optional

from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .simulation_runner import SimulationRunner

logger = get_logger('mirofish.verdict')

ARBITRATOR_AGENTS = [
    {"agent_id": 0, "name": "Presiding Arbitrator", "philosophy": "doctrinal textualist"},
    {"agent_id": 1, "name": "Co-Arbitrator (Commercial)", "philosophy": "commercially pragmatic"},
    {"agent_id": 2, "name": "Co-Arbitrator (Equity)", "philosophy": "equity and good-faith focused"},
]

BALLOT_PROMPT_TEMPLATE = """The hearing and deliberation are now closed. As a member of the tribunal, cast your FINAL VOTE on the award. Respond with VALID JSON ONLY, no other text, in exactly this schema:

{{
  "findings": [
    {{
      "claim_id": "<id>",
      "claim_title": "<title>",
      "finding": "claimant" or "respondent",
      "confidence": <0.0-1.0, how certain you are in this finding>,
      "reasoning": "<2-4 sentences: the decisive rule/clause and evidence>",
      "decisive_evidence": "<the single most decisive piece of evidence or clause>"
    }}
  ],
  "damages_awarded": <total monetary award to Claimant as a plain number, 0 if none, null if not quantifiable>,
  "damages_currency": "<currency code or null>",
  "overall_view": "<1-2 sentence summary of your overall disposition>"
}}

The claims you must vote on:
{claims_list}

Vote strictly according to your judicial philosophy, the record of these proceedings, and the governing law ({governing_law}). "finding" is who prevails ON THAT CLAIM."""


def _sim_dir(simulation_id: str) -> str:
    return os.path.join(SimulationRunner.RUN_STATE_DIR, simulation_id)


def _verdict_path(simulation_id: str) -> str:
    return os.path.join(_sim_dir(simulation_id), "verdict.json")


class VerdictExtractor:
    """采访仲裁员并聚合成结构化裁决预测"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    # ---------- 解析 ----------

    def _parse_ballot(self, raw: Any) -> Optional[Dict[str, Any]]:
        """从采访回复中解析JSON选票（宽容解析 + LLM修复兜底）"""
        if isinstance(raw, dict):
            # 双平台采访会返回 {platform: text}；仲裁模式只有 reddit
            raw = raw.get("reddit") or next(iter(raw.values()), "")
        text = str(raw or "")
        # 直接找最外层JSON对象
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end + 1])
                data = self._sanitize_ballot(data)
                if data:
                    return data
            except json.JSONDecodeError:
                pass
        # LLM修复兜底
        try:
            data = self.llm_client.chat_json(
                messages=[
                    {"role": "system", "content": "Convert the arbitrator's answer into the requested ballot JSON schema (findings[], damages_awarded, damages_currency, overall_view). Each finding must be an object with claim_id, finding, confidence, reasoning. Output valid JSON only. If a field is missing, infer conservatively or use null."},
                    {"role": "user", "content": text[:8000]},
                ],
                temperature=0.1,
                max_tokens=8192,
            )
            data = self._sanitize_ballot(data)
            if data:
                return data
        except Exception as e:
            logger.warning(f"Ballot repair failed: {e}")
        return None

    @staticmethod
    def _sanitize_ballot(data: Any) -> Optional[Dict[str, Any]]:
        """校验选票结构：findings 必须是 dict 列表，过滤掉字符串等异常项"""
        if not isinstance(data, dict):
            return None
        findings = data.get("findings")
        if not isinstance(findings, list):
            return None
        data["findings"] = [f for f in findings if isinstance(f, dict)]
        return data if data["findings"] else None

    # ---------- 聚合 ----------

    def _aggregate(self, ballots: List[Dict[str, Any]], case_meta: Dict[str, Any]) -> Dict[str, Any]:
        claims = case_meta.get("claims") or []
        claim_ids = [c.get("id") for c in claims] or sorted({
            f.get("claim_id") for b in ballots for f in b.get("ballot", {}).get("findings", [])
        })

        per_claim = []
        claimant_wins = 0
        for cid in claim_ids:
            votes = []
            for b in ballots:
                for f in b.get("ballot", {}).get("findings", []):
                    if f.get("claim_id") == cid or (not f.get("claim_id") and len(claim_ids) == 1):
                        votes.append({
                            "arbitrator": b["arbitrator"]["name"],
                            "finding": (f.get("finding") or "").lower(),
                            "confidence": max(0.0, min(1.0, float(f.get("confidence") or 0.5))),
                            "reasoning": f.get("reasoning", ""),
                            "decisive_evidence": f.get("decisive_evidence", ""),
                        })
                        break
            c_votes = [v for v in votes if v["finding"] == "claimant"]
            r_votes = [v for v in votes if v["finding"] == "respondent"]
            majority = "claimant" if len(c_votes) > len(r_votes) else "respondent"
            majority_votes = c_votes if majority == "claimant" else r_votes
            confidence = (
                sum(v["confidence"] for v in majority_votes) / len(majority_votes)
                if majority_votes else 0.5
            )
            # 3票制下：2-1多数按票数比例折减置信度
            vote_ratio = len(majority_votes) / len(votes) if votes else 0.5
            claim_title = next((c.get("title") for c in claims if c.get("id") == cid), cid)
            if majority == "claimant":
                claimant_wins += 1
            per_claim.append({
                "claim_id": cid,
                "claim_title": claim_title,
                "majority_finding": majority,
                "vote_split": f"{len(majority_votes)}-{len(votes) - len(majority_votes)}",
                "unanimous": len(majority_votes) == len(votes) and len(votes) > 0,
                "probability": round(confidence * vote_ratio + (1 - vote_ratio) * 0.5, 3),
                "votes": votes,
            })

        # 损害赔偿区间（多数方裁决金额）
        amounts = [
            b["ballot"].get("damages_awarded")
            for b in ballots
            if isinstance(b["ballot"].get("damages_awarded"), (int, float))
        ]
        currency = next(
            (b["ballot"].get("damages_currency") for b in ballots if b["ballot"].get("damages_currency")),
            None,
        )
        damages = {
            "min": min(amounts) if amounts else None,
            "max": max(amounts) if amounts else None,
            "median": median(amounts) if amounts else None,
            "currency": currency,
            "per_arbitrator": [
                {"arbitrator": b["arbitrator"]["name"], "amount": b["ballot"].get("damages_awarded")}
                for b in ballots
            ],
        }

        overall_probability = (
            round(sum(pc["probability"] for pc in per_claim) / len(per_claim), 3)
            if per_claim else None
        )

        return {
            "generated_at": datetime.now().isoformat(),
            "claimant": case_meta.get("claimant"),
            "respondent": case_meta.get("respondent"),
            "governing_law": case_meta.get("governing_law"),
            "headline": {
                "claims_total": len(per_claim),
                "claims_for_claimant": claimant_wins,
                "overall_probability": overall_probability,
            },
            "per_claim": per_claim,
            "damages": damages,
            "arbitrator_ballots": ballots,
            "disclaimer": "Simulation-based prediction generated by AI agents. Not legal advice.",
        }

    # ---------- 主流程 ----------

    def extract(self, simulation_id: str, case_meta: Dict[str, Any], timeout: float = 180.0) -> Dict[str, Any]:
        """采访3名仲裁员，聚合并持久化 verdict.json"""
        claims = case_meta.get("claims") or []
        claims_list = "\n".join(
            f"- {c.get('id')}: {c.get('title')} (basis: {c.get('basis')}; relief: {c.get('relief')})"
            for c in claims
        ) or "- claim_1: The Claimant's claim as framed in the proceedings"

        prompt = BALLOT_PROMPT_TEMPLATE.format(
            claims_list=claims_list,
            governing_law=case_meta.get("governing_law") or "the applicable law",
        )

        ballots = []
        errors = []
        for arb in ARBITRATOR_AGENTS:
            logger.info(f"Collecting ballot from {arb['name']} (agent {arb['agent_id']})")
            try:
                result = SimulationRunner.interview_agent(
                    simulation_id=simulation_id,
                    agent_id=arb["agent_id"],
                    prompt=prompt,
                    platform="reddit",
                    timeout=timeout,
                )
            except Exception as e:
                errors.append(f"{arb['name']}: {e}")
                continue
            if not result.get("success"):
                errors.append(f"{arb['name']}: {result.get('error')}")
                continue
            ballot = self._parse_ballot(result.get("result"))
            if ballot:
                ballots.append({"arbitrator": arb, "ballot": ballot})
            else:
                errors.append(f"{arb['name']}: ballot unparseable")

        if not ballots:
            raise RuntimeError(f"No arbitrator ballots collected. Errors: {errors}")

        verdict = self._aggregate(ballots, case_meta)
        if errors:
            verdict["warnings"] = errors

        with open(_verdict_path(simulation_id), "w", encoding="utf-8") as f:
            json.dump(verdict, f, ensure_ascii=False, indent=2)
        logger.info(f"Verdict saved: {_verdict_path(simulation_id)} "
                    f"({len(ballots)}/{len(ARBITRATOR_AGENTS)} ballots)")
        return verdict


def load_verdict(simulation_id: str) -> Optional[Dict[str, Any]]:
    path = _verdict_path(simulation_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
