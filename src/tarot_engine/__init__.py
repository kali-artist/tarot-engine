"""tarot_engine: honest-divination engine. Five layers: data -> deck -> spread -> assembler -> resonance -> synthesizer."""
__version__ = "0.1.0"

from .loader import load_cards, load_spreads, load_traditions
from .deck import DeckEngine, DrawnCard, Orientation
from .spread import SpreadRegistry
from .assembler import Assembler, AssembledContext
from .resonance import ResonanceLayer, QuerentSignature, ResonanceMark

__all__ = [
    "load_cards", "load_spreads", "load_traditions",
    "DeckEngine", "DrawnCard", "Orientation",
    "SpreadRegistry", "Assembler", "AssembledContext",
    "ResonanceLayer", "QuerentSignature", "ResonanceMark",
]
