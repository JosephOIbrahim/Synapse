import sys, json
from PySide6 import QtWidgets, QtCore
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
out = {}
for r in (999, 100, 14, 8):
    host = QtWidgets.QWidget(); host.setObjectName("host"); host.setAttribute(QtCore.Qt.WA_StyledBackground, True)
    host.setStyleSheet(f"QWidget#host{{background:#2a2a2a;}} QPushButton{{background:#363636;border:none;border-radius:{r}px;padding:6px 10px;}}")
    b = QtWidgets.QPushButton("EXPERT", host); b.move(10, 10); b.resize(81, 29)
    host.resize(120, 60); host.show(); app.processEvents(); app.processEvents()
    im = host.grab().toImage()
    px = lambda x, y: im.pixelColor(x, y).name()
    out[f"radius_{r}"] = {"btn_corner": px(10, 10), "btn_inset2": px(12, 12), "btn_mid_top": px(50, 10), "btn_center": px(50, 24), "host_bg": px(2, 2)}
    host.close()
sys.stdout.write(json.dumps(out) + "\n")
