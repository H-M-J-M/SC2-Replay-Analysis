from typing import Callable, Tuple
import pandas as pd
from sc2.unit import Unit
from sc2.units import Units

def resource_snap(u: Unit) -> bool:
    return u.is_snapshot and ( u.is_mineral_field or u.is_vespene_geyser )

def split_units(units: Units, predicate: Callable[[Unit], bool]) -> Tuple[Units, Units]:
    """Split a Units collection into two based on a boolean filter function.
    
    Returns:
        A tuple of two Units objects: (true_units, false_units).
    """
    true_list = []
    false_list = []

    for u in units:
        true_list.append(u) if predicate(u) else false_list.append(u)


    return (Units(true_list, units._bot_object), Units(false_list, units._bot_object))

def optimize_unit_dtypes(dfI: pd.DataFrame) -> pd.DataFrame:
    """Optimizes unit DataFrame dtypes for smaller file size."""
    type_mapping = {
        'timestamp': 'Float32',
        'unit_tag': 'UInt64',
        'unit_type': 'category',
        'player_id': 'UInt8',
        'position_x': 'Float32',
        'position_y': 'Float32',
        'is_snapshot': 'boolean',
        'health': 'Float32',
        'shield': 'Float32',
        'energy': 'Float32',
        'build_progress': 'Float32',
        'resource_remaining': 'Int16',        
    }

    dfO = dfI.astype(type_mapping)
    
    return dfO

def optimize_death_dtypes(dfI: pd.DataFrame) -> pd.DataFrame:
    
    type_mapping = {
        'timestamp': 'Float32',
        'unit_tag': 'UInt64',
        'unit_type': 'category',
        'player_id': 'UInt8',
        'position_x': 'Float32',
        'position_y': 'Float32',
    }
    dfO = dfI.astype(type_mapping)
    
    return dfO

def optimize_resource_dtypes(dfI: pd.DataFrame) -> pd.DataFrame:
    """Optimizes unit DataFrame dtypes for smaller file size."""
    type_mapping = {
        'timestamp': 'Float32',
        'p1_minerals': 'UInt32',
        'p1_vespene': 'UInt32',
        'p1_supply_cap': 'UInt16',
        'p1_supply_used': 'UInt16',
        'p1_supply_army': 'UInt16',
        'p2_minerals': 'UInt32',
        'p2_vespene': 'UInt32',
        'p2_supply_cap': 'UInt16',
        'p2_supply_used': 'UInt16',
        'p2_supply_army': 'UInt16',
    }
    dfO = dfI.astype(type_mapping)
    
    return dfO

def optimize_upgrade_dtypes(dfI: pd.DataFrame) -> pd.DataFrame:
    """Optimizes upgrade DataFrame dtypes for smaller file size."""
    type_mapping = {
        'time_completed': 'Float32', 
        'upgrade': 'category', 
        'player_id': 'UInt8', 
        'mineral_cost': 'UInt16', 
        'vespene_cost': 'UInt16', 
        'imputed_start': 'Float32'
    }
    dfO = dfI.astype(type_mapping)

    return dfO