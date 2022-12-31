FROM condaforge/miniforge3:latest

COPY conda-requirements.txt conda-requirements.txt
RUN conda install --file conda-requirements.txt
RUN conda install rasterio pandas numpy
RUN conda install click logging
#RUN conda install -c conda-forge gdal