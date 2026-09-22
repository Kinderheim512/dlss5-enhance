"""Load an API-format workflow, resolve the DLSS5 node and inject the job."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .config import TargetSelector
from .errors import WorkflowError
from .i18n import tr

REQUIRED_INPUTS = (
    "video_path",
    "filename_prefix",
    "output_directory",
    "codec",
    "container",
    "quality",
    "max_frames",
    "copy_audio",
    "verify_neural_rendering",
)

EXAMPLE_WORKFLOW_NAME = "exemple_dlss5_video.json"


def missing_workflow_message(path: str | Path) -> str:
    """Explain how to get a workflow, and point at the shipped example if present."""
    workflow_path = Path(path)
    lines = [
        tr("w.missing", path=workflow_path),
        tr("w.missing_hint"),
    ]
    example = workflow_path.parent / EXAMPLE_WORKFLOW_NAME
    if example.is_file():
        lines.append(tr("w.missing_example", example=example))
    return "\n".join(lines)


def load_workflow(path: str | Path) -> dict[str, Any]:
    """Read an API-format workflow JSON exported from ComfyUI."""
    workflow_path = Path(path)
    if not workflow_path.is_file():
        raise WorkflowError(missing_workflow_message(workflow_path))
    try:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(tr("w.bad_json", path=workflow_path, error=exc)) from exc
    if not isinstance(workflow, dict) or not workflow:
        raise WorkflowError(tr("w.not_api", path=workflow_path))
    for node_id, node in workflow.items():
        if not isinstance(node, Mapping) or "class_type" not in node:
            raise WorkflowError(
                tr("w.node_no_class", path=workflow_path, node=node_id)
            )
    return workflow


def node_title(node: Mapping[str, Any]) -> str:
    meta = node.get("_meta")
    if isinstance(meta, Mapping):
        title = meta.get("title")
        if title:
            return str(title)
    return str(node.get("class_type", ""))


def describe_nodes(workflow: Mapping[str, Any]) -> str:
    """One 'id (class_type, title)' entry per node, for error messages."""
    entries = [
        f"{node_id} ({node.get('class_type')}"
        + (f", title={node_title(node)!r})" if node_title(node) != node.get("class_type") else ")")
        for node_id, node in workflow.items()
    ]
    return "; ".join(entries)


def resolve_target(workflow: Mapping[str, Any], selector: TargetSelector) -> str:
    """Return the node id of the DLSS5 node: by id, else title, else class_type."""
    if selector.id:
        if selector.id not in workflow:
            raise WorkflowError(
                tr("w.no_id", id=selector.id, nodes=describe_nodes(workflow))
            )
        return selector.id

    if selector.title:
        matches = [
            node_id
            for node_id, node in workflow.items()
            if node_title(node) == selector.title
        ]
        wanted = tr("w.by_title", title=selector.title)
    elif selector.class_type:
        matches = [
            node_id
            for node_id, node in workflow.items()
            if node.get("class_type") == selector.class_type
        ]
        wanted = tr("w.by_class", class_type=selector.class_type)
    else:
        raise WorkflowError(tr("w.no_selector"))

    if not matches:
        raise WorkflowError(
            tr("w.no_match", wanted=wanted, nodes=describe_nodes(workflow))
        )
    if len(matches) > 1:
        raise WorkflowError(
            tr(
                "w.ambiguous",
                count=len(matches),
                wanted=wanted,
                ids=", ".join(matches),
            )
        )
    return matches[0]


def build_prompt(
    workflow: Mapping[str, Any],
    target_id: str,
    values: Mapping[str, Any],
    force: bool = False,
    is_changed_token: str | None = None,
    settings_class_type: str | None = None,
    settings_values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deep-copy the workflow and inject the per-job values into the target node.

    `settings_values` (a preset's DLSS5 Settings overrides) go into the node whose
    class_type is `settings_class_type`; every other node is left untouched.
    """
    prompt = copy.deepcopy(dict(workflow))
    _inject(prompt, target_id, values)

    if settings_values:
        if not settings_class_type:
            raise WorkflowError(tr("w.settings_needed"))
        settings_id = resolve_target(prompt, TargetSelector(class_type=settings_class_type))
        _inject(prompt, settings_id, settings_values)

    if force:
        prompt[target_id]["is_changed"] = is_changed_token or "dlss5-enhance-force"
    return prompt


def _inject(prompt: dict[str, Any], node_id: str, values: Mapping[str, Any]) -> None:
    node = prompt[node_id]
    inputs = node.get("inputs")
    if not isinstance(inputs, Mapping):
        raise WorkflowError(tr("w.no_inputs_object", node=node_id))

    unknown = [key for key in values if key not in inputs]
    if unknown:
        raise WorkflowError(
            tr(
                "w.unknown_input",
                node=node_id,
                class_type=node.get("class_type"),
                keys=", ".join(sorted(unknown)),
                available=", ".join(sorted(inputs)),
            )
        )
    for key, value in values.items():
        node["inputs"][key] = value


def read_settings_values(
    workflow: Mapping[str, Any],
    class_type: str,
    names: Iterable[str],
) -> dict[str, Any]:
    """Current values of the given inputs on the DLSS5 Settings node."""
    wanted = tuple(names)
    for node in workflow.values():
        if node.get("class_type") != class_type:
            continue
        inputs = node.get("inputs") or {}
        return {name: inputs[name] for name in wanted if name in inputs}
    return {}


def read_upscaling_mode(
    workflow: Mapping[str, Any],
    settings_class_type: str = "DLSS5Settings",
    input_name: str = "upscaling_mode",
) -> float:
    """Best-effort read of the DLSS settings' upscaling factor (1.0 when unknown)."""
    for node in workflow.values():
        if node.get("class_type") != settings_class_type:
            continue
        value = (node.get("inputs") or {}).get(input_name)
        if value is None:
            continue
        text = str(value).strip().lower()
        head = text.split("x", 1)[0].strip()
        try:
            factor = float(head)
        except ValueError:
            continue
        if factor > 0:
            return factor
    return 1.0


def iter_node_ids(workflow: Mapping[str, Any], class_type: str) -> Iterable[str]:
    for node_id, node in workflow.items():
        if node.get("class_type") == class_type:
            yield node_id
