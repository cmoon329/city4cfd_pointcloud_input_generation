import ee
import geemap

import geopandas as gpd
import pandas as pd
from shapely import wkb
from rasterio import features
from rasterio import mask
import osmnx as ox
import overturemaps
import rasterio
import numpy as np
import os

import get_dtm


def get_gee_dsm(save_dir, target_region, target_city, bbox):
    # 1. Initialize Google Earth Engine (GEE)
    try:
        ee.Initialize(project='city4cfd')
    except:
        ee.Authenticate()
        ee.Initialize(project='city4cfd')

    # 2. Preprocess save path and AOI
    save_path = os.path.join(save_dir, f'{target_city}.tif')

    bbox_s = float(bbox[1]) - 0.005
    bbox_n = float(bbox[3]) + 0.005
    bbox_w = float(bbox[0]) - 0.005
    bbox_e = float(bbox[2]) + 0.005

    aoi = ee.Geometry.BBox(bbox_w, bbox_s, bbox_e, bbox_n)

    # 3. Get DSM from GEE
    # [Case 1] If a target city is located in England
    print("Loading DSM from Google Earth Engine...")
    if target_region == 'england':
        dsm = ee.Image("UK/EA/ENGLAND_1M_TERRAIN/2022").clip(aoi).select('dsm_first')
        scale = 1
        crs = 'EPSG:32630'
    elif target_region in ['netherlands', 'the netherlands']:
        dsm = ee.ImageCollection("AHN/AHN4").filterBounds(aoi).mosaic().clip(aoi).select('dsm')
        scale = 0.5
        crs = 'EPSG:28992'
    else:
        raise ValueError('To use Google Earth Engine, a target city must be located in either England or the Netherlands')

    # 4. Export DSM
    geemap.ee_export_image(
        dsm,
        filename=save_path,
        scale=scale,
        crs=crs,
        region=aoi,
        file_per_band=False
    )

    print(f"Successfully downloaded DSM! Check: {save_path}")
    return save_path


def get_building_data(bbox, target_crs):
    bbox = tuple(bbox)
    buildings_reprojected = gpd.GeoDataFrame()

    # 1. Get building footprint from osm and save it to GeoDataFrame
    try:
        print(f"Loading building footprints from Open Street Map...")
        tags = {'building': True}
        gdf_buildings_footprints = ox.features_from_bbox(bbox, tags=tags)

        if gdf_buildings_footprints.crs != 'EPSG:4326':
            gdf_buildings_footprints = gdf_buildings_footprints.to_crs('EPSG:4326')  # Convert to WGS84

        print(f"Loading building heights from Overture Maps...")
        types = ['building', 'building_part']
        bbox_buildings = tuple(gdf_buildings_footprints.total_bounds)
        overture_gdf = gpd.GeoDataFrame()

        for type in types:
            table_iter = overturemaps.record_batch_reader(type, bbox=bbox_buildings, release='2026-03-18.0')
            for batch in table_iter:
                batch_df = batch.to_pandas()

                # Convert geometry data to WKB format
                if 'geometry' in batch_df.columns and not batch_df['geometry'].empty:
                    if batch_df['geometry'].apply(lambda x: isinstance(x, bytes)).any():
                        batch_df['geometry'] = batch_df['geometry'].apply(wkb.loads)

                # Save data to GeoDataFrame
                batch_gdf = gpd.GeoDataFrame(batch_df, geometry='geometry', crs='EPSG:4326')
                overture_gdf = pd.concat([overture_gdf, batch_gdf], ignore_index=True)

        overture_gdf = overture_gdf.reset_index(drop=True)

        # Keep only geometry and height data of the buildings
        overture_join_df = overture_gdf[['geometry', 'height']].copy()
        overture_join_df.rename(columns={'height': 'overture_height'}, inplace=True)

        # 2. Join Overture height data to OSM footprint data
        buildings_with_heights = gpd.sjoin(gdf_buildings_footprints, overture_join_df, how='left', predicate='intersects')
        if 'overture_height' not in buildings_with_heights.columns:
            buildings_with_heights['overture_height'] = None
        if 'index_right' in buildings_with_heights.columns:
            buildings_with_heights = buildings_with_heights.drop(columns=['index_right'])

        # 3. Reproject the joined data to the target CRS
        buildings_reprojected = buildings_with_heights.to_crs(target_crs)

        if buildings_reprojected.empty or buildings_reprojected.geometry.name is None:
            print("\n[ERROR] No building data found")
            return False
        else:
            print('Successfully prepared building data!')

    except Exception as e:
        print(f'\n[ERROR] {e}')

    return buildings_reprojected


