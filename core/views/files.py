'''
files managing views
'''

import os
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _, ugettext_lazy
from django.utils.encoding import force_str
from django.views.generic import View, FormView
from django import forms
from django.views import static
from django.contrib import messages
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
        context['title'] = _('Files of %(groupname)s in %(folder)s') % {
            'groupname': cg.name_with_date(),
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
                _('File %s has been uploaded sucessfully.') % upfile.name)
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
        cg = self.contactgroup
        filename = self.kwargs['filename']
        fullfilename = cg.get_fullfilename(filename)
        if os.path.isdir(force_str(fullfilename)):
            return HttpResponseRedirect(
                cg.get_absolute_url() + 'files/' + filename + '/')
        return static.serve(
            request, filename, cg.static_folder(), show_indexes=False)
