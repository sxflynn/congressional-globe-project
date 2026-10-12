"""Access the packaged, provisional controlled subject vocabulary."""

import json
from importlib.resources import files

from congressional_globe.subjects import SubjectVocabulary


def load_draft_vocabulary() -> SubjectVocabulary:
    """Load and validate the packaged draft; cues remain candidates, not assignments."""
    resource = files("congressional_globe").joinpath("data/subject_vocabulary_draft.json")
    return SubjectVocabulary.model_validate(json.loads(resource.read_text(encoding="utf-8")))
