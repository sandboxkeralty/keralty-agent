"""Developer-provided capability skills (SKILL.md packages) — see backend/skills/.

Each skill lives at backend/skills/<skill_id>/SKILL.md (YAML frontmatter +
Markdown body), optionally with references/*.md alongside. Two consumption
paths (hybrid loading):

- The body's `## Core` section (short, <=~300 tokens) is baked into the
  instruction of each agent listed in frontmatter `agents` at import time,
  via core_block_for_agent().
- The FULL body plus all references is consumed deterministically in code by
  the tools listed in frontmatter `tools`, via full_guidance_for_tool()
  (e.g. tools/image_tools.py::_enrich_prompt).

Loaded once at import time — agent modules build their INSTRUCTION strings at
import, so this module must not import anything from agents/. All text is
brace-sanitized on load: skill content enters ADK-templated instructions,
where a bare {token} raises KeyError and kills every turn (the brace trap —
allowed placeholders are exactly {writing_style?} and {signature?}).
Missing/malformed skills log and skip — startup never fails because of a skill.

Validator CLI (run from backend/): python -m services.skill_registry
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
CORE_WARN_CHARS = 1200  # ~300 tokens — soft cap for instruction-baked Core blocks

KNOWN_AGENTS = {
    "OrchestratorAgent",
    "AnalysisAgent",
    "ResearchAgent",
    "WritingAgent",
    "EditingAgent",
    "ReviewAgent",
    "VisualAgent",
    "EmailAgent",
    "KnowledgeAgent",
}

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_CORE_SECTION_RE = re.compile(
    r"^##\s+core\s*$\n(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE
)


@dataclass(frozen=True)
class Skill:
    skill_id: str
    name: str
    description: str
    version: int
    agents: Tuple[str, ...]
    tools: Tuple[str, ...]
    core: str  # sanitized `## Core` section body ("" if the skill has none)
    body: str  # sanitized full SKILL.md body after frontmatter (Core included)
    references: Dict[str, str] = field(default_factory=dict)  # filename -> sanitized text
    # Provider scoping: () = all providers. Vocabulary is
    # model_registry.ModelSpec.provider: "google" | "anthropic" | "openai"
    # (e.g. image-gen-pro targets only openai-model conversations,
    # gemini-api-image-gen the google/anthropic → Imagen path).
    providers: Tuple[str, ...] = ()
    # Which references feed full_guidance_for_tool; () = all of them. Lets a
    # skill keep pure API-code references out of the enricher context.
    tool_references: Tuple[str, ...] = ()


def _sanitize(text: str) -> str:
    # Same idiom as style_service.format_style_block: braces would be
    # interpreted as ADK state placeholders inside agent instructions.
    return text.replace("{", "(").replace("}", ")")


def _parse_skill(skill_dir: Path) -> Skill:
    raw = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_RE.match(raw)
    if not fm_match:
        raise ValueError("SKILL.md has no YAML frontmatter (--- ... ---)")
    meta = yaml.safe_load(fm_match.group(1)) or {}
    for required in ("name", "description"):
        if not meta.get(required):
            raise ValueError(f"frontmatter missing required field '{required}'")

    body = _sanitize(raw[fm_match.end():].strip())
    core_match = _CORE_SECTION_RE.search(body)
    core = core_match.group(1).strip() if core_match else ""

    references: Dict[str, str] = {}
    ref_dir = skill_dir / "references"
    if ref_dir.is_dir():
        for ref in sorted(ref_dir.glob("*.md")):
            references[ref.name] = _sanitize(ref.read_text(encoding="utf-8").strip())

    return Skill(
        skill_id=skill_dir.name,
        name=str(meta["name"]),
        description=str(meta["description"]).strip(),
        version=int(meta.get("version", 1)),
        agents=tuple(meta.get("agents") or ()),
        tools=tuple(meta.get("tools") or ()),
        core=core,
        body=body,
        references=references,
        providers=tuple(meta.get("providers") or ()),
        tool_references=tuple(meta.get("tool_references") or ()),
    )


def _load_all() -> Dict[str, Skill]:
    skills: Dict[str, Skill] = {}
    if not SKILLS_DIR.is_dir():
        print("[skill_registry] no skills directory — registry empty", flush=True)
        return skills
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
            continue
        try:
            skill = _parse_skill(skill_dir)
            skills[skill.skill_id] = skill
            if len(skill.core) > CORE_WARN_CHARS:
                print(
                    f"[skill_registry] WARN {skill.skill_id}: Core is "
                    f"{len(skill.core)} chars (> {CORE_WARN_CHARS}) — it is baked "
                    "into agent instructions on every turn; keep it short",
                    flush=True,
                )
        except Exception as e:
            print(f"[skill_registry] SKIPPED {skill_dir.name}: {e}", flush=True)
    if skills:
        summary = ", ".join(
            f"{s.skill_id} (core={len(s.core)}ch, body={len(s.body)}ch, "
            f"refs={len(s.references)}, agents={'/'.join(s.agents) or '-'}, "
            f"tools={'/'.join(s.tools) or '-'})"
            for s in skills.values()
        )
        print(f"[skill_registry] loaded {len(skills)} skill(s): {summary}", flush=True)
    return skills


SKILLS: Dict[str, Skill] = _load_all()


def get_skill(skill_id: str) -> Optional[Skill]:
    return SKILLS.get(skill_id)


def skills_for_agent(agent_name: str) -> List[Skill]:
    return [s for s in SKILLS.values() if agent_name in s.agents]


def skills_for_tool(tool_name: str) -> List[Skill]:
    return [s for s in SKILLS.values() if tool_name in s.tools]


def core_block_for_agent(agent_name: str) -> str:
    """Instruction-ready block of every Core targeting the agent; "" if none.

    Safe to concatenate directly into an agent INSTRUCTION (already
    brace-sanitized at load; empty string renders nothing).
    """
    blocks = [
        f"\n# SKILL ACTIVA: {s.name}\n{s.core}\n"
        for s in skills_for_agent(agent_name)
        if s.core
    ]
    return "".join(blocks)


def full_guidance_for_tool(tool_name: str, provider: Optional[str] = None) -> str:
    """Concatenated full bodies + tool references of skills targeting the tool.

    provider filters provider-scoped skills (a skill with no `providers:`
    matches every provider). Returns "" when nothing matches.
    """
    parts: List[str] = []
    for s in skills_for_tool(tool_name):
        if s.providers and provider is not None and provider not in s.providers:
            continue
        parts.append(s.body)
        for ref_name, ref_text in s.references.items():
            if s.tool_references and ref_name not in s.tool_references:
                continue
            parts.append(ref_text)
    return "\n\n".join(parts)


def _validate() -> int:  # pragma: no cover — CLI helper
    errors = 0
    if not SKILLS_DIR.is_dir():
        print(f"skills dir not found: {SKILLS_DIR}")
        return 1
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        name = skill_dir.name
        if not (skill_dir / "SKILL.md").is_file():
            print(f"ERROR {name}: no SKILL.md")
            errors += 1
            continue
        skill = SKILLS.get(name)
        if skill is None:
            print(f"ERROR {name}: failed to load (see SKIPPED log above)")
            errors += 1
            continue
        if not _ID_RE.match(name):
            print(f"ERROR {name}: directory name must be kebab-case ascii")
            errors += 1
        if skill.name != name:
            print(f"ERROR {name}: frontmatter name '{skill.name}' != directory name")
            errors += 1
        raw = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        raw_refs = "".join(
            p.read_text(encoding="utf-8") for p in (skill_dir / "references").glob("*.md")
        ) if (skill_dir / "references").is_dir() else ""
        fm = _FRONTMATTER_RE.match(raw)
        content = raw[fm.end():] if fm else raw
        if "{" in content or "}" in content or "{" in raw_refs or "}" in raw_refs:
            print(f"WARN  {name}: contains braces — sanitized to () at load; "
                  "prefer removing them from the source")
        if len(skill.core) > CORE_WARN_CHARS:
            print(f"WARN  {name}: Core {len(skill.core)}ch > {CORE_WARN_CHARS}ch cap")
        if not skill.core and not skill.tools:
            print(f"WARN  {name}: no Core section and no tools target — skill is inert")
        for a in skill.agents:
            if a not in KNOWN_AGENTS:
                print(f"ERROR {name}: unknown agent '{a}' (known: {sorted(KNOWN_AGENTS)})")
                errors += 1
        for p in skill.providers:
            # model_registry.ModelSpec.provider vocabulary
            if p not in ("google", "anthropic", "openai"):
                print(f"ERROR {name}: unknown provider '{p}' (known: google/anthropic/openai)")
                errors += 1
        for r in skill.tool_references:
            if r not in skill.references:
                print(f"ERROR {name}: tool_references entry '{r}' has no matching references/*.md")
                errors += 1
        print(f"OK    {name}: core={len(skill.core)}ch body={len(skill.body)}ch "
              f"refs={list(skill.references)} agents={list(skill.agents)} "
              f"tools={list(skill.tools)}")
    print(f"\n{len(SKILLS)} skill(s) loaded, {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(_validate())
