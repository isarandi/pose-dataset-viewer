# noinspection PyUnresolvedReferences
import functools

import matplotlib.colors as mcolors
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from PyQt6.QtWidgets import QScrollArea, \
    QSizePolicy, QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar

import barecat_pose_viewer.improc as improc


class PlotWidget(QWidget):
    def __init__(self, joint_names, joint_edges):
        super().__init__()
        self.plotter = PosePlotter(
            joint_names=joint_names, joint_edges=joint_edges)
        self.canvas = FigureCanvas(self.plotter.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        plot_layout = QVBoxLayout()
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas)

        plot_widget = QWidget()
        plot_widget.setLayout(plot_layout)
        self.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.canvas.updateGeometry()

        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setWidget(plot_widget)
        layout = QVBoxLayout(self)
        layout.addWidget(self.scrollArea)

    def plot(self, image, box, pose3d, camera, mask=None):
        self.plotter.plot(image, box, pose3d, camera, mask)
        self.canvas.draw()


class PosePlotter:
    def __init__(self, joint_names, joint_edges):
        self.fig = plt.figure(figsize=(12, 6), layout='constrained')
        self.im_ax = self.fig.add_subplot(1, 2, 1)
        self.pose_ax = self.fig.add_subplot(1, 2, 2, projection='3d')
        self.pose_ax.view_init(5, -85)
        view_range = 800
        self.pose_ax.set_xlim3d(-view_range, view_range)
        self.pose_ax.set_ylim3d(-view_range, view_range)
        self.pose_ax.set_zlim3d(-view_range, view_range)
        self.pose_ax.set_box_aspect((1, 1, 1))

        self.image_obj = None
        self.box_rect = None
        self.lines2d = None
        self.scatter2d = None
        self.lines3d = None
        self.scatter3d = None

        self.joint_names = joint_names
        self.joint_edges = joint_edges
        self.left_color = 'tab:blue'
        self.right_color = 'tab:red'
        self.mask_color = 'tab:orange'
        self.point = 'wo'

    def plot(self, image, box, pose3d, camera, mask=None):
        if mask is not None:
            mask = crop_or_pad(mask, image.shape[:2])
            improc.draw_mask(image, mask, get_named_color(self.mask_color))
        self.imshow(image)
        self.draw_box(box)
        self.plot_pose2d(camera.world_to_image(pose3d))
        coords = camera.world_to_camera(pose3d)
        coords -= np.nanmean(coords, axis=0)
        self.plot_pose3d(coords, (0, -1, 0))
        self.fig.canvas.draw_idle()
        self.fig.canvas.blit(self.im_ax.bbox)
        self.fig.canvas.blit(self.pose_ax.bbox)

    def imshow(self, image):
        if self.image_obj is None:
            self.image_obj = self.im_ax.imshow(image, animated=True, origin='upper')
        else:
            self.image_obj.set_data(image)
            self.image_obj.set_extent([0, image.shape[1], image.shape[0], 0])
            self.im_ax.set_xlim([0, image.shape[1]])
            self.im_ax.set_ylim([image.shape[0], 0])

    def draw_box(self, box):
        if self.box_rect:
            self.box_rect.set_bounds(box[0], box[1], box[2], box[3])
        else:
            self.box_rect = patches.Rectangle(
                (box[0], box[1]), box[2], box[3], linewidth=1, edgecolor='r', facecolor='none')
            self.im_ax.add_patch(self.box_rect)

    def plot_pose3d(self, pose3d, up_vector):
        pose3d = pose3d @ rotation_mat(up_vector).T

        if self.lines3d is None:
            self.lines3d = []
            for i_start, i_end in self.joint_edges:
                is_left = self.joint_names[i_start][0] == 'l' or self.joint_names[i_end][0] == 'l'
                line, = self.pose_ax.plot(
                    *zip(pose3d[i_start], pose3d[i_end]),
                    c=self.left_color if is_left else self.right_color, linewidth=3)
                self.lines3d.append(line)
        else:
            for i, (i_start, i_end) in enumerate(self.joint_edges):
                self.lines3d[i].set_data(*zip(pose3d[i_start, :2], pose3d[i_end, :2]))
                self.lines3d[i].set_3d_properties(*zip(pose3d[i_start, 2:], pose3d[i_end, 2:]))

        # if self.scatter3d is None:
        #     self.scatter3d = self.pose_ax.scatter(
        #         *pose3d.T, c=self.point[0], marker=self.point[1], s=5)
        # else:
        #     self.scatter3d.set_offsets(pose3d[:, :2])
        #
        # for name, i in ji.ids.items():
        #     c = pose3d[i]
        #     if np.isfinite(c[0]):
        #         self.pose_ax.text(c[0], c[1], c[2], name)

    def plot_pose2d(self, pose2d):
        if self.lines2d is None:
            self.lines2d = []
            for i_start, i_end in self.joint_edges:
                is_left = self.joint_names[i_start][0] == 'l' or self.joint_names[i_end][0] == 'l'
                line, = self.im_ax.plot(
                    *zip(pose2d[i_start], pose2d[i_end]),
                    c=self.left_color if is_left else self.right_color, linewidth=3)
                self.lines2d.append(line)
        else:
            for i, (i_start, i_end) in enumerate(self.joint_edges):
                self.lines2d[i].set_data(*zip(pose2d[i_start], pose2d[i_end]))

        if self.scatter2d is None:
            self.scatter2d = self.im_ax.scatter(
                *pose2d.T, c=self.point[0], marker=self.point[1], s=50)
        else:
            self.scatter2d.set_offsets(pose2d)


def get_named_color(name):
    return np.array(mcolors.to_rgb(name)) * 255


def rotation_mat(up, rightlike=(1, 0, 0), rightlike_alternative=(0, 1, 0)):
    up = np.array(up, np.float32)
    rightlike = np.array(rightlike, np.float32)
    if np.allclose(up, rightlike):
        rightlike = np.array(rightlike_alternative, np.float32)

    forward = unit_vector(np.cross(up, rightlike))
    right = np.cross(forward, up)
    return np.row_stack([right, forward, up])


def unit_vector(vectors, axis=-1):
    norm = np.linalg.norm(vectors, axis=axis, keepdims=True)
    return vectors / norm


def crop_or_pad(mask, dst_shape):
    src_shape = mask.shape
    if src_shape == dst_shape:
        return mask
    elif src_shape[0] > dst_shape[0] and src_shape[1] > dst_shape[1]:
        return mask[:dst_shape[0], :dst_shape[1]]
    else:
        dst_mask = np.zeros(dst_shape, dtype=mask.dtype)
        dst_mask[:src_shape[0], :src_shape[1]] = mask
        return dst_mask


