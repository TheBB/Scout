from qtpy.QtCore import Qt  # type: ignore

from qtpy.QtWidgets import (
    QFrame,
    QGridLayout,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QWidget
)

from qtpy.QtCore import (
    QAbstractAnimation,
    QParallelAnimationGroup,
    QPropertyAnimation,
)


class Collapsible(QWidget):

    toggle: QToolButton
    header: QFrame
    content: QScrollArea
    toggle_anim: QParallelAnimationGroup
    layout: QGridLayout

    duration: int

    def __init__(self, title, parent, duration: int = 100):
        super().__init__(parent)

        self.duration = duration

        self.toggle = QToolButton(self)
        self.toggle.setStyleSheet('QToolButton { border: none; }')
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(False)

        self.header = QFrame(self)
        self.header.setFrameShape(QFrame.HLine)
        self.header.setFrameShadow(QFrame.Sunken)
        self.header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.content = QScrollArea(self)
        self.content.setStyleSheet('QScrollArea { border: none; }')
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content.setMaximumHeight(0)
        self.content.setMinimumHeight(0)

        self.toggle_anim = QParallelAnimationGroup(self)
        self.toggle_anim.addAnimation(QPropertyAnimation(self, b'minimumHeight'))
        self.toggle_anim.addAnimation(QPropertyAnimation(self, b'maximumHeight'))
        self.toggle_anim.addAnimation(QPropertyAnimation(self.content, b'maximumHeight'))

        self.layout = QGridLayout(self)
        self.layout.setVerticalSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.layout.addWidget(self.toggle, 0, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.header, 0, 2, 1, 1)
        self.layout.addWidget(self.content, 1, 0, 1, 3)

        self.setLayout(self.layout)
        self.toggle.clicked.connect(self.trigger)

    def trigger(self):
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if self.toggle.isChecked() else Qt.ArrowType.RightArrow)
        self.toggle_anim.setDirection(QAbstractAnimation.Forward if self.toggle.isChecked() else QAbstractAnimation.Backward)
        self.toggle_anim.start()

    def set_content_layout(self, layout):
        self.content.setLayout(layout)
        collapsed_height = self.sizeHint().height() - self.content.maximumHeight()
        content_height = layout.sizeHint().height()

        for i in range(2):
            anim: QPropertyAnimation = self.toggle_anim.animationAt(i)
            anim.setDuration(self.duration)
            anim.setStartValue(collapsed_height)
            anim.setEndValue(collapsed_height + content_height)

        anim: QPropertyAnimation = self.toggle_anim.animationAt(2)
        anim.setDuration(self.duration)
        anim.setStartValue(0)
        anim.setEndValue(content_height)

