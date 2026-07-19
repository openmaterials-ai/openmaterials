"""Errors shared across omdc."""


class MissingExtraError(ImportError):
    """A requested distance or encoder needs an optional dependency.

    Never a silent fallback: the caller asked for a specific distance, and
    substituting a weaker one would poison stored results."""

    def __init__(self, feature: str, extra: str):
        self.extra = extra
        super().__init__(
            f"{feature} needs the '{extra}' extra: pip install 'openmaterials-ai[distance,{extra}]'. "
            "The always-available channels are 'comp' and 'exact'; "
            "no silent fallback is performed."
        )
