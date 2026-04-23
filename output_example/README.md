#### Used command line for 
- London
  ```
  python main.py --region England --city London --crs EPSG:27700
  ```
- Seoul
  ```
  python main.py --region "South Korea" --city Seoul --crs EPSG:32652 --dtm_dataset NASADEM --api-key _put_your_api_key_ --no-compress
  ```
- Madrid
  ```
  python main.py --region Spain --city Madrid --crs EPSG:25830 --bbox "[-3.7050, 40.4430, -3.6750, 40.4850]" --dtm_dataset COP30 --api-key _put_your_api_key_ --subsample 2
  ```
