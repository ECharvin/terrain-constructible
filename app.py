from flask import Flask, request, jsonify
import requests
import geopandas as gpd
from shapely.geometry import shape

app = Flask(__name__)

# -------------------------------------------------------------------
# Récupération des zones urbanisme
# -------------------------------------------------------------------
def get_constructible_zones(geom):
    # bbox pour limiter les appels API
    minx, miny, maxx, maxy = geom.bounds

    url = "https://www.geoportail-urbanisme.gouv.fr/api/geometries"
    params = {
        "output": "geojson",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "type": "zone_urba",
    }

    r = requests.get(url, params=params)
    r.raise_for_status()

    zones = gpd.GeoDataFrame.from_features(r.json()["features"], crs="EPSG:4326")

    # zones constructibles = commençant par U ou AU
    return zones[zones["libelle_zone"].str.startswith(("U", "AU"), na=False)]

# -------------------------------------------------------------------
# Parcelles cadastrales
# -------------------------------------------------------------------
def get_parcels(geom):
    minx, miny, maxx, maxy = geom.bounds
    url = "https://apicarto.ign.fr/api/cadastre/parcelle"

    params = {
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "format": "geojson"
    }

    r = requests.get(url, params=params)
    r.raise_for_status()
    return gpd.GeoDataFrame.from_features(r.json()["features"], crs="EPSG:4326")

# -------------------------------------------------------------------
# Bâtiments
# -------------------------------------------------------------------
def get_buildings(geom):
    minx, miny, maxx, maxy = geom.bounds
    url = "https://apicarto.ign.fr/api/cadastre/bati"

    params = {
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "format": "geojson"
    }

    r = requests.get(url, params=params)
    r.raise_for_status()
    return gpd.GeoDataFrame.from_features(r.json()["features"], crs="EPSG:4326")

# -------------------------------------------------------------------
# Route API
# -------------------------------------------------------------------
@app.route("/process_polygon", methods=["POST"])
def process_polygon():
    data = request.get_json()
    geom = shape(data["geometry"])

    # 1. Récupérer zones U/AU
    zones = get_constructible_zones(geom)

    # 2. Parcelles
    parcels = get_parcels(geom)

    # 3. Bâtiments
    buildings = get_buildings(geom)

    # Intersection parcelles / zones constructibles
    parcels_in_zone = gpd.overlay(parcels, zones, how="intersection")

    # Jointure spatiale avec les bâtiments
    parcels_with_buildings = gpd.sjoin(parcels_in_zone, buildings, how="left", predicate="intersects")

    # Garder celles sans bâtiment
    empty_parcels = parcels_with_buildings[parcels_with_buildings["index_right"].isna()]

    return jsonify({
        "count": len(empty_parcels),
        "parcels": empty_parcels.to_json()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
