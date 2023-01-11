FROM condaforge/miniforge3:latest
LABEL description="Sentinel5P script for the SAGUI platform"
LABEL maintainer="Jean Pommier, jean.pommier@pi-geosolutions.fr"
LABEL project-scope="SAGUI"
LABEL git-repo="https://github.com/HydroMetGuyane-Hydro-Matters/sagui_platform"

COPY conda-requirements.txt conda-requirements.txt
RUN conda install --file conda-requirements.txt
#RUN conda install cairosvg

COPY src/ app/
ENV ATMO_STORAGE_PATH=/mnt/data \
    ATMO_FOOTPRINT=/app/Guyane_watersheds.geojson \
    ATMO_VRT_TEMPLATE=/app/templates/atmo_palette.j2


WORKDIR "/app"
CMD ["python", "atmo_process.py"]


