import argparse
import os.path as osp
import sys

import barecat
import msgpack_numpy
import posepile.tools.dataset_pickle_to_barecat
import rlemasklib
import simplepyutils as spu
from PyQt6.QtCore import QModelIndex, Qt, pyqtSlot
from PyQt6.QtGui import QStandardItem, \
    QStandardItemModel
from PyQt6.QtWidgets import QAbstractItemView, QApplication, QHBoxLayout, QHeaderView, \
    QSplitter, QStyleFactory, QTableView, QTreeView, QWidget

from barecat_pose_viewer import improc, plotter, util


def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create(QApplication.style().objectName()))

    parser = argparse.ArgumentParser(description='View images stored in a barecat archive.')
    parser.add_argument('--annotations', type=str, help='barecat to load annotations from')
    parser.add_argument('--images', type=str, help='barecat to load images from')
    args = parser.parse_args()
    viewer = PoseViewer(args.annotations, args.images)
    viewer.show()
    sys.exit(app.exec())


class PoseViewer(QWidget):
    def __init__(self, annotations_path, images_path):
        super().__init__()
        self.annotation_reader = barecat.Reader(annotations_path, decoder=msgpack_numpy.unpackb)
        self.image_reader = barecat.Reader(images_path, decoder=improc.decode_jpeg)

        self.directory_tree = QTreeView()
        self.directory_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_table = self.create_file_table()

        self.joint_info = posepile.tools.dataset_pickle_to_barecat.get_joint_info(
            self.annotation_reader['metadata.msgpack'])
        self.plot_area = plotter.PlotWidget(
            self.joint_info.names, self.joint_info.stick_figure_edges)

        splitter = QSplitter()
        splitter.addWidget(self.directory_tree)
        splitter.addWidget(self.file_table)
        splitter.addWidget(self.plot_area)
        splitter.setSizes([650, 650, 1000])

        layout = QHBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

        self.resize(2400, 800)

        self.fill_directory_tree()
        self.directory_tree.selectionModel().selectionChanged.connect(self.update_file_table)
        self.directory_tree.activated.connect(self.expand_tree_item)
        self.directory_tree.doubleClicked.connect(self.expand_tree_item)

        root_index = self.directory_tree.model().index(0, 0)
        self.directory_tree.setCurrentIndex(root_index)

    def create_file_table(self):
        ft = QTableView()
        ft.verticalHeader().setVisible(False)
        ft.verticalHeader().setDefaultSectionSize(20)
        ft.setShowGrid(False)
        ft.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        ft.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        ft.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['Name', 'Size'])
        ft.setModel(model)
        ft.selectionModel().selectionChanged.connect(self.show_selected_file)
        ft.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        ft.horizontalHeader().setStyleSheet(
            "QHeaderView::section {font-weight: normal; text-align: left;}")
        return ft

    def fill_directory_tree(self):
        root_item = TreeItem(self.annotation_reader)
        size, count, has_subdirs, has_files = self.annotation_reader.index.get_dir_info('')
        item = TreeItem(
            self.annotation_reader, path='', size=size, count=count, has_subdirs=has_subdirs,
            parent=root_item)
        root_item.children.append(item)
        self.model = LazyItemModel(root_item)
        self.directory_tree.setModel(self.model)

        root_index = self.directory_tree.model().index(0, 0)
        self.directory_tree.expand(root_index)  # Expand the root item by default
        self.directory_tree.setColumnWidth(0, 400)
        self.directory_tree.setColumnWidth(1, 70)
        self.directory_tree.setColumnWidth(2, 70)

    @pyqtSlot(QModelIndex)
    def expand_tree_item(self, index):
        if self.directory_tree.isExpanded(index):
            self.directory_tree.collapse(index)
        else:
            self.directory_tree.expand(index)

    def update_file_table(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes:
            return

        index = indexes[0]  # Get the first selected index
        item = index.internalPointer()

        model = self.file_table.model()
        model.removeRows(0, model.rowCount())
        files_and_sizes = self.annotation_reader.index.get_files_with_size(item.path)
        files_and_sizes = sorted(files_and_sizes, key=lambda x: spu.natural_sort_key(x[0]))
        for file, size in files_and_sizes:
            file_item = QStandardItem(osp.basename(file))
            file_item.setData(file, Qt.ItemDataRole.UserRole)  # Store the full path as user data
            model.appendRow([file_item, QStandardItem(util.format_size(size))])

        if len(files_and_sizes) > 0:
            first_file_index = self.file_table.model().index(0, 0)
            self.file_table.setCurrentIndex(first_file_index)
        else:
            for dirname, subdirs, files in self.annotation_reader.index.walk(item.path):
                file = next(iter(files), None)
                if file is not None:
                    self.show_file(file)
                    break

    def show_selected_file(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes:
            return
        path = self.file_table.model().item(indexes[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        self.show_file(path)

    def show_file(self, path):
        content = self.annotation_reader[path]
        if 'impath' in content:
            ex = posepile.tools.dataset_pickle_to_barecat.dict_to_example(
                content, self.joint_info.n_joints)
            mask = rlemasklib.decode(ex.mask) if ex.mask is not None else None
            image = self.image_reader[ex.image_path]
            self.plot_area.plot(image, ex.bbox, ex.world_coords, ex.camera, mask)


class LazyItemModel(QStandardItemModel):
    def __init__(self, root):
        super().__init__()
        self.root = root

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_item = self.root if not parent.isValid() else parent.internalPointer()
        return (
            self.createIndex(row, column, parent_item.children[row])
            if row < len(parent_item.children)
            else QModelIndex())

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        parent_item = index.internalPointer().parent
        return self.createIndex(parent_item.row, 0, parent_item) if parent_item else QModelIndex()

    def rowCount(self, parent=QModelIndex()):
        parent_item = self.root if not parent.isValid() else parent.internalPointer()
        return len(parent_item.children)

    def columnCount(self, parent=QModelIndex()):
        return 3  # Name, Size, Count

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ["Name", "Size", "Count"][section]
        return None

    def data(self, index, role):
        item = index.internalPointer()
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                if item.parent == self.root:
                    return '[root]'
                return osp.basename(item.path)
            elif index.column() == 1:
                return util.format_size(item.size)
            elif index.column() == 2:
                return util.format_count(item.count)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() in [1, 2]:
                return Qt.AlignmentFlag.AlignRight
        return None

    def canFetchMore(self, index):
        if not index.isValid():
            return False
        return not index.internalPointer().fetched

    def fetchMore(self, index):
        item = index.internalPointer()
        if item == self.root:
            return
        item.fetch_more()
        self.beginInsertRows(index, 0, len(item.children) - 1)
        self.endInsertRows()

    def hasChildren(self, index=QModelIndex()):
        if not index.isValid():
            return True
        return index.internalPointer().has_subdirs


class TreeItem:
    def __init__(self, file_reader, path='', size=0, count=0, has_subdirs=True, parent=None):
        self.file_reader = file_reader

        self.path = path
        self.parent = parent
        self.children = []

        self.size = size
        self.count = count
        self.has_subdirs = has_subdirs
        self.fetched = False

    def fetch_more(self):
        if self.fetched:
            return
        subdir_infos = self.file_reader.index.get_subdir_infos(self.path)
        subdir_infos = sorted(subdir_infos, key=lambda x: spu.natural_sort_key(x[0]))
        for dir, size, count, has_subdirs, has_files in subdir_infos:
            self.children.append(TreeItem(
                self.file_reader, path=dir, size=size, count=count, has_subdirs=has_subdirs,
                parent=self))

        self.fetched = True

    @property
    def row(self):
        return self.parent.children.index(self) if self.parent else 0


if __name__ == '__main__':
    main()
