# -*- coding: utf-8 -*-

"""
This file is part of the Code Syntax Highlighter add-on for Anki.

Main Module, hooks add-on methods into Anki.

Copyright: (c) 2012-2015 Tiago Barroso <https://github.com/tmbb>
           (c) 2015 Tim Rae <https://github.com/timrae>
           (c) 2018 Glutanimate <https://glutanimate.com/>

License: GNU AGPLv3 <https://www.gnu.org/licenses/agpl.html>
"""

from __future__ import unicode_literals

import os
import sys

from .consts import *
# always use shipped pygments library
sys.path.insert(0, os.path.join(addon_path, "libs"))

from pygments import highlight
from pygments.lexers import get_lexer_by_name, get_all_lexers
from pygments.formatters import HtmlFormatter

from aqt.qt import *
from aqt import mw
from aqt.editor import Editor
from anki.utils import json
from anki.hooks import addHook
from anki import hooks

###############################################################
###
# Configurable preferences
###
###############################################################

HOTKEY = "Alt+s"

# Defaults conf
# - we create a new item in mw.col.conf. This syncs the
# options across machines (but not on mobile)
default_conf = {'linenos': True,  # show numbers by default
                'centerfragments': True,  # Use <center> when generating code fragments
                'cssclasses': False,  # Use css classes instead of colors directly in html
                'defaultlangperdeck': True,  # Default to last used language per deck
                'deckdefaultlang': {},  # Map to store the default language per deck
                'lang': 'Python'}  # default language is Python
###############################################################


def sync_keys(tosync, ref):
    for key in [x for x in list(tosync.keys()) if x not in ref]:
        del(tosync[key])

    for key in [x for x in list(ref.keys()) if x not in tosync]:
        tosync[key] = ref[key]


def sync_config_with_default(col):
    if not 'syntax_highlighting_conf' in col.conf:
        col.conf['syntax_highlighting_conf'] = default_conf
    else:
        sync_keys(col.conf['syntax_highlighting_conf'], default_conf)

    # Mark collection state as modified, else config changes get lost unless
    # some unrelated action triggers the flush of collection data to db
    col.setMod()
    # col.flush()


def get_deck_name(mw):
    deck_name = None
    try:
        deck_name = mw.col.decks.current()['name']
    except AttributeError:
        # No deck opened?
        deck_name = None
    return deck_name


def get_default_lang(mw):
    addon_conf = mw.col.conf['syntax_highlighting_conf']
    lang = addon_conf['lang']
    if addon_conf['defaultlangperdeck']:
        deck_name = get_deck_name(mw)
        if deck_name and deck_name in addon_conf['deckdefaultlang']:
            lang = addon_conf['deckdefaultlang'][deck_name]
    return lang


def set_default_lang(mw, lang):
    addon_conf = mw.col.conf['syntax_highlighting_conf']
    addon_conf['lang'] = lang  # Always update the overall default
    if addon_conf['defaultlangperdeck']:
        deck_name = get_deck_name(mw)
        if deck_name:
            addon_conf['deckdefaultlang'][deck_name] = lang


