import json
from matplotlib.path import Path
try:
    import pycountry    
except Exception as e:
    print(f"\n WARNUNG: beim Importieren von pycountry: {e}"
           "\n beachte: Bei neu installiertem LEPMON OS 2.1.5+ muss das Paket 'adafruit-circuitpython-bme280' über den Paket-Installer installiert werden.")
from json_read_write import get_coordinates

def load_features(filename):
    with open(filename, encoding="utf-8") as f:
        return json.load(f)["features"]

COUNTRIES = load_features("/home/Ento/LepmonOS/geo_ref_shapes/ne_110m_admin_0_countries.geojson")
REGIONS = load_features("/home/Ento/LepmonOS/geo_ref_shapes/ne_10m_admin_1_states_provinces.geojson")

def point_in_polygon(point, polygon):
    # polygon: GeoJSON coordinates (list of [lon, lat])
    path = Path(polygon)
    return path.contains_point(point)

def find_country_and_region():
    latitude, longitude, *_ = get_coordinates()
    point = (longitude, latitude)
    country_name = None
    region_name = None

    for feature in COUNTRIES:
        coords = feature["geometry"]["coordinates"]
        # GeoJSON: Polygon or MultiPolygon
        if feature["geometry"]["type"] == "Polygon":
            if point_in_polygon(point, coords[0]):
                iso = feature["properties"]["ISO_A2"]
                country = pycountry.countries.get(alpha_2=iso)
                country_name = country.name if country else iso
                break
        elif feature["geometry"]["type"] == "MultiPolygon":
            for poly in coords:
                if point_in_polygon(point, poly[0]):
                    iso = feature["properties"]["ISO_A2"]
                    country = pycountry.countries.get(alpha_2=iso)
                    country_name = country.name if country else iso
                    break

    for feature in REGIONS:
        coords = feature["geometry"]["coordinates"]
        if feature["geometry"]["type"] == "Polygon":
            if point_in_polygon(point, coords[0]):
                region_name = feature["properties"]["name"]
                break
        elif feature["geometry"]["type"] == "MultiPolygon":
            for poly in coords:
                if point_in_polygon(point, poly[0]):
                    region_name = feature["properties"]["name"]
                    break

    return country_name, region_name

if __name__ == "__main__":
    country, region = find_country_and_region()
    print(f"Land   : {country}")
    print(f"Region : {region}")