#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""caminfo_relay.py (REALPREP) - CHI can neu dung go2_perception/realsense_node (khong co realsense2_camera).

robot_ros nghe intrinsics o <depth_topic>/../camera_info. realsense_node phat anh depth DA CANH THEO MAU
(/go2/camera/aligned_depth/image_raw) nhung chi phat /go2/camera/color/camera_info -> robot_ros khong co intrinsics
va dung FOV mac dinh 87 do (FOV depth goc) cho anh co FOV mau ~69 do: SAI hinh hoc. Nut nay chep camera_info cua
mau sang /go2/camera/aligned_depth/camera_info (anh canh theo mau co cung intrinsics voi anh mau).
  python3 deploy/caminfo_relay.py      (moi truong ROS cua cho, cung ROS_DOMAIN_ID voi bridge)
"""
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo


def main():
    rclpy.init()
    n = rclpy.create_node("realprep_caminfo_relay")
    pub = n.create_publisher(CameraInfo, "/go2/camera/aligned_depth/camera_info", qos_profile_sensor_data)

    def cb(m):
        pub.publish(m)
    n.create_subscription(CameraInfo, "/go2/camera/color/camera_info", cb, qos_profile_sensor_data)
    try:
        rclpy.spin(n)
    except KeyboardInterrupt:
        pass
    n.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
