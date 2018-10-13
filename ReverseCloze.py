# -*- coding: utf-8 -*-
# See github page to report issues or to contribute:
# https://github.com/Arthaey/anki-reverse-cloze
#
# Also available for Anki at https://ankiweb.net/shared/info/ANKI_ID_HERE


################################################################################
# USER SETTINGS AND PREFERENCES BELOW HERE, RENAME AS YOU LIKE! :)
################################################################################

DEFAULT_CLOZE_NOTE_NAME = "Cloze"
REVERSE_CLOZE_NOTE_NAME = "Cloze (and reversed card)"

TEXT_FIELD = "Text"
HINT_FIELD_PREFIX = "Hint"

ORIGINAL_ID_FIELD = "ReverseClozeOriginalId"
REVERSED_ID_FIELD = "ReverseClozeReversedId"


################################################################################
# DO NOT MODIFY BELOW THIS LINE (unless you know what you're doing)
################################################################################

import re

MENU_TEXT = "Update reverse cloze cards"

CLOZE_REGEX = re.compile(r"({{c(\d+)::(?:([^:]+?)(?:::([^:]+?))?)}})")

from PyQt4.QtCore import SIGNAL
from PyQt4.QtGui import QAction
from anki.hooks import addHook
from aqt import mw
from aqt.utils import showInfo, showText
from anki.notes import Note


def updateReverseClozeCards(manuallyTriggered=False):
    model = _findOrCreateReverseClozeModel()
    if len(mw.col.models.nids(model)) > 0:
        _start()
        reportMsg = ""
        reportMsg += _updateExistingReverseNotes(model)
        reportMsg += _createNewReverseNotes(model)
        reportMsg += _checkInconsistentNotes(model)
        _finish()
        showText(reportMsg)
    elif manuallyTriggered:
        showInfo("There are no notes for the '" + REVERSE_CLOZE_NOTE_NAME + "' note type. Make some first!")


def _findOrCreateReverseClozeModel():
    mm = mw.col.models
    model = mm.byName(REVERSE_CLOZE_NOTE_NAME)

    if not model:
        defaultClozeModel = mm.byName(DEFAULT_CLOZE_NOTE_NAME)
        model = mm.copy(defaultClozeModel)
        model["name"] = REVERSE_CLOZE_NOTE_NAME
        mm.save(model)

    _createFieldIfNeeded(model, ORIGINAL_ID_FIELD)
    _createFieldIfNeeded(model, REVERSED_ID_FIELD)

    return model


def _createFieldIfNeeded(model, fieldName):
    mm = mw.col.models
    allFields = mm.fieldNames(model)
    if not fieldName in allFields:
        field = mm.newField(fieldName)
        mm.addField(model, field)


def _updateExistingReverseNotes(model):
    reportMsg = ""
    updateReserveNoteNids = _getNidsThatHaveExistingReverseNotes(model)

    if len(updateReserveNoteNids) == 0:
        reportMsg += "NO EXISTING REVERSE NOTES TO UPDATE.\n"
    else:
        reportMsg += "FOUND " + str(len(updateReserveNoteNids)) + " REVERSE NOTES TO UPDATE:\n"

    for originalNid in updateReserveNoteNids:
        originalNote = mw.col.getNote(originalNid)
        existingReverseNids = _getNidsThatAreReverseNotes(model, originalNid)

        if len(existingReverseNids) > 1:
            nids = [mw.col.getNote(nid)["id"] for nid in existingReverseNids]
            reportMsg += "- Multiple reverse notes for " + str(originalNid) + "; skipping " + ", ".join(nids) + ".\n"
        elif len(existingReverseNids) == 0:
            reportMsg += "- Reverse note " + str(originalNote[REVERSED_ID_FIELD]) + " no longer exists; " + \
                         "clearing field on " + str(originalNid) + ".\n"
            originalNote[REVERSED_ID_FIELD] = ""
            originalNote.flush()
        else:
            # TODO: don't update if the original note hasn't changed since last time
            reverseNote = mw.col.getNote(existingReverseNids[0])
            _updateReverseNote(originalNote, reverseNote)
            reportMsg += "- Updated reverse note " + str(reverseNote.id) + " from " + str(originalNid) + ".\n"

    return reportMsg + "\n\n"


