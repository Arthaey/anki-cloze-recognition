# -*- coding: utf-8 -*-
# See github page to report issues or to contribute:
# https://github.com/Arthaey/anki-cloze-recognition
#
# Also available for Anki at https://ankiweb.net/shared/info/ANKI_ID_HERE


################################################################################
# USER SETTINGS AND PREFERENCES BELOW HERE, RENAME AS YOU LIKE! :)
################################################################################

DEFAULT_CLOZE_NOTE_NAME = "Cloze"
RECOGNITION_CLOZE_NOTE_NAME = "Cloze (and recognition card)"

TEXT_FIELD = "Text"
HINT_FIELD_PREFIX = "Hint"

PRODUCTION_ID_FIELD = "RecognitionClozeProductionId"
RECOGNITION_ID_FIELD = "RecognitionClozeRecognitionId"

BROWSER_COLOR_RECOGNITION = "#9E9E9E"


################################################################################
# DO NOT MODIFY BELOW THIS LINE (unless you know what you're doing)
################################################################################

import re

MENU_TEXT = "Update recognition cloze cards"

CLOZE_REGEX = re.compile(r"({{c(\d+)::(?:([^:]+?)(?:::([^:]+?))?)}})")

from PyQt4.QtCore import SIGNAL
from PyQt4.QtGui import QAction, QBrush, QColor, QItemDelegate
from anki.hooks import addHook, wrap
from aqt import mw
from aqt.browser import StatusDelegate
from aqt.editor import Editor
from aqt.utils import showInfo, showText
from anki.notes import Note


def updateRecognitionClozeCards(manuallyTriggered=False):
    model = _findOrCreateRecognitionClozeModel()
    if len(mw.col.models.nids(model)) > 0:
        _start()
        reportMsg = ""
        reportMsg += _updateExistingRecognitionNotes(model)
        reportMsg += _createNewRecognitionNotes(model)
        reportMsg += _checkInconsistentNotes(model)
        _finish()
        showText(reportMsg)
    elif manuallyTriggered:
        showInfo("There are no notes for the '" + RECOGNITION_CLOZE_NOTE_NAME + "' note type. Make some first!")


def _findOrCreateRecognitionClozeModel():
    mm = mw.col.models
    model = mm.byName(RECOGNITION_CLOZE_NOTE_NAME)

    if not model:
        defaultClozeModel = mm.byName(DEFAULT_CLOZE_NOTE_NAME)
        model = mm.copy(defaultClozeModel)
        model["name"] = RECOGNITION_CLOZE_NOTE_NAME
        mm.save(model)

    _createFieldIfNeeded(model, PRODUCTION_ID_FIELD)
    _createFieldIfNeeded(model, RECOGNITION_ID_FIELD)

    return model


def _createFieldIfNeeded(model, fieldName):
    mm = mw.col.models
    allFields = mm.fieldNames(model)
    if not fieldName in allFields:
        field = mm.newField(fieldName)
        mm.addField(model, field)


def _updateExistingRecognitionNotes(model):
    reportMsg = ""
    updateReserveNoteNids = _getNidsThatHaveExistingRecognitionNotes(model)

    if len(updateReserveNoteNids) == 0:
        reportMsg += "NO EXISTING RECOGNITION NOTES TO UPDATE.\n"
    else:
        reportMsg += "FOUND " + str(len(updateReserveNoteNids)) + " RECOGNITION NOTES TO UPDATE:\n"

    for productionNid in updateReserveNoteNids:
        productionNote = mw.col.getNote(productionNid)
        existingRecognitionNids = _getNidsThatAreRecognitionNotes(model, productionNid)

        if len(existingRecognitionNids) > 1:
            nids = [mw.col.getNote(nid)["id"] for nid in existingRecognitionNids]
            reportMsg += "- Multiple recognition notes for " + str(productionNid) + "; skipping " + ", ".join(nids) + ".\n"
        elif len(existingRecognitionNids) == 0:
            reportMsg += "- Recognition note " + str(productionNote[RECOGNITION_ID_FIELD]) + " no longer exists; " + \
                         "clearing field on " + str(productionNid) + ".\n"
            productionNote[RECOGNITION_ID_FIELD] = ""
            productionNote.flush()
        else:
            # TODO: don't update if the production note hasn't changed since last time
            recognitionNote = mw.col.getNote(existingRecognitionNids[0])
            _updateRecognitionNote(productionNote, recognitionNote)
            reportMsg += "- Updated recognition note " + str(recognitionNote.id) + " from " + str(productionNid) + ".\n"

    return reportMsg + "\n\n"


