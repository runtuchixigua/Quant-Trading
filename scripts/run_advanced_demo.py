"""运行第 24 周配置驱动的离线毕业流水线。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from ashare_quant.config import load_config
from ashare_quant.pipeline import run_advanced_pipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/advanced_research.yaml"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="必须是尚不存在的目录；省略时自动创建带时间戳的实验目录",
    )
    args = parser.parse_args()
    output = args.output or Path("artifacts") / (
        "advanced_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    manifest = run_advanced_pipeline(load_config(args.config), output)
    print(json.dumps({"output": str(output), **manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
