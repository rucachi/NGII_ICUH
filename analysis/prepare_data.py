import geopandas as gpd
import os

def convert_shp_to_geojson(shp_path, output_path):
    print(f"Reading SHP: {shp_path}")
    try:
        gdf = gpd.read_file(shp_path)
        # Convert to EPSG:4326 for web mapping (OpenLayers loves 4326 or 3857)
        if gdf.crs != "EPSG:4326":
            print("Reprojecting to EPSG:4326...")
            gdf = gdf.to_crs("EPSG:4326")
            
        print(f"Saving to GeoJSON: {output_path}")
        gdf.to_file(output_path, driver="GeoJSON")
        print("Conversion complete.")
    except Exception as e:
        print(f"Error converting SHP: {e}")

if __name__ == "__main__":
    # Adjust paths as needed
    shp_path = r"C:\NGII\SHP\WKMSBSN.shp"
    output_path = r"C:\NGII\web\static\WKMSBSN.geojson"
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    convert_shp_to_geojson(shp_path, output_path)
