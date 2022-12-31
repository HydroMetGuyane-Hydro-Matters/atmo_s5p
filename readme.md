# Atmospheric data processing & notes
The data retrieved using `sentinelsat` python package for Sentiel 5P data are netcdf data that actually are not "raster-like": x and y refer to the satellite pass, not coordinates. Lat/lon are variable like others. They are in EPSG:4326 but the netcdf's shape does not match an EPSG:4326 shape, meaning we cannot process them easily are raster data, rather as a collection of points.

To trasnfrom that into raster data, we have to interpolate the values along a regular grid. The only easy way to do that, AFAIK, is to use the [HARP tool](https://stcorp.github.io/harp/doc/html/index.html).

## Setup
We will use HARP tool. It is hard to install, unless you resort to conda environment. Since I'm not using conda on my computer, the simplest way I found is to use docker interpreter. So, I'm configuring my IDE (pycharm pro) to run this script using the same dockerfile as what will be used in prod (see https://www.jetbrains.com/help/pycharm/using-docker-as-a-remote-interpreter.html#config-docker)

## Processing steps (experimenting)

### Download the data
The python script does the job well to retrieve the netcdf files.

### resample (interpolate) the values to produce a regular geographic grid
For this, we will use harp tools.
`harpmerge` should be able to do this *and* merge the files of the day (when there are several) into one, but I couldn't get this done.

So, for now, let's stick to the main task, resampling:
```
harpconvert -a 'keep(latitude_bounds,longitude_bounds,absorbing_aerosol_index);bin_spatial(241,1,0.025,281,-57,0.025);squash(time, (latitude_bounds,longitude_bounds));derive(latitude {latitude});derive(longitude {longitude});exclude(latitude_bounds,longitude_bounds,count,weight)' S5P_NRTI_L2__AER_AI_20221215T162905_20221215T163405_26804_03_020400_20221215T170746.nc aai1.nc
```
To loop over the files of the day

### Merge the files of the day
gdal is our guy here. A simple `gdal_merge.py -o aai.tif  aai?.nc` does the trick. But we will also want to optimize the result. The best would be to ouput a geotiff with a color palette that matches Adrien's specs. This would produce a very small geotiff that Florent could use directly for display

