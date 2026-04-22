## Point Cloud for City Generation Code for City4CFD 

### Description
A Python pipeline that generates Digital Surface Model (DSMs) and converts them into point clouds for City4CFD modeling. Due to the lack of open, high-resolution global DSM datasets, the generation logic differs by target city (see the figure below).

<img width="75%" src="https://github.com/user-attachments/assets/21401314-0f1f-4175-9ee3-e6c80134756c" />

### Repository Structure
```
├── code/
│   ├── main.py
│   ├── get_dtm.py
│   ├── get_dsm.py
│   └── convert_dsm_to_las.py
├── output_example/
│   ├── london/
│   ├── seoul/
│   └── madrid/
└── README.md
```

### Prerequisites / Setup
- **OpenTopography API Key**: Required to download DTM datasets (e.g., COP30, NASADEM) for cities outside of England/Netherlands.
- **Libraries**: Install the required dependencies using the following command:
  ```
  pip install earthengine-api geemap geopandas pandas shapely rasterio osmnx overturemaps numpy laspy lazrs pyproj tqdm requests
  ```

### How to Run
1. Download the `/code/` directory
2. Run `main.py` with the necessary arguments
   Examples by case:
    - **[Case 1] For cities in England/Netherlands** (uses Google Earth Engine high-resolution data)
      ```
      python main.py --region England --city London --crs EPSG:27700
      ```
    - **[Case 2] For cities outside of England/Netherlands** (uses OpenTopography for DTM and OSM/Overture Maps for building data)
      - Save as uncompressed LAS
        ``` 
        python main.py --region "South Korea" --city Seoul --crs EPSG:32652 --dtm_dataset NASADEM --api-key _put_your_api_key_ --no-compress
        ```
      - Convert with subsampling (every 2nd pixel)
        ```
        python main.py --region Spain --city Madrid --crs EPSG:25830 --bbox "[-3.7050, 40.4430, -3.6750, 40.4850]" --dtm_dataset COP30 --api-key _put_your_api_key_ --subsample 2
        ```

### Expected Output

| File Name | Description | Resolution |
| :--- | :--- | :--- |
| `[city_name].tif` | Merged DSM | • **England**: 1m × 1m <br> • **Netherlands**: 0.5m × 0.5m <br> • **Others**: 1m × 1m |
| `[city_name]_dtm.tif` | DTM (_Only for non-England/Netherlands cities_) | 1m × 1m |
| `[city_name].las` / `.laz` | Point Cloud | - |


### Reference
- https://github.com/slzhang-git/cenergy/blob/main/src/cenergy3/core.py
