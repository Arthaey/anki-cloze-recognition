# -*- coding: utf-8 -*-
# See github page to report issues or to contribute:
# https://github.com/Arthaey/anki-reverse-cloze
#
# Also available for Anki at https://ankiweb.net/shared/info/ANKI_ID_HERE


################################################################################
# USER SETTINGS AND PREFERENCES BELOW HERE, CUSTOMIZE AS YOU LIKE! :)
################################################################################

CLOZE_NOTE_TYPES = [ "Reverse Cloze" ]

TEXT_FIELD = "Text"

HINT_FIELD_PREFIX = "Hint"


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
from aqt.utils import showInfo
from anki.notes import Note


def updateReverseClozeCards(manuallyTrigger=False):
    updated = False

    mw.checkpoint(MENU_TEXT)
    mw.progress.start()

    mm = mw.col.models

    nids = []

    for modelName in CLOZE_NOTE_TYPES:
        model = mm.byName(modelName)
        if model:
            allFields = mm.fieldNames(model)
            if not "ReverseClozeSourceId" in allFields:
                field = mm.newField("ReverseClozeSourceId")
                mm.addField(model, field)
            if not "ReverseClozeDestId" in allFields:
                field = mm.newField("ReverseClozeDestId")
                mm.addField(model, field)
            if not "ReverseClozeLastUpdated" in allFields:
                field = mm.newField("ReverseClozeLastUpdated")
                mm.addField(model, field)
            nids += mm.nids(model)
        else:
            showInfo("Could not find the model " + modelName)

    # TODO: search by source, then by dest, instead of all cards for the model(s)

    #for nid in nids:
    nid = nids[0] # DELETE ME

    note = mw.col.getNote(nid)

    #sourceId = note["ReverseClozeSourceId"]
    #destId = note["ReverseClozeDestId"]

    text = note[TEXT_FIELD]
    reverseText = text

    clozeMatches = CLOZE_REGEX.findall(text)
    clozes = {int(num): (full, ans) for (full, num, ans, placeholder) in clozeMatches}

    hintFields = [f for f in note.keys() if f.startswith(HINT_FIELD_PREFIX)]
    hintFields.sort()

    reverseNote = Note(mw.col, model)

    for i, hintField in enumerate(hintFields):
        if note[hintField]:
            fullClozeString, clozeAnswer = clozes[i+1]

            reverseClozeString = "{{c" + str(i+1) + "::" + note[hintField] + "}}"
            reverseText = re.sub(fullClozeString, reverseClozeString, reverseText)

            reverseNote[TEXT_FIELD] = reverseText
            reverseNote[hintField] = clozeAnswer

    mw.col.addNote(reverseNote)

    if updated:
        mw.col.save(MENU_TEXT)
        mw.col.reset()
        showInfo("Reverse cloze cards updated.")
    elif manuallyTrigger:
        showInfo("No updates for reverse cloze cards.")

    mw.progress.finish()
    mw.reset()


def _manuallyUpdateReverseClozeCards():
    updateReverseClozeCards(manuallyTrigger=True)


addHook("profileLoaded", updateReverseClozeCards)

action = QAction(MENU_TEXT, mw)
mw.connect(action, SIGNAL("triggered()"), _manuallyUpdateReverseClozeCards)
mw.form.menuTools.addAction(action)
