# Copyright (c) 2007, 2012, Oracle and/or its affiliates. All rights reserved.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; version 2 of the
# License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301  USA

from mforms import App, Utilities, newBox, newPanel, newButton, newLabel, newTabView, newTabSwitcher, newTextEntry, newSelector, Form, newTreeNodeView
import mforms
import wb_admin_ssh
import errno
from paramiko import SFTPError
from wb_common import OperationCancelledError, InvalidPasswordError, dprint_ex

#===============================================================================
#
#================== =============================================================
class RemoteFileSelector(object):
    def __init__(self, ls, cwd, cd, title):
        self.ls = ls
        self.cwd = cwd
        self.cd = cd
        self.selection = ""
        self.title = title or "Select configuration file on remote server"

    def get_filenames(self):
        return self.selection

    def on_change(self):
        selid = self.flist.get_selected_node()
        if selid:
            fname = selid.get_string(0)
            self.selection = self.curdir.get_string_value() + fname

    def on_cd(self, row, column):
        fname = None
        selid = self.flist.get_selected_node()
        if selid:
            fname = selid.get_string(0)
        self.chdir(fname, True)


    def chdir(self, fname, accept_if_file):
        if fname is not None and fname != "":
            cd_success = False
            try:
                cd_success = self.cd(fname)
            except SFTPError, e:
                if len(e.args) > 0 and e[0] == errno.ENOTDIR:
                    cd_success = False
                else:
                    raise

            # not cd_success means that cd to a file was attempted
            if not cd_success and accept_if_file:
                self.selection = self.curdir.get_string_value() + fname
                self.form.close()
                return

        curdir = self.cwd()
        if curdir:
            if curdir[-1] != "/":
                curdir += "/"
            self.curdir.set_value(curdir)
        self.flist.clear()

        (disr, files) = ((),())
        try:
            (dirs, files) = self.ls('.')
        except IOError, e:
            # At least on osx paramiko is silent on attempts to chdir to a file
            # so that leads to some unpleasant results
            if e.errno == errno.ENOENT:
                path = self.curdir.get_string_value()
                if (type(path) is str or type(path) is unicode):
                    path = path.rstrip("/ ")
                else:
                    path = None
                self.selection = path
                self.form.close()
                return

        row_id = self.flist.add_node()
        row_id.set_icon_path(0, 'folder')
        row_id.set_string(0, '..')

        for d in dirs:
            row_id = self.flist.add_node()
            row_id.set_icon_path(0, 'folder')
            row_id.set_string(0, d)

        for f in files:
            row_id = self.flist.add_node()
            row_id.set_string(0, f)

    def cancel_action(self):
        self.selection = None

    def accept_action(self):
        self.form.close()

    def text_action(self, action):
        if action == mforms.EntryActivate:
            dir = self.curdir.get_string_value().encode("utf8")
            self.chdir(dir, False)


    def run(self):
        self.form  = Form(None, mforms.FormResizable)
        self.form.set_title(self.title)
        self.flist = newTreeNodeView(mforms.TreeFlatList)
        self.curdir = newTextEntry()

        self.flist.add_column(mforms.IconStringColumnType, "File", 400, False)
        self.flist.end_columns()

        self.curdir.add_action_callback(self.text_action)
        self.flist.add_activated_callback(self.on_cd)
        self.flist.add_changed_callback(self.on_change)

        accept = newButton()
        accept.set_text("OK")
        cancel = newButton()
        cancel.set_text("Cancel")
        button_box = newBox(True)
        button_box.set_padding(10)
        button_box.set_spacing(8)
        Utilities.add_end_ok_cancel_buttons(button_box, accept, cancel)

        box = newBox(False) # Hosts all entries on that dialog.
        box.set_padding(10)
        box.set_spacing(10)
        box.add(self.curdir, False, False)
        box.add(self.flist, True, True)
        box.add(button_box, False, False)

        self.form.set_content(box)
        self.form.set_size(500, 400)

        cancel.add_clicked_callback(self.cancel_action)
        accept.add_clicked_callback(self.accept_action)

        self.form.relayout()
        self.form.center()

        self.on_cd(0, 0)

        # Don't use the accept button in run_modal or you won't be able to press <enter>
        #  to change the path via the top edit control.
        self.form.run_modal(None, cancel)

#-------------------------------------------------------------------------------
def remote_file_selector(profile, password_delegate, ssh=None, title=None):
    close_ssh = False
    if not ssh:
        #TODO this needs to be rewritten
        close_ssh = True
        try:
            ssh = wb_admin_ssh.WbAdminSSH()
            ssh.wrapped_connect(profile, password_delegate)
        except OperationCancelledError:
            ssh = None
        except wb_admin_ssh.SSHDownException:
            ssh = None

    file_names = []

    if ssh is not None and ssh.is_connected():
        ftp = ssh.getftp()

        if ftp:
            rfs = RemoteFileSelector(ls = ftp.ls, cwd = ftp.pwd, cd = ftp.cd, title = title)
            rfs.run()
            result = rfs.get_filenames()
            if result is not None:
                file_names = result

            ftp.close()
        if close_ssh:
            ssh.close()

    ret = ""
    if type(file_names) is list:
        if len(file_names) > 0:
            ret = file_names[0]
    else:
        ret = file_names

    return ret
