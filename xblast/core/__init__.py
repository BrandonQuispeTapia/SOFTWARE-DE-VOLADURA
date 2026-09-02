"""Motor de ingenieria de X-BLAST.

Modulos:
    models          Entidades del dominio (taladro, macizo, explosivo, diseno).
    explosives      Catalogo de agentes de voladura, cebos y tacos.
    detonators      Catalogo de detonadores y sus limites de programacion.
    pattern         Generacion de mallas y formulas de dimensionamiento.
    charging        Columna de carga por plataformas y perfiles de energia.
    burden          Burden real, alivio y volumenes de responsabilidad.
    timing          Secuencia de salida, cooperacion y dispersion.
    fragmentation   Kuz-Ram, Cunningham y curva de Swebrec.
    vibration       PPV en campo lejano y cercano, superposicion y normativa.
    airblast        Onda aerea y proyeccion de rocas.
    energy          Campo 3D de distribucion de energia.
    costs           Modelo de costos mina-planta.
    optimizer       Barrido de escenarios y optimizacion economica.
    analysis        Orquestador del analisis completo.
"""

from .analysis import BlastAnalysis, analyze
from .models import (
    BlastDesign, CostParams, Deck, DeckKind, DirectionVector, Explosive, Hole,
    HoleType, InitiationSystem, PatternParams, PatternType, RockMass,
    SiteConstraints, TimingParams,
)

__all__ = [
    "BlastAnalysis", "analyze", "BlastDesign", "CostParams", "Deck", "DeckKind",
    "DirectionVector", "Explosive", "Hole", "HoleType", "InitiationSystem",
    "PatternParams", "PatternType", "RockMass", "SiteConstraints", "TimingParams",
]
