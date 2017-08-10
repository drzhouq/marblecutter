# noqa
# coding=utf-8
from __future__ import absolute_import

import logging
import os

from flask import Flask, jsonify, render_template, url_for
from flask_cors import CORS
from mercantile import Tile

from . import NoDataAvailable, skadi, tiling
from .catalogs import OAMJSONCatalog, PostGISCatalog
from .formats import PNG, ColorRamp, GeoTIFF
from .transformations import Hillshade, Image, Normal, Terrarium

LOG = logging.getLogger(__name__)

app = Flask("marblecutter")
CORS(app, send_wildcard=True)

app.config["APPLICATION_ROOT"] = os.getenv("APPLICATION_ROOT")
app.config["PREFERRED_URL_SCHEME"] = os.getenv("PREFERRED_URL_SCHEME", "http")
# app.config["SERVER_NAME"] = os.getenv("SERVER_NAME", "localhost:8000")

GEOTIFF_FORMAT = GeoTIFF()
HILLSHADE_FORMAT = ColorRamp()
HILLSHADE_TRANSFORMATION = Hillshade(resample=True, add_slopeshade=True)
IMAGE_TRANSFORMATION = Image()
NORMAL_TRANSFORMATION = Normal()
PNG_FORMAT = PNG()
TERRARIUM_TRANSFORMATION = Terrarium()
POSTGIS_CATALOG = PostGISCatalog()


class InvalidTileRequest(Exception):  # noqa
    status_code = 404

    def __init__(self, message, status_code=None, payload=None):  # noqa
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):  # noqa
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@app.route("/favicon.ico")
def favicon():  # noqa
    return '', 404


@app.route("/<renderer>/")
def meta(renderer):  # noqa
    if renderer not in ["hillshade", "buffered_normal", "normal", "terrarium", "oam"]:
        return '', 404

    meta = {
        "minzoom": 0,
        "maxzoom": 22,
        "bounds": [-180, -85.05113, 180, 85.05113],
    }

    with app.app_context():
        meta["tiles"] = [
            "{}{{z}}/{{x}}/{{y}}.png".format(
                url_for("meta", _external=True, renderer=renderer))
        ]

    return jsonify(meta)


@app.route("/<renderer>/preview")
def preview(renderer):  # noqa
    if renderer not in ["hillshade", "buffered_normal", "normal", "terrarium", "oam"]:
        return '', 404

    with app.app_context():
        return render_template(
            "preview.html",
            tilejson_url=url_for(
                "meta", _external=True, _scheme="", renderer=renderer),
        ), 200, {
            "Content-Type": "text/html"
        }


@app.route("/geotiff/<int:z>/<int:x>/<int:y>.tif")
def render_geotiff(z, x, y):  # noqa
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile, POSTGIS_CATALOG, format=GEOTIFF_FORMAT, scale=2)

    return data, 200, headers


@app.route("/hillshade/<int:z>/<int:x>/<int:y>.png")
@app.route("/hillshade/<int:z>/<int:x>/<int:y>@<int:scale>x.png")
def render_hillshade_png(z, x, y, scale=1):  # noqa
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        POSTGIS_CATALOG,
        format=HILLSHADE_FORMAT,
        transformation=HILLSHADE_TRANSFORMATION,
        scale=scale)

    return data, 200, headers


@app.route("/hillshade/<int:z>/<int:x>/<int:y>.tif")
def render_hillshade_tiff(z, x, y):  # noqa
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        POSTGIS_CATALOG,
        format=GEOTIFF_FORMAT,
        transformation=HILLSHADE_TRANSFORMATION,
        scale=2)

    return data, 200, headers


@app.route("/buffered_normal/<int:z>/<int:x>/<int:y>.png")
@app.route("/buffered_normal/<int:z>/<int:x>/<int:y>@<int:scale>x.png")
def render_buffered_normal(z, x, y, scale=1):  # noqa
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        POSTGIS_CATALOG,
        format=PNG_FORMAT,
        transformation=NORMAL_TRANSFORMATION,
        scale=scale,
        buffer=2)

    return data, 200, headers


@app.route("/normal/<int:z>/<int:x>/<int:y>.png")
@app.route("/normal/<int:z>/<int:x>/<int:y>@<int:scale>x.png")
def render_normal(z, x, y, scale=1):  # noqa
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        POSTGIS_CATALOG,
        format=PNG_FORMAT,
        transformation=NORMAL_TRANSFORMATION,
        scale=scale)

    return data, 200, headers


@app.route("/skadi/<_>/<tile>.hgt.gz")
def render_skadi(_, tile):  # noqa
    headers, data = skadi.render_tile(tile)

    return data, 200, headers


@app.route("/terrarium/<int:z>/<int:x>/<int:y>.png")
@app.route("/terrarium/<int:z>/<int:x>/<int:y>@<int:scale>x.png")
def render_terrarium(z, x, y, scale=1):  # noqa
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        POSTGIS_CATALOG,
        format=PNG_FORMAT,
        transformation=TERRARIUM_TRANSFORMATION,
        scale=scale)

    return data, 200, headers

OAM_JSON_CATALOG = OAMJSONCatalog("http://oin-hotosm.s3.amazonaws.com/5796733584ae75bb00ec746a/0/579674e02b67227a79b4fd52.json")


@app.route("/oam/<int:z>/<int:x>/<int:y>.png")
@app.route("/oam/<int:z>/<int:x>/<int:y>@<int:scale>x.png")
def render_oam(z, x, y, scale=1):  # noqa
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        OAM_JSON_CATALOG,
        format=PNG_FORMAT,
        transformation=IMAGE_TRANSFORMATION,
        scale=scale)

    return data, 200, headers


@app.errorhandler(InvalidTileRequest)
def handle_invalid_tile_request(error):  # noqa
    response = jsonify(error.to_dict())
    response.status_code = error.status_code

    return response


@app.errorhandler(NoDataAvailable)
def handle_no_data_available(error):  # noqa
    return "", 404


@app.errorhandler(IOError)
def handle_ioerror(error):  # noqa
    LOG.warn(error)

    return "", 500


static = app.send_static_file