class SyntaxHighlighting_Options(QWidget):
    def __init__(self, mw):
        super(SyntaxHighlighting_Options, self).__init__()
        self.mw = mw
        self.addon_conf = None

    def switch_linenos(self):
        linenos_ = self.addon_conf['linenos']
        self.addon_conf['linenos'] = not linenos_

    def switch_centerfragments(self):
        centerfragments_ = self.addon_conf['centerfragments']
        self.addon_conf['centerfragments'] = not centerfragments_

    def switch_defaultlangperdeck(self):
        defaultlangperdeck_ = self.addon_conf['defaultlangperdeck']
        self.addon_conf['defaultlangperdeck'] = not defaultlangperdeck_

    def switch_cssclasses(self):
        cssclasses_ = self.addon_conf['cssclasses']
        self.addon_conf['cssclasses'] = not cssclasses_

    def setupUi(self):
        # If config options have changed, sync with default config first
        sync_config_with_default(self.mw.col)

        self.addon_conf = self.mw.col.conf['syntax_highlighting_conf']

        linenos_label = QLabel('<b>Line numbers</b>')
        linenos_checkbox = QCheckBox('')
        linenos_checkbox.setChecked(self.addon_conf['linenos'])
        linenos_checkbox.stateChanged.connect(self.switch_linenos)

        center_label = QLabel('<b>Center code fragments</b>')
        center_checkbox = QCheckBox('')
        center_checkbox.setChecked(self.addon_conf['centerfragments'])
        center_checkbox.stateChanged.connect(self.switch_centerfragments)

        cssclasses_label = QLabel('<b>Use CSS classes</b>')
        cssclasses_checkbox = QCheckBox('')
        cssclasses_checkbox.setChecked(self.addon_conf['cssclasses'])
        cssclasses_checkbox.stateChanged.connect(self.switch_cssclasses)

        defaultlangperdeck_label = QLabel(
            '<b>Default to last language used per deck</b>')
        defaultlangperdeck_checkbox = QCheckBox('')
        defaultlangperdeck_checkbox.setChecked(
            self.addon_conf['defaultlangperdeck'])
        defaultlangperdeck_checkbox.stateChanged.connect(
            self.switch_defaultlangperdeck)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(linenos_label, 0, 0)
        grid.addWidget(linenos_checkbox, 0, 1)
        grid.addWidget(center_label, 1, 0)
        grid.addWidget(center_checkbox, 1, 1)
        grid.addWidget(cssclasses_label, 2, 0)
        grid.addWidget(cssclasses_checkbox, 2, 1)
        grid.addWidget(defaultlangperdeck_label, 3, 0)
        grid.addWidget(defaultlangperdeck_checkbox, 3, 1)

        self.setLayout(grid)

        self.setWindowTitle('Syntax Highlighting Options')
        self.show()


mw.SyntaxHighlighting_Options = SyntaxHighlighting_Options(mw)

options_action = QAction("Syntax Highlighting Options ...", mw)
options_action.triggered.connect(mw.SyntaxHighlighting_Options.setupUi)
mw.form.menuTools.addAction(options_action)


###############################################################
###
# Utilities to generate buttons
###
###############################################################

standardHeight = 20
standardWidth = 20

# This is taken from the aqt source code to


def add_plugin_button_(self,
                       ed,
                       name,
                       func,
                       text="",
                       key=None,
                       tip=None,
                       height=False,
                       width=False,
                       icon=None,
                       check=False,
                       native=False,
                       canDisable=True):

    b = QPushButton(text)

    if check:
        b.clicked[bool].connect(func)
    else:
        b.clicked.connect(func)

    if height:
        b.setFixedHeight(height)
    if width:
        b.setFixedWidth(width)

    if not native:
        b.setStyle(ed.plastiqueStyle)
        b.setFocusPolicy(Qt.NoFocus)
    else:
        b.setAutoDefault(False)

    if icon:
        b.setIcon(QIcon(icon))
    if key:
        b.setShortcut(QKeySequence(key))
    if tip:
        b.setToolTip(tip)
    if check:
        b.setCheckable(True)

    self.addWidget(b)  # this part is changed

    if canDisable:
        ed._buttons[name] = b
    return b


def add_code_langs_combobox(self, func, previous_lang):
    combo = QComboBox()
    combo.addItem(previous_lang)
    for lang in sorted(LANGUAGES_MAP.keys()):
        combo.addItem(lang)

    combo.activated[str].connect(func)
    self.addWidget(combo)
    return combo


icon_path = os.path.join(addon_path, "icons", "button.png")

QSplitter.add_plugin_button_ = add_plugin_button_
QSplitter.add_code_langs_combobox = add_code_langs_combobox


def init_highlighter(ed, *args, **kwargs):
    # If config options have changed, sync with default config first
    sync_config_with_default(mw.col)

    #  Get the last selected language (or the default language if the user
    # has never chosen any)
    previous_lang = get_default_lang(mw)
    ed.codeHighlightLangAlias = LANGUAGES_MAP[previous_lang]

    if anki21:
        # TODO: Anki 2.1 no longer uses a Qt widget for its buttons. We will have to migrate
        # to an HTML-based solution here
        pass
    else:
        # Add the buttons to the Icon Box
        splitter = QSplitter()
        splitter.add_plugin_button_(ed,
                                    "highlight_code",
                                    lambda _: highlight_code(ed),
                                    key=HOTKEY,
                                    text="",
                                    icon=icon_path,
                                    tip=_("Paste highlighted code ({})".format(HOTKEY)),
                                    check=False)
        splitter.add_code_langs_combobox(
            lambda lang: onCodeHighlightLangSelect(ed, lang), previous_lang)
        splitter.setFrameStyle(QFrame.Plain)
        rect = splitter.frameRect()
        splitter.setFrameRect(rect.adjusted(10, 0, -10, 0))
        ed.iconsBox.addWidget(splitter)


