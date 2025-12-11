from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os
import rasterio
import numpy as np
from rasterio.transform import rowcol

app = Flask(__name__, template_folder='../web/templates', static_folder='../web/static')
CORS(app)

# Configuration
DEM_PATH = r"C:\NGII\output\dummy_dem.tif" # Default to dummy for now, update if real DEM exists
# In a real scenario, we might want to load the DEM once or handle it more robustly

def get_terrain_value(x, y):
    """
    Query DEM and derived rasters for a specific coordinate (EPSG:4326 or 5179).
    Assuming input x,y are in the same CRS as the raster or need transformation.
    For this demo, we assume the DEM is in EPSG:4326 (as per dummy generator) 
    or we handle re-projection if needed.
    """
    # Check if DEM exists
    if not os.path.exists(DEM_PATH):
        return {"error": "DEM file not found"}

    try:
        with rasterio.open(DEM_PATH) as src:
            # Convert world coords to pixel coords
            # src.index(x, y) works if x,y are in src CRS
            row, col = src.index(x, y)
            
            # Read value
            # Note: This is slow to open/read for every request. 
            # Production: Keep dataset open or use a tile server.
            elev = float(src.read(1)[row, col])
            
            # We could also read slope/twi if they exist in output dir
            # For now just returning elevation as proof of concept
            
        return {
            "elevation": elev,
            "slope": "N/A", # Implement reading slope.tif similarly
            "twi": "N/A"
        }
    except IndexError:
        return {"error": "Coordinate out of bounds"}
    except Exception as e:
        return {"error": str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/query', methods=['GET'])
def query_terrain():
    try:
        x = float(request.args.get('x'))
        y = float(request.args.get('y'))
        # Assuming input is Long/Lat (EPSG:4326)
        
        data = get_terrain_value(x, y)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

from terrain_analysis import TerrainAnalyzer
from site_evaluation import SiteEvaluator
import geopandas as gpd

@app.route('/api/analyze_aoi', methods=['POST'])
def analyze_aoi():
    try:
        # Get GeoJSON from request
        geojson = request.get_json()
        if not geojson:
            return jsonify({"error": "No GeoJSON data provided"}), 400
            
        # Use a temporary output directory for dynamic analysis
        output_dir = r"C:\NGII\output\aoi_analysis"
        os.makedirs(output_dir, exist_ok=True)
        
        analyzer = TerrainAnalyzer(DEM_PATH, output_dir)
        
        # 1. Clip DEM
        dem, transform, meta, clipped_path = analyzer.clip_dem_by_geometry(geojson)
        
        # 2. Calculate Indices
        slope = analyzer.calculate_slope(dem)
        curv = analyzer.calculate_curvature(dem)
        flow = analyzer.calculate_flow_accumulation(dem)
        twi = analyzer.calculate_twi(slope, flow)
        
        # 3. Evaluate
        evaluator = SiteEvaluator(output_dir)
        candidates = evaluator.evaluate(slope, curv, twi, flow, transform, meta['crs'])
        
        if candidates.empty:
             return jsonify({"message": "No suitable sites found in this area.", "candidates": []})
             
        # Convert to GeoJSON
        return candidates.to_json()
        
    except Exception as e:
        print(f"Analysis Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
