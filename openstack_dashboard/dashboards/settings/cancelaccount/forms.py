# Copyright (C) 2014 Universidad Politecnica de Madrid
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging

from django import shortcuts

from horizon import exceptions
from horizon import forms
from horizon import messages

from openstack_dashboard import api


LOG = logging.getLogger('idm_logger')

class BasicCancelForm(forms.SelfHandlingForm):

    def handle(self, request, data):
        user_is_editable = api.keystone.keystone_can_edit_user()
        if user_is_editable:
            try:
                api.keystone.user_delete(request, request.user.id)
                msg = ("Account canceled succesfully")
                LOG.info(msg)
                messages.success(request, msg)
                # Log the user out
                response = shortcuts.redirect('logout') 
                return response
            except Exception as e:   
                exceptions.handle(request,
                                  ('Unable to cancel account.'))
                LOG.error(e)
                return False
        else:
            messages.error(request, ('Account canceling is not supported.'))
            return False
