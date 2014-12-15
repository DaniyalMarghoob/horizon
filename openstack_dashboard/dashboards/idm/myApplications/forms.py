# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import os
from PIL import Image 

from django import forms
from django import shortcuts
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon.utils import functions as utils

from openstack_dashboard import fiware_api
from openstack_dashboard.dashboards.idm import forms as idm_forms


LOG = logging.getLogger('idm_logger')
AVATAR = settings.MEDIA_ROOT+"/"+"ApplicationAvatar/"

class CreateApplicationForm(forms.SelfHandlingForm):
    appID = forms.CharField(label=_("ID"), widget=forms.HiddenInput(), required=False)
    nextredir = forms.CharField(widget=forms.HiddenInput(), required=False)
    name = forms.CharField(label=_("Name"), required=True)
    description = forms.CharField(label=_("Description"), 
                                widget=forms.Textarea, 
                                required=True)
    url = forms.CharField(label=_("URL"), required=True)
    callbackurl = forms.CharField(label=_("Callback URL"), required=True)
    title = 'Information'

    def handle(self, request, data):
        #create application
        #default_domain = api.keystone.get_default_domain(request)
        if data['nextredir'] == "create":
            try:

                extra = {
                    'url':data['url'],
                    'img': "/static/dashboard/img/logos/small/app.png"
                }
                application = fiware_api.keystone.application_create(request,
                                                    name=data['name'],
                                                    description=data['description'],
                                                    redirect_uris=[data['callbackurl']],
                                                    extra=extra)
                LOG.debug('Application {0} created'.format(application.name))
            except Exception:
                exceptions.handle(request, _('Unable to register the application.'))
                return False
            
            response = shortcuts.redirect('horizon:idm:myApplications:upload', application.id)

        else:
            try:
                application = fiware_api.keystone.application_get(request, data['appID'])
                LOG.debug('updating application {0}'.format(data['appID']))
                redirect_uris = [data['callbackurl'],]
                extra = application.extra
                extra['url'] = data['url'] 
                fiware_api.keystone.application_update(request, data['appID'], name=data['name'], description=data['description'],
                        redirect_uris=redirect_uris, extra=extra)
                LOG.debug('image {0}'.format(application.id))
                msg = 'Application updated successfully.'
                messages.success(request, _(msg))
                LOG.debug('image {0}'.format(application.id))
                LOG.debug(msg)
                response = shortcuts.redirect('horizon:idm:myApplications:detail', data['appID'])
                return response
            except Exception as e:
                LOG.error(e)
                response = shortcuts.redirect('horizon:idm:myApplications:detail', data['appID'])

        return response
    
class AvatarForm(forms.SelfHandlingForm, idm_forms.ImageCropMixin):
    appID = forms.CharField(label=_("ID"), widget=forms.HiddenInput())
    image = forms.ImageField(required=False)
    nextredir = forms.CharField(widget=forms.HiddenInput(), required=False)
    title = 'Avatar Update'

    def handle(self, request, data):
        application_id = data['appID']
        if request.FILES:

            image = request.FILES['image'] 
            output_img = self.crop(image)
            
            imageName = application_id
            output_img.save(settings.MEDIA_ROOT+"/"+"ApplicationAvatar/"+imageName, 'JPEG')
            
            img = settings.MEDIA_URL+'ApplicationAvatar/'+imageName
            fiware_api.keystone.application_update(request, application_id, img=img)

        if data['nextredir'] == "update":
            response = shortcuts.redirect('horizon:idm:myApplications:detail', application_id) 
            LOG.debug('Avatar for application {0} updated'.format(application_id))
        else:
            response = shortcuts.redirect('horizon:idm:myApplications:roles_index')
            LOG.debug('Avatar for application {0} saved'.format(application_id))
        return response


class CreateRoleForm(forms.SelfHandlingForm):
    # application_id = forms.CharField(label=_("Domain ID"),
    #                             required=True,
    #                             widget=forms.HiddenInput())
    name = forms.CharField(max_length=255, label=_("Role Name"))
    no_autocomplete = True

    def handle(self, request, data):
        try:
            LOG.info('Creating role with name "%s"' % data['name'])
            new_role = fiware_api.keystone.role_create(request,
                                                name=data['name'])
            messages.success(request,
                             _('Role "%s" was successfully created.')
                             % data['name'])
            return new_role
        except Exception:
            exceptions.handle(request, _('Unable to create role.'))


class CreatePermissionForm(forms.SelfHandlingForm):
    # application_id = forms.CharField(label=_("Domain ID"),
    #                             required=True,
    #                             widget=forms.HiddenInput())
    name = forms.CharField(max_length=255, label=_("Permission Name"))
    no_autocomplete = True

    def handle(self, request, data):
        try:
            LOG.info('Creating permission with name "%s"' % data['name'])
            new_permission = fiware_api.keystone.permission_create(request,
                                                name=data['name'])
            messages.success(request,
                             _('Permission "%s" was successfully created.')
                             % data['name'])
            return new_permission
        except Exception:
            exceptions.handle(request, _('Unable to create permission.'))

        
class CancelForm(forms.SelfHandlingForm):
    appID = forms.CharField(label=_("ID"), widget=forms.HiddenInput())
    title = 'Cancel'

    def handle(self, request, data, application):
        image = application.extra['img']
        LOG.debug(image)
        if "ApplicationAvatar" in image:
            os.remove(AVATAR + application.id)
            LOG.debug('Avatar deleted from server')    
        fiware_api.keystone.application_delete(request, application.id)
        LOG.info('Application {0} deleted'.format(application.id))
        messages.success(request, _("Application deleted successfully."))
        response = shortcuts.redirect('horizon:idm:myApplications:index')
        return response