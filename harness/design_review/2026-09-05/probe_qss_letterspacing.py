import os, json, sys
os.environ["QT_QPA_PLATFORM"]="offscreen"
from PySide6 import QtWidgets, QtGui
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
out={}
def mk(txt, qss=None, px=11):
    l = QtWidgets.QLabel(txt); f=QtGui.QFont("Space Mono"); f.setPixelSize(px); l.setFont(f)
    if qss: l.setStyleSheet(qss)
    l.ensurePolished(); return l
a = mk("BUILD HDA"); b = mk("BUILD HDA", "QLabel { letter-spacing: 5px; }")
out["hint_no_qss"]=a.sizeHint().width(); out["hint_qss_5px"]=b.sizeHint().width()
out["font_letterSpacing_qss"]=b.font().letterSpacing(); out["type"]=str(b.font().letterSpacingType())
# both: QFont percent then QSS px -> which wins?
c = mk("BUILD HDA"); fc=c.font(); fc.setLetterSpacing(QtGui.QFont.PercentageSpacing, 115.0); c.setFont(fc); c.ensurePolished()
out["hint_qfont_115"]=c.sizeHint().width()
d = mk("BUILD HDA"); fd=d.font(); fd.setLetterSpacing(QtGui.QFont.PercentageSpacing, 115.0); d.setFont(fd)
d.setStyleSheet("QLabel { letter-spacing: 5px; }"); d.ensurePolished()
out["hint_qfont115_then_qss5"]=d.sizeHint().width(); out["d_font_ls"]=d.font().letterSpacing(); out["d_type"]=str(d.font().letterSpacingType())
out["qt"]=QtGui.qVersion() if hasattr(QtGui,'qVersion') else None
from PySide6 import QtCore; out["qt"]=QtCore.qVersion()
print(json.dumps(out))
