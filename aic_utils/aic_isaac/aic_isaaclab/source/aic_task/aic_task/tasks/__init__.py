# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Package containing task implementations for the extension."""

##
# Register Gym environments.
##
try:
    from isaaclab_tasks.utils import import_packages

    # The blacklist is used to prevent importing configs from sub-packages
    _BLACKLIST_PKGS = ["utils", ".mdp"]
    # Import all configs in this package
    import_packages(__name__, _BLACKLIST_PKGS)
except Exception as exc:
    # Isaac Sim can fail package discovery during extension startup, but the
    # task module itself is still importable and performs Gym registration.
    _PACKAGE_DISCOVERY_ERROR = exc
else:
    _PACKAGE_DISCOVERY_ERROR = None

# Ensure nested task registration is deterministic even when package discovery
# does not descend into the manager_based/aic_task package.
from .manager_based import aic_task  # noqa: F401,E402

if _PACKAGE_DISCOVERY_ERROR is not None:
    print(f"Registered AIC task via fallback import after package discovery failed: {_PACKAGE_DISCOVERY_ERROR}")
