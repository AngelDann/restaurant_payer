from .base import *  # noqa: F403

DEBUG = False

STORAGES["staticfiles"]["BACKEND"] = (  # noqa: F405
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)
