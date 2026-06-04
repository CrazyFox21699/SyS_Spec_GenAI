"""Project context file loading — kind detection and per-kind structured extraction."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

FILE_KINDS = (
    "RTE_HEADER",
    "ADAPTER_HEADER",
    "MOCK_HEADER",
    "MOCK_IMPL",
    "TEST_FIXTURE",
    "DEFAULT_BEHAVIOR",
    "SAMPLE_TEST",
    "CONSTANTS_MACROS",
    "UNKNOWN",
)

_ACCEPTED_EXTS = {".h", ".hpp", ".c", ".cc", ".cpp", ".cxx", ".txt", ".md"}


def is_accepted_extension(filename: str) -> bool:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in _ACCEPTED_EXTS


def detect_file_kind(filename: str, content: str) -> str:
    """Heuristic kind detection from filename and content."""
    fn = filename.lower()
    base = fn.rsplit("/", 1)[-1]

    # SAMPLE_TEST: contains TEST_F
    if re.search(r"\bTEST_F\s*\(", content):
        return "SAMPLE_TEST"

    # RTE_HEADER: Rte_*.h / Rte.h
    if re.match(r"rte[_.].*\.h", base) or (base.startswith("rte") and base.endswith(".h")):
        if re.search(r"\bRte_(?:Read|Write|Call)_\w+", content):
            return "RTE_HEADER"

    # ADAPTER_HEADER: *adapter*.h or *_swc*.h or igsw*.h
    if re.search(r"(adapter|_swc_|igsw)", base) and base.endswith(".h"):
        return "ADAPTER_HEADER"

    # MOCK_HEADER: mock_*.h / *_mock.h
    if re.search(r"(mock_|_mock\.|gmock)", base) and base.endswith(".h"):
        return "MOCK_HEADER"

    # MOCK_IMPL: mock_*.cpp/cc
    if re.search(r"(mock_|_mock\.)", base) and re.search(r"\.(cpp|cc|c)$", base):
        return "MOCK_IMPL"

    # TEST_FIXTURE: rte_default_action.h or fixture*.h
    if re.search(r"(rte_default_action|fixture)", base) and base.endswith(".h"):
        return "TEST_FIXTURE"

    # DEFAULT_BEHAVIOR: rte_default_action.cpp
    if re.search(r"(rte_default_action|default_action)", base) and re.search(r"\.(cpp|cc|c)$", base):
        if re.search(r"EXPECT_CALL|WillRepeatedly|GTEST_", content):
            return "DEFAULT_BEHAVIOR"

    # CONSTANTS_MACROS: contains many #define / enum / constexpr
    define_count = len(re.findall(r"^\s*#define\b", content, re.MULTILINE))
    enum_count = len(re.findall(r"\benum\b", content))
    constexpr_count = len(re.findall(r"\bconstexpr\b", content))
    if define_count + enum_count + constexpr_count >= 3:
        return "CONSTANTS_MACROS"

    # Fallback: detect by content
    if re.search(r"\bRte_(?:Read|Write|Call)_\w+", content):
        return "RTE_HEADER"
    if re.search(r"\bigsw_Main_Run\b|\bigsw_Main_PowInit\b", content):
        return "ADAPTER_HEADER"
    if re.search(r"\bMOCK_METHOD\b|\bNiceMock\b|\bStrictMock\b", content):
        return "MOCK_HEADER"
    if re.search(r"WillRepeatedly|WillOnce|SetArgPointee", content):
        return "DEFAULT_BEHAVIOR"

    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Per-kind extractors
# ---------------------------------------------------------------------------

def extract_rte_header(content: str) -> dict[str, Any]:
    """Extract Rte_Read/Write/Call signatures from an RTE header."""
    apis: list[dict[str, str]] = []
    # Match function declarations like: FUNC(type, ...) Rte_Read_Signal(P2VAR(...))
    # Also simple: Std_ReturnType Rte_Read_XXX(P2VAR(...) data);
    for m in re.finditer(
        r"(?:Std_ReturnType|FUNC\([^)]+\))\s+(Rte_(Read|Write|Call)_(\w+))\s*\(([^;]*)\);",
        content, re.DOTALL
    ):
        api_full = m.group(1)
        direction = {"Read": "INPUT", "Write": "OUTPUT", "Call": "SERVICE"}.get(m.group(2), "UNKNOWN")
        signal = m.group(3)
        params = m.group(4).strip()
        # Extract pointer type from param
        type_m = re.search(r"P2(?:VAR|CONST)\s*\(([^,)]+)", params)
        c_type = type_m.group(1).strip() if type_m else ""
        apis.append({
            "signal": signal,
            "api": api_full,
            "direction": direction,
            "type": c_type,
            "return": "Std_ReturnType",
        })
    # Simpler fallback: just collect all Rte_Read/Write/Call names
    if not apis:
        for m in re.finditer(r"\bRte_(Read|Write|Call)_(\w+)\b", content):
            direction = {"Read": "INPUT", "Write": "OUTPUT", "Call": "SERVICE"}.get(m.group(1), "UNKNOWN")
            signal = m.group(2)
            if not any(a["signal"] == signal for a in apis):
                apis.append({"signal": signal, "api": f"Rte_{m.group(1)}_{signal}",
                              "direction": direction, "type": "", "return": "Std_ReturnType"})
    return {"apis": apis}


def extract_adapter_header(content: str) -> dict[str, Any]:
    """Extract public entry-point API signatures from an adapter/SWC header."""
    entry_points: list[dict[str, str]] = []
    # Look for function declarations
    for m in re.finditer(
        r"(?:void|Std_ReturnType|uint\w*|sint\w*|boolean)\s+(igsw_\w+)\s*\(([^;]*)\);",
        content
    ):
        fn = m.group(1)
        params = m.group(2).strip()
        purpose = ""
        if "Run" in fn:
            purpose = "Run cycle"
        elif "PowInit" in fn or "Init" in fn:
            purpose = "Init"
        elif "Write" in fn or "2e" in fn.lower():
            purpose = "Service/DID write"
        elif "Read" in fn or "22" in fn:
            purpose = "Service/DID read"
        entry_points.append({"fn": fn, "params": params, "purpose": purpose})
    return {"entry_points": entry_points}


def extract_mock_header(content: str) -> dict[str, Any]:
    """Extract mock class name and mock methods from a gmock header."""
    # Find mock class name
    class_m = re.search(r"\bclass\s+(\w+Mock\w*|\w+_mock_\w*|Mock\w+)\b", content, re.IGNORECASE)
    mock_class = class_m.group(1) if class_m else ""
    # Find MOCK_METHOD lines
    mock_methods: list[str] = []
    for m in re.finditer(r"\bMOCK_METHOD\d*\s*\(([^)]+)\)", content):
        mock_methods.append(m.group(1).strip().split(",")[0].strip())
    return {"mock_class": mock_class, "mock_methods": mock_methods[:12]}


def extract_mock_impl(content: str) -> dict[str, Any]:
    """Extract mock binding wrappers from a mock implementation file."""
    # Global mock instance: MockClass mock_xxx;
    global_instances: list[str] = []
    for m in re.finditer(r"^(\w+Mock\w*|\w+_mock_\w*|Mock\w+)\s+(\w+)\s*;", content, re.MULTILINE):
        global_instances.append(f"{m.group(1)} {m.group(2)}")

    # Wrapper pattern: Rte_Read_xxx → mock_.Rte_Read_xxx(...)
    bindings: list[dict[str, str]] = []
    for m in re.finditer(
        r"(?:Std_ReturnType|void)\s+(Rte_(?:Read|Write|Call)_\w+)\s*\([^)]*\)\s*\{[^}]*?(\w+)\.(\w+)\s*\(",
        content, re.DOTALL
    ):
        bindings.append({
            "real_api": m.group(1),
            "mock_instance": m.group(2),
            "mock_method": m.group(3),
        })
    return {"global_instances": global_instances, "bindings": bindings[:12]}


def extract_fixture(content: str) -> dict[str, Any]:
    """Extract fixture class, member variables, and observable outputs from fixture header."""
    # Fixture class
    class_m = re.search(r"\bclass\s+(\w+Test\w*|\w+Fixture\w*)\s*[:{]", content, re.IGNORECASE)
    fixture_class = class_m.group(1) if class_m else ""

    # Member variables: type name; (simple heuristic)
    members: list[str] = []
    for m in re.finditer(r"^\s+(?:uint\w*|sint\w*|boolean|int|float|double|Std_\w+)\s+(\w+)\s*;", content, re.MULTILINE):
        members.append(m.group(1))

    # Observable output variables (global or fixture members that look like outputs)
    # Usually uppercase: V_PMODE_STS, ACCD, IGD
    output_vars: list[str] = []
    for m in re.finditer(r"\b(V_[A-Z_]+|[A-Z]{2,}_[A-Z_]+)\b", content):
        v = m.group(1)
        if v not in output_vars and len(v) >= 4:
            output_vars.append(v)
    output_vars = output_vars[:8]

    # RTE/mock instance member
    rte_m = re.search(r"\b(rte|mock_|Rte)(?:_instance|Instance)?\s*;|(\w+)\s+rte\s*;", content, re.IGNORECASE)
    rte_member = rte_m.group(2) or rte_m.group(1) if rte_m else "rte"

    return {
        "fixture_class": fixture_class,
        "members": members[:8],
        "output_vars": output_vars,
        "rte_member": rte_member,
    }


def extract_default_behavior(content: str) -> dict[str, Any]:
    """Extract EXPECT_CALL default patterns from default behavior setup."""
    defaults: list[dict[str, str]] = []
    for m in re.finditer(
        r"EXPECT_CALL\s*\([^,]+,\s*(Rte_(?:Read|Write|Call)_\w+)\s*\([^)]*\)\s*\)"
        r"\s*\.WillRepeatedly\s*\(([^)]+)\)",
        content, re.DOTALL
    ):
        api = m.group(1)
        pattern = m.group(2).strip()[:120]
        # Try to extract the default value from DoAll(SetArgPointee<0>(VALUE), ...)
        val_m = re.search(r"SetArgPointee<\d+>\s*\(([^)]+)\)", pattern)
        default_val = val_m.group(1).strip() if val_m else ""
        defaults.append({"api": api, "pattern": pattern, "default_value": default_val})
    return {"defaults": defaults[:12]}


def extract_sample_test(content: str) -> dict[str, Any]:
    """Extract style patterns and a representative TEST_F block from a sample test file."""
    from web.project_testcode_memory import extract_patterns_from_sample
    patterns = extract_patterns_from_sample(content)

    # Extract one representative TEST_F block (prefer one with Japanese or EXPECT_CALL)
    representative = ""
    blocks: list[str] = []
    for m in re.finditer(r"(/\*\*.*?\*/\s*)?TEST_F\s*\([^)]+\)\s*\{", content, re.DOTALL):
        # Find matching closing brace
        start = m.start()
        brace_depth = 0
        pos = start
        for i, ch in enumerate(content[start:]):
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    blocks.append(content[start: start + i + 1])
                    break
        if len(blocks) >= 3:
            break

    # Score each block
    def _score(b: str) -> int:
        s = 0
        if re.search(r"[ぁ-ん]|[ァ-ン]|[一-龥]", b):
            s += 5
        if "EXPECT_CALL" in b:
            s += 2
        if "Rte_Read" in b:
            s += 2
        if "igsw_Main_Run" in b:
            s += 2
        if "EXPECT_THAT" in b:
            s += 1
        if "WillRepeatedly" in b:
            s += 1
        return s

    if blocks:
        representative = max(blocks, key=_score)[:3000]

    # Extract includes
    includes = re.findall(r'#include\s+"([^"]+)"', content)[:10]
    namespace = re.findall(r"\bnamespace\s+(\w+)\b", content)[:3]

    return {
        **patterns,
        "representative_test_f": representative,
        "includes": includes,
        "namespaces": namespace,
    }


def extract_constants_macros(content: str) -> dict[str, Any]:
    """Extract #define, enum, constexpr values."""
    defines: list[dict[str, str]] = []
    # #define NAME VALUE
    for m in re.finditer(r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+(.+)$", content, re.MULTILINE):
        name = m.group(1)
        value = m.group(2).strip()[:60]
        if re.search(r"[0-9u]|STD_ON|STD_OFF|TRUE|FALSE", value):
            defines.append({"name": name, "value": value, "kind": "define"})
    # enum values
    for enum_m in re.finditer(r"\benum\s+(?:\w+\s+)?\{([^}]+)\}", content, re.DOTALL):
        for item_m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*([^,}\n]+))?", enum_m.group(1)):
            defines.append({"name": item_m.group(1), "value": (item_m.group(2) or "").strip()[:60], "kind": "enum"})
    # constexpr
    for m in re.finditer(r"\bconstexpr\b.+?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^;]+);", content):
        defines.append({"name": m.group(1), "value": m.group(2).strip()[:60], "kind": "constexpr"})
    return {"values": defines[:30]}


