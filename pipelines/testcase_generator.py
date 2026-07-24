import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.config import load_environment
from agents.testcase_agent import create_testcase_agent

load_environment()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 1:
        print("Usage: python pipelines/testcase_generator.py <ssm-folder> [output-dir]")
        return 2

    ssm_folder = Path(args[0])
    out = args[1] if len(args) > 1 else "artifacts/manual_testcases"
    clean = "--clean" in args

    if not ssm_folder.exists() or not ssm_folder.is_dir():
        print(f"Input path must be an existing folder: {ssm_folder}")
        return 2

    supported = {"json"}
    ssm_files = sorted([p for p in ssm_folder.iterdir() if p.suffix.lower().lstrip(".") in supported])
    if not ssm_files:
        print(f"No SSM JSON files found in {ssm_folder}")
        return 2

    print(f"Found {len(ssm_files)} SSM files. Generating manual test cases...")
    out_dir_path = Path(out)
    if clean and out_dir_path.exists():
        shutil.rmtree(out_dir_path)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    provider = os.getenv("TESTCASE_AGENT_PROVIDER") or ("openai" if os.getenv("OPENAI_API_KEY") else "mock")
    prompt_path = Path("prompts/test_generation.txt")
    prompt_template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else None
    agent = create_testcase_agent(provider=provider, prompt_template=prompt_template)

    for ssm_file in ssm_files:
        try:
            with open(ssm_file, "r", encoding="utf-8") as f:
                ssm_data = json.load(f)

            result_text = agent.generate_from_ssm(ssm_data, source_ssm=str(ssm_file), filename=ssm_file.stem)
            timestamp = int(time.time())
            out_path = out_dir_path / f"manual_testcases_{ssm_file.stem}_{timestamp}.txt"
            out_path.write_text(result_text, encoding="utf-8")
            print(f"Wrote manual test cases to {out_path}")
        except Exception as exc:
            print(f"FAILED {ssm_file}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
