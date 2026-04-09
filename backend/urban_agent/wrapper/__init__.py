"""Lightweight wrappers that forward parameters to the coupled backend."""

from .cfd_solver import CFDParameters, CFDSolverAgent
from .solar_solver import SolarParameters, SolarSolverAgent

__all__ = [
    "CFDSolverAgent",
    "CFDParameters",
    "SolarSolverAgent",
    "SolarParameters",
]

