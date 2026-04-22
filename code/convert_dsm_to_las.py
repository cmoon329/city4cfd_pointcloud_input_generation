import numpy as np
import rasterio
import laspy
import pyproj
from tqdm import tqdm


def tif_to_las(tif_path, las_path, subsample=1, compress=True):
    """
    Convert a GeoTIFF file to LAS/LAZ point cloud format with CRS preserved.
    
    Parameters:
    -----------
    tif_path : str
        Path to input .tif file
    las_path : str
        Path to output .las/.laz file
    subsample : int
        Subsample factor (1 = all pixels, 2 = every 2nd pixel, etc.)
    compress : bool
        Save as compressed LAZ format
    """
    
    write_and_add_crs = False
    
    # Read the GeoTIFF file
    print(f"Reading: {tif_path}")
    with rasterio.open(tif_path) as src:
        # Read elevation data
        elevation = src.read(1)
        
        # Get metadata
        transform = src.transform
        crs = src.crs
        nodata = src.nodata
        
        print(f"  CRS: {crs}")
        print(f"  Dimensions: {src.width} x {src.height}")
        print(f"  Resolution: {src.res[0]}m x {src.res[1]}m")
        print(f"  Bounds: {src.bounds}")
        print(f"  NoData value: {nodata}")
        
        # Get dimensions
        rows, cols = elevation.shape
        
        # Calculate total points before filtering
        total_pixels = (rows // subsample) * (cols // subsample)
        print(f"\nGenerating coordinates for {total_pixels:,} pixels...")
        
        # Create coordinate arrays with subsampling
        row_indices, col_indices = np.meshgrid(
            np.arange(0, rows, subsample),
            np.arange(0, cols, subsample),
            indexing='ij'
        )
        
        # Convert pixel coordinates to geographic coordinates
        print("Converting to geographic coordinates...")
        xs, ys = rasterio.transform.xy(
            transform, 
            row_indices.flatten(), 
            col_indices.flatten()
        )
        
        # Get elevation values
        zs = elevation[::subsample, ::subsample].flatten()
        
        # Filter out nodata values
        print("Filtering nodata values...")
        xs = np.array(xs)
        ys = np.array(ys)
        
        if nodata is not None:
            # Use approximate comparison for float nodata values
            valid = ~np.isclose(zs, nodata, rtol=1e-5)
            xs = xs[valid]
            ys = ys[valid]
            zs = zs[valid]
            print(f"  Removed {total_pixels - len(xs):,} nodata points")
        
        print(f"  Valid points: {len(xs):,}")
        
        if len(xs) == 0:
            print("\nERROR: No valid points found!")
            return
        
        print(f"\nData range:")
        print(f"  X: [{xs.min():.2f}, {xs.max():.2f}]")
        print(f"  Y: [{ys.min():.2f}, {ys.max():.2f}]")
        print(f"  Z: [{zs.min():.2f}, {zs.max():.2f}]")
    
    # Determine output format
    if compress or las_path.endswith('.laz'):
        if not las_path.endswith('.laz'):
            las_path = las_path.replace('.las', '.laz')
        print(f"\nCreating compressed LAZ file: {las_path}")
    else:
        print(f"\nCreating LAS file: {las_path}")
    
    # Create LAS file with progress bar
    print("Writing point cloud...")
    
    # Create header
    header = laspy.LasHeader(point_format=3, version="1.4")
    header.offsets = [np.min(xs), np.min(ys), np.min(zs)]
    header.scales = [0.01, 0.01, 0.01]  # 1cm precision
    
    # Create LAS data
    las = laspy.LasData(header)
    
    # Set coordinates
    las.x = xs
    las.y = ys
    las.z = zs
    
    # Add CRS information to the LAS file
    if crs:
        try:
            # Get EPSG code if available
            epsg = crs.to_epsg()
            if epsg:
                print(f"  Adding CRS: EPSG:{epsg}")
                crs_obj = pyproj.CRS.from_epsg(epsg)
            else:
                print(f"  Adding CRS: {crs}")
                crs_obj = pyproj.CRS.from_wkt(crs.to_wkt())
            
            # Try different methods to add CRS based on laspy version
            try:
                # Method 1: Using add_crs (newer laspy)
                las.add_crs(crs_obj)
                print("  ✓ CRS added to LAS header (method 1)")
            except AttributeError:
                try:
                    # Method 2: Using VLR directly
                    from laspy.vlrs.known import WktCoordinateSystemVlr
                    vlr = WktCoordinateSystemVlr(crs_obj.to_wkt())
                    las.vlrs.append(vlr)
                    print("  ✓ CRS added to LAS header (method 2)")
                except Exception as e2:
                    # Method 3: Write file first, then add CRS with las2las
                    print(f"  ⚠ Could not add CRS directly: {e2}")
                    print(f"  → Will add CRS using las2las after writing...")
                    write_and_add_crs = True
            
        except Exception as e:
            print(f"  ⚠ Warning: Error adding CRS: {e}")
            write_and_add_crs = True
    else:
        write_and_add_crs = False
    
    # Write to file with progress
    with tqdm(total=1, desc="  Writing file") as pbar:
        las.write(las_path)
        pbar.update(1)
    
    # If CRS couldn't be added directly, use las2las
    if crs and write_and_add_crs:
        try:
            import subprocess
            epsg = crs.to_epsg()
            if epsg:
                print(f"\n  Adding CRS using las2las...")
                temp_path = las_path + ".temp"
                subprocess.run([
                    "las2las64", "-i", las_path, "-o", temp_path, 
                    "-epsg", str(epsg)
                ], check=True, capture_output=True)
                
                # Replace original with CRS-enabled version
                import os
                os.replace(temp_path, las_path)
                print(f"  ✓ CRS EPSG:{epsg} added successfully")
        except Exception as e:
            print(f"  ⚠ Could not add CRS with las2las: {e}")
            print(f"  → You can manually add it later with:")
            print(f"     las2las64 -i {las_path} -o {las_path.replace('.la', '_crs.la')} -epsg {epsg if epsg else 27700}")
    
    print(f"\n✓ Success!")
    print(f"  Output: {las_path}")
    print(f"  Total points: {len(xs):,}")
    print(f"\nTo verify CRS, run:")
    print(f"  lasinfo {las_path} | grep -i 'epsg\\|crs'")
