# Copyright (C) 2014 Universidad Politecnica de Madrid
#
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

import os
import logging

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic.base import TemplateView

from horizon import exceptions
from horizon import tables
from horizon.utils import memoized
from horizon import tabs
from horizon import forms

from openstack_dashboard import api

from openstack_dashboard.dashboards.idm.organizations \
    import tables as organization_tables
from openstack_dashboard.dashboards.idm.organizations \
    import tabs as organization_tabs
from openstack_dashboard.dashboards.idm.organizations \
    import forms as organization_forms


LOG = logging.getLogger('idm_logger')
AVATAR_ROOT = os.path.abspath(os.path.join(settings.MEDIA_ROOT, 'OrganizationAvatar'))

class IndexView(tabs.TabbedTableView):
    tab_group_class = organization_tabs.PanelTabs
    template_name = 'idm/organizations/index.html'


class CreateOrganizationView(forms.ModalFormView):
    form_class = organization_forms.CreateOrganizationForm
    template_name = 'idm/organizations/create.html'


class DetailOrganizationView(tables.MultiTableView):
    template_name = 'idm/organizations/detail.html'
    table_classes = (organization_tables.MembersTable,
                     organization_tables.ApplicationsTable)
    
    def get_members_data(self):        
        users = []
        try:
            users = api.keystone.user_list(self.request,
                                         project=self.kwargs['organization_id'])
        except Exception:
            exceptions.handle(self.request,
                              _("Unable to retrieve member information."))
        return users

    def get_applications_data(self):
        applications = []
        return applications

    def get_context_data(self, **kwargs):
        context = super(DetailOrganizationView, self).get_context_data(**kwargs)
        organization_id = self.kwargs['organization_id']
        organization = api.keystone.tenant_get(self.request, organization_id, admin=True)
        context['contact_info'] = organization.description
        context['organization.id'] = organization.id
        context['organization_name'] = organization.name
        context['image'] = getattr(organization, 'img', '/static/dashboard/img/logos/small/group.png')
        context['city'] = getattr(organization, 'city', '')
        context['email'] = getattr(organization, 'email', '')
        context['website'] = getattr(organization, 'website', '')
        return context


class MultiFormView(TemplateView):
    template_name = 'idm/organizations/edit.html'

    @memoized.memoized_method
    def get_object(self):
        try:
            return api.keystone.tenant_get(self.request, self.kwargs['organization_id'])
        except Exception:
            redirect = reverse("horizon:idm:organizations:index")
            exceptions.handle(self.request, 
                    _('Unable to update organization'), redirect=redirect)

    def get_context_data(self, **kwargs):
        context = super(MultiFormView, self).get_context_data(**kwargs)
        organization = self.get_object()
        context['organization'] = organization

        #Existing data from organizations
           
        initial_data = {
            "orgID": organization.id,
            "name": organization.name,
            "description": organization.description,    
            "city": getattr(organization, 'city', ''),
            "email": getattr(organization, 'email', ''),
            "website":getattr(organization, 'website', ''),
        }
       
        #Create forms
        info = organization_forms.InfoForm(self.request, initial=initial_data)
        contact = organization_forms.ContactForm(self.request, initial=initial_data)
        avatar = organization_forms.AvatarForm(self.request, initial=initial_data)
        cancel = organization_forms.CancelForm(self.request, initial=initial_data)

        #Actions and titles
        # TODO(garcianavalon) quizas es mejor meterlo en el __init__ del form
        info.action = 'info/'
        info.title = 'Information'
        contact.action = "contact/"
        contact.title = 'Contact Information'
        avatar.action = "avatar/"
        avatar.title = 'Avatar Update'
        cancel.action = "cancel/"
        cancel.title = 'Cancel'

        context['forms'] = [info, contact, avatar]
        context['cancel_form'] = cancel
        context['image'] = getattr(organization, 'img', '/static/dashboard/img/logos/small/group.png')
        return context


class HandleForm(forms.ModalFormView):
    template_name = ''
    http_method_not_allowed = ['get']

class InfoFormView(HandleForm):    
    form_class = organization_forms.InfoForm
    http_method_not_allowed = ['get']


class ContactFormView(HandleForm):
    form_class = organization_forms.ContactForm

   
class AvatarFormView(forms.ModalFormView):
    form_class = organization_forms.AvatarForm


class CancelFormView(forms.ModalFormView):
    form_class = organization_forms.CancelForm