def onCodeHighlightLangSelect(ed, lang):
    set_default_lang(mw, lang)
    alias = LANGUAGES_MAP[lang]
    ed.codeHighlightLangAlias = alias



def onSetupButtons21(buttons, editor):
    """Add buttons to Editor for Anki 2.1.x"""
    # no need for a lambda since onBridgeCmd passes current editor instance
    # to method anyway (cf. "self._links[cmd](self)")
    b = editor.addButton(icon_path, "CH", highlight_code,
                         tip="Paste highlighted code ({})".format(HOTKEY),
                         keys=HOTKEY)
    buttons.append(b)

    # HTML "combobox"

    frame_str = """<select class=blabel>{}</select>"""
    option_str = """<option value="{}">{}</option>"""
    
    previous_lang = get_default_lang(mw)

    options = []
    options.append(option_str.format(previous_lang, previous_lang))
    for lang in sorted(LANGUAGES_MAP.keys()):
        options.append(option_str.format(lang, lang))

    combo = frame_str.format("".join(options))

    buttons.append(combo)
    return buttons



###############################################################


# This code sets a correspondence between:
#  The "language names": long, descriptive names we want
#   to show the user AND
#  The "language aliases": short, cryptic names for internal
#   use by HtmlFormatter
LANGUAGES_MAP = {}
for lex in get_all_lexers():
    #  This line uses the somewhat weird structure of the the map
    # returned by get_all_lexers
    LANGUAGES_MAP[lex[0]] = lex[1][0]

###############################################################


def highlight_code(self):
    addon_conf = mw.col.conf['syntax_highlighting_conf']

    #  Do we want line numbers? linenos is either true or false according
    # to the user's preferences
    linenos = addon_conf['linenos']

    centerfragments = addon_conf['centerfragments']

    # Do we want to use css classes or have formatting directly in HTML?
    # Using css classes takes up less space and gives the user more
    # customization options, but is less self-contained as it requires
    # setting the styling on every note type where code is used
    noclasses = not addon_conf['cssclasses']

    selected_text = self.web.selectedText()
    if selected_text:
        #  Sometimes, self.web.selectedText() contains the unicode character
        # '\u00A0' (non-breaking space). This character messes with the
        # formatter for highlighted code. To correct this, we replace all
        # '\u00A0' characters with regular space characters
        code = selected_text.replace('\u00A0', ' ')
    else:
        clipboard = QApplication.clipboard()
        # Get the code from the clipboard
        code = clipboard.text()

    langAlias = self.codeHighlightLangAlias

    # Select the lexer for the correct language
    my_lexer = get_lexer_by_name(langAlias, stripall=True)

    # Create html formatter object including flags for line nums and css classes
    my_formatter = HtmlFormatter(
        linenos=linenos, noclasses=noclasses, font_size=16)

    if linenos:
        if centerfragments:
            pretty_code = "".join(["<center>",
                                   highlight(code, my_lexer, my_formatter),
                                   "</center><br>"])
        else:
            pretty_code = "".join([highlight(code, my_lexer, my_formatter),
                                   "<br>"])
    # TODO: understand why this is neccessary
    else:
        if centerfragments:
            pretty_code = "".join(["<center><table><tbody><tr><td>",
                                   highlight(code, my_lexer, my_formatter),
                                   "</td></tr></tbody></table></center><br>"])
        else:
            pretty_code = "".join(["<table><tbody><tr><td>",
                                   highlight(code, my_lexer, my_formatter),
                                   "</td></tr></tbody></table><br>"])

    # These two lines insert a piece of HTML in the current cursor position
    self.web.eval("document.execCommand('inserthtml', false, %s);"
                  % json.dumps(pretty_code))

if anki21:
    addHook("setupEditorButtons", onSetupButtons21)
Editor.__init__ = hooks.wrap(Editor.__init__, init_highlighter)
