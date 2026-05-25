# -*- coding: utf-8 -*-
"""
Logistics Module for SmartMandi DSS.
Calculates geospatial distances and transport costs to determine the best net price.
"""

import math
from typing import Dict, List, Tuple, Union

# We can later move this to a database or a config JSON
MANDI_DB = {
    'Pune': {'lat': 18.4900, 'lon': 73.8600},
    'Baramati': {'lat': 18.1500, 'lon': 74.5800},
    'Shirur': {'lat': 18.8200, 'lon': 74.3700},
    'Khed': {'lat': 18.7500, 'lon': 73.8500},
    'Junnar': {'lat': 19.2000, 'lon': 73.8700},
    'Indapur': {'lat': 18.1114, 'lon': 74.3839},
    'Manchar': {'lat': 19.0044, 'lon': 74.4784},
    'Nira': {'lat': 18.0997, 'lon': 74.1222}
}

TRANSPORT_RATE_PER_KM_QUINTAL = 4.00  # ₹ per km per quintal


def canonical_mandi_name(raw_name: str) -> str | None:
    """Normalize raw mandi labels from the data source to our known MANDI_DB keys."""
    if not raw_name:
        return None
    lookup = raw_name.lower()
    if 'pune' in lookup:
        return 'Pune'
    if 'baramati' in lookup:
        return 'Baramati'
    if 'shirur' in lookup:
        return 'Shirur'
    if 'khed' in lookup:
        return 'Khed'
    if 'junnar' in lookup:
        return 'Junnar'
    return None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two points on Earth.
    
    Args:
        lat1, lon1: Coordinates of the first point (Farmer).
        lat2, lon2: Coordinates of the second point (Mandi).
        
    Returns:
        Distance in kilometers (float).
    """
    R = 6371.0  # Earth radius in kilometers
    
    # Convert degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def calculate_net_prices(
    farmer_location: Tuple[float, float], 
    mandi_forecasts: Dict[str, Union[float, Dict[str, float]]]
) -> List[Dict[str, float]]:
    """
    Evaluates net profitability for all provided mandi forecasts.
    
    Args:
        farmer_location: Tuple of (latitude, longitude).
        mandi_forecasts: Dictionary mapping mandi names to either a gross price
                         or a quantile forecast dictionary.
                         e.g., {'Pune': 2500.0} or {'Pune': {'p10': 2100.5, 'p50': 2500.0, 'p90': 2950.0}}
                         
    Returns:
        A list of dictionaries, sorted by highest expected Net Price.
    """
    farmer_lat, farmer_lon = farmer_location
    results = []
    
    for mandi, forecast in mandi_forecasts.items():
        canonical_name = mandi if mandi in MANDI_DB else canonical_mandi_name(mandi)
        if canonical_name not in MANDI_DB:
            # Skip mandis we don't have geospatial data for
            continue

        if isinstance(forecast, dict):
            gross_price = float(forecast.get('p50', 0.0))
            p10 = forecast.get('p10', gross_price)
            p90 = forecast.get('p90', gross_price)
        else:
            gross_price = float(forecast)
            p10 = gross_price
            p90 = gross_price
            
        mandi_lat = MANDI_DB[canonical_name]['lat']
        mandi_lon = MANDI_DB[canonical_name]['lon']
        
        # Calculations
        distance_km = haversine_distance(farmer_lat, farmer_lon, mandi_lat, mandi_lon)
        transport_cost = distance_km * TRANSPORT_RATE_PER_KM_QUINTAL
        net_price = gross_price - transport_cost
        
        results.append({
            'mandi': mandi,
            'mandi_name': mandi,
            'gross_price_p50': round(gross_price, 2),
            'distance_km': round(distance_km, 2),
            'transport_cost': round(transport_cost, 2),
            'net_price': round(net_price, 2),
            'p10': round(float(p10), 2),
            'p90': round(float(p90), 2)
        })
        
    # Sort descending by net_price
    results.sort(key=lambda x: x['net_price'], reverse=True)
    
    return results