def _createNewRecognitionNotes(model):
    reportMsg = ""
    createReserveNoteNids = _getNidsThatNeedRecognitionNotesCreated(model)

    if len(createReserveNoteNids) == 0:
        reportMsg += "NO NEW RECOGNITION NOTES TO CREATE.\n"
    else:
        reportMsg += "CREATED " + str(len(createReserveNoteNids)) + " NEW RECOGNITION NOTES:\n"

    for productionNid in createReserveNoteNids:
        productionNote = mw.col.getNote(productionNid)

        recognitionNote = Note(mw.col, model)
        recognitionNote[PRODUCTION_ID_FIELD] = str(productionNid)
        mw.col.addNote(recognitionNote)

        productionNote[RECOGNITION_ID_FIELD] = str(recognitionNote.id)
        productionNote.flush()

        _updateRecognitionNote(productionNote, recognitionNote)
        reportMsg += "- new recognition note " + str(recognitionNote.id) + " from " + str(productionNid) + "\n"

    return reportMsg + "\n\n"


def _updateRecognitionNote(productionNote, recognitionNote):
    recognitionText = productionNote[TEXT_FIELD]

    clozeMatches = CLOZE_REGEX.findall(recognitionText)
    clozes = {int(num): (full, ans) for (full, num, ans, placeholder) in clozeMatches}

    hintFields = [f for f in productionNote.keys() if f.startswith(HINT_FIELD_PREFIX)]
    hintFields.sort()

    for i, hintField in enumerate(hintFields):
        if productionNote[hintField]:
            fullClozeString, clozeAnswer = clozes[i+1]
            recognitionClozeString = "{{c" + str(i+1) + "::" + clozeAnswer + "::" + clozeAnswer + "}}"
            recognitionText = re.sub(fullClozeString, recognitionClozeString, recognitionText)
            recognitionNote[TEXT_FIELD] = recognitionText
            recognitionNote[hintField] = productionNote[hintField]

    recognitionNote.flush()


def _checkInconsistentNotes(model):
    reportMsg = ""
    inconsistentNids = _getNidsThatAreInconsistent(model)

    if len(inconsistentNids) > 0:
        reportMsg += "Found " + str(len(inconsistentNids)) + " inconsistent notes that have both " + \
                    PRODUCTION_ID_FIELD + " and " + RECOGNITION_ID_FIELD + " fields set, when they should " + \
                    "only have one or the other set:\n- " + "\n- ".join(inconsistentNids) + "\n"

    return reportMsg


def _getNidsThatNeedRecognitionNotesCreated(model):
    # both Production and Recognition IDs are blank
    return mw.col.findNotes(PRODUCTION_ID_FIELD + ": " + RECOGNITION_ID_FIELD + ": ")


def _getNidsThatHaveExistingRecognitionNotes(model):
    # Production ID is blank, Recognition ID is not blank
    return mw.col.findNotes(PRODUCTION_ID_FIELD + ": " + RECOGNITION_ID_FIELD + ":_*")


def _getNidsThatAreRecognitionNotes(model, productionNid):
    # Production ID is not blank, Recognition ID is blank
    return mw.col.findNotes(PRODUCTION_ID_FIELD + ":" + str(productionNid) + " " + RECOGNITION_ID_FIELD + ": ")


def _getNidsThatAreInconsistent(model):
    # both Production and Recognition IDs are not blank
    return mw.col.findNotes(PRODUCTION_ID_FIELD + ":_* " + RECOGNITION_ID_FIELD + ":_*")


def _isRecognitionNote(note):
    return note and PRODUCTION_ID_FIELD in note.keys() and note[PRODUCTION_ID_FIELD]


def _paintRecognitionCardsInBrowser(statusDelegateSelf, painter, option, index):
    card = statusDelegateSelf.model.getCard(index)
    note = card.note()

    if _isRecognitionNote(note):
        brush = QBrush(QColor(BROWSER_COLOR_RECOGNITION))
        painter.save()
        painter.fillRect(option.rect, brush)
        painter.restore()

    return QItemDelegate.paint(statusDelegateSelf, painter, option, index)


def _start():
    mw.checkpoint(MENU_TEXT)
    mw.progress.start()


def _finish():
    mw.col.save(MENU_TEXT)
    mw.col.reset()
    mw.progress.finish()
    mw.reset()


def _manuallyUpdateRecognitionClozeCards():
    updateRecognitionClozeCards(manuallyTriggered=True)


StatusDelegate.paint = wrap(StatusDelegate.paint, _paintRecognitionCardsInBrowser, "after")

addHook("profileLoaded", updateRecognitionClozeCards)

action = QAction(MENU_TEXT, mw)
mw.connect(action, SIGNAL("triggered()"), _manuallyUpdateRecognitionClozeCards)
mw.form.menuTools.addAction(action)
