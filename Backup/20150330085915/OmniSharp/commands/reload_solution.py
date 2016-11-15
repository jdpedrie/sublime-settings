import os
import sublime
import sublime_plugin

from ..lib import helpers
from ..lib import omnisharp

class OmniSharpReloadSolution(sublime_plugin.TextCommand):
    
    def run(self, edit):

        omnisharp.get_response_from_empty_httppost(self.view, '/reloadsolution', self._handle_reloadsolution)

    def is_enabled(self):
        return helpers.is_csharp(sublime.active_window().active_view())

    def _handle_reloadsolution(self, data):
        print("Solution Reloaded")
