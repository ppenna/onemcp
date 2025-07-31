from os.path import dirname, join, realpath

ONEMCP_PROJ_ROOT = dirname(dirname(dirname(dirname(realpath(__file__)))))
ONEMCP_SRC_ROOT = join(ONEMCP_PROJ_ROOT, "src", "onemcp")
