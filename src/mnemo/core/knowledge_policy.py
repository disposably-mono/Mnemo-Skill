"""Shared policy constants for knowledge-structure classification."""

from __future__ import annotations

KNOWLEDGE_KIND_CUES = {
    "example": ("example", "for example", "for instance", "such as"),
    "exception": ("except", "exception", "unless", "however", "but not", "only when"),
    "application": ("calculate", "compute", "solve", "apply", "given that", "scenario"),
    "derivation": ("derive", "derivation", "prove", "proof"),
    "argument": ("claim", "evidence", "premise", "conclusion", "argue", "argues", "therefore", "objection"),
    "procedure": ("step", "steps", "procedure", "instructions", "how to"),
    "ordered-process": ("first", "second", "third", "finally", "stage", "phase"),
    "narrative": ("before", "after", "then", "eventually", "turning point", "protagonist"),
    "comparison": ("versus", "compared with", "differ from", "differs from", "whereas", "unlike", "similar"),
    "mechanism": ("because", "cause", "causes", "result in", "results in", "lead to", "leads to", "thereby", "through which"),
    "taxonomy": ("include", "includes", "contain", "contains", "consists of", "type of", "types of", "categories of"),
    "definition": ("is defined as", "means", "refers to", "what is", "define"),
    "relation": ("is", "are", "has", "have", "use", "uses", "produce", "produces", "require", "requires", "prevent", "prevents", "allow", "allows"),
    "formula": ("formula", "equation", "equal", "equals", "ratio", "rate", "percentage"),
}
