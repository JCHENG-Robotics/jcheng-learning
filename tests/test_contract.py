"""Contract checks for the jcheng-learning capability manifest.

The checks mirror `capability-manifest.v1.schema.json` in jcheng-interfaces
without adding a jsonschema runtime dependency. They also pin the document set
and the README structure required by the organization documentation standard.
"""

from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = yaml.safe_load((ROOT / "capability.yaml").read_text(encoding="utf-8"))

TOP_LEVEL = {
    "schema_version",
    "name",
    "version",
    "contract",
    "safety",
    "hardware_access",
    "runtime",
}
CONTRACT_HASH = (
    "sha256:0b8d72ced7f54d444d6851d8b99a51a78e2bed3f687324f51a15f76557f24b42"
)


def test_top_level_fields():
    assert set(MANIFEST) == TOP_LEVEL


def test_identity_and_version():
    assert MANIFEST["schema_version"] == 1
    assert MANIFEST["name"] == "jcheng-learning"
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", MANIFEST["version"])
    assert MANIFEST["version"] == (ROOT / "VERSION").read_text().strip()


def test_contract_hash_and_ranges():
    contract = MANIFEST["contract"]
    assert set(contract) == {"interfaces", "contract_hash", "system_api"}
    assert contract["interfaces"] == ">=0.1,<0.2"
    assert contract["system_api"] == ">=0.1,<0.2"
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", contract["contract_hash"])
    assert contract["contract_hash"] == CONTRACT_HASH


def test_safety_is_offline_and_scoped_out():
    safety = MANIFEST["safety"]
    assert set(safety) == {
        "class",
        "scopes",
        "requires_lease",
        "max_rate_hz",
        "deadman_ms",
    }
    assert safety["class"] == "offline"
    assert safety["scopes"] == []
    # Required by the v1 schema; vacuous while no intent is produced.
    assert safety["requires_lease"] is True
    assert safety["max_rate_hz"] == 1
    assert safety["deadman_ms"] == 500


def test_hardware_access_is_none():
    assert MANIFEST["hardware_access"] == "none"


def test_runtime_surface_is_empty():
    runtime = MANIFEST["runtime"]
    assert set(runtime) == {"ros_domains", "publishes", "subscribes"}
    assert runtime["ros_domains"] == []
    assert runtime["publishes"] == []
    assert runtime["subscribes"] == []


def test_document_set_exists():
    for name in (
        "README.md",
        "README.zh-CN.md",
        "ROADMAP.md",
        "CHANGELOG.md",
        "ACCEPTANCE.md",
        "LICENSE-REVIEW.md",
        "docs/ARCHITECTURE.md",
        "docs/DATA.md",
        "docs/INTEGRATION.md",
        "scripts/check_repo_gate.sh",
        "evidence/20261126_scaffold/README.md",
    ):
        assert (ROOT / name).is_file(), f"missing {name}"


def test_readme_required_sections():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for heading in (
        "## Scope and boundary",
        "## Repository layout",
        "## Requirements",
        "## Quick start",
        "## Validation status",
        "## Related repositories",
        "## License",
    ):
        assert heading in text, f"missing section {heading}"


def test_status_vocabulary():
    allowed = {
        "Complete",
        "In progress",
        "Planned",
        "Not started",
        "Verified",
        "Partially verified",
        "Unverified",
        "Inconclusive",
        "Experimental",
        "Deployed",
        "Frozen",
        "Archived",
    }
    assert "Partially verified" in allowed
    # The status block must use the organization's repository-state vocabulary.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Status: **Experimental**" in readme
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    assert "Planned" in roadmap
    assert "Not started" in roadmap
