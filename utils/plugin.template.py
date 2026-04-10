#!/usr/bin/env python3
# <xbar.title>AI Status — {{DESCRIPTION}}</xbar.title>
# <xbar.desc>{{DESCRIPTION}} usage in the menu bar</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from providers._core import run_provider
run_provider("{{PROVIDER_KEY}}")
