import requests
import os
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from pyproj import CRS
import numpy as np


def download_dtm(save_path, bbox, api_key, dem_dataset):
    bbox_s = bbox[1] - 0.005
    bbox_n = bbox[3] + 0.005
    bbox_w = bbox[0] - 0.005
    bbox_e = bbox[2] + 0.005

    url = f"https://portal.opentopography.org/API/globaldem?demtype={dem_dataset}&south={bbox_s}&north={bbox_n}&west={bbox_w}&east={bbox_e}&outputFormat=GTiff&API_Key={api_key}"

    print("Downloading DTM from Open Topography...")
    response = requests.get(url)

    if response.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(response.content)
        print(f"Successfully saved DTM! Check: {save_path}")
        return save_path
    else:
        print(f"\n[ERROR] Request failed with status code: {response.status_code}")
        return False


def reproject_to_utm(save_path, target_crs):
    try:
        dst_crs = CRS.from_user_input(target_crs)
    except Exception:
        print(f"[ERROR] {target_crs} not a valid CRS")
        print(f"        Example: 'EPSG:28992")
        return False

    with rasterio.open(save_path) as src:
        if src.crs == dst_crs:
            print("[INFO] No reprojection made")
        else:
            print(f"Reprojecting DTM from {src.crs.to_string()} to {dst_crs.to_string()}")

            # 1. Update metadata
            if src.nodata is not None and src.nodata != 0:
                dst_nodata = src.nodata
            else:
                dst_nodata = -9999.0

            # Set resolution to 1m*1m
            dst_res = (1.0, 1.0)
            transform, width, height = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=dst_res)

            kwargs = src.meta.copy()
            kwargs.update({
                "crs": dst_crs,
                "transform": transform,
                "width": width,
                "height": height,
                "nodata": dst_nodata
            })

            # 2. Generate an array for the reprojected data
            reprojected_data_arr = []
            for band_idx in range(1, src.count + 1):
                dst_arr = np.empty((height, width), dtype=src.meta['dtype'])
                reproject(
                    source=rasterio.band(src, band_idx),
                    destination=dst_arr,
                    src_crs=src.crs,
                    src_transform=src.transform,
                    dst_crs=dst_crs,
                    src_nodata=src.nodata,
                    dst_nodata=dst_nodata,
                    resampling=Resampling.bilinear,
                )
                reprojected_data_arr.append(dst_arr)

    # 3. Update the file
    with rasterio.open(save_path, "w", **kwargs) as dst:
        for band_idx, band_data in enumerate(reprojected_data_arr, 1):
            dst.write(band_data, band_idx)

    print(f"Successfully saved the reprojected DTM! Check: {save_path}")
    return save_path


def get_dtm(save_dir, target_city, target_crs, api_key, bbox=None, dem_dataset="COP30"):
    save_path = os.path.join(save_dir, f'{target_city}_dtm.tif')

    dtm_path = download_dtm(save_path, bbox, api_key, dem_dataset)

    if dtm_path:
        reprojected_dtm_path = reproject_to_utm(dtm_path, target_crs)
    else:
        print(f"\n[ERROR] Could not download DTM")

    return reprojected_dtm_path
