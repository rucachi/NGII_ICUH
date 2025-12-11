import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import rasterio
import os

class SiteEvaluator:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        
    def evaluate(self, slope, curvature, twi, flow_acc, transform, crs):
        """
        Evaluates each cell and assigns a suitability score.
        Returns a GeoDataFrame of candidate sites.
        """
        rows, cols = slope.shape
        
        # Normalize inputs or define thresholds
        # Criteria (Example):
        # 1. Slope: 0-15 degrees is best.
        # 2. Curvature: Negative (Concave) is better for water collection.
        # 3. TWI: Higher is better (wetter).
        # 4. FlowAccum: Higher is better (more catchment).
        
        # Score initialization
        score_grid = np.zeros_like(slope)
        
        # 1. Slope Score (0-100)
        # Linear decay from 0 to 20 degrees. >20 is 0.
        slope_score = np.maximum(0, 100 - (slope * 5))
        slope_score[slope > 20] = 0
        
        # 2. Curvature Score
        # Concave (<0) gets points. Convex (>0) gets 0.
        curv_score = np.zeros_like(curvature)
        curv_score[curvature < 0] = np.minimum(100, np.abs(curvature[curvature < 0]) * 50)
        
        # 3. TWI Score
        # Normalize TWI to 0-100 range based on min/max in the grid
        twi_min, twi_max = np.nanmin(twi), np.nanmax(twi)
        if twi_max > twi_min:
            twi_score = (twi - twi_min) / (twi_max - twi_min) * 100
        else:
            twi_score = np.zeros_like(twi)
            
        # 4. Flow Accumulation Score
        # Log scale usually better for FlowAccum
        log_flow = np.log1p(flow_acc)
        lf_min, lf_max = np.nanmin(log_flow), np.nanmax(log_flow)
        if lf_max > lf_min:
            flow_score = (log_flow - lf_min) / (lf_max - lf_min) * 100
        else:
            flow_score = np.zeros_like(flow_acc)
            
        # Weighted Sum
        # Weights: Slope(0.3), Curvature(0.2), TWI(0.3), Flow(0.2)
        total_score = (0.3 * slope_score + 
                       0.2 * curv_score + 
                       0.3 * twi_score + 
                       0.2 * flow_score)
                       
        # Threshold for candidates
        threshold = 70 # Top 30% roughly, or absolute score
        candidates_mask = total_score >= threshold
        
        # Extract points
        candidates = []
        y_idxs, x_idxs = np.where(candidates_mask)
        
        for y, x in zip(y_idxs, x_idxs):
            # Convert array indices to map coordinates
            # rasterio transform: (x, y) = transform * (col, row)
            # Note: transform expects (col, row) -> (x, y)
            xs, ys = rasterio.transform.xy(transform, y, x, offset='center')
            
            # Generate Reason
            reasons = []
            if slope[y, x] < 5:
                reasons.append(f"매우 완만한 경사({slope[y, x]:.1f}도)")
            elif slope[y, x] < 15:
                reasons.append(f"적절한 경사({slope[y, x]:.1f}도)")
                
            if twi[y, x] > 10:
                reasons.append(f"높은 지형습윤지수({twi[y, x]:.1f})로 수자원 풍부")
            elif twi[y, x] > 5:
                reasons.append(f"양호한 지형습윤지수({twi[y, x]:.1f})")
                
            if curvature[y, x] < -0.1:
                reasons.append("오목한 지형으로 집수 유리")
                
            reason_str = ", ".join(reasons) if reasons else "종합 점수 우수"
            
            candidates.append({
                'geometry': Point(xs, ys),
                'score': float(total_score[y, x]),
                'slope': float(slope[y, x]),
                'curvature': float(curvature[y, x]),
                'twi': float(twi[y, x]),
                'flow_acc': float(flow_acc[y, x]),
                'reason': reason_str
            })
            
        if not candidates:
            print("No candidates found above threshold.")
            return gpd.GeoDataFrame()
            
        gdf = gpd.GeoDataFrame(candidates, crs=crs)
        
        # Sort by score
        gdf = gdf.sort_values('score', ascending=False).reset_index(drop=True)
        
        # Save results
        output_path = os.path.join(self.output_dir, "candidates.geojson")
        gdf.to_file(output_path, driver="GeoJSON")
        
        csv_path = os.path.join(self.output_dir, "candidates.csv")
        gdf.drop(columns='geometry').to_csv(csv_path, index=False)
        
        return gdf