def extract_from_kind(kind: str, content: str) -> dict[str, Any]:
    """Dispatch extraction by file kind."""
    if kind == "RTE_HEADER":
        return extract_rte_header(content)
    if kind == "ADAPTER_HEADER":
        return extract_adapter_header(content)
    if kind == "MOCK_HEADER":
        return extract_mock_header(content)
    if kind == "MOCK_IMPL":
        return extract_mock_impl(content)
    if kind == "TEST_FIXTURE":
        return extract_fixture(content)
    if kind == "DEFAULT_BEHAVIOR":
        return extract_default_behavior(content)
    if kind == "SAMPLE_TEST":
        return extract_sample_test(content)
    if kind == "CONSTANTS_MACROS":
        return extract_constants_macros(content)
    return {}


def process_file(filename: str, content: str) -> dict[str, Any]:
    """Detect kind, extract, return file descriptor."""
    kind = detect_file_kind(filename, content)
    extraction = extract_from_kind(kind, content)
    # Build a short summary
    summary_parts: list[str] = []
    if kind == "RTE_HEADER":
        n = len(extraction.get("apis") or [])
        summary_parts.append(f"{n} RTE API(s)")
    elif kind == "ADAPTER_HEADER":
        n = len(extraction.get("entry_points") or [])
        summary_parts.append(f"{n} entry point(s)")
    elif kind == "MOCK_HEADER":
        summary_parts.append(f"Mock class: {extraction.get('mock_class','?')}")
    elif kind == "MOCK_IMPL":
        summary_parts.append(f"{len(extraction.get('bindings',[]))} binding(s)")
    elif kind == "TEST_FIXTURE":
        summary_parts.append(f"Fixture: {extraction.get('fixture_class','?')}")
    elif kind == "DEFAULT_BEHAVIOR":
        summary_parts.append(f"{len(extraction.get('defaults',[]))} default EXPECT_CALL(s)")
    elif kind == "SAMPLE_TEST":
        fixtures = extraction.get("fixtures") or []
        summary_parts.append(f"Fixture: {fixtures[0] if fixtures else '?'}")
        if extraction.get("representative_test_f"):
            summary_parts.append("representative TEST_F extracted")
    elif kind == "CONSTANTS_MACROS":
        n = len(extraction.get("values") or [])
        summary_parts.append(f"{n} constant/macro(s)")

    return {
        "filename": filename,
        "kind": kind,
        "extraction": extraction,
        "summary": "; ".join(summary_parts) or kind,
        "content_len": len(content),
        "loaded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


# ---------------------------------------------------------------------------
# Build proposed memory sections from context file extractions
# ---------------------------------------------------------------------------

def build_memory_sections_from_files(file_descriptors: list[dict[str, Any]]) -> str:
    """Build a proposed memory markdown string from a list of processed file descriptors."""
    sections: dict[str, list[str]] = {
        "RTE API Map": [],
        "Entry Points / Call Order": [],
        "Mock Interface": [],
        "Mock Binding Pattern": [],
        "Fixture / Observable Variables": [],
        "Default Mock Behavior": [],
        "Representative Test Style": [],
        "Constants / Value Map": [],
        "Spec Signal to Test Code Map": [],
    }

    rte_apis: list[dict[str, str]] = []
    fixture_info: dict[str, Any] = {}
    mock_class: str = ""

    for fd in file_descriptors:
        kind = fd.get("kind", "")
        ex = fd.get("extraction") or {}
        fn = fd.get("filename", "")

        if kind == "RTE_HEADER":
            for api in ex.get("apis") or []:
                rte_apis.append(api)
                lines = [f"- Signal: `{api['signal']}`"]
                lines.append(f"  - API: `{api['api']}`")
                lines.append(f"  - Direction: {api['direction']}")
                if api.get("type"):
                    lines.append(f"  - Type: `{api['type']}`")
                lines.append(f"  - Return: `{api['return']}`")
                sections["RTE API Map"].extend(lines)

        elif kind == "ADAPTER_HEADER":
            for ep in ex.get("entry_points") or []:
                line = f"- `{ep['fn']}({ep['params'][:40]})`"
                if ep.get("purpose"):
                    line += f": {ep['purpose']}"
                sections["Entry Points / Call Order"].append(line)

        elif kind == "MOCK_HEADER":
            mock_class = ex.get("mock_class", "") or mock_class
            if mock_class:
                sections["Mock Interface"].append(f"- Mock class: `{mock_class}`")
            for method in ex.get("mock_methods") or []:
                sections["Mock Interface"].append(f"  - Mock method: `{method}`")

        elif kind == "MOCK_IMPL":
            for inst in ex.get("global_instances") or []:
                sections["Mock Binding Pattern"].append(f"- Global mock instance: `{inst}`")
            for b in ex.get("bindings") or []:
                sections["Mock Binding Pattern"].append(
                    f"- Real API: `{b['real_api']}` → `{b['mock_instance']}.{b['mock_method']}(...)`"
                )

        elif kind == "TEST_FIXTURE":
            fixture_info = ex
            fc = ex.get("fixture_class", "")
            if fc:
                sections["Fixture / Observable Variables"].append(f"- Fixture: `{fc}`")
            for v in ex.get("output_vars") or []:
                sections["Fixture / Observable Variables"].append(f"- Observable output: `{v}`")
            rte_mem = ex.get("rte_member", "")
            if rte_mem:
                sections["Fixture / Observable Variables"].append(f"- RTE/mock instance: `{rte_mem}`")

        elif kind == "DEFAULT_BEHAVIOR":
            for d in ex.get("defaults") or []:
                sections["Default Mock Behavior"].append(f"- API: `{d['api']}`")
                if d.get("default_value"):
                    sections["Default Mock Behavior"].append(f"  - Default value: `{d['default_value']}`")
                sections["Default Mock Behavior"].append(f"  - Pattern: `{d['pattern'][:80]}`")

        elif kind == "SAMPLE_TEST":
            rep = ex.get("representative_test_f", "")
            if rep:
                sections["Representative Test Style"].append(
                    f"From `{fn}`:\n```cpp\n{rep[:1500]}\n```"
                )
            fixtures = ex.get("fixtures") or []
            if fixtures:
                sections["Fixture / Observable Variables"].append(f"- Sample fixture: `{fixtures[0]}`")

        elif kind == "CONSTANTS_MACROS":
            for v in (ex.get("values") or [])[:15]:
                meaning = ""
                name = v["name"]
                val = v["value"]
                if "STD_ON" in name or val == "1":
                    meaning = "Enabled"
                elif "STD_OFF" in name or val == "0":
                    meaning = "Disabled"
                line = f"- `{name}` = `{val}`"
                if meaning:
                    line += f" ({meaning})"
                sections["Constants / Value Map"].append(line)

    # Build signal map from collected RTE APIs + fixture outputs
    if rte_apis:
        out_vars = fixture_info.get("output_vars") or []
        fc = fixture_info.get("fixture_class", "") or (
            sections["Fixture / Observable Variables"][0].replace("- Fixture: `", "").rstrip("`")
            if sections["Fixture / Observable Variables"] else ""
        )
        mc = mock_class
        for api in rte_apis[:8]:
            sections["Spec Signal to Test Code Map"].append(f"- Spec signal: `{api['signal']}`")
            sections["Spec Signal to Test Code Map"].append(f"  - RTE API: `{api['api']}`")
            sections["Spec Signal to Test Code Map"].append(f"  - Direction: {api['direction']}")
            if mc:
                sections["Spec Signal to Test Code Map"].append(
                    f"  - Mock pattern: `EXPECT_CALL({mc.lower()}, {api['api']}(NotNull()))`"
                )
        for v in out_vars[:4]:
            sections["Spec Signal to Test Code Map"].append(f"- Spec output: `{v}`")
            sections["Spec Signal to Test Code Map"].append(
                f"  - Observable variable: `{v}`"
            )
            sections["Spec Signal to Test Code Map"].append(
                f"  - Assertion pattern: `EXPECT_THAT({v}, Eq(expected_value))`"
            )

    # Compose output markdown
    lines: list[str] = ["# Project Test Code Memory (Proposed)\n"]
    for section, bullets in sections.items():
        lines.append(f"## {section}")
        if bullets:
            lines.extend(bullets)
        else:
            lines.append("")
        lines.append("")

    return "\n".join(lines)
