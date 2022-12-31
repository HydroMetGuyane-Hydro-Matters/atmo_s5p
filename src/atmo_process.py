#!/usr/bin/env python
# -*- coding: utf-8 -*-

import click
# import json
import logging
import numpy as np
import pandas as pd
import rasterio
import os
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt

logging.basicConfig(level=logging.INFO)

# Fix errors about proj lib
os.environ['PROJ_LIB'] = '/opt/conda/share/proj'

# Extent used in the request to copernicus API
# watersheds='''
# {
# "type": "FeatureCollection",
# "name": "Guyane_watersheds",
# "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
# "features": [
# { "type": "Feature", "properties": { "id": 1 }, "geometry": { "type": "MultiPolygon", "coordinates": [ [ [ [ -54.192218236600425, 6.064250318016612 ], [ -53.372095358519537, 5.998111376235896 ], [ -51.626027295508607, 5.151532921442717 ], [ -51.308560374961168, 4.291726678293397 ], [ -51.520204988659458, 2.638253133775472 ], [ -52.604883633863224, 1.778446890626151 ], [ -54.139307083175851, 1.923952562543729 ], [ -56.20284206673422, 2.386925155008748 ], [ -56.467397833857092, 3.431920435144076 ], [ -55.713413897556919, 3.683248413910801 ], [ -54.192218236600425, 6.064250318016612 ] ] ] ] } }
# ]
# }
# '''

sentinel_config = {
    'uri': 'https://s5phub.copernicus.eu/dhus/',
    'user': 's5pguest',
    'password': 's5pguest',
    'start_date': 'NOW-1DAY/DAY',
    'end_date': 'NOW/DAY',
    'producttype':'L2__AER_AI',
    'platformname':'Sentinel-5',
}

@click.command()
@click.option('--footprint', default='./Guyane_watersheds.geojson', help='path to geojson file defining the footprint to retrieve')
@click.option('--storage_path', default='../data', help='path to store the data')
@click.option('--generate_styled_geotiff', default=True, type=bool, help='Generate a geotiff styled file(3bit data with integrated colormap)')
@click.option('--generate_styled_png', default=True, type=bool, help='Generate a png styled file')
# Options can also be set using env vars, prefixed by ATMO_, e.g. ATMO_STORAGE_PATH
def atmo_5sp(footprint,
             storage_path,
             generate_styled_geotiff,
             generate_styled_png,
             ):

    logging.info(f'Storing data into {storage_path}')
    # Generate subfolders for storage if necessary. Need to use bash for this syntax
    os.system(f'/bin/bash -c "mkdir -p {storage_path}/{{nc,raw,styled,tmp}}"')

    api = SentinelAPI(sentinel_config['user'], sentinel_config['password'], sentinel_config['uri'])
    # footprint = geojson_to_wkt(json.loads(watersheds))
    footprint = geojson_to_wkt(read_geojson(footprint))
    products = api.query(footprint,
                         date=(sentinel_config['start_date'], sentinel_config['end_date']),
                         producttype=sentinel_config['producttype'],
                         platformname=sentinel_config['platformname'])
    downloaded_products = api.download_all(products, directory_path=f'{storage_path}/nc')
    products_date = list(products.items())[0][1]['endposition']

    # list_files = glob.glob('./tmp/*.nc')
    # print(list_files)
    # for filename in list_files:
    for file in downloaded_products[0].values():
        filename = file["path"]
        logging.debug(f'Processing file {filename}')
        # Convert the original netcdf files to more "raster-like" files using HARP tool
        cmd = f"harpconvert -a 'keep(latitude_bounds,longitude_bounds,absorbing_aerosol_index);bin_spatial(241,1,0.025,281,-57,0.025);squash(time, (latitude_bounds,longitude_bounds));derive(latitude {{latitude}});derive(longitude {{longitude}});exclude(latitude_bounds,longitude_bounds,count,weight)' {filename} {storage_path}/tmp/{os.path.splitext(os.path.basename(filename))[0]}_converted.nc"
        logging.debug(f'Running shell command `{cmd}`')
        os.system(cmd)

    # Merge the netcdf files
    # Following line does not work, might be possible to fix
    # os.system("harpconvert -a 'keep(latitude_bounds,longitude_bounds,absorbing_aerosol_index);bin_spatial(241,1,0.025,281,-57,0.025);squash(time, (latitude_bounds,longitude_bounds));derive(latitude {latitude});derive(longitude {longitude});exclude(latitude_bounds,longitude_bounds,count,weight)'
    merged_aai_filename = f'{storage_path}/raw/{products_date.strftime("%Y%m%d")}_merged_aai.tif'
    logging.info(f'Merging data into geotiff file {merged_aai_filename}')
    os.system(f'gdal_merge.py -o {merged_aai_filename}  {storage_path}/tmp/*_converted.nc')

    logging.info(f'Converting raw Float32 values into categories of atmospheric alerts')
    with rasterio.open(f'{storage_path}/raw/{products_date.strftime("%Y%m%d")}_merged_aai.tif') as input:
        band1 = input.read(1)

        # Flatten to feed 1-dim data into pd.cut
        b = band1.ravel()
        ai_c = pd.cut(
            x=b,
            bins=[-np.inf, 0.4, 0.6, 0.9, 1.2, 1.5, np.inf],
            labels=["good", "feeble", "medium", "high", "vhigh", "critical"],
        )

        # Unflatten to get back our 2D array
        classified_data = np.reshape(ai_c.codes, (input.height, input.width))
        with rasterio.open(
            f'{storage_path}/tmp/atmo_categories.tif',
            'w',
            driver='GTiff',
            height=classified_data.shape[0],
            width=classified_data.shape[1],
            count=1,
            dtype=np.int8,
            crs='+proj=latlong',
            transform=input.transform,
        ) as dst:
            dst.write(classified_data, 1)

    logging.info(f'Optimizing and styling the data:')
    styled_aai_filename = f'{storage_path}/styled/{products_date.strftime("%Y%m%d")}_aai'
    if generate_styled_geotiff:
        logging.info(f'    Generating geotiff 3bit data with integrated colormap: {styled_aai_filename}.tif')
        # os.system('gdal_translate -co COMPRESS=LZW -co NBITS=3 -co ALPHA=YES atmo_palette.vrt {styled_aai_filename}.tif')
        os.system(f'gdal_translate -co COMPRESS=LZW -co NBITS=3 -co ALPHA=YES atmo_palette.vrt {styled_aai_filename}.tif')
    # We may have to use the PNG export, because geotiff when using a palette don't support alpha channel
    # (https://gdal.org/drivers/raster/gtiff.html#creation-issues)
    if generate_styled_png:
        logging.info(f'    Generating png file: {styled_aai_filename}.png')
        os.system(f'gdal_translate -of PNG -co WORLDFILE=YES atmo_palette.vrt {styled_aai_filename}.png')

    logging.info(f'Removing temporary files')
    os.system(f'rm {storage_path}/tmp/*')

if __name__ == '__main__':
    atmo_5sp(auto_envvar_prefix='ATMO')