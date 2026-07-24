import os
import sys
import json
import time
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.config import load_environment
from agents.vision_agent import create_vision_agent
from models.ssm import ScreenSemanticModel

load_environment()


def run(image_path: str, out_dir: str = "artifacts/ssm_json_output", clean: bool = False) -> Path:
    provider = os.getenv("VISION_AGENT_PROVIDER", "mock")

    prompt_path = Path("prompts/vision_analysis.txt")
    prompt_template = (
        prompt_path.read_text(encoding="utf-8")
        if prompt_path.exists()
        else None
)
    agent = create_vision_agent(
    provider=provider,
    prompt_template=prompt_template,
)
    print("VISION_AGENT_PROVIDER =", provider)
    print("Agent =", type(agent).__name__)

    raw = agent.analyze_image(image_path)

    ssm = ScreenSemanticModel.model_validate(raw)

    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    name = ssm.screen_name or Path(image_path).stem
    out_path = out_dir_path / f"ssm_{name}_{timestamp}.json"
    out_path.write_text(ssm.model_dump_json(indent=2))
    return out_path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 1:
        print("Usage: python pipelines/ssm_generator.py <image-folder> [output-dir]")
        return 2

    image_folder = Path(args[0])
    out = args[1] if len(args) > 1 else "artifacts/ssm_json_output"
    clean = "--clean" in args

    if not image_folder.exists() or not image_folder.is_dir():
        print(f"Input path must be an existing folder: {image_folder}")
        return 2

    supported = {"png", "jpg", "jpeg", "webp", "bmp"}
    screenshots = sorted([p for p in image_folder.iterdir() if p.suffix.lower().lstrip(".") in supported])
    if not screenshots:
        print(f"No supported screenshots found in {image_folder}")
        return 2

    if clean and Path(out).exists():
        shutil.rmtree(Path(out))

    print(f"Found {len(screenshots)} screenshots. Processing...")
    for image in screenshots:
        try:
            path = run(str(image), out, clean=False)
            print(f"Wrote SSM JSON to {path}")
        except Exception as exc:
            print(f"FAILED {image}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
