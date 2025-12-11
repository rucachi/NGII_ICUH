import os
import argparse
import numpy as np
import rasterio
from rasterio.transform import from_origin
from terrain_analysis import TerrainAnalyzer
from site_evaluation import SiteEvaluator

def create_dummy_dem(path, width=4000, height=4000):
    """Creates a dummy DEM covering South Korea (approx 126-130E, 34-38N)."""
    print("Creating dummy DEM for testing (South Korea extent)...")
    # Extent: 126.0 to 130.0 (4 degrees), 34.0 to 38.0 (4 degrees)
    # Resolution: 0.001 degrees (~100m) -> 4000x4000 pixels
    
    data = np.zeros((height, width), dtype=np.float32)
    
    # Create a simple terrain
    x = np.linspace(-10, 10, width)
    y = np.linspace(-10, 10, height)
    X, Y = np.meshgrid(x, y)
    Z = X**2 + Y**2 # Bowl shape base
    
    # Add some noise/roughness
    Z += np.random.normal(0, 0.5, Z.shape)
    
    # Normalize to realistic elevation (e.g., 0m to 1500m)
    Z = ((Z - Z.min()) / (Z.max() - Z.min())) * 1500
    
    # Origin: West=126.0, North=38.0 (Top-Left)
    # Pixel size: 0.001, 0.001
    transform = from_origin(126.0, 38.0, 0.001, 0.001)
    
    meta = {
        'driver': 'GTiff',
        'height': height,
        'width': width,
        'count': 1,
        'dtype': rasterio.float32,
        'crs': 'EPSG:4326',
        'transform': transform
    }
    
    with rasterio.open(path, 'w', **meta) as dst:
        dst.write(Z, 1)
    return path

def main():
    parser = argparse.ArgumentParser(description="Groundwater Storage Dam Suitability Analysis")
    parser.add_argument("--dem", help="Path to input DEM GeoTIFF", default=None)
    parser.add_argument("--shp", help="Path to Basin SHP", default=r"C:\NGII\SHP\WKMSBSN.shp")
    parser.add_argument("--out", help="Output directory", default=r"C:\NGII\output")
    
    args = parser.parse_args()
    
    # Check inputs
    dem_path = args.dem
    if not dem_path or not os.path.exists(dem_path):
        print("No valid DEM provided. Using dummy DEM.")
        os.makedirs(args.out, exist_ok=True)
        dem_path = os.path.join(args.out, "dummy_dem.tif")
        create_dummy_dem(dem_path)
        
    analyzer = TerrainAnalyzer(dem_path, args.out)
    
    # 1. Load and Clip
    # Note: If using dummy DEM, clipping might fail if SHP doesn't overlap dummy coords.
    # For this run, we'll try-except the clipping or just use the full DEM if clip fails (for testing).
    try:
        dem, transform, meta, clipped_path = analyzer.load_and_clip_dem(args.shp)
        print("DEM Clipped successfully.")
    except Exception as e:
        print(f"Clipping failed (likely no overlap with dummy data): {e}")
        print("Proceeding with full DEM.")
        with rasterio.open(dem_path) as src:
            dem = src.read(1)
            transform = src.transform
            meta = src.meta
            
    # 2. Calculate Indices
    print("Calculating Slope...")
    slope = analyzer.calculate_slope(dem)
    analyzer.save_raster(slope, meta.copy(), "slope.tif")
    
    print("Calculating Curvature...")
    curv = analyzer.calculate_curvature(dem)
    analyzer.save_raster(curv, meta.copy(), "curvature.tif")
    
    print("Calculating Flow Accumulation...")
    flow = analyzer.calculate_flow_accumulation(dem)
    analyzer.save_raster(flow, meta.copy(), "flow_accum.tif")
    
    print("Calculating TWI...")
    twi = analyzer.calculate_twi(slope, flow)
    analyzer.save_raster(twi, meta.copy(), "twi.tif")
    
    # 3. Evaluate Sites
    print("Evaluating Candidates...")
    evaluator = SiteEvaluator(args.out)
    candidates = evaluator.evaluate(slope, curv, twi, flow, transform, meta['crs'])
    
    print(f"Analysis Complete. Found {len(candidates)} candidates.")
    print(f"Results saved to {args.out}")

if __name__ == "__main__":
    main()
