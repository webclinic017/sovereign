import os
from pkg_resources import get_distribution, resource_filename
from fastapi.responses import JSONResponse
from starlette.templating import Jinja2Templates
from sovereign import config_loader
from sovereign.utils.dictupdate import merge
from sovereign.schemas import (
    SovereignAsgiConfig,
    SovereignConfig,
    SovereignConfigv2,
)


json_response_class = JSONResponse
try:
    import orjson
    from fastapi.responses import ORJSONResponse

    json_response_class = ORJSONResponse
except ImportError:
    try:
        import ujson
        from fastapi.responses import UJSONResponse

        json_response_class = UJSONResponse
    except ImportError:
        pass


def parse_raw_configuration(path: str):
    ret = dict()
    for p in path.split(","):
        spec = config_loader.Loadable.from_legacy_fmt(p)
        ret = merge(obj_a=ret, obj_b=spec.load(), merge_lists=True)
    return ret


__version__ = get_distribution("sovereign").version
config_path = os.getenv("SOVEREIGN_CONFIG", "file:///etc/sovereign.yaml")
html_templates = Jinja2Templates(resource_filename("sovereign", "templates"))
old_config = SovereignConfig(**parse_raw_configuration(config_path))
config = SovereignConfigv2.from_legacy_config(old_config)
asgi_config = SovereignAsgiConfig()
XDS_TEMPLATES = config.xds_templates()