def _createNewReverseNotes(model):
    reportMsg = ""
    createReserveNoteNids = _getNidsThatNeedReverseNotesCreated(model)

    if len(createReserveNoteNids) == 0:
        reportMsg += "NO NEW REVERSE NOTES TO CREATE.\n"
    else:
        reportMsg += "CREATED " + str(len(createReserveNoteNids)) + " NEW REVERSE NOTES:\n"

    for originalNid in createReserveNoteNids:
        originalNote = mw.col.getNote(originalNid)

        reverseNote = Note(mw.col, model)
        reverseNote[ORIGINAL_ID_FIELD] = str(originalNid)
        mw.col.addNote(reverseNote)

        originalNote[REVERSED_ID_FIELD] = str(reverseNote.id)
        originalNote.flush()

        _updateReverseNote(originalNote, reverseNote)
        reportMsg += "- new reverse note " + str(reverseNote.id) + " from " + str(originalNid) + "\n"

    return reportMsg + "\n\n"


def _updateReverseNote(originalNote, reverseNote):
    reverseText = originalNote[TEXT_FIELD]

    clozeMatches = CLOZE_REGEX.findall(reverseText)
    clozes = {int(num): (full, ans) for (full, num, ans, placeholder) in clozeMatches}

    hintFields = [f for f in originalNote.keys() if f.startswith(HINT_FIELD_PREFIX)]
    hintFields.sort()

    for i, hintField in enumerate(hintFields):
        if originalNote[hintField]:
            fullClozeString, clozeAnswer = clozes[i+1]
            reverseClozeString = "{{c" + str(i+1) + "::" + clozeAnswer + "::" + clozeAnswer + "}}"
            reverseText = re.sub(fullClozeString, reverseClozeString, reverseText)
            reverseNote[TEXT_FIELD] = reverseText
            reverseNote[hintField] = originalNote[hintField]

    reverseNote.flush()


def _checkInconsistentNotes(model):
    reportMsg = ""
    inconsistentNids = _getNidsThatAreInconsistent(model)

    if len(inconsistentNids) > 0:
        reportMsg += "Found " + str(len(inconsistentNids)) + " inconsistent notes that have both " + \
                    ORIGINAL_ID_FIELD + " and " + REVERSED_ID_FIELD + " fields set, when they should " + \
                    "only have one or the other set:\n- " + "\n- ".join(inconsistentNids) + "\n"

    return reportMsg


def _getNidsThatNeedReverseNotesCreated(model):
    # both Original and Reverse IDs are blank
    return mw.col.findNotes(ORIGINAL_ID_FIELD + ": " + REVERSED_ID_FIELD + ": ")


def _getNidsThatHaveExistingReverseNotes(model):
    # Original ID is blank, Reverse ID is not blank
    return mw.col.findNotes(ORIGINAL_ID_FIELD + ": " + REVERSED_ID_FIELD + ":_*")


def _getNidsThatAreReverseNotes(model, originalNid):
    # Original ID is not blank, Reverse ID is blank
    return mw.col.findNotes(ORIGINAL_ID_FIELD + ":" + str(originalNid) + " " + REVERSED_ID_FIELD + ": ")


def _getNidsThatAreInconsistent(model):
    # both Original and Reverse IDs are not blank
    return mw.col.findNotes(ORIGINAL_ID_FIELD + ":_* " + REVERSED_ID_FIELD + ":_*")


def _start():
    mw.checkpoint(MENU_TEXT)
    mw.progress.start()


def _finish():
    mw.col.save(MENU_TEXT)
    mw.col.reset()
    mw.progress.finish()
    mw.reset()


def _manuallyUpdateReverseClozeCards():
    updateReverseClozeCards(manuallyTriggered=True)


addHook("profileLoaded", updateReverseClozeCards)

action = QAction(MENU_TEXT, mw)
mw.connect(action, SIGNAL("triggered()"), _manuallyUpdateReverseClozeCards)
mw.form.menuTools.addAction(action)
