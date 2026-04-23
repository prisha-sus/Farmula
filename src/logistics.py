"""
Logistics Module for SmartMandi DSS.
Calculates geospatial distances and transport costs to determine the best net price.
"""

import math
from typing import Dict, List, Tuple

# We can later move this to a database or a config JSON
MANDI_DB = {
    'Pune': {'lat': 18.4900, 'lon': 73.8600},
    'Baramati': {'lat': 18.1500, 'lon': 74.5800},
    'Shirur': {'lat': 18.8200, 'lon': 74.3700},
    'Khed': {'lat': 18.7500, 'lon': 73.8500},
    'Junnar': {'lat': 19.2000, 'lon': 73.8700}
}

TRANSPORT_RATE_PER_KM_QUINTAL = 4.00  # ₹ per km per quintal


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
    mandi_forecasts: Dict[str, float]
) -> List[Dict[str, float]]:
    """
    Evaluates net profitability for all provided mandi forecasts.
    
    Args:
        farmer_location: Tuple of (latitude, longitude).
        mandi_forecasts: Dictionary mapping mandi names to expected gross prices.
                         e.g., {'Pune': 2500.0, 'Baramati': 2600.0}
                         
    Returns:
        A list of dictionaries, sorted by highest expected Net Price.
    """
    farmer_lat, farmer_lon = farmer_location
    results = []
    
    for mandi, gross_price in mandi_forecasts.items():
        if mandi not in MANDI_DB:
            # Skip mandis we don't have geospatial data for
            continue
            
        mandi_lat = MANDI_DB[mandi]['lat']
        mandi_lon = MANDI_DB[mandi]['lon']
        
        # Calculations
        distance_km = haversine_distance(farmer_lat, farmer_lon, mandi_lat, mandi_lon)
        transport_cost = distance_km * TRANSPORT_RATE_PER_KM_QUINTAL
        net_price = gross_price - transport_cost
        
        results.append({
            'mandi': mandi,
            'gross_price': round(gross_price, 2),
            'distance_km': round(distance_km, 2),
            'transport_cost': round(transport_cost, 2),
            'net_price': round(net_price, 2)
        })
        
    # Sort descending by net_price
    results.sort(key=lambda x: x['net_price'], reverse=True)
    
    return results