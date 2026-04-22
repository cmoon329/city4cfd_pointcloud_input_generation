import argparse
import os

import get_dsm
import convert_dsm_to_las


def main():
    parser = argparse.ArgumentParser(
        description="Generate DSM (GeoTIFF) and convert to LAS/LAZ point cloud with CRS preserved",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=""" Examples:
                    # If a target city is located in England or the Netherlands & Convert to LAS with full resolution 
                    python main.py --region England --city London --crs EPSG:27700
                    
                    # If a target city is not located in England or the Netherlands & Save as uncompressed LAS
                    python main.py --region "South Korea" --city Seoul --crs EPSG:32652 --dtm_dataset NASADEM --api-key 6f6bbfb0d1507a71b87ebcf1575563cf --no-compress
                    
                    # If a target city is not located in England or the Netherlands & Convert with subsampling (every 2nd pixel)
                    python main.py --region Spain --city Madrid --crs EPSG:25830 --bbox "[-3.7050, 40.4430, -3.6750, 40.4850]" --dtm_dataset COP30 --api-key 6f6bbfb0d1507a71b87ebcf1575563cf --subsample 2
                    """
    )

    # For get_dsm
    parser.add_argument("--region", type=str, required=True, help="Target region name")
    parser.add_argument("--city", type=str, required=True, help="Target city name")
    parser.add_argument("--crs", type=str, required=True, help="Target CRS")

    parser.add_argument("--bbox", type=str,
                        help="[Optional] Area of Interest [West, South, East, North] (e.g., [4.3, 51.9, 4.4, 52.1]")
    parser.add_argument("--dist", type=float, default=1500,
                        help="[Optional] Bounding box distance from center in meters (default: 1500)")
    parser.add_argument("--dtm_dataset", type=str, default="COP30",
                        help="[Optional] OpenTopography global raster dataset name: COP30, NASADEM, etc. (default: COP30)")
    parser.add_argument("--api-key", type=str,
                        help="OpenTopography API Key. Required if a target city is not located in England or the Netherlands")

    # For convert_dsm_to_las
    parser.add_argument("--subsample", type=int, default=1,
                        help="Subsample factor: 1=all pixels, 2=every 2nd, etc. (default: 1)")
    parser.add_argument("--no-compress", action="store_true",
                        help="Save as uncompressed LAS instead of LAZ")

    args = parser.parse_args()

    if args.bbox is not None:
        bbox = args.bbox.strip("()[]").split(",")
        for i in range(len(bbox)):
            bbox[i] = float(bbox[i].strip())
        if len(bbox) != 4:
            print("[ERROR] bbox requires four coordinates (W, S, E, N)!")
            return False
    else:
        bbox = args.bbox

    target_region = args.region.lower()
    target_city = args.city.lower().replace(' ', '_').replace(',', '')

    out_dir = os.getcwd()
    save_dir = os.path.join(out_dir, 'output')
    os.makedirs(save_dir, exist_ok=True)

    if args.no_compress:
        las_save_path = os.path.join(save_dir, f'{target_city}.las')
    else:
        las_save_path = os.path.join(save_dir, f'{target_city}.laz')

    tif_path = get_dsm.create_dsm(save_dir, target_region, target_city, args.dist, bbox, args.crs, args.api_key, args.dtm_dataset)
    convert_dsm_to_las.tif_to_las(tif_path, las_save_path, args.subsample, args.no_compress)


if __name__ == "__main__":
    main()
