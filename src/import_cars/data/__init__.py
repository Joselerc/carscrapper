"""
Data mappings for car makes, models, fuel types, transmissions, etc.
"""
from .coches_net_makes import COCHES_NET_MAKES
from .mobile_de_makes import MOBILE_DE_MAKES
from .fuel_mappings import COCHES_NET_FUEL_TYPES, MOBILE_DE_FUEL_TYPES
from .transmission_mappings import COCHES_NET_TRANSMISSION_TYPES, MOBILE_DE_TRANSMISSION_TYPES

__all__ = [
    "COCHES_NET_MAKES",
    "MOBILE_DE_MAKES",
    "COCHES_NET_FUEL_TYPES",
    "MOBILE_DE_FUEL_TYPES",
    "COCHES_NET_TRANSMISSION_TYPES",
    "MOBILE_DE_TRANSMISSION_TYPES",
]

