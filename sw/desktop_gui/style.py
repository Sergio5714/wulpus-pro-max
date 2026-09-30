"""
Copyright (C) 2026 Sergei Vostrikov

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0


Style components for the desktop application.
"""

from __future__ import annotations

import logging

from PySide6 import QtGui, QtWidgets

logger = logging.getLogger(__name__)
TX_RX_STYLESHEET = """
QFrame#configCard {
    border:1px solid #69727d;
    border-radius:5px;
}
QFrame#configCard[selected=true] {
    border:2px solid #228be6;
}
QToolButton {
    min-width:28px;
    min-height:28px;
    border:1px solid #69727d;
    border-radius:3px;
}
QToolButton:checked {
    background:#228be6;
    color:white;
    border-color:#74c0fc;
}
"""

DARK_STYLESHEET = (
    """
QMainWindow,QWidget {
    background:#15191f;
    color:#e7edf3;
}
QLineEdit,QComboBox,QSpinBox,QPlainTextEdit,QTableWidget,QListWidget {
    background:#252b33;
    border:1px solid #46505c;
    padding:4px;
}
QPushButton {
    background:#252b33;
    border:1px solid #46505c;
    border-radius:4px;
    padding:6px;
}
QPushButton:hover {
    border-color:#4dabf7;
}
QPushButton:disabled {
    color:#69727d;
}
QPushButton#connectButton[connected="true"] {
    background:#2f9e44;
    border-color:#69db7c;
    color:#ffffff;
}
QGroupBox {
    border:1px solid #343b45;
    margin-top:8px;
    padding-top:8px;
}
"""
    + TX_RX_STYLESHEET
)

LIGHT_STYLESHEET = (
    """
QMainWindow,QWidget {
    background:#f4f6f8;
    color:#18202a;
}
QLineEdit,QComboBox,QSpinBox,QPlainTextEdit,QTableWidget,QListWidget {
    background:#ffffff;
    border:1px solid #aeb7c2;
    padding:4px;
}
QPushButton {
    background:#ffffff;
    border:1px solid #aeb7c2;
    border-radius:4px;
    padding:6px;
}
QPushButton:hover {
    border-color:#1971c2;
}
QPushButton:disabled {
    color:#8a939d;
}
QPushButton#connectButton[connected="true"] {
    background:#2b8a3e;
    border-color:#2f9e44;
    color:#ffffff;
}
QGroupBox {
    border:1px solid #cbd1d8;
    margin-top:8px;
    padding-top:8px;
}
"""
    + TX_RX_STYLESHEET
)


def _compact_controls(root):
    """Apply one consistent sizing policy without constraining data views."""
    spin_boxes = root.findChildren(QtWidgets.QSpinBox) + root.findChildren(
        QtWidgets.QDoubleSpinBox
    )
    for widget in spin_boxes:
        widget.setMaximumWidth(140)
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
        )
    for widget in root.findChildren(QtWidgets.QComboBox):
        widget.setMaximumWidth(220)
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
        )
    for widget in root.findChildren(QtWidgets.QLineEdit):
        widget.setMaximumWidth(260)
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
        )
    for widget in root.findChildren(QtWidgets.QPushButton):
        widget.setMinimumWidth(90)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
    for widget in root.findChildren(QtWidgets.QProgressBar):
        widget.setMinimumWidth(250)
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
    for layout in root.findChildren(QtWidgets.QFormLayout):
        layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldsStayAtSizeHint)


def _expanding_field(widget, minimum=280):
    """Apply the shared expanding size policy to an input widget."""
    widget.setMinimumWidth(minimum)
    widget.setMaximumWidth(16777215)
    widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)


def _style_plot(plot, theme):
    """Apply theme-aware defaults to a pyqtgraph plot."""
    if theme == "dark":
        background, foreground = "#15191f", "#e7edf3"
    elif theme == "light":
        background, foreground = "#ffffff", "#18202a"
    else:
        palette = QtWidgets.QApplication.palette()
        background = palette.color(QtGui.QPalette.Base)
        foreground = palette.color(QtGui.QPalette.Text)
    plot.setBackground(background)
    plot_item = plot.getPlotItem()
    for name in ("left", "right", "top", "bottom"):
        axis = plot_item.getAxis(name)
        axis.setPen(foreground)
        axis.setTextPen(foreground)
