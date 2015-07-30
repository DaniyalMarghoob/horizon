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

import datetime
import logging
import json

from django import http
from django.conf import settings
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from horizon import forms

from openstack_dashboard import api
from openstack_dashboard import fiware_api
from openstack_dashboard.dashboards.idm_admin.user_accounts \
    import forms as user_accounts_forms
from openstack_dashboard.dashboards.idm_admin \
    import utils as idm_admin_utils

LOG = logging.getLogger('idm_logger')

class FindUserView(forms.ModalFormView):
    form_class = user_accounts_forms.FindUserByEmailForm
    template_name = 'idm_admin/user_accounts/index.html'

    def dispatch(self, request, *args, **kwargs):
        if idm_admin_utils.is_current_user_administrator(request):
            return super(FindUserView, self).dispatch(request, *args, **kwargs)
        else:
            return redirect('horizon:user_home')


class UpdateAccountView(forms.ModalFormView):
    form_class = user_accounts_forms.UpdateAccountForm
    template_name = 'idm_admin/user_accounts/update.html'
    success_url = 'horizon:idm_admin:user_accounts:update'

    def dispatch(self, request, *args, **kwargs):
        if idm_admin_utils.is_current_user_administrator(request):
            self.user = fiware_api.keystone.user_get(request,
                kwargs['user_id'])
            return super(UpdateAccountView, self).dispatch(request, *args, **kwargs)
        else:
            return redirect('horizon:user_home')

    def get_context_data(self, **kwargs):
        context = super(UpdateAccountView, self).get_context_data(**kwargs)
        user = self.user

        context['user'] = user

        context['allowed_regions'] = json.dumps(
            getattr(settings, 'FIWARE_ALLOWED_REGIONS', None))

        context['default_durations'] = json.dumps(
            getattr(settings, 'FIWARE_DEFAULT_DURATION', None))

        account_type = self._current_account(user.id)[1]
        account_info = {
            'account_type': account_type,
            'started_at': getattr(user, account_type + '_started_at', None),
            'duration': getattr(user, account_type + '_duration', None),
            'regions': self._current_regions(self.user.cloud_project_id)
        }

        if account_info['started_at'] and account_info['duration']:
            start_date = datetime.datetime.strptime(account_info['started_at'], '%Y-%m-%d')
            end_date = start_date + datetime.timedelta(days=account_info['duration'])
            account_info['end_date'] = end_date.strftime('%Y-%m-%d')

        context['account_info'] = account_info
        return context

    def get_initial(self):
        initial = super(UpdateAccountView, self).get_initial()
        user_id = self.user.id
        
        current_account = self._current_account(user_id)
        current_regions = self._current_regions(self.user.cloud_project_id)

        initial.update({
            'user_id': user_id,
            'regions': [(region_id, region_id) for region_id in current_regions],
            'account_type': current_account[0],
        })
        return initial

    def _current_account(self, user_id):
        # TODO(garcianavalon) find a better solution to this
        user_roles = [
            a.role['id'] for a 
            in fiware_api.keystone.role_assignments_list(self.request, 
                user=user_id, domain='default')
        ]
       
        fiware_roles = user_accounts_forms.get_account_choices()

        return next((role for role in fiware_roles
            if role[0] in user_roles))

    def _current_regions(self, cloud_project_id):
        endpoint_groups = fiware_api.keystone.list_endpoint_groups_for_project(
            self.request, cloud_project_id)
        current_regions = []
        for endpoint_group in endpoint_groups:
            if 'region_id' in endpoint_group.filters:
                current_regions.append(endpoint_group.filters['region_id'])
        return current_regions



class UpdateAccountEndpointView(View, user_accounts_forms.UserAccountsLogicMixin):
    """ Upgrade account logic with out the form"""
    http_method_names = ['post']
    use_idm_account = True
    
    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        # Check there is a valid keystone token in the header
        token = request.META.get('HTTP_X_AUTH_TOKEN', None)
        if not token:
            return http.HttpResponse('Unauthorized', status=401)

        try:
            fiware_api.keystone.validate_keystone_token(request, token)
        except Exception:
            return http.HttpResponse('Unauthorized', status=401)

        return super(UpdateAccountEndpointView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            user = fiware_api.keystone.user_get(request, data['user_id'])
            role_id = data['role_id']

            if (role_id == fiware_api.keystone.get_trial_role(
                request).id):

                trial_left = self._max_trial_users_reached(request)
                if not trial_left:
                    return http.HttpResponseNotAllowed()

            regions = data.get('regions', [])

            if (role_id != fiware_api.keystone.get_basic_role(
                    request).id
                and not regions):

                return http.HttpResponseBadRequest()

            self.update_account(request, user, role_id, regions)

            return http.HttpResponse()

        except Exception:
            return http.HttpResponseServerError()
