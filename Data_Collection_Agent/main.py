"""
Data_Collection_Agent/main.py  (v9 — Self-Learning Agentic Loop)
=================================================================
Agentic data collection entrypoint for RAD-ML.

Pipeline (self-healing loop):
  Tier -1: Experience Memory   — instant replay of known-good datasets
  Tier  0: Local Cache         — CSV files already on disk
  Tier  1: Parallel Search     — Kaggle + UCI + OpenML + HuggingFace (parallel)
  Tier  2: Kaggle Fallbacks    — known dataset refs from the prompt spec
  Tier  3: OpenML Deep Search  — keyword / task / domain search
  Tier  4: HuggingFace Hub     — no API key required

  On failure (0 results OR all features mismatched):
    → SearchReflector asks LLM to analyze the failure
    → LLM suggests broader keywords / relaxed constraints
    → Retry from Tier 1 with revised spec (max 2 retries)

  On feature mismatch with match_ratio >= 60%:
    → LLMFeatureRepairer renames/derives missing columns
    → Dataset re-verified with repaired columns

  On success:
    → ExperienceMemory records the winning dataset for next time
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from pathlib import Path

ROOT         = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
for import_path in (str(ROOT), str(PROJECT_ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

# Maximum self-reflection retries (prevents infinite loops)
_MAX_RETRIES = 2


def _load_config(path=None) -> dict:
    import yaml
    for candidate in [path, ROOT / "config.yaml", PROJECT_ROOT / "config.yaml"]:
        if candidate and Path(candidate).exists():
            with open(candidate, encoding="utf-8") as handle:
                return yaml.safe_load(handle) or {}
    return {}


def _setup_logging(config: dict) -> None:
    log_cfg = config.get("logging", {})
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_cfg.get("console_level", "INFO").upper(), logging.INFO),
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_cfg.get("log_file", "logs/rad_ml.log")),
        ],
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH ENGINE  (stateless helpers, called in the agentic loop)
# ══════════════════════════════════════════════════════════════════════════════

def _make_collector_cache(config: dict) -> dict:
    """Lazily create collectors — stored by name so each is built once."""
    return {}


def _get_collector(name: str, cache: dict, config: dict):
    if name not in cache:
        if name == "kaggle":
            from collectors.kaggle_collector import KaggleCollector
            cache[name] = KaggleCollector(config)
        elif name == "uci":
            from collectors.uci_collector import UCICollector
            cache[name] = UCICollector(config)
        elif name == "openml":
            from collectors.openml_collector import OpenMLCollector
            cache[name] = OpenMLCollector(config)
        elif name == "huggingface":
            from collectors.huggingface_collector import HuggingFaceCollector
            cache[name] = HuggingFaceCollector(config)
        else:
            raise KeyError(f"Unknown collector '{name}'")
    return cache[name]


def _search_provider(
    provider_name: str, keyword: str, spec: dict, cache: dict, config: dict
) -> tuple[str, list[dict], str]:
    try:
        if provider_name == "kaggle":
            c = _get_collector("kaggle", cache, config)
            return provider_name, c.search(keyword), c.last_error
        if provider_name == "uci":
            c = _get_collector("uci", cache, config)
            return provider_name, c.search(keyword), ""
        if provider_name == "openml":
            c = _get_collector("openml", cache, config)
            return provider_name, c.search(keyword, spec), ""
        if provider_name == "huggingface":
            c = _get_collector("huggingface", cache, config)
            return provider_name, c.search(keyword, spec), c.last_error
    except Exception as exc:
        return provider_name, [], str(exc)
    return provider_name, [], f"Unknown provider '{provider_name}'"


def _search_keyword_parallel(
    keyword: str,
    spec: dict,
    cache: dict,
    config: dict,
    timeout_secs: int,
    step,
    provider_health: dict,
) -> dict[str, list[dict]]:
    provider_names = ["kaggle", "uci", "openml", "huggingface"]
    step("search", f"  query: '{keyword}' (parallel, {timeout_secs}s budget)")
    executor = ThreadPoolExecutor(max_workers=16)
    futures = {
        executor.submit(_search_provider, pn, keyword, spec, cache, config): pn
        for pn in provider_names
    }
    results: dict[str, list[dict]] = {pn: [] for pn in provider_names}
    errors: dict[str, str] = {}
    try:
        for future in as_completed(futures, timeout=timeout_secs):
            pn = futures[future]
            name, metas, error = future.result()
            results[name] = metas
            provider_health[name] = "ok"
            if error:
                errors[name] = error
            step("search", f"    {name}: {len(metas)} result(s)")
    except FutureTimeoutError:
        pending = [futures[f] for f in futures if not f.done()]
        for pn in pending:
            provider_health[pn] = "timeout"
        step("search", f"    timeout: continuing without {pending}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    for pn, err in errors.items():
        if provider_health.get(pn) != "timeout":
            provider_health[pn] = "error"
        step("search", f"    {pn} note: {err}")
    return results


def _find_local_cache_candidates(spec: dict, keywords: list, fallback_refs: list) -> list[dict]:
    candidate_dirs = [
        PROJECT_ROOT / "data" / "raw",
        PROJECT_ROOT / "Chatbot_Interface" / "backend" / "data" / "raw",
    ]
    raw_terms: set[str] = set()
    raw_terms.update(str(spec.get("domain", "")).lower().split())
    raw_terms.update(k.lower() for k in keywords)
    raw_terms.update(
        part.lower()
        for ref in fallback_refs
        for part in ref.replace("/", " ").replace("-", " ").split()
    )
    terms = [t for t in raw_terms if len(t) >= 3]
    if not terms:
        return []
    metas: list[dict] = []
    seen_paths: set[str] = set()
    for base_dir in candidate_dirs:
        if not base_dir.exists():
            continue
        for csv_path in base_dir.rglob("*.csv"):
            haystack = f"{csv_path.name} {csv_path.parent.name}".lower()
            if not any(t in haystack for t in terms):
                continue
            resolved = str(csv_path.resolve())
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            metas.append({
                "source": "local_cache", "ref": resolved,
                "title": csv_path.parent.name.replace("_", " "),
                "url": resolved,
                "size_mb": round(csv_path.stat().st_size / 1_000_000, 2),
                "vote_count": 0, "local_path": resolved,
            })
    return metas[:8]


def _add_unique(metas: list[dict], all_metas: list[dict], seen_refs: set[str]) -> None:
    for meta in metas:
        ref = meta.get("ref", "")
        if ref and ref not in seen_refs:
            seen_refs.add(ref)
            all_metas.append(meta)


# ══════════════════════════════════════════════════════════════════════════════
# DOWNLOAD & VERIFY  (single candidate)
# ══════════════════════════════════════════════════════════════════════════════

def _download_candidate(
    meta: dict, cache: dict, config: dict, step, reflector, spec: dict
) -> tuple[list[Path], str, bool]:
    """
    Download one candidate and return (csv_paths, error_msg, repaired).
    """
    source = meta.get("source", "kaggle")
    ref    = meta.get("ref", "")
    repaired = False

    try:
        if source == "local_cache":
            return [Path(meta["local_path"])], "", False
        elif source == "kaggle":
            c = _get_collector("kaggle", cache, config)
            return c.download(ref), c.last_error, False
        elif source == "uci":
            c = _get_collector("uci", cache, config)
            return c.download(ref), "", False
        elif source == "openml":
            c = _get_collector("openml", cache, config)
            return c.download(ref), "", False
        elif source in ("huggingface", "kaggle_fallback"):
            dl_source = "huggingface" if source == "huggingface" else "kaggle"
            c = _get_collector(dl_source, cache, config)
            paths = c.download(ref)
            return paths, getattr(c, "last_error", ""), False
        else:
            return [], f"Unsupported source '{source}'.", False
    except Exception as exc:
        step("download", f"  -> Download error: {exc}")
        return [], str(exc), False


# ══════════════════════════════════════════════════════════════════════════════
# MAIN AGENTIC COLLECTION FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def run_collection(prompt: str, config: dict, job_id: str, log_fn=None) -> dict:
    from dca_brain.prompt_parser import PromptParser
    from dca_brain.experience import ExperienceMemory
    from dca_brain.reflection import SearchReflector
    from utils.dataset_merger import DatasetMerger
    from utils.dataset_scorer import DatasetScorer
    from utils.feature_verifier import FeatureVerifier
    from utils.s3_uploader import S3Uploader

    log = logging.getLogger(__name__)

    def step(name: str, msg: str) -> None:
        log.info("[%s] %s", name, msg)
        if log_fn:
            log_fn(name, msg)

    # ── Parse prompt (enhanced spec) ──────────────────────────────────────────
    step("parse", f"Parsing prompt: {prompt[:80]}")
    spec = PromptParser().parse(prompt)
    step("parse", (
        f"Intent -> intent={spec['intent'].upper()}  "
        f"task={spec['task_type'].upper()}  domain='{spec['domain']}'"
    ))
    step("parse", (
        f"Search keywords: {spec['keywords']}  |  "
        f"Inputs: {spec['input_params']}  |  Target: {spec['target_param']}"
    ))
    if spec.get("missing_information"):
        step("parse", f"Detected gaps: {spec['missing_information']}")
    if spec.get("fallback_refs"):
        step("parse", f"Fallback datasets ready: {spec['fallback_refs'][:3]}")

    # ── Shared state ──────────────────────────────────────────────────────────
    scorer        = DatasetScorer(config)
    memory        = ExperienceMemory(config)
    reflector     = SearchReflector(config)
    feat_verifier = FeatureVerifier(config)
    cache: dict   = _make_collector_cache(config)
    search_timeout = int(config.get("collection", {}).get("provider_search_timeout_secs", 10))
    min_rows       = int(config.get("collection", {}).get("min_row_threshold", 500))

    mem_stats = memory.stats()
    step("memory", (
        f"Experience memory loaded — "
        f"{mem_stats['total_entries']} entries, "
        f"{mem_stats['total_uses']} total reuses"
    ))

    # ─────────────────────────────────────────────────────────────────────────
    # TIER -1: Experience Memory  (instant replay)
    # ─────────────────────────────────────────────────────────────────────────
    mem_hit = memory.query(spec)
    if mem_hit:
        step("memory", (
            f"Tier -1 HIT — reusing cached dataset from '{mem_hit['provider']}' "
            f"ref={mem_hit['dataset_ref']}  rows={mem_hit['row_count']}"
        ))
        local_path = Path(mem_hit["local_path"])
        import pandas as pd
        df_preview = pd.read_csv(local_path, nrows=10)
        row_count  = mem_hit["row_count"]
        columns    = mem_hit["columns"]
        payload = _build_payload(
            job_id, prompt, spec, str(local_path), None,
            columns, row_count, 1,
            df_preview.to_dict(orient="records"), False,
            [{"source": mem_hit["provider"],
              "title": mem_hit["dataset_ref"],
              "url": "",
              "final_score": mem_hit["score"],
              "row_count": row_count}],
            config,
        )
        step("done", f"Collection complete (from memory) - {row_count:,} rows")
        return payload

    # ─────────────────────────────────────────────────────────────────────────
    # AGENTIC SELF-HEALING LOOP
    # ─────────────────────────────────────────────────────────────────────────
    current_spec       = dict(spec)
    retry_count        = 0
    last_failure       = ""
    provider_health: dict[str, str] = {}

    while retry_count <= _MAX_RETRIES:
        if retry_count > 0:
            step("reflect", f"--- RETRY {retry_count}/{_MAX_RETRIES} ---")
            step("reflect", f"Applying revised strategy: keywords={current_spec['keywords']}")

        keywords      = current_spec["keywords"]
        fallback_refs = current_spec.get("fallback_refs", [])
        all_metas:  list[dict] = []
        seen_refs:  set[str]   = set()

        # TIER 0: Local cache
        local_cache = _find_local_cache_candidates(current_spec, keywords, fallback_refs)
        if local_cache:
            _add_unique(local_cache, all_metas, seen_refs)
            step("search", f"Tier 0 - found {len(local_cache)} local cached dataset(s)")

        # TIER 1: Parallel search
        step("search", "Tier 1 - searching Kaggle + UCI + OpenML + HuggingFace")
        if len(all_metas) < 5:
            for keyword in keywords[:4]:
                results = _search_keyword_parallel(
                    keyword, current_spec, cache, config,
                    search_timeout, step, provider_health,
                )
                for pn in ["kaggle", "uci", "openml", "huggingface"]:
                    _add_unique(results.get(pn, []), all_metas, seen_refs)
                step("search", (
                    f"  '{keyword}' -> "
                    f"Kaggle:{len(results.get('kaggle',[]))}  "
                    f"UCI:{len(results.get('uci',[]))}  "
                    f"OpenML:{len(results.get('openml',[]))}  "
                    f"HuggingFace:{len(results.get('huggingface',[]))}"
                ))
                if len(all_metas) >= 5:
                    break

        # TIER 2: Kaggle fallbacks
        if not all_metas and fallback_refs:
            kaggle = _get_collector("kaggle", cache, config)
            if not kaggle.are_credentials_available():
                step("search", "Tier 2 - SKIPPED (Kaggle credentials unavailable)")
            else:
                step("search", f"Tier 2 - resolving {len(fallback_refs)} fallback ref(s)")
                for ref in fallback_refs[:5]:
                    step("search", f"  resolving fallback: {ref}")
                    _add_unique(kaggle.search_by_ref(ref), all_metas, seen_refs)
                if all_metas:
                    step("search", f"Tier 2 success: {len(all_metas)} dataset(s) resolved")

        # TIER 3: OpenML deep search
        if not all_metas:
            step("search", "Tier 3 - OpenML deep search")
            if provider_health.get("openml") != "timeout":
                openml = _get_collector("openml", cache, config)
                for kw in keywords[:5]:
                    step("search", f"  OpenML: '{kw}'")
                    _add_unique(openml.search(kw, current_spec), all_metas, seen_refs)
                    if len(all_metas) >= 5:
                        break
                # Task and domain fallbacks
                for search_term in [
                    current_spec.get("task_type", ""),
                    current_spec.get("domain", ""),
                ]:
                    if not all_metas and search_term:
                        _add_unique(openml.search(search_term, current_spec), all_metas, seen_refs)
                if all_metas:
                    step("search", f"Tier 3 success: {len(all_metas)} dataset(s)")

        # TIER 4: HuggingFace Hub
        if not all_metas:
            step("search", "Tier 4 - HuggingFace Hub")
            hf = _get_collector("huggingface", cache, config)
            for kw in keywords[:4]:
                step("search", f"  HuggingFace: '{kw}'")
                _add_unique(hf.search(kw, current_spec), all_metas, seen_refs)
                if len(all_metas) >= 5:
                    break
            if all_metas:
                step("search", f"Tier 4 success: {len(all_metas)} dataset(s)")

        # ── No results: reflect and retry ─────────────────────────────────────
        if not all_metas:
            last_failure = "All search tiers returned 0 results"
            step("reflect", f"Zero results — triggering reflection (retry {retry_count + 1}/{_MAX_RETRIES})")
            if retry_count < _MAX_RETRIES:
                current_spec = reflector.reflect_on_search_failure(current_spec, last_failure)
                retry_count += 1
                provider_health = {}   # reset health for next attempt
                continue
            else:
                break   # exhausted retries

        # ── Score and rank ────────────────────────────────────────────────────
        for meta in all_metas:
            scorer.score_metadata(meta, current_spec)
        all_metas.sort(key=lambda m: m.get("pre_score", 0), reverse=True)

        top_k = all_metas[:8]
        step("score", (
            f"Best candidate: '{top_k[0]['title']}'  "
            f"source={top_k[0]['source'].upper()}  "
            f"score={top_k[0].get('pre_score', 0):.3f}"
        ))

        # ── Download, verify, and repair ──────────────────────────────────────
        scored_csvs: list[tuple]       = []
        feature_failed_csvs: list[tuple] = []
        download_failures: list[str]   = []

        for meta in top_k:
            source = meta.get("source", "kaggle")
            step("download", f"[{source.upper()}] {meta.get('title', '')[:55]}")

            csv_paths, src_error, _ = _download_candidate(
                meta, cache, config, step, reflector, current_spec
            )

            if not csv_paths:
                msg = src_error or "no usable tabular files extracted"
                step("download", f"  -> {msg}")
                download_failures.append(f"{source.upper()} {meta.get('ref','')}: {msg}")
                continue

            csv_path   = max(csv_paths, key=lambda p: p.stat().st_size)
            final_score = scorer.score_csv(csv_path, meta, current_spec)
            meta["local_path"] = str(csv_path)

            # ── Get repair plan from reflector if partial match available ─────
            quick_check = feat_verifier.verify(csv_path, current_spec)
            repair_plan: dict | None = None
            if not quick_check.passed and quick_check.match_ratio >= 0.4:
                step("repair", (
                    f"  -> Partial match ({quick_check.match_ratio:.0%}) — "
                    f"asking reflector for repair plan..."
                ))
                repair_plan = reflector.reflect_on_feature_mismatch(
                    current_spec,
                    quick_check.csv_columns,
                    quick_check.missing_features,
                )

            # ── Verify (with repair if available) ─────────────────────────────
            fv_result = feat_verifier.verify_and_repair(csv_path, current_spec, repair_plan)

            if fv_result.repaired:
                step("repair", f"  -> Column repair applied to {csv_path.name}")

            if fv_result.passed:
                scored_csvs.append((csv_path, final_score, meta))
                step("download", (
                    f"  -> {csv_path.name}  rows={meta.get('row_count', '?')}  "
                    f"score={final_score:.3f}  features={fv_result.match_ratio:.0%} matched"
                    + ("  [REPAIRED]" if fv_result.repaired else "")
                ))
            else:
                feature_failed_csvs.append((csv_path, final_score, meta))
                step("download", (
                    f"  -> {csv_path.name}  FEATURE MISMATCH ({fv_result.match_ratio:.0%})  "
                    f"missing={fv_result.missing_features}  cols={fv_result.csv_columns[:8]}"
                ))

            step("download", f"  -> {csv_path.name}  rows={meta.get('row_count', '?')}  score={final_score:.3f}")

            should_stop_early = meta.get("row_count", 0) >= min_rows and (
                source == "local_cache" or len(scored_csvs) >= 2
            )
            if should_stop_early:
                step("download", "Row threshold met — stopping early.")
                break

        # ── All datasets failed features — reflect on mismatch ────────────────
        if not scored_csvs and feature_failed_csvs and retry_count < _MAX_RETRIES:
            best_ff = max(feature_failed_csvs, key=lambda x: x[1])
            best_csv_path, _, best_meta = best_ff
            partial_verify = feat_verifier.verify(best_csv_path, current_spec)
            last_failure = (
                f"All datasets failed feature verification. "
                f"Best match={partial_verify.match_ratio:.0%}, "
                f"missing={partial_verify.missing_features}"
            )
            step("reflect", f"Feature mismatch — triggering reflection (retry {retry_count + 1}/{_MAX_RETRIES})")
            revised = reflector.reflect_on_search_failure(current_spec, last_failure)
            current_spec = revised
            retry_count += 1
            provider_health = {}
            continue

        # ── Fallback: use best feature-failed dataset if nothing else works ───
        if not scored_csvs and feature_failed_csvs:
            feature_failed_csvs.sort(key=lambda x: x[1], reverse=True)
            best_ff = feature_failed_csvs[0]
            scored_csvs.append(best_ff)
            step("download", (
                f"All datasets failed feature verification. "
                f"Using best fallback: {best_ff[0].name} (score={best_ff[1]:.3f})"
            ))

        if not scored_csvs:
            if retry_count < _MAX_RETRIES:
                last_failure = "Found metadata but all downloads failed"
                step("reflect", f"Download failures — triggering reflection (retry {retry_count + 1}/{_MAX_RETRIES})")
                current_spec = reflector.reflect_on_search_failure(current_spec, last_failure)
                retry_count += 1
                provider_health = {}
                continue
            else:
                break  # give up

        # ── We have good scored_csvs — exit the loop ──────────────────────────
        break

    # ── Final guard: raise informative error if still nothing ─────────────────
    if not locals().get("scored_csvs"):
        scored_csvs = []

    if not scored_csvs:
        kg_user = config.get("kaggle", {}).get("username", "")
        kg_key  = config.get("kaggle", {}).get("key", "")
        raise RuntimeError(
            "No datasets found after exhausting all search tiers and "
            f"{retry_count} retry/reflection attempt(s).\n"
            f"  Last failure: {last_failure}\n\n"
            "Diagnosis:\n"
            f"  Kaggle configured : {'no' if not kg_user else 'yes'}\n"
            f"  Kaggle API key    : {'not set' if not kg_key else 'set'}\n"
            f"  Intent detected   : {spec.get('intent', '?').upper()}\n"
            f"  Task type         : {spec.get('task_type', '?').upper()}\n"
            f"  Domain detected   : '{spec.get('domain', 'n/a')}'\n"
            f"  Keywords tried    : {spec.get('keywords', [])}\n\n"
            "Fixes to try:\n"
            "  1. Use the 'Upload CSV' button if you already have a dataset.\n"
            "  2. Verify Kaggle username and API key in config.yaml.\n"
            "  3. Regenerate your Kaggle API token.\n"
            "  4. Check internet connectivity.\n"
            "  5. Try a broader prompt (e.g. remove location constraints).\n"
            "  6. Retry later if provider APIs are unavailable.\n"
        )

    # ── Merge ─────────────────────────────────────────────────────────────────
    scored_csvs.sort(key=lambda x: x[1], reverse=True)
    step("merge", "Building final dataset")
    merger = DatasetMerger(config)
    ds_info = merger.build_final_dataset(scored_csvs, job_id)
    step("merge", (
        f"Final dataset: {ds_info['row_count']:,} rows x "
        f"{len(ds_info['columns'])} cols  merged={ds_info['merged']}"
    ))

    # ── Upload ────────────────────────────────────────────────────────────────
    step("upload", "Uploading to S3")
    uploader = S3Uploader(config)
    s3_uri   = uploader.upload_dataset(ds_info["path"], job_id)
    step("upload", f"S3 URI: {s3_uri or '(disabled/skipped)'}")

    # ── Record success in experience memory ───────────────────────────────────
    winning_meta  = scored_csvs[0][2]
    winning_score = scored_csvs[0][1]
    memory.record(
        spec       = spec,
        provider   = winning_meta.get("source", "unknown"),
        dataset_ref= winning_meta.get("ref", ""),
        local_path = str(ds_info["path"]),
        row_count  = ds_info["row_count"],
        columns    = ds_info["columns"],
        score      = winning_score,
        job_id     = job_id,
    )
    step("memory", f"Recorded successful run in experience memory (ref={winning_meta.get('ref','')})")

    # ── Assemble payload ──────────────────────────────────────────────────────
    top_sources = [
        {
            "source":      m.get("source"),
            "title":       m.get("title"),
            "url":         m.get("url"),
            "final_score": m.get("final_score", m.get("pre_score", 0)),
            "row_count":   m.get("row_count", 0),
        }
        for _, _, m in scored_csvs[:3]
    ]

    payload = _build_payload(
        job_id, prompt, current_spec,
        str(ds_info["path"]), s3_uri,
        ds_info["columns"], ds_info["row_count"],
        ds_info["source_count"], ds_info["preview_rows"],
        ds_info["merged"], top_sources, config,
    )

    results_path = Path(
        config.get("storage", {}).get("results_json", "Data_Collection_Agent/db_results.json")
    )
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)

    results_json_s3_uri = uploader.upload_results_json(payload, job_id)
    if results_json_s3_uri:
        payload["results_json_s3_uri"] = results_json_s3_uri

    step("done", (
        f"Collection complete - {ds_info['row_count']:,} rows "
        f"from {ds_info['source_count']} source(s)  "
        f"retries_used={retry_count}"
    ))
    return payload


def _build_payload(
    job_id, prompt, spec, local_path, s3_uri,
    columns, row_count, source_count, preview_rows, merged,
    top_sources, config,
) -> dict:
    return {
        "job_id":  job_id,
        "prompt":  prompt,
        "spec":    spec,
        "dataset": {
            "local_path":   local_path,
            "s3_uri":       s3_uri,
            "columns":      columns,
            "row_count":    row_count,
            "source_count": source_count,
            "preview_rows": preview_rows,
            "merged":       merged,
        },
        "top_sources": top_sources,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAD-ML Self-Learning Data Collection Agent"
    )
    parser.add_argument("--prompt",  required=True, help="Natural language task description")
    parser.add_argument("--job-id",  default=None,  help="Job ID (auto-generated if omitted)")
    parser.add_argument("--config",  default=None,  help="Path to config.yaml")
    args = parser.parse_args()

    config = _load_config(args.config)
    _setup_logging(config)
    job_id = args.job_id or str(uuid.uuid4())[:8]

    try:
        result = run_collection(args.prompt, config, job_id)
        print(f"\nDataset : {result['dataset']['local_path']}")
        print(f"Rows    : {result['dataset']['row_count']:,}")
        print(f"Columns : {len(result['dataset']['columns'])}")
    except Exception as exc:
        logging.getLogger(__name__).critical("Collection failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
