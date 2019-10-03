'''
files managing views
'''

import json
import os
import stat
import sys
from email.quoprimime import header_encode

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import (FileResponse, Http404, HttpResponseNotModified,
                         HttpResponseRedirect)
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_str
from django.utils.http import http_date
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views import static
from django.views.generic import FormView, View
from PIL import Image

from ngw.core import perms
from ngw.core.models import ContactField, ContactFieldValue
from ngw.core.views.generic import InGroupAcl, NgwUserAcl

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
        context['title'] = _('Files of {group} in {folder}').format(
            group=cg,
            folder=path)
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
                _('File {} has been uploaded successfully.')
                .format(upfile.name))
        except IOError as err:
            messages.add_message(
                request, messages.ERROR,
                _('Could not upload file {filename}: {error}').format(
                    filename=upfile.name,
                    error=err))
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


class FileContactFieldView(NgwUserAcl, View):
    '''
    That view serves a contact field that are files.
    '''
    def get(self, request, fid, cid):
        cf = get_object_or_404(ContactField, pk=fid)
        if not perms.c_can_view_fields_cg(request.user.id,
                                          cf.contact_group_id):
            raise PermissionDenied
        fullpath = os.path.join(settings.MEDIA_ROOT, 'fields', fid, cid)
        if not os.path.exists(fullpath):
            raise Http404(_('"{path}" does not exist').format(path=fullpath))
        # Respect the If-Modified-Since header.
        statobj = os.stat(fullpath)
        if not static.was_modified_since(
           request.META.get('HTTP_IF_MODIFIED_SINCE'),
           statobj.st_mtime, statobj.st_size):
            return HttpResponseNotModified()

        # START OF content_type detection
        cfv = get_object_or_404(ContactFieldValue,
                                contact_id=cid, contact_field_id=fid)
        fileinfo = json.loads(cfv.value)
        content_type = fileinfo['content_type']
        # END OF content_type detection

        response = FileResponse(open(fullpath, 'rb'),
                                content_type=content_type)
        response["Last-Modified"] = http_date(statobj.st_mtime)
        if stat.S_ISREG(statobj.st_mode):
            response["Content-Length"] = statobj.st_size

        response['Content-Disposition'] = 'inline; filename="{0}"'.format(
            header_encode(fileinfo['filename'].encode('utf-8'), 'utf-8'))
        return response


class FileContactFieldThumbView(NgwUserAcl, View):
    '''
    That view serves a contact field that are files.
    '''
    def get(self, request, fid, cid, width, height):
        cf = get_object_or_404(ContactField, pk=fid)
        if not perms.c_can_view_fields_cg(request.user.id,
                                          cf.contact_group_id):
            raise PermissionDenied

        fullpath_orig = os.path.join(settings.MEDIA_ROOT, 'fields', fid, cid)
        fullpath_thumb = os.path.join(settings.MEDIA_ROOT, 'fields', fid,
                                      cid + ".{0}x{1}".format(width, height))
        try:
            stat_orig = os.stat(fullpath_orig)
        except FileNotFoundError:
            raise Http404(_('"{path}" does not exist').format(
                path=fullpath_orig))

        try:
            stat_thumb = os.stat(fullpath_thumb)
            thumb_outdated = (stat_thumb.st_mtime < stat_orig.st_mtime)
        except FileNotFoundError:
            thumb_outdated = True

        if thumb_outdated:
            img = Image.open(fullpath_orig)
            width, height = int(width), int(height)
            img.thumbnail((width, height))
            img.save(fullpath_thumb, "JPEG")
            stat_thumb = os.stat(fullpath_thumb)
        else:
            # Respect the If-Modified-Since header.
            if not static.was_modified_since(
               request.META.get('HTTP_IF_MODIFIED_SINCE'),
               stat_thumb.st_mtime, stat_thumb.st_size):
                return HttpResponseNotModified()

        # START OF content_type detection
        cfv = get_object_or_404(ContactFieldValue,
                                contact_id=cid, contact_field_id=fid)
        fileinfo = json.loads(cfv.value)
        content_type = fileinfo['content_type']
        # END OF content_type detection

        response = FileResponse(open(fullpath_thumb, 'rb'),
                                content_type=content_type)
        response["Last-Modified"] = http_date(stat_thumb.st_mtime)
        if stat.S_ISREG(stat_thumb.st_mode):
            response["Content-Length"] = stat_thumb.st_size

        response['Content-Disposition'] = 'inline; filename="{0}"'.format(
            header_encode(fileinfo['filename'].encode('utf-8'), 'utf-8'))
        return response