def inject_building_to_dtm(tif_path, buildings_reprojected, target_city):
    with rasterio.open(tif_path) as src:
        # 1. Read dtm data and metadata
        dtm_elev = src.read(1)
        dtm_transform = src.transform
        dtm_crs = src.crs
        dtm_nodata = src.nodata

        if dtm_nodata is None:
            dtm_nodata = -9999.0
        if dtm_crs != buildings_reprojected.crs:
            buildings_reprojected = buildings_reprojected.to_crs(dtm_crs)

        # 2. Preprocess building data
        print(f"Computing roof heights based on terrain of {target_city}...")
        geom_height_pairs = []
        for geom, height in zip(buildings_reprojected.geometry, buildings_reprojected['overture_height']):
            # Skip if geometry data is empty
            if pd.isna(geom) or geom.is_empty:
                continue

            # Set height to 3.0m if height is missing (assuming a single-story building)
            if pd.isna(height):
                height = 3.0
            else:
                height = float(height)

            # 3. Compute roof heights based on DTM
            try:
                building_footprint, _ = rasterio.mask.mask(src, [geom], crop=True, nodata=dtm_nodata)
                building_footprint_valid_pixels = building_footprint[(building_footprint != dtm_nodata) & (~np.isnan(building_footprint))]

                if building_footprint_valid_pixels.size > 0:
                    base_elev = np.min(building_footprint_valid_pixels)

            except ValueError:
                continue

            roof_height = base_elev + height
            geom_height_pairs.append((geom, roof_height))

        # 4. Create an array for building data
        arr_building = rasterio.features.rasterize(
            shapes=geom_height_pairs,
            out_shape=dtm_elev.shape,
            transform=dtm_transform,
            fill=dtm_nodata,
            default_value=dtm_nodata,
            all_touched=False,  # Only pixels whose center is within the polygon will be burned in
            dtype=dtm_elev.dtype
        )

        # 5. Create an array for DSM
        print(f"Generating a DSM array...")
        arr_dsm = np.where(
            arr_building != dtm_nodata,
            arr_building,
            dtm_elev
        )

    return arr_dsm


def save_dsm(save_dir, target_city, tif_path, arr_dsm):
    save_path = os.path.join(save_dir, f'{target_city}.tif')

    with rasterio.open(tif_path) as src:
        out_metadata = src.meta.copy()

    out_metadata.update({
        'driver': 'GTiff',
        'height': arr_dsm.shape[0],
        'width': arr_dsm.shape[1],
        'dtype': arr_dsm.dtype
    })

    with rasterio.open(save_path, 'w', **out_metadata) as dsm:
        dsm.write(arr_dsm, 1)

    print(f'Successfully saved DSM! Check: {save_path}')

    return save_path


def create_dsm(save_dir, target_region, target_city, dist=None, bbox=None, target_crs=None, api_key=None, dtm_dataset="COP30"):
    # If bbox and dist are empty, set dist to 1,500m and get bbox
    if bbox is None:
        center_coord = ox.geocoder.geocode(target_city)
        if dist is None:
            dist = 1500
            bbox = ox.utils_geo.bbox_from_point(center_coord, dist)  # west, south, east, north
        else:
            bbox = ox.utils_geo.bbox_from_point(center_coord, float(dist))

    # [Case 1] A target city is located either England or the Netherlands
    if target_region in ['england', 'netherlands', 'the netherlands']:
        # Get DSM from Google Earth Engine
        save_path = get_gee_dsm(save_dir, target_region, target_city, bbox)
    # [Case 2] A target city is not located either England or the Netherlands
    else:
        # 1. Get DTM from Open Topography
        tif_path = get_dtm.get_dtm(save_dir, target_city, target_crs, api_key, bbox, dtm_dataset)
        # 2. Get building height & footprint data from OSM & Overture Maps
        gdp_bldg = get_building_data(bbox, target_crs)
        # 3. Create DSM by merging DTM and building data
        arr_dsm = inject_building_to_dtm(tif_path, gdp_bldg, target_city)
        save_path = save_dsm(save_dir, target_city, tif_path, arr_dsm)

    return save_path
