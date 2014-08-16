# -*- encoding: utf-8 -*-
'''
files managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
import os
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text, force_str
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django import forms
from django.views import static
from django.contrib import messages
from ngw.core.models import GROUP_USER_NGW, ContactGroup
from ngw.core import perms
from ngw.core.views.decorators import login_required, require_group

class UploadFileForm(forms.Form):
    file_to_upload = forms.FileField(label=_('File to upload'))


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_files(request, gid, path):
    gid = gid and int(gid) or None
    if not perms.c_can_see_files_cg(request.user.id, gid):
        raise PermissionDenied

    cg = get_object_or_404(ContactGroup, pk=gid)

    #return render_to_response('message.html', {
    #    'message': 'real path = %s' % cg.get_fullfilename('')
    #    }, RequestContext(request))

    if request.method == 'POST':
        if not perms.c_can_change_files_cg(request.user.id, gid):
            raise PermissionDenied
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            upfile = request.FILES['file_to_upload']
            # name has already been sanitized by UploadedFile._set_name
            fullfilename = cg.get_fullfilename(path + os.path.sep + upfile.name)
            destination = None
            try:
                destination = open(force_str(fullfilename), 'wb')
                for chunk in upfile.chunks():
                    destination.write(chunk)
                messages.add_message(request, messages.SUCCESS,
                    _('File %s has been uploaded sucessfully.') % upfile.name)
            except IOError as err:
                messages.add_message(request, messages.ERROR,
                    _('Could not upload file %(filename)s: %(error)s') % {
                        'filename': upfile.name,
                        'error': str(err)})
            finally:
                if destination:
                    destination.close()
            form = UploadFileForm() # ready for another file
    else:
        form = UploadFileForm()

    context = {}
    context['title'] = _('Files for group %s') % cg.name
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
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
    context['form'] = form
    return render_to_response('group_files.html', context, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def media_group_file(request, gid, filename):
    gid = int(gid)
    if not perms.c_can_see_files_cg(request.user.id, gid):
        raise PermissionDenied

    cg = get_object_or_404(ContactGroup, pk=gid)

    fullfilename = cg.get_fullfilename(filename)
    if os.path.isdir(force_str(fullfilename)):
        return HttpResponseRedirect('/contactgroups/'+force_text(cg.id)+'/files/'+filename)
    return static.serve(request, filename, cg.static_folder(), show_indexes=False)
