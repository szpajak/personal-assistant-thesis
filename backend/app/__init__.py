"""Backend application package."""

from __future__ import annotations

import warnings

# Silence langgraph's pending-deprecation warning about the JsonPlusSerializer
# `allowed_objects` default. This runs on package import, before any submodule
# (and therefore langgraph) is imported.
warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects` will change.*",
)
