'''
files managing views
'''

import os
import sys

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.utils.encoding import force_str
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views import static
from django.views.generic import FormView, View

from ngw.core import perms
from ngw.core.views.generic import InGroupAcl


###############################################################################
#
# File list / upload
#
###############################################################################


class UploadFileForm(forms.Form):
    'Simple form for file upload'
    file_to_upload = forms.FileField(label=ugettext_lazy('File to upload'))


class FileListView(InGroupAcl, FormView):
    '''
    That view lists the files in a given group and folder.
    '''
    form_class = UploadFileForm
    template_name = 'group_files.html'

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.VIEW_FILES:
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        path = self.kwargs['path']
        cg = self.contactgroup
        context = {}
        context['title'] = _('Files of %(group)s in %(folder)s') % {
            'group': cg,
            'folder': path,
        }
        context['nav'] = cg.get_smart_navbar() \
            .add_component(('files', _('files')))
        base_fullname = cg.get_fullfilename()
        path_fullname = cg.get_fullfilename(path)
        if not path_fullname.startswith(base_fullname):
            raise PermissionDenied
        for part in path_fullname[len(base_fullname):].split('/'):
            if part:
                context['nav'] = context['nav'].add_component(part)
        context['active_submenu'] = 'files'
        context['path'] = path
        context['files'] = cg.get_filenames(path)
        context.update(kwargs)
        return super().get_context_data(**context)

    def form_valid(self, form):
        cg = self.contactgroup
        request = self.request
        if not cg.userperms & perms.WRITE_FILES:
            raise PermissionDenied
        upfile = request.FILES['file_to_upload']
        # name has already been sanitized by UploadedFile._set_name
        path = self.kwargs['path']
        fullfilename = cg.get_fullfilename(os.path.join(path, upfile.name))
        destination = None
        try:  # We're not using "with" because we want to show errors
            destination = open(force_str(fullfilename), 'wb')
            for chunk in upfile.chunks():
                destination.write(chunk)
            messages.add_message(
                request, messages.SUCCESS,
                _('File %s has been uploaded successfully.') % upfile.name)
        except IOError as err:
            messages.add_message(
                request, messages.ERROR,
                _('Could not upload file %(filename)s: %(error)s') % {
                    'filename': upfile.name,
                    'error': str(err)})
        finally:
            if destination:
                destination.close()
        return self.get(self.request)


###############################################################################
#
# File download
#
###############################################################################

class GroupMediaFileView(InGroupAcl, View):
    '''
    That view serves a media file in a given group.
    '''
    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.VIEW_FILES:
            raise PermissionDenied

    def get(self, request, *args, **kwargs):
        def surogate_encode(filename):
            '''
            On apache, using wsgi, LANG is not set, so that
            sys.getfilesystemencoding() returns ascii.
            This leads to os.path.exists('é') to crash.
            The way around is to use 'surrogateescape' that maps unencoded
            chars into unicode private range U+DCxx.
            '''
            name_bytes = bytes(filename, encoding=settings.FILE_CHARSET)
            return str(
                name_bytes,
                encoding=sys.getfilesystemencoding(),
                errors='surrogateescape')

        def simple_quote(txt):
            '''
            This is a simple urlquote fonction whose only purpose is to make
            sure unquote won't do nasty stuff, like double unquoting '../..'
            '''
            return txt.replace('%', '%25')

        cg = self.contactgroup
        filename = self.kwargs['filename']
        fullfilename = cg.get_fullfilename(filename)
        if os.path.isdir(surogate_encode(fullfilename)):
            return HttpResponseRedirect(
                cg.get_absolute_url() + 'files/' + filename + '/')
        return static.serve(
            request,
            simple_quote(surogate_encode(filename)),
            cg.static_folder(),
            show_indexes=False)
