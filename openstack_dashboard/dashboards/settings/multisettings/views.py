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

import logging
import datetime

from django.conf import settings

from horizon import forms
from horizon import views

from openstack_dashboard import api
from openstack_dashboard import fiware_api
from openstack_dashboard.dashboards.settings.multisettings \
    import forms as settings_forms


LOG = logging.getLogger('idm_logger')

class MultiFormView(views.APIView):
    template_name = 'settings/multisettings/index.html'
    
    def get_context_data(self, **kwargs):
        context = super(MultiFormView, self).get_context_data(**kwargs)

        # Initial data
        user_id = self.request.user.id
        user = fiware_api.keystone.user_get(self.request, user_id)
        initial_email = {
            'email': user.name
        }

        # Current account_type
        # TODO(garcianavalon) find a better solution to this
        user_roles = [a.role['id'] for a in fiware_api.keystone.role_assignments_list(self.request, 
            user=user_id, domain='default')]
        basic_role = fiware_api.keystone.get_basic_role(self.request, use_idm_account=True)
        trial_role = fiware_api.keystone.get_trial_role(self.request, use_idm_account=True)
        community_role = fiware_api.keystone.get_community_role(self.request, use_idm_account=True)
        account_roles = [
            basic_role,
            trial_role,
            community_role,
        ]
        account_type = next((r.name for r in account_roles 
            if r.id in user_roles), None)

        account_info = {
            'account_type': str(account_type),
            'started_at': getattr(user, str(account_type) + '_started_at', None),
            'duration': getattr(user, str(account_type) + '_duration', None),
            #'regions': self._current_regions(self.user.cloud_project_id)
        }

        if account_info['started_at'] and account_info['duration']:
            start_date = datetime.datetime.strptime(account_info['started_at'], '%Y-%m-%d')
            end_date = start_date + datetime.timedelta(days=account_info['duration'])
            account_info['end_date'] = end_date.strftime('%Y-%m-%d')

        context['account_info'] = account_info

        if account_type != community_role.name:
            context['show_community_request'] = True

        if (account_type == basic_role.name 
            and len(fiware_api.keystone.get_trial_role_assignments(self.request)) 
                < getattr(settings, 'MAX_TRIAL_USERS', 0)):
            context['show_trial_request'] = True

        if fiware_api.keystone.two_factor_is_enabled(self.request, user):
            context['two_factor_enabled'] = True

        #Create forms
        status = settings_forms.UpgradeForm(self.request)
        cancel = settings_forms.BasicCancelForm(self.request)
        password = settings_forms.PasswordForm(self.request)
        email = settings_forms.EmailForm(self.request, initial=initial_email)
        two_factor = settings_forms.ManageTwoFactorForm(self.request)

        context['forms'] = [status, password, email, two_factor, cancel]
        return context


# Handeling views
class AccountStatusView(forms.ModalFormView):
    form_class = settings_forms.UpgradeForm
    template_name = 'settings/multisettings/status.html'

class PasswordView(forms.ModalFormView):
    form_class = settings_forms.PasswordForm
    template_name = 'settings/multisettings/change_email.html'

class EmailView(forms.ModalFormView):

    form_class = settings_forms.EmailForm
    template_name = 'settings/useremail/change_password.html'

    def get_form_kwargs(self):
        kwargs = super(EmailView, self).get_form_kwargs()
        user_id = self.request.user.id
        user = fiware_api.keystone.user_get(self.request, user_id)
        kwargs['initial']['email'] = getattr(user, 'name', '')
        return kwargs

class CancelView(forms.ModalFormView):
    form_class = settings_forms.BasicCancelForm
    template_name = 'settings/cancelaccount/cancel.html'

class ManageTwoFactorView(forms.ModalFormView):
    form_class = settings_forms.ManageTwoFactorForm
    template_name = 'settings/two_factor/two_factor.html'