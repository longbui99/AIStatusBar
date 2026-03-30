#!/usr/bin/env python3
# <xbar.title>AI Status — Claude</xbar.title>
# <xbar.desc>Claude (Anthropic) usage in the menu bar</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from providers._core import run_provider
run_provider("anthropic")
