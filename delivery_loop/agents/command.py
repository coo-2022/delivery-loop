from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from delivery_loop.config import AgentConfig


@dataclass
class CommandAgent:
    config: AgentConfig

    def run_design(self, repo_dir: Path, prompt: str) -> str:
        command = self.config.command.format(repo_dir=repo_dir)
        result = subprocess.run(
            command.split(),
            input=prompt,
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_dir,
        )
        return result.stdout
