"""Translations. English is the source of truth; French is a full translation."""

from __future__ import annotations

import os
from typing import Any

LANGUAGES = ("en", "fr")
DEFAULT_LANGUAGE = "en"
LANGUAGE_LABELS: dict[str, str] = {"en": "English", "fr": "Français"}
ENV_VAR = "DLSS5_LANG"

MESSAGES: dict[str, tuple[str, str]] = {
    # mappings
    "m.quality_invalid": (
        "Invalid quality {value!r}. Accepted: draft|low (Auto), normal|medium (Good), high (Best), max (Max).",
        "Qualité invalide {value!r}. Valeurs acceptées : draft|low (Auto), normal|medium (Good), high (Best), max (Max).",
    ),
    "m.codec_invalid": (
        "Invalid codec {value!r}. Accepted: h264 (H.264), h265|hevc (HEVC), av1 (AV1), prores (ProRes Proxy).",
        "Codec invalide {value!r}. Valeurs acceptées : h264 (H.264), h265|hevc (HEVC), av1 (AV1), prores (ProRes Proxy).",
    ),
    "m.container_invalid": (
        "Invalid container {value!r}. Accepted: mp4, mkv, mov.",
        "Conteneur invalide {value!r}. Valeurs acceptées : mp4, mkv, mov.",
    ),
    "m.codec_unknown": (
        "Unknown codec {codec!r}. Accepted: {options}.",
        "Codec inconnu {codec!r}. Valeurs acceptées : {options}.",
    ),
    "m.container_unknown": (
        "Unknown container {container!r}. Accepted: {options}.",
        "Conteneur inconnu {container!r}. Valeurs acceptées : {options}.",
    ),
    "m.prores_needs": (
        "ProRes Proxy needs the MOV or MKV container.",
        "ProRes Proxy exige le conteneur MOV ou MKV.",
    ),
    # presets
    "p.upscaling_required": (
        "upscaling_mode is required in a preset.",
        "upscaling_mode est requis dans un preset.",
    ),
    "p.upscaling_unknown": (
        "Unknown upscaling mode {value!r}. Accepted: {modes} (or a factor: 1, 1.5, 1.724, 2, 3).",
        "Mode d'upscaling inconnu {value!r}. Valeurs acceptées : {modes} (ou un facteur : 1, 1.5, 1.724, 2, 3).",
    ),
    "p.section_mapping": (
        "The 'presets' section must be a mapping.",
        "La section 'presets' doit être un dictionnaire.",
    ),
    "p.empty_name": (
        "A preset has an empty name.",
        "Un preset porte un nom vide.",
    ),
    "p.body_mapping": (
        "Preset {key!r} must be a mapping.",
        "Le preset {key!r} doit être un dictionnaire.",
    ),
    "p.unknown_keys": (
        "Preset {key!r} has unknown keys: {unknown}. Accepted keys: {known}.",
        "Le preset {key!r} contient des clés inconnues : {unknown}. Clés acceptées : {known}.",
    ),
    "p.settings_mapping": (
        "Preset {key!r}: 'settings' must be a mapping.",
        "Le preset {key!r} : 'settings' doit être un dictionnaire.",
    ),
    "p.none_configured": ("(none configured)", "(aucun preset configuré)"),
    "p.unknown_name": (
        "Unknown preset {name!r}. Available presets: {known}.",
        "Preset inconnu {name!r}. Presets disponibles : {known}.",
    ),
    # sources
    "s.one_source": (
        "Give exactly one source: a video file, or a folder.",
        "Indiquer exactement une source : un fichier vidéo, ou un dossier.",
    ),
    "s.file_missing": (
        "File not found: {path}",
        "Fichier introuvable : {path}",
    ),
    "s.extension_warning": (
        "Warning: {name} is not one of the watched extensions ({extensions}).",
        "Attention : {name} n'est pas dans les extensions surveillées ({extensions}).",
    ),
    "s.folder_missing": (
        "Folder not found: {path}",
        "Dossier introuvable : {path}",
    ),
    "s.no_files": (
        "No {extensions} file in {folder}{recursive}.",
        "Aucun fichier {extensions} dans {folder}{recursive}.",
    ),
    "s.recursive_suffix": (" (recursive)", " (récursif)"),
    # workflow
    "w.missing": ("Workflow JSON not found: {path}", "Workflow JSON introuvable : {path}"),
    "w.missing_hint": (
        "In ComfyUI: 'Workflow' -> 'Export (API)', then save the file at that path — or pick "
        "another one (--workflow, or the 'Browse…' button next to the Workflow field).",
        "Dans ComfyUI : « Workflow » → « Export (API) », puis enregistrer le fichier à ce "
        "chemin — ou en choisir un autre (--workflow, ou le bouton « Parcourir » à côté du "
        "champ Workflow).",
    ),
    "w.missing_example": (
        "To try it right away, an example ships with the tool: {example}",
        "Pour essayer tout de suite, un exemple est fourni : {example}",
    ),
    "w.bad_json": ("{path} is not valid JSON: {error}", "{path} n'est pas un JSON valide : {error}"),
    "w.not_api": (
        "{path} is not an API-format workflow (expected an object of node id -> node).",
        "{path} n'est pas un workflow au format API (objet attendu : id de node -> node).",
    ),
    "w.node_no_class": (
        "{path}: node {node!r} has no 'class_type'. Export the workflow with 'Export (API)', "
        "not the plain workflow format.",
        "{path} : le node {node!r} n'a pas de 'class_type'. Exporter le workflow avec "
        "« Export (API) », pas le format workflow simple.",
    ),
    "w.no_id": (
        "No node with id {id!r} in the workflow. Nodes: {nodes}",
        "Aucun node d'id {id!r} dans le workflow. Nodes : {nodes}",
    ),
    "w.no_match": (
        "No node matching {wanted} in the workflow. Nodes: {nodes}",
        "Aucun node ne correspond à {wanted} dans le workflow. Nodes : {nodes}",
    ),
    "w.ambiguous": (
        "{count} nodes match {wanted} ({ids}); set workflow.target.id or "
        "workflow.target.title to disambiguate.",
        "{count} nodes correspondent à {wanted} ({ids}) ; préciser workflow.target.id ou "
        "workflow.target.title pour lever l'ambiguïté.",
    ),
    "w.no_selector": (
        "No target node selector configured (id, title or class_type).",
        "Aucun sélecteur de node cible configuré (id, title ou class_type).",
    ),
    "w.by_title": ("the title {title!r}", "le titre {title!r}"),
    "w.by_class": ("the class_type {class_type!r}", "le class_type {class_type!r}"),
    "w.no_inputs_object": (
        "Target node {node} has no 'inputs' object.",
        "Le node cible {node} n'a pas d'objet 'inputs'.",
    ),
    "w.unknown_input": (
        "Target node {node} ({class_type}) has no input {keys}. Its inputs are: {available}.",
        "Le node cible {node} ({class_type}) n'a pas l'entrée {keys}. Ses entrées sont : "
        "{available}.",
    ),
    "w.settings_needed": (
        "Preset settings were given but no DLSS5Settings class_type is configured "
        "(workflow.settings.class_type).",
        "Des réglages de preset sont fournis mais aucun class_type de node DLSS5Settings "
        "n'est configuré (workflow.settings.class_type).",
    ),
    # comfy client
    "c.unreachable": ("{url} unreachable: {error}", "{url} injoignable : {error}"),
    "c.stats_http": (
        "/system_stats returned HTTP {status}.",
        "/system_stats a renvoyé HTTP {status}.",
    ),
    "c.stats_not_json": (
        "/system_stats did not return JSON.",
        "/system_stats n'a pas renvoyé de JSON.",
    ),
    "c.submit_failed": (
        "Could not submit to {url}: {error}",
        "Soumission impossible vers {url} : {error}",
    ),
    "c.prompt_http": ("/prompt returned HTTP {status}.", "/prompt a renvoyé HTTP {status}."),
    "c.prompt_no_id": (
        "/prompt accepted the workflow but returned no prompt_id.",
        "/prompt a accepté le workflow mais n'a renvoyé aucun prompt_id.",
    ),
    "c.rejected": (
        "ComfyUI rejected the workflow — {details}",
        "ComfyUI a rejeté le workflow — {details}",
    ),
    "c.rejected_plain": (
        "ComfyUI rejected the workflow (node_errors).",
        "ComfyUI a rejeté le workflow (node_errors).",
    ),
    "c.node_error": ("node {node}: {message}", "node {node} : {message}"),
    "c.invalid_input": ("invalid input", "entrée invalide"),
    "c.execution_error": ("execution error", "erreur d'exécution"),
    # comfy server
    "v.root_missing": ("comfy.root not found: {path}", "comfy.root introuvable : {path}"),
    "v.python_missing": ("comfy.python not found: {path}", "comfy.python introuvable : {path}"),
    "v.module_missing": (
        "comfy.server_module not found: {path}",
        "comfy.server_module introuvable : {path}",
    ),
    "v.tunnel_detected": (
        "Port {port} is forwarded by an SSH tunnel ({name}, PID {pid}) to a remote ComfyUI, "
        "not a local one. The DLSS5 node has to run locally (D3D12 worker). Stop the tunnel "
        "or change comfy.port.",
        "Le port {port} est forwardé par un tunnel SSH ({name}, PID {pid}) vers un ComfyUI "
        "distant, pas un ComfyUI local. Le node DLSS5 doit tourner en local (worker D3D12). "
        "Arrêter le tunnel ou changer comfy.port.",
    ),
    "v.reuse": (
        "ComfyUI already listening on {url} — {owner}. Reusing it.",
        "Serveur ComfyUI déjà en écoute sur {url} — {owner}. Réutilisation.",
    ),
    "v.desktop_shared": (
        "The ComfyUI Desktop app ({name}) is running: the queue is shared, and closing the "
        "app will stop the server mid-job.",
        "L'app ComfyUI Desktop ({name}) tourne : la file d'attente est partagée et fermer "
        "l'app arrêtera le serveur en cours de traitement.",
    ),
    "v.port_busy": (
        "Port {port} is held by {name} (PID {pid}), which does not answer like a ComfyUI "
        "server. Free the port or change comfy.port.",
        "Le port {port} est occupé par {name} (PID {pid}), qui ne répond pas comme un serveur "
        "ComfyUI. Libérez le port ou changez comfy.port.",
    ),
    "v.other_process": ("another process", "un autre process"),
    "v.no_autostart": (
        "No ComfyUI server on {url} and --no-autostart is set.",
        "Aucun serveur ComfyUI sur {url} et --no-autostart est actif.",
    ),
    "v.start_failed": (
        "Could not start ComfyUI: {error}",
        "Impossible de démarrer ComfyUI : {error}",
    ),
    "v.start_timeout": (
        "The ComfyUI server did not answer on {url} after {seconds:.0f} s.",
        "Le serveur ComfyUI n'a pas répondu sur {url} après {seconds:.0f} s.",
    ),
    "v.start_died": (
        "The ComfyUI server stopped during startup ({url}).",
        "Le serveur ComfyUI s'est arrêté pendant le démarrage ({url}).",
    ),
    "v.ready": (
        "ComfyUI ready on {url} (PID {pid}).",
        "Serveur ComfyUI prêt sur {url} (PID {pid}).",
    ),
    "v.starting": ("Starting ComfyUI: {command}", "Démarrage de ComfyUI : {command}"),
    "v.stopped": ("ComfyUI server stopped.", "Serveur ComfyUI arrêté."),
    "v.extra_paths_missing": (
        "extra_model_paths_config not found ({path}): argument dropped (DLSS5 needs no model).",
        "extra_model_paths_config introuvable ({path}) : argument retiré (DLSS5 n'a besoin "
        "d'aucun modèle).",
    ),
    "v.stray_workers": (
        "Leftover DLSS5 worker(s): {workers} — they may still hold the GPU.",
        "Worker(s) DLSS5 résiduel(s) : {workers} — ils peuvent retenir la GPU.",
    ),
    # config
    "g.bool_expected": ("{key} must be a boolean, got {value!r}.", "{key} doit être un booléen, reçu {value!r}."),
    "g.number_expected": ("{key} must be a number, got {value!r}.", "{key} doit être un nombre, reçu {value!r}."),
    "g.int_expected": ("{key} must be an integer, got {value!r}.", "{key} doit être un entier, reçu {value!r}."),
    "g.yaml_invalid": ("{path} is not valid YAML: {error}", "{path} n'est pas un YAML valide : {error}"),
    "g.mapping_expected": (
        "{path} must contain a mapping at the top level.",
        "{path} doit contenir un mapping au premier niveau.",
    ),
    "g.timeout_positive": (
        "processing.timeout must be greater than zero.",
        "processing.timeout doit être supérieur à zéro.",
    ),
    # progress
    "r.timeout": (
        "Timeout of {seconds:.0f} s reached (prompt {prompt}): interruption requested.",
        "Timeout de {seconds:.0f} s atteint (prompt {prompt}) : interruption demandée.",
    ),
    "r.cancelled": (
        "Cancellation requested (prompt {prompt}): interrupting.",
        "Annulation demandée (prompt {prompt}) : interruption.",
    ),
    "r.timeout_error": (
        "timeout after {seconds:.0f} s",
        "timeout après {seconds:.0f} s",
    ),
    "r.server_gone": (
        "The ComfyUI process disappeared during the job",
        "Le process ComfyUI a disparu pendant le job",
    ),
    "r.ws_connected": ("WebSocket connected.", "WebSocket connecté."),
    "r.ws_error": ("WebSocket: {error}", "WebSocket : {error}"),
    "r.ws_missing": (
        "websocket-client missing: progress falls back to polling /history.",
        "websocket-client absent : suivi par polling /history uniquement.",
    ),
    "r.cache_node": (
        "ComfyUI reports node {node} as served from its cache.",
        "ComfyUI signale le node {node} comme servi par le cache.",
    ),
    # report
    "t.status.new": ("new render", "nouveau rendu"),
    "t.status.cache": ("served from cache", "servi par le cache"),
    "t.status.failed": ("failed", "échec"),
    "t.status.timeout": ("timeout", "timeout"),
    "t.status.crashed": ("server crash", "crash du serveur"),
    "t.status.cancelled": ("cancelled", "annulé"),
    "t.duration_s": ("{seconds} s", "{seconds} s"),
    "t.duration_min": ("{minutes} min {seconds:02d} s", "{minutes} min {seconds:02d} s"),
    "t.duration_h": ("{hours} h {minutes:02d}", "{hours} h {minutes:02d}"),
    "t.new_render": ("OK — new render: {path}", "OK — nouveau rendu : {path}"),
    "t.cache_hit": (
        "CACHE-HIT — no new render; existing file {path} (re-run with --force to force one)",
        "CACHE-HIT — aucun nouveau rendu ; fichier existant {path} (relancer avec --force pour forcer)",
    ),
    "t.cache_hit_nofile": ("CACHE-HIT — no new render", "CACHE-HIT — aucun nouveau rendu"),
    "t.ws_confirmed": (" [confirmed by the WebSocket]", " [confirmé par le WebSocket]"),
    "t.line": ("{name}: {body} ({duration})", "{name} : {body} ({duration})"),
    "t.summary_header": ("Summary:", "Résumé :"),
    "t.summary_counts": (
        "  {total} file(s) processed: {new} new render(s), {cache} served from cache, "
        "{failed} failure(s).",
        "  {total} fichier(s) traité(s) : {new} nouveau(x) rendu(s), {cache} servi(s) par le "
        "cache, {failed} échec(s).",
    ),
    "t.summary_failures": ("  Failures:", "  Échecs :"),
    "t.summary_failure_line": ("    - {name}: {reason}", "    - {name} : {reason}"),
    # runner
    "j.interrupted": (
        "Interrupted: cancelling the running job…",
        "Interruption : annulation du job en cours…",
    ),
    "j.ffprobe_unavailable": (
        "ffprobe unavailable on {name} ({error}).",
        "ffprobe indisponible sur {name} ({error}).",
    ),
    "j.geometry_overflow": (
        "Warning: {factor:g}x on {width}x{height} asks for {target_w}x{target_h}, beyond the "
        "node's limits (long edge 7680, short edge 4320). The node will refuse that mode or "
        "pick a weaker one.",
        "Attention : {factor:g}x sur {width}x{height} demande {target_w}x{target_h}, au-delà "
        "des limites du node (bord long 7680, bord court 4320). Le node refusera ce mode ou en "
        "choisira un plus faible.",
    ),
    "j.plan_header": (
        "Check (nothing submitted):",
        "Vérification (aucune soumission) :",
    ),
    "j.plan_server": (
        "  ComfyUI server    : {url} (answers /system_stats)",
        "  serveur ComfyUI   : {url} (répond à /system_stats)",
    ),
    "j.plan_target": (
        "  target node       : {class_type} (id {node})",
        "  node cible        : {class_type} (id {node})",
    ),
    "j.plan_workflow": ("  workflow          : {path}", "  workflow          : {path}"),
    "j.plan_preset": ("  preset            : {label}", "  preset            : {label}"),
    "j.plan_no_preset": (
        "(none — the workflow's upscaling mode)",
        "(aucun — mode d'upscaling du workflow)",
    ),
    "j.plan_settings": ("  preset settings   : {settings}", "  réglages preset   : {settings}"),
    "j.plan_codec": (
        "  codec / container : {codec} / {container}  (quality {quality})",
        "  codec / container : {codec} / {container}  (quality {quality})",
    ),
    "j.plan_upscaling": (
        "  upscaling         : {factor:g}x  ->  output {width}x{height}",
        "  upscaling         : {factor:g}x  ->  sortie {width}x{height}",
    ),
    "j.plan_output": ("  output folder     : {path}", "  dossier de sortie : {path}"),
    "j.plan_encoders": ("  encoders          : {table}", "  encodeurs         : {table}"),
    "j.plan_files": ("  files ({count}):", "  fichiers ({count}) :"),
    "j.plan_file_line": ("    - {name}{detail}", "    - {name}{detail}"),
    "j.encoder_probe_ok": (
        "Encoder probe: {encoder} available at {width}x{height}.",
        "Sonde encodeur : {encoder} disponible à {width}x{height}.",
    ),
    "j.encoder_fallback": (
        "{encoder} unavailable ({reason}): the node will fall back to its software encoder, "
        "which is slower.",
        "{encoder} indisponible ({reason}) : le node basculera sur l'encodeur logiciel, plus lent.",
    ),
    "j.av1_unavailable": (
        "av1_nvenc unavailable on this machine ({reason}). The DLSS5 node has no software "
        "fallback for AV1 — use --codec h265 or h264.",
        "av1_nvenc indisponible sur cette machine ({reason}). Le node DLSS5 n'a pas de repli "
        "logiciel pour AV1 — utiliser --codec h265 ou h264.",
    ),
    "j.ffmpeg_missing": (
        "comfy.ffmpeg not found: encoder probe skipped.",
        "comfy.ffmpeg introuvable : sonde d'encodeur ignorée.",
    ),
    "j.encoder_software": ("software encoding", "encodage logiciel"),
    "j.encoder_probe_impossible": (
        "node ffmpeg not found — probe impossible",
        "ffmpeg du node introuvable — sonde impossible",
    ),
    "j.server_gone_stop": (
        "ComfyUI stopped: processing interrupted after {index}/{total} file(s).",
        "Serveur ComfyUI arrêté : traitement interrompu après {index}/{total} fichier(s).",
    ),
    "j.max_restarts": (
        "Limit of {max} restarts reached: stopping the batch.",
        "Plafond de {max} redémarrages atteint : arrêt du batch.",
    ),
    "j.restart_refused": ("Restart refused: stopping the batch.", "Relance refusée : arrêt du batch."),
    "j.abandoned": ("not processed: {reason}", "non traité : {reason}"),
    "j.abandoned_cancelled": ("cancelled", "annulé"),
    "j.abandoned_server": ("ComfyUI stopped", "serveur ComfyUI arrêté"),
    "j.abandoned_restarts": ("too many restarts", "trop de redémarrages"),
    "j.abandoned_refused": ("restart refused", "relance refusée"),
    "j.cancel_batch": (
        "Cancellation requested: stopping the batch after {index}/{total}.",
        "Annulation demandée : arrêt du batch après {index}/{total}.",
    ),
    "j.restart_decision": (
        "Restart decision: {flag} ({remaining} file(s) left).",
        "Décision de relance : {flag} ({remaining} fichier(s) restant(s)).",
    ),
    "j.restart_noninteractive": (
        "Non-interactive input: restarting automatically to continue.",
        "Entrée non interactive : redémarrage automatique pour continuer.",
    ),
    "j.restart_ask": (
        "Restart ComfyUI and continue with the {remaining} remaining file(s)? [Y/n] ",
        "Relancer le serveur ComfyUI et continuer avec les {remaining} fichier(s) restant(s) ? [Y/n] ",
    ),
    "j.restarting": ("Restarting the ComfyUI server…", "Redémarrage du serveur ComfyUI…"),
    "j.job_header": (
        "[{index}/{total}] {name} — codec {codec}, container {container}, quality {quality}",
        "[{index}/{total}] {name} — codec {codec}, container {container}, quality {quality}",
    ),
    "j.prompt_submitted": ("{name}: prompt {prompt} submitted.", "{name} : prompt {prompt} soumis."),
    "j.submit_refused": ("{name}: submission refused — {error}", "{name} : soumission refusée — {error}"),
    "j.submit_refused_reason": (
        "submission refused: {error}",
        "soumission refusée : {error}",
    ),
    "j.job_cancelled": ("{name}: job cancelled.", "{name} : job annulé."),
    "j.server_disappeared": (
        "{name}: the ComfyUI process disappeared during the job.",
        "{name} : le process ComfyUI a disparu pendant le job.",
    ),
    "j.server_line": ("  server | {line}", "  serveur | {line}"),
    "j.render_failed": ("{name}: render failed — {error}", "{name} : échec du rendu — {error}"),
    "j.no_output": ("no output file in {path}", "aucun fichier de sortie dans {path}"),
    "j.no_output_cached": (
        "no output file in {path} — ComfyUI served this job from its cache, but the matching "
        "file no longer exists (re-run with --force to force a new render)",
        "aucun fichier de sortie dans {path} — ComfyUI a servi ce job depuis son cache, mais "
        "le fichier correspondant n'existe plus (relancer avec --force pour forcer un nouveau rendu)",
    ),
    "j.ws_state": ("websocket connected: {state}", "websocket connecté : {state}"),
    "j.preset_line": (
        "Preset: {label} ({name}) — upscaling {mode}",
        "Preset : {label} ({name}) — upscaling {mode}",
    ),
    "j.journal": ("Log file: {path}", "Journal : {path}"),
    "j.configuration": ("Configuration: {path}", "Configuration : {path}"),
    "j.workflow_mode": ("workflow", "workflow"),
    # cli
    "n.error": ("Error: {message}", "Erreur : {message}"),
    "n.interrupted": ("Interrupted by the user.", "Interrompu par l'utilisateur."),
    "j.no_output_dir": (
        "No output folder: pass --output or set processing.output in config.yaml.",
        "Aucun dossier de sortie : passer --output ou définir processing.output dans config.yaml.",
    ),
    "j.target_inputs_missing": (
        "Target node {node} ({class_type}) is missing the inputs {keys}. Inputs present: "
        "{available}.",
        "Le node cible {node} ({class_type}) n'a pas les entrées {keys}. Entrées présentes : "
        "{available}.",
    ),
    "j.preset_unknown_input": (
        "Preset {name!r} sets {keys}, which do not exist on node {class_type} (id {node}). "
        "Inputs available: {available}.",
        "Le preset {name!r} règle {keys}, qui n'existe pas sur le node {class_type} "
        "(id {node}). Entrées disponibles : {available}.",
    ),
    "j.node_not_loaded": (
        "Node {class_type} is not loaded on the ComfyUI server. Check that "
        "ComfyUI-DLSS5-Enhancer is installed and that the server started without error.",
        "Le node {class_type} n'est pas chargé sur le serveur ComfyUI. Vérifier que "
        "ComfyUI-DLSS5-Enhancer est installé et que le serveur a démarré sans erreur.",
    ),
    "j.tick_init": (
        "initialising / counting frames…",
        "initialisation / comptage des frames…",
    ),
    "j.encoder_ok": ("OK", "OK"),
    "j.encoder_unavailable": ("UNAVAILABLE", "INDISPONIBLE"),
    # doctor / setup
    "d.header": ("Installation check:", "Vérification de l'installation :"),
    "d.gpu": ("NVIDIA GPU and driver", "GPU NVIDIA et pilote"),
    "d.comfyui": ("ComfyUI", "ComfyUI"),
    "d.node": ("DLSS5 node pack", "Pack de nodes DLSS5"),
    "d.runtime": ("DLSS5 native runtime", "Runtime natif DLSS5"),
    "d.ffmpeg": ("ffmpeg / ffprobe", "ffmpeg / ffprobe"),
    "d.disk": ("Free disk space", "Espace disque libre"),
    "d.status.ok": ("OK", "OK"),
    "d.status.missing": ("MISSING", "MANQUANT"),
    "d.status.broken": ("TO FIX", "À RÉPARER"),
    "d.line": ("  [{status}] {label}{detail}", "  [{status}] {label}{detail}"),
    "d.gpu_ok": ("{name}, driver {driver}", "{name}, pilote {driver}"),
    "d.gpu_missing": (
        "nvidia-smi not found: an NVIDIA card and a current driver are required",
        "nvidia-smi introuvable : une carte NVIDIA et un pilote à jour sont requis",
    ),
    "d.comfy_ok": ("{root}", "{root}"),
    "d.comfy_missing": (
        "not installed — point at an existing folder or download the portable build",
        "non installé — indiquer un dossier existant ou télécharger la version portable",
    ),
    "d.node_ok": ("{path}", "{path}"),
    "d.node_missing": (
        "not installed in custom_nodes",
        "absent de custom_nodes",
    ),
    "d.runtime_ok": ("{path}", "{path}"),
    "d.runtime_missing": (
        "missing (about 467 MB to download, third-party binaries)",
        "absent (environ 467 Mo à télécharger, binaires tiers)",
    ),
    "d.ffmpeg_ok": ("{path}", "{path}"),
    "d.ffmpeg_missing": (
        "not found (it ships with the node's runtime)",
        "introuvable (il vient avec le runtime du node)",
    ),
    "d.disk_ok": ("{free} GB free on {volume}", "{free} Go libres sur {volume}"),
    "d.disk_low": (
        "{free} GB free on {volume}, about 6 GB needed",
        "{free} Go libres sur {volume}, environ 6 Go nécessaires",
    ),
    "d.ready": ("Everything is ready.", "Tout est prêt."),
    "d.not_ready": (
        "Something is still missing: run --setup (or the Setup button).",
        "Il manque encore quelque chose : lancer --setup (ou le bouton Installation).",
    ),
    "d.ask_comfy_download": (
        "Download ComfyUI (about 1.8 GB)? [y/N] ",
        "Télécharger ComfyUI (environ 1,8 Go) ? [y/N] ",
    ),
    "d.ask_comfy_browse": (
        "ComfyUI was not found. Give the folder that contains it (or press Enter to skip): ",
        "ComfyUI est introuvable. Indiquer le dossier qui le contient (ou Entrée pour passer) : ",
    ),
    "d.comfy_downloading": ("Downloading ComfyUI", "Téléchargement de ComfyUI"),
    "d.comfy_extracting": ("Extracting ComfyUI", "Extraction de ComfyUI"),
    "d.node_downloading": ("Downloading the node pack", "Téléchargement du pack de nodes"),
    "d.deps_installing": ("Installing the node dependencies", "Installation des dépendances du node"),
    "d.runtime_downloading": ("Downloading the DLSS5 runtime", "Téléchargement du runtime DLSS5"),
    "d.runtime_notice": (
        "The DLSS5 runtime is a third-party download (about 467 MB) from the node pack's\n"
        "own installer. It contains: nvngx.dll (standalone D3D12 worker, upstream project),\n"
        "nvngx_dlss.dll and nvngx_dlssnr.dll (NVIDIA proprietary terms), dxgi.dll (ReShade,\n"
        "BSD-3-Clause), renodx-dlss5.addon64 (RenoDX, its own terms), ffmpeg.exe/ffprobe.exe.\n"
        "These files are neither owned nor redistributed by this tool. Install only what you\n"
        "are authorised to use, from sources their licences permit.",
        "Le runtime DLSS5 est un téléchargement tiers (environ 467 Mo) effectué par\n"
        "l'installateur du pack de nodes. Il contient : nvngx.dll (worker D3D12 autonome,\n"
        "projet amont), nvngx_dlss.dll et nvngx_dlssnr.dll (termes propriétaires NVIDIA),\n"
        "dxgi.dll (ReShade, BSD-3-Clause), renodx-dlss5.addon64 (RenoDX, ses propres termes),\n"
        "ffmpeg.exe/ffprobe.exe. Ces fichiers ne sont ni la propriété ni redistribués par cet\n"
        "outil. N'installez que ce que vous êtes autorisé à utiliser.",
    ),
    "d.ask_accept_runtime": (
        "I have read the notice above and accept downloading the runtime [y/N] ",
        "J'ai lu l'avis ci-dessus et j'accepte de télécharger le runtime [y/N] ",
    ),
    "d.ask_runtime_dir": (
        "Path to an existing 'DLSS 5 Visual Enhancer' runtime folder (Enter to download): ",
        "Chemin d'un dossier runtime « DLSS 5 Visual Enhancer » existant (Entrée pour télécharger) : ",
    ),
    "d.selftest": (
        "Self test: rendering a one-second clip",
        "Auto-test : rendu d'un clip d'une seconde",
    ),
    "d.selftest_ok": ("Self test passed ({path}).", "Auto-test réussi ({path})."),
    "d.selftest_failed": ("Self test failed: {error}", "Auto-test échoué : {error}"),
    "d.saved": ("Settings saved to {path}.", "Réglages enregistrés dans {path}.")
    ,
    "d.invalid_root": (
        "{path} does not look like a ComfyUI folder (no ComfyUI/main.py).",
        "{path} ne ressemble pas à un dossier ComfyUI (pas de ComfyUI/main.py).",
    ),
    "d.node_install_hint": (
        "Install it from the node repository, or re-run --setup with network access.",
        "L'installer depuis le dépôt du node, ou relancer --setup avec un accès réseau.",
    ),
    "d.need_runtime_accept": (
        "Runtime not installed: re-run --setup and accept the notice (or pass --runtime-dir).",
        "Runtime non installé : relancer --setup et accepter l'avis (ou passer --runtime-dir).",
    ),
    # gui
    "u.title": ("DLSS5 Enhance {version}", "DLSS5 Enhance {version}"),
    "u.section.preset": ("Preset", "Preset"),
    "u.section.source": ("Source", "Source"),
    "u.section.paths": ("Output and workflow", "Sortie et workflow"),
    "u.section.progress": ("Progress", "Progression"),
    "u.section.log": ("Log", "Journal"),
    "u.pick_file": ("Choose a file…", "Choisir un fichier…"),
    "u.pick_folder": ("Choose a folder…", "Choisir un dossier…"),
    "u.no_source": ("(no source)", "(aucune source)"),
    "u.output_label": ("Output", "Sortie"),
    "u.workflow_label": ("Workflow", "Workflow"),
    "u.browse": ("Browse…", "Parcourir…"),
    "u.run": ("Run", "Lancer"),
    "u.check": ("Check", "Vérifier"),
    "u.cancel": ("Cancel", "Annuler"),
    "u.force": ("Force a new render", "Forcer un nouveau rendu"),
    "u.open_output": ("Open output folder", "Ouvrir le dossier de sortie"),
    "u.language": ("Language", "Langue"),
    "u.ready": ("Ready.", "Prêt."),
    "u.verifying": ("Checking, then starting…", "Vérification puis lancement…"),
    "u.nothing_to_cancel": ("Nothing to cancel.", "Rien à annuler."),
    "u.cancelling": ("Cancellation requested…", "Annulation demandée…"),
    "u.finished": ("Done.", "Terminé."),
    "u.cancelled": ("Cancelled.", "Annulé."),
    "u.finished_errors": ("Finished with errors (code {code}).", "Terminé avec des erreurs (code {code})."),
    "u.preset_none": ("No preset in config.yaml.", "Aucun preset dans config.yaml."),
    "u.upscaling": ("Upscaling: {mode}", "Upscaling : {mode}"),
    "u.title.pick_file": ("Choose a video", "Choisir une vidéo"),
    "u.title.pick_folder": ("Choose a folder of videos", "Choisir un dossier de vidéos"),
    "u.title.pick_output": ("Output folder", "Dossier de sortie"),
    "u.title.pick_workflow": ("Workflow (API export)", "Workflow (export API)"),
    "u.filetypes.videos": ("Videos", "Vidéos"),
    "u.filetypes.workflow": ("Workflow JSON", "Workflow JSON"),
    "u.filetypes.all": ("All files", "Tous les fichiers"),
    "u.dlg.source_title": ("Source", "Source"),
    "u.dlg.source_msg": ("Choose a file or a folder.", "Choisir un fichier ou un dossier."),
    "u.dlg.output_title": ("Output", "Sortie"),
    "u.dlg.output_msg": ("Choose an output folder.", "Choisir un dossier de sortie."),
    "u.dlg.workflow_title": ("Workflow", "Workflow"),
    "u.dlg.workflow_msg": (
        "Choose the workflow exported in API format ('Browse…' button).",
        "Choisir le workflow exporté en format API (bouton « Parcourir… »).",
    ),
    "u.dlg.config_title": ("Configuration", "Configuration"),
    "u.dlg.quit_title": ("Quit", "Quitter"),
    "u.dlg.quit_msg": (
        "A job is running. Cancel it and quit?",
        "Un traitement est en cours. L'annuler et quitter ?",
    ),
    "u.unexpected": ("Unexpected error: {error}", "Erreur inattendue : {error}"),
    "u.infra": ("Infrastructure: {error}", "Infrastructure : {error}"),
    "u.error": ("Error: {error}", "Erreur : {error}"),
    "u.setup_button": ("Setup…", "Installation…"),
}


