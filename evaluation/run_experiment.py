"""Run the existing evaluator while preserving source/data provenance for comparison."""

import argparse
import hashlib
from pathlib import Path
import sys
import zipfile

from evaluation.evaluate import evaluate
from load_data import read_json, write_json


ROOT = Path(__file__).resolve().parents[1]


def file_hash(path):
    """Hash bytes without inspecting answer-key contents or changing input files."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run_experiment(output_dir, data_dir=Path("data/seed-data_no-ground-truth"),
                   truth_dir=Path("data/seed-data_with-ground-truth"), labels_path=None,
                   max_domain_count=10, benign_sample=100, random_seed=6262):
    """Snapshot the measured code, run evaluation, and record verified metric hashes."""
    output_dir, data_dir, truth_dir = Path(output_dir), Path(data_dir), Path(truth_dir)
    if output_dir.exists():
        raise ValueError(f"Refusing to overwrite an existing experiment: {output_dir}")
    sources = sorted([ROOT / "load_data.py", *(ROOT / "pivot").glob("*.py"),
                      *(ROOT / "evaluation").glob("*.py"), *(ROOT / "tests").glob("*.py")])
    data_paths = [data_dir / name for name in ("resolutions.jsonl", "infra.json", "domains.json", "manifest.json")]
    truth_path = truth_dir / "ground_truth.json"
    source_hashes = {str(path.relative_to(ROOT)): file_hash(path) for path in sources}
    data_hashes = {str(path): file_hash(path) for path in data_paths}
    truth_hash = file_hash(truth_path)  # Evaluation provenance only; never a pivot feature.
    labels_hash = file_hash(Path(labels_path)) if labels_path is not None else None
    output_dir.mkdir(parents=True)
    with zipfile.ZipFile(output_dir / "source.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sources:
            archive.write(path, path.relative_to(ROOT).as_posix())
    evaluate(data_dir, truth_dir, output_dir, labels_path, max_domain_count, benign_sample, random_seed)
    if any(file_hash(path) != source_hashes[str(path.relative_to(ROOT))] for path in sources):
        raise ValueError("Source changed during evaluation; this run cannot be certified")
    if any(file_hash(path) != data_hashes[str(path)] for path in data_paths) or file_hash(truth_path) != truth_hash:
        raise ValueError("Data changed during evaluation; this run cannot be certified")
    if labels_path is not None and file_hash(Path(labels_path)) != labels_hash:
        raise ValueError("Filter labels changed during evaluation; this run cannot be certified")
    summary = read_json(output_dir / "summary.json")
    write_json(output_dir / "run_manifest.json", {
        "python": sys.version, "source_sha256": source_hashes, "data_sha256": data_hashes,
        "ground_truth_sha256": truth_hash, "labels_sha256": labels_hash,
        "evaluation_config": summary["config"],
        "artifact_sha256": {name: file_hash(output_dir / name)
                            for name in ("summary.json", "per_seed.jsonl", "source.zip")},
    })


def main():
    """Expose the evaluator's existing settings without adding a second scoring pipeline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data/seed-data_no-ground-truth"))
    parser.add_argument("--truth-dir", type=Path, default=Path("data/seed-data_with-ground-truth"))
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--max-domain-count", type=int, default=10)
    parser.add_argument("--benign-sample", type=int, default=100)
    parser.add_argument("--random-seed", type=int, default=6262)
    args = parser.parse_args()
    try:
        run_experiment(args.output_dir, args.data_dir, args.truth_dir, args.labels,
                       args.max_domain_count, args.benign_sample, args.random_seed)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Source snapshot and verified run manifest saved to {args.output_dir}")


if __name__ == "__main__":
    main()
