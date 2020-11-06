"""
Example script to detect aruco markers from an image using OpenCV
"""
import math

import json
import numpy as np
import cv2
from cv2 import aruco
from utils.aruco_utils import aruco_poses_to_transforms
from utils.select_video_source import select_video_source

# energy cores
import numpy as np
import cv2
from utils.ecore_utils import image_to_center_points
from utils.select_video_source import select_video_source

# motor
import socket

# Select the camera source by setting this
VIDEO_SOURCE = "ffmpeg"  # Options: 'gstreamer', 'webcam' or 'opencv'
#VIDEO_SOURCE = 'webcam'
#VIDEO_SOURCE = 'gstreamer'

ARUCO_DICT = aruco.Dictionary_get(aruco.DICT_4X4_50)
ARUCO_DETECTER_PARAMETERS = aruco.DetectorParameters_create()
# Let's set some aruco detection parameters to make the marker
# detection a bit more stable
ARUCO_DETECTER_PARAMETERS.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
ARUCO_DETECTER_PARAMETERS.cornerRefinementWinSize = 5
ARUCO_DETECTER_PARAMETERS.minMarkerDistanceRate = 0.05
ARUCO_DETECTER_PARAMETERS.cornerRefinementMinAccuracy = 0.5

# Read camera calibration params. The calibration parameters are
# camera model specific. These calibration params have been made for
# Rapsberry Pi Camera Module 2 but they seem to work OK with a webcam too.
# To create your own calibration params see this guide:
# https://github.com/robot-uprising-hq/ai-backend-connector/blob/master/docs/Camera-Calibration.md
with open('rpi-camera-calib-params.json') as json_file:
    calib_params = json.load(json_file)
    MTX = np.array(calib_params['mtx'], dtype=np.float32)
    DIST = np.array(calib_params['dist'], dtype=np.float32)
SIZE_OF_MARKER = 0.15

POS_ECORE_LOW_COLOR = np.array([120, 80, 100], dtype=np.float32)
POS_ECORE_HIGH_COLOR = np.array([175, 255, 255], dtype=np.float32)
NEG_ECORE_LOW_COLOR = np.array([25, 80, 100], dtype=np.float32)
NEG_ECORE_HIGH_COLOR = np.array([40, 255, 255], dtype=np.float32)

# '192.168.43.120' #'192.168.43.68' ##'192.168.0.148' #"127.0.0.1"
ROBOT_IP = '192.168.1.53'
ROBOT_PORT = 3000  # 3001
LEFT_TRACK_SPEED = 50  # -100
RIGHT_TRACK_SPEED = 50

LIMIT = 100


def print_transforms(transforms):
    """
    Function to pretty print the Aruco marker ID, X and Y coordinate
    and rotation of the robots found.
    """
    for aruco_id in transforms.keys():
        position = transforms[aruco_id]['position']
        rotation = transforms[aruco_id]['rotation']

        print(f'=== Aruco {aruco_id}\n'
              f'Position: X: {position[0]:.2f}, Y: {position[1]:.2f}\n'
              f'Rotation: {rotation[0]:.2f} Degrees\n')


def print_core_positions(pos_ecore_positions, neg_ecore_positions):
    """
    Function to pretty print the X and Y coordinates for energy cores
    """
    if pos_ecore_positions:
        for i, core in enumerate(pos_ecore_positions):
            print(f'Positive Core {i}: X: {core[0]:.2f}, Y: {core[1]:.2f}')
    if neg_ecore_positions:
        for i, core in enumerate(neg_ecore_positions):
            print(f'Negative Core {i}: X: {core[0]:.2f}, Y: {core[1]:.2f}')
    if not pos_ecore_positions and not neg_ecore_positions:
        print('No Energy Cores detected')
    print('=== Done\n')


def main():
    """
    Get an image from the chosen video source and then detect the robots
    from the image. Finally print the coordinates of the found robots.
    """
    get_image_func = select_video_source(VIDEO_SOURCE)
    i = 0
    while True:
        # Capture stream frame by frame
        frame = get_image_func()
        if frame is None:
            continue

        corners, detected_ids, rejected_img_points = \
            aruco.detectMarkers(frame,
                                ARUCO_DICT,
                                parameters=ARUCO_DETECTER_PARAMETERS)

        rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(corners,
                                                          SIZE_OF_MARKER,
                                                          MTX,
                                                          DIST)

        #frame = get_image_func()
        if frame is None:
            continue

        cv2.imshow('frame', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        pos_ecore_positions = image_to_center_points(
            frame,
            POS_ECORE_LOW_COLOR,
            POS_ECORE_HIGH_COLOR,
            'Positive Energy Cores')
        neg_ecore_positions = image_to_center_points(
            frame,
            NEG_ECORE_LOW_COLOR,
            NEG_ECORE_HIGH_COLOR,
            'Negative Energy Cores')
        #print_core_positions(pos_ecore_positions, neg_ecore_positions)

        if tvecs is not None and rvecs is not None:
            imaxis = aruco.drawDetectedMarkers(frame, corners, detected_ids)
            for i, _ in enumerate(tvecs):
                aruco.drawAxis(imaxis,
                               MTX,
                               DIST,
                               rvecs[i],
                               tvecs[i],
                               SIZE_OF_MARKER)
            cv2.imshow('frame', imaxis)
            transforms = aruco_poses_to_transforms(detected_ids=detected_ids,
                                                   corners=corners,
                                                   rvecs=rvecs)
            print_transforms(transforms)

            for id in transforms.keys():
                if id == 10:
                    robot = {
                        x: transforms[id]['position'][0],
                        y: transforms[id]['position'][1],
                        rotation: transforms[id]['rotation']
                    }

                    target_rotation = (math.atan((540 - robot.y)/(540 - robot.x)) * 180) / math.pi
                    rotation_diff = robot.rotation - target_rotation
                    if robot.rotation < 0:
                        robot.rotation = 360 - (robot.rotation * -1)
                    print(target_rotation)
                    print(robot.rotation)
                    print(rotation_diff)
                    if robot.rotation > rotation_diff:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.sendto(bytes(f"0;30", "utf-8"), (ROBOT_IP, ROBOT_PORT))
                        # if transforms[id]['position'][1] < 540:
                        #sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        # sock.sendto(bytes(f"{LEFT_TRACK_SPEED};{RIGHT_TRACK_SPEED}", "utf-8"),(ROBOT_IP, ROBOT_PORT))
                    else:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.sendto(bytes(f"0;0", "utf-8"), (ROBOT_IP, ROBOT_PORT))

                else:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.sendto(bytes(f"0;0", "utf-8"), (ROBOT_IP, ROBOT_PORT))
        else:
            cv2.imshow('frame', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


if __name__ == '__main__':
    main()
