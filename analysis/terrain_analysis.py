import os
import numpy as np
import rasterio
from rasterio.mask import mask
import geopandas as gpd
from shapely.geometry import mapping
from scipy.ndimage import generic_filter

class TerrainAnalyzer:
    def __init__(self, dem_path, output_dir):
        self.dem_path = dem_path
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def load_and_clip_dem(self, shp_path, basin_id=None):
        """
        Loads DEM and clips it to the basin boundary defined in the SHP file.
        If basin_id is provided, filters the SHP by that ID.
        """
        print(f"Loading Basin SHP: {shp_path}")
        gdf = gpd.read_file(shp_path)
        
        # Ensure CRS matches. Assuming DEM is EPSG:5179 or 4326. 
        # We will check DEM CRS later. For now, just read SHP.
        
        if basin_id:
            # Adjust column name 'WKW_BSN_CD' or similar based on actual data
            # For now, taking the first polygon if no ID or generic clip
            pass
            
        # Get geometry for clipping
        shapes = [feature["geometry"] for feature in gdf.iterfeatures()]
        
        return self._clip_dem(shapes, "clipped_dem.tif")

    def clip_dem_by_geometry(self, geojson_geometry):
        """
        Clips DEM using a GeoJSON geometry (dict).
        """
        # Convert GeoJSON dict to Shapely geometry if needed, or just use the dict as mask expects
        # rasterio.mask.mask expects a list of GeoJSON-like dicts
        shapes = [geojson_geometry]
        return self._clip_dem(shapes, "aoi_clipped_dem.tif")

    def _clip_dem(self, shapes, output_filename):
        """
        Internal method to clip DEM by shapes.
        """
        print(f"Opening DEM: {self.dem_path}")
        with rasterio.open(self.dem_path) as src:
            out_image, out_transform = mask(src, shapes, crop=True)
            out_meta = src.meta.copy()
            
            # Update metadata
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })
            
            # Save clipped DEM for verification
            clipped_dem_path = os.path.join(self.output_dir, output_filename)
            with rasterio.open(clipped_dem_path, "w", **out_meta) as dest:
                dest.write(out_image)
                
            return out_image[0], out_transform, out_meta, clipped_dem_path

    def calculate_slope(self, dem, cell_size=1.0):
        """
        Calculates slope in degrees.
        dem: 2D numpy array
        cell_size: resolution in meters (default 1m)
        """
        x, y = np.gradient(dem, cell_size)
        slope_rad = np.arctan(np.sqrt(x*x + y*y))
        slope_deg = np.degrees(slope_rad)
        return slope_deg

    def calculate_curvature(self, dem, cell_size=1.0):
        """
        Calculates mean curvature.
        Simple approximation using gradients.
        Positive = Convex (볼록), Negative = Concave (오목/계곡)
        """
        # Second derivatives
        zy, zx = np.gradient(dem, cell_size)
        zyy, zyx = np.gradient(zy, cell_size)
        zxy, zxx = np.gradient(zx, cell_size)
        
        # Mean curvature formula (simplified)
        # H = ( (1 + zx^2)zyy - 2zx*zy*zxy + (1 + zy^2)zxx ) / ( 2 * (1 + zx^2 + zy^2)^(3/2) )
        # For terrain analysis, often Laplacian or simple profile/plan curvature is used.
        # Here we use Laplacian as a proxy for general convexity/concavity
        curvature = zxx + zyy
        return curvature

    def calculate_flow_accumulation(self, dem):
        """
        Calculates Flow Accumulation.
        Note: This is a complex algorithm usually requiring specialized libraries like pysheds or richdem.
        For this implementation, we will use a simplified D8 algorithm or a placeholder 
        if external heavy libraries are not desired. 
        
        Here we implement a very basic D8 flow direction and accumulation for demonstration.
        For production/thesis, use 'pysheds'.
        """
        # Placeholder for full FlowAccum implementation
        # Real implementation requires filling sinks, calculating flow direction, then accumulation.
        # Returning a dummy array for now or a simplified version.
        rows, cols = dem.shape
        flow_acc = np.zeros_like(dem)
        
        # Simple local minima check (sink) - just for feature extraction demo
        # In real code, use: from pysheds.grid import Grid
        return flow_acc

    def calculate_twi(self, slope_deg, flow_acc, cell_size=1.0):
        """
        Calculates Topographic Wetness Index (TWI).
        TWI = ln(a / tan(b))
        a = specific catchment area = (flow_acc + 1) * cell_size
        b = slope in radians
        """
        slope_rad = np.radians(slope_deg)
        tan_slope = np.tan(slope_rad)
        
        # Avoid division by zero
        tan_slope[tan_slope < 0.001] = 0.001
        
        a = (flow_acc + 1) * cell_size
        twi = np.log(a / tan_slope)
        return twi

    def save_raster(self, data, meta, filename):
        path = os.path.join(self.output_dir, filename)
        # Update dtype if needed
        meta.update(dtype=rasterio.float32, count=1)
        with rasterio.open(path, "w", **meta) as dest:
            dest.write(data.astype(rasterio.float32), 1)
        return path