def normalize_language(value: Any) -> str | None:
    """Map 'fr', 'fr-FR', 'en_US' onto a supported code; None when unknown."""
    if value is None:
        return None
    text = str(value).strip().lower().replace("_", "-")
    if not text:
        return None
    head = text.split("-", 1)[0]
    return head if head in LANGUAGES else None


def resolve_language(*candidates: Any) -> str:
    """First supported candidate wins; the environment then the default fill in."""
    for candidate in candidates:
        resolved = normalize_language(candidate)
        if resolved is not None:
            return resolved
    from_env = normalize_language(os.environ.get(ENV_VAR))
    return from_env or DEFAULT_LANGUAGE


class Translator:
    """Holds the active language; a fresh process starts in English."""

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self.language = normalize_language(language) or DEFAULT_LANGUAGE

    def set(self, language: Any) -> str:
        resolved = normalize_language(language)
        if resolved is not None:
            self.language = resolved
        return self.language

    def get(self) -> str:
        return self.language

    def tr(self, message_key: str, **kwargs: Any) -> str:
        entry = MESSAGES.get(message_key)
        if entry is None:
            return message_key
        index = 0 if self.language == "en" else 1
        template = entry[index] or entry[0]
        if not kwargs:
            return template
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return template


TRANSLATOR = Translator()


def set_language(language: Any) -> str:
    return TRANSLATOR.set(language)


def language() -> str:
    return TRANSLATOR.get()


def tr(message_key: str, **kwargs: Any) -> str:
    return TRANSLATOR.tr(message_key, **kwargs)
