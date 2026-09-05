import json, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "python"))
from PySide6 import QtWidgets, QtGui, QtCore
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
from synapse.panel.designsystem import qss
from synapse.panel.synapse_panel import SynapsePanel
p = SynapsePanel(); p.setStyleSheet(qss.stylesheet()); p.resize(340, 760); p.show()
app.processEvents(); app.processEvents()
out = {"density": p.property("density"), "pills": [], "thin_layouts": []}
for b in p.findChildren(QtWidgets.QPushButton, "DsPill"):
    f = b.font(); par = b.parentWidget()
    out["pills"].append({"text": b.text(), "role": b.property("rhythm_role"), "spacing": round(f.letterSpacing(), 1),
        "family": f.family(), "h": b.height(), "w": b.width(), "y": b.mapTo(p, QtCore.QPoint(0,0)).y(),
        "parent": par.objectName(), "parent_role": par.property("rhythm_role"), "visible": b.isVisible()})
for lay in p.findChildren(QtWidgets.QLayout):
    if 0 < lay.spacing() < 4:
        pw = lay.parentWidget(); kids = [lay.itemAt(i).widget() for i in range(lay.count()) if lay.itemAt(i).widget()]
        out["thin_layouts"].append({"spacing": lay.spacing(), "owner": pw.objectName() if pw else None,
            "owner_class": type(pw).__name__ if pw else None, "owner_parent_class": type(pw.parentWidget()).__name__ if pw and pw.parentWidget() else None,
            "first_kids": [(k.objectName(), type(k).__name__) for k in kids[:3]]})
# crop: rail + ribbon + tab row, 2x
pm = p.grab(QtCore.QRect(0, 0, 340, 190))
pm = pm.scaled(680, 380, QtCore.Qt.KeepAspectRatio, QtCore.Qt.FastTransformation)
pm.save(os.environ["CROP_OUT"])
sys.stdout.write(json.dumps(out) + "\n")
p.close(); app.processEvents()
