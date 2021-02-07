import logging
import pathlib

import pkg_resources

from mopidy import config, ext

__version__ = pkg_resources.get_distribution("Mopidy-SoundcloudSimple").version

# TODO: If you need to log, use loggers named after the current Python module
logger = logging.getLogger(__name__)

class Extension(ext.Extension):

    dist_name = "Mopidy-SoundcloudSimple"
    ext_name = "soundcloudsimple"
    version = __version__

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        schema["auth_token"] = config.Secret()
        schema["client_id"] = config.Secret()
        schema["user_id"] = config.Secret()
        return schema

    def setup(self, registry):
        from .backend import SoundcloudSimpleBackend
        registry.add("backend", SoundcloudSimpleBackend)
