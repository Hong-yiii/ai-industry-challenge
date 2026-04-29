#!/usr/bin/env python3
"""Rewrite URDF mesh URIs for Foxglove WebSocket + foxglove_bridge.

Upstream URDF often uses absolute install paths (see ``force_abs_paths`` on
``ur_robot`` in ``aic_description``):

- ``file:///ws_aic/install/share/<pkg>/...`` — workspace install tree
- ``file:///opt/ros/<distro>/share/<pkg>/...`` — system packages (UR arms, etc.)

The Foxglove **web** client resolves ``file://`` on the **laptop**, so those
meshes never load. The bridge serves ``package://...`` via the **assets**
capability when files exist in the sidecar image.

This node subscribes to ``/robot_description`` (TRANSIENT_LOCAL) and republishes
the same XML on ``/robot_description_foxglove`` with both prefixes rewritten
to ``package://<pkg>/...``.
"""
from __future__ import annotations

import re
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

# Typical URDF mesh attrs use double quotes; match through the closing quote.
_WS_AIC_FILE_RE = re.compile(r"file:///ws_aic/install/share/([^/]+)/([^\"]+)")
_OPT_ROS_FILE_RE = re.compile(r"file:///opt/ros/[^/]+/share/([^/]+)/([^\"]+)")


def rewrite_urdf(xml: str) -> str:
    def repl_ws(m: re.Match[str]) -> str:
        pkg, rest = m.group(1), m.group(2)
        return f"package://{pkg}/{rest}"

    def repl_opt(m: re.Match[str]) -> str:
        pkg, rest = m.group(1), m.group(2)
        return f"package://{pkg}/{rest}"

    out = _WS_AIC_FILE_RE.sub(repl_ws, xml)
    return _OPT_ROS_FILE_RE.sub(repl_opt, out)


class UrdfRewriteNode(Node):
    def __init__(self) -> None:
        super().__init__("foxglove_urdf_rewrite")
        qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self._pub = self.create_publisher(String, "/robot_description_foxglove", qos)
        self._got_input = False
        self._sub = self.create_subscription(String, "/robot_description", self._cb, qos)
        self.create_timer(30.0, self._timeout_check)
        self.get_logger().info(
            "Waiting for /robot_description to publish /robot_description_foxglove "
            "(file:// -> package:// for bridge assets)"
        )

    def _timeout_check(self) -> None:
        if not self._got_input:
            self.get_logger().warning(
                "Still no /robot_description after 30s; Foxglove URDF rewrite idle"
            )

    def _cb(self, msg: String) -> None:
        if self._got_input:
            return
        self._got_input = True
        out = rewrite_urdf(msg.data)
        n_ws = len(_WS_AIC_FILE_RE.findall(msg.data))
        n_opt = len(_OPT_ROS_FILE_RE.findall(msg.data))
        if out != msg.data:
            self.get_logger().info(
                "Republishing URDF on /robot_description_foxglove "
                f"({n_ws} ws_aic + {n_opt} opt/ros file:// path(s) rewritten)"
            )
        else:
            self.get_logger().info(
                "Republishing URDF on /robot_description_foxglove "
                "(no ws_aic or opt/ros file:// paths found)"
            )
        self._pub.publish(String(data=out))


def main() -> int:
    rclpy.init(args=sys.argv)
    node = UrdfRewriteNